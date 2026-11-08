"""Grounded assistant and opt-in account-scoped saved conversations.

Inference is outside every SQLAlchemy session. Final authorization, public source
revision validation, and private live reads always use a newly opened session.
"""
from contextlib import contextmanager
from time import monotonic
from typing import Literal
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator, model_validator
from sqlalchemy import delete, func, select, text, update

from . import assistant_tools, knowledge, model_runtime, observation_contract, observability, release
from .db import Record, SessionLocal, User, now
from .schemas import Strict
from .security import current_user, optional_user

CHAT = 'assistant_chat'
RETENTION = 30 * 86400
MAX_CONVERSATIONS = 20
MAX_MESSAGES = 20
PENDING_TTL = 300
MAX_PENDING = 2
router = APIRouter(prefix='/api/release/assistant', dependencies=[Depends(release.public_only)])


class HistoryMessage(Strict):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)


class Ask(Strict):
    question: str = Field(min_length=2, max_length=1200)
    conversation_id: str | None = Field(default=None, pattern=r'^[0-9a-f-]{36}$')
    remember: bool = Field(default=False, strict=True)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=8)

    @field_validator('question')
    @classmethod
    def question_text(cls, value):
        value = value.strip()
        if len(value) < 2 or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('질문을 다시 확인해 주세요.')
        return value

    @model_validator(mode='after')
    def history_size(self):
        if sum(len(item.content) for item in self.history) > 8000:
            raise ValueError('최근 대화가 너무 깁니다. 새 대화로 시작해 주세요.')
        return self


class Citation(Strict):
    source_id: str
    chunk_id: str
    title: str
    url: str
    source_type: str
    checked_at: str
    revision: str
    quote: str


class Action(Strict):
    label: str
    url: str
    kind: Literal['community', 'saved', 'preferences', 'item', 'login']


class Generation(Strict):
    mode: Literal['generated', 'local_extractive', 'retrieval_only', 'abstained']
    reason: str | None = None
    model: str | None = None


class Answer(Strict):
    answer: str
    citations: list[Citation]
    actions: list[Action]
    basis: Literal['public_knowledge', 'live_data', 'mixed', 'no_evidence', 'unsupported']
    live_checked_at: str
    generation: Generation
    conversation_id: str | None = None
    request_id: str


@contextmanager
def session(write=False):
    with SessionLocal() as db:
        try:
            if write and db.bind.dialect.name == 'sqlite':
                db.execute(text('BEGIN IMMEDIATE'))
            yield db
        except Exception:
            db.rollback()
            raise


def cleanup_expired_conversations(db=None):
    """Remove expired text immediately; caller may also schedule this hourly."""
    if db is None:
        with session(write=True) as owned:
            count = cleanup_expired_conversations(owned)
            owned.commit()
            return count
    legacy_empty=(Record.status=='active') & (Record.data['messages'].as_string()=='[]')
    return db.execute(delete(Record).where(Record.kind==CHAT,(Record.ends<=now()) | legacy_empty)).rowcount


def owned_chat(db, user, identifier, active=True):
    row = db.scalar(select(Record).where(Record.kind == CHAT, Record.id == identifier,
                                         Record.owner_id == user.id))
    if not row or row.ends <= now():
        raise HTTPException(404, '저장된 대화를 찾을 수 없습니다.')
    if active and row.status != 'active':
        raise HTTPException(409, '이미 종료되거나 삭제된 대화입니다. 새 대화로 시작해 주세요.')
    return row


def summary(row):
    return {'id': row.id, 'title': row.data.get('title', '저장된 대화'),
            'updated_at': release.timestamp(row.data.get('updated', row.created)),
            'expires_at': release.timestamp(row.ends), 'revision': row.revision, 'status': row.status}


def clear_chat(db, row, status):
    result = db.execute(update(Record).where(Record.id == row.id, Record.kind == CHAT,
        Record.owner_id == row.owner_id, Record.revision == row.revision).values(
        data={}, status=status, revision=Record.revision+1, ends=now()+RETENTION))
    if result.rowcount != 1:
        raise HTTPException(409, '대화 상태가 변경되었습니다. 다시 확인해 주세요.')



class RequestObservation:
    """Request-local numbers/enums only; never hold account or conversation content."""
    def __init__(self):
        self.started = monotonic()
        self.timings = {name: 0. for name in observation_contract.STAGES}
        self.states = {name: 'skipped' for name in observation_contract.STAGES}
        self.tools = {}
        self.sources = []
        self.outcome = 'error'
        self.error_code = 'none'

    @contextmanager
    def stage(self, name):
        started = monotonic()
        try:
            yield
        except Exception:
            self.states[name] = 'error'
            raise
        else:
            if self.states[name] != 'error':
                self.states[name] = 'completed'
        finally:
            self.timings[name] += (monotonic()-started)*1000

    def error(self, error):
        if isinstance(error, model_runtime.ModelFailure):
            code = error.code
        elif isinstance(error, HTTPException):
            code = ('auth_changed' if error.status_code in (401, 403) else
                    'quota' if error.status_code == 429 else
                    'invalid_request' if error.status_code < 500 else 'unavailable')
        else:
            code = 'unavailable'
        self.error_code = code if code in observation_contract.ERRORS else 'unavailable'

    def finish(self):
        self.timings['total'] = (monotonic()-self.started)*1000
        self.states['total'] = 'error' if self.outcome == 'error' else 'completed'
        try:
            # Candidate transport discards this internal correlation token. Only the
            # static public source map, enums and numbers cross its strict contract.
            observability.record(uuid4().hex, self.timings, self.sources, self.outcome,
                error_code=self.error_code, tools=self.tools, stage_status=self.states)
        except Exception:
            pass

    def citations(self, citations):
        try:
            allowed = observation_contract.source_map()
            sources = {item['source_id']: item['revision'] for item in citations}
            if all(allowed.get(key) == value for key, value in sources.items()):
                self.sources = [{'source_id': key, 'revision': value} for key, value in sources.items()][:5]
        except (observation_contract.ObservationError, KeyError, TypeError):
            self.sources = []


def initial_state(body, request, observation):
    cleanup_expired_conversations()
    identifier,revision,user_id=None,None,None
    prior_questions=[message.content for message in body.history if message.role=='user']
    with session(write=True) as db:
        user = optional_user(request, db)
        user_id = user.id if user else None
        if (body.remember or body.conversation_id) and not user:
            current_user(user)
        cleanup_expired_conversations(db)
        if body.conversation_id:
            row = owned_chat(db, user, body.conversation_id)
            if body.remember:
                identifier,revision=row.id,row.revision
                prior_questions=[message.get('content','') for message in row.data.get('messages',[]) if message.get('role')=='user']
            else:
                # Before inference, invalidate every pending writer and erase all text.
                clear_chat(db, row, 'opted_out')
        elif body.remember:
            # Serialize account allocation on PostgreSQL; SQLite has BEGIN IMMEDIATE.
            db.scalar(select(User).where(User.id == user.id).with_for_update())
            count = db.scalar(select(func.count()).select_from(Record).where(
                Record.kind == CHAT, Record.owner_id == user.id, Record.status == 'active', Record.ends > now()))
            if count >= MAX_CONVERSATIONS:
                raise HTTPException(409, '저장 가능한 대화 수에 도달했습니다. 기존 대화를 삭제한 후 다시 시도해 주세요.')
            pending=db.scalar(select(func.count()).select_from(Record).where(Record.kind==CHAT,Record.owner_id==user.id,Record.status=='pending',Record.ends>now()))
            if pending>=MAX_PENDING:
                raise HTTPException(429,'준비 중인 대화가 있습니다. 잠시 후 다시 시도해 주세요.',headers={'Retry-After':'5'})
            row=Record(kind=CHAT,owner_id=user.id,status='pending',data={'messages':[]},ends=now()+PENDING_TTL)
            db.add(row)
            db.flush()
            identifier, revision = row.id, row.revision
        # Execute the allowlisted tool once to detect failure before starting expensive inference.
        prior_topic=knowledge.latest_public_topic(prior_questions)
        effective_question,needs_clarification=knowledge.resolve_public_question(body.question,prior_topic)
        if not needs_clarification and not knowledge.restricted_data_request(effective_question):
            with observation.stage('tools'):
                assistant_tools.live_read(db,user,effective_question)
        db.commit()
    return user_id,identifier,revision,effective_question,needs_clarification


def retrieval_answer(chunks):
    if not chunks:
        return '질문에 답할 수 있는 확인된 자료를 찾지 못했어요. 비교하려는 분야나 제품을 조금 더 구체적으로 알려주세요.', []
    selected=[]
    for chunk in chunks[:3]:
        end=0
        for unit in model_runtime.evidence_sentences(chunk):
            start=chunk.text.find(unit,end)
            boundary=start+len(unit)
            if start<0 or boundary>800:break
            end=boundary
        if end:selected.append((chunk,chunk.text[:end].strip()))
    if not selected:
        return '확인한 자료에서 완결된 안내 문장을 찾지 못했어요. 질문을 조금 더 구체적으로 알려주세요.',[]
    # Source excerpts end at complete sentence/line boundaries, never midway through a negation.
    return '확인된 자료에서 찾은 안내예요.\n\n'+'\n\n'.join(quote for _,quote in selected),[chunk.citation(quote) for chunk,quote in selected]


@router.get('/status')
def status():
    return {**model_runtime.status(), 'history_retention_days': 30, 'remember_default': False,
            'observability': observability.status()}


def discard_pending(identifier,owner_id,revision):
    with session(write=True) as db:
        db.execute(delete(Record).where(Record.kind==CHAT,Record.id==identifier,
            Record.owner_id==owner_id,Record.status=='pending',Record.revision==revision))
        db.commit()


@router.post('/ask',response_model=Answer)
def ask(body:Ask,request:Request):
    observation = RequestObservation()
    request_id = uuid4().hex
    user_id = identifier = revision = None
    is_new = bool(body.remember and not body.conversation_id)
    try:
        with assistant_tools.capture_tool_calls(observation.tools):
            with observation.stage('validation'):
                user_id,identifier,revision,effective_question,needs_clarification=initial_state(body,request,observation)
            return answer_request(body,request,observation,request_id,user_id,identifier,revision,is_new,effective_question,needs_clarification)
    except Exception as error:
        observation.error(error)
        if is_new and identifier:
            try:discard_pending(identifier,user_id,revision)
            except Exception:pass  # An unavailable DB is bounded by the short pending TTL.
        raise
    finally:
        request.state.assistant_observation_recorded = True
        observation.finish()


def answer_request(body,request,observation,request_id,user_id,identifier,revision,is_new,effective_question,needs_clarification):
    restricted=knowledge.restricted_data_request(effective_question)
    unsupported=knowledge.unsupported(effective_question)
    if unsupported:needs_clarification=False
    chunks=[]
    if not needs_clarification and not unsupported:
        with observation.stage('retrieval'):
            chunks=knowledge.retrieve(effective_question)
    reason, model, citations = None, None, []
    if needs_clarification:
        mode,reason='abstained','clarification_needed'
        answer='어떤 제품이나 분야를 말씀하시는지 확인하기 어려워요. 대상 이름을 함께 적어주세요.'
    elif unsupported:
        mode = 'abstained'
        reason = unsupported
        messages = {
            'medical': '증상·진단·약 복용은 여기서 판단할 수 없어요. 의료진에게 상담해 주세요. 호흡 곤란이나 의식 저하 같은 응급 상황이면 즉시 응급 도움을 요청해 주세요.',
            'certification': '개별 제품의 안전성이나 KC 인증을 확인할 근거가 없어요. 정확한 모델명으로 공식 제품 설명과 인증 정보를 확인해 주세요.',
            'price': '현재 가격·재고를 확인하는 연결이 없어 금액이나 구매 가능 여부를 확정할 수 없어요. 연결된 공식 판매처에서 현재 조건을 확인해 주세요.',
        }
        answer = messages[unsupported]
    elif chunks:
        try:
            with observation.stage('generation'):
                answer, citations, model = model_runtime.generate(effective_question,chunks)
            mode='local_extractive'
        except model_runtime.ModelFailure as error:
            observation.error(error)
            if error.code == 'disabled':observation.states['generation'] = 'skipped'
            reason, mode = error.code, 'retrieval_only'
            answer, citations = retrieval_answer(chunks)
    else:
        reason, mode = 'no_evidence', 'retrieval_only'
        answer, citations = retrieval_answer([])
    with observation.stage('validation'), session(write=True) as db:
        user = optional_user(request, db)
        if (user.id if user else None) != user_id:
            raise HTTPException(401, '로그인 상태가 변경되었습니다. 다시 로그인해 주세요.')
        # Source files are reread, not trusted from retrieval or a previous answer.
        valid_chunks = knowledge.revalidate(chunks)
        if not unsupported and len(valid_chunks) != len(chunks):
            answer, citations = retrieval_answer(valid_chunks)
            mode, reason, model = 'retrieval_only', 'evidence_changed', None
            observation.error_code = 'evidence_changed'
            observation.states['validation'] = 'error'
        live={'actions':[],'notes':[],'references':[]}
        if not needs_clarification and not restricted:
            with observation.stage('tools'):
                live=assistant_tools.live_read(db,user,effective_question)
        if restricted:
            answer='비밀번호·인증 토큰과 다른 회원의 비공개 정보는 제공할 수 없어요. 확인된 공개 안내만 제공해요.\n\n'+answer
        if (not restricted and live.get('verified_offer') and unsupported in (None, 'price')
                and reason != 'evidence_changed' and re.search(r'공구|공동.?구매|가격|얼마', effective_question)):
            answer='판매처에서 마지막으로 수집한 공구 정보를 안내해요. 최종 금액과 구매 조건은 판매처에서 확인해 주세요.'
            mode, reason, unsupported, model, citations = 'retrieval_only', None, None, None, []
        if live['notes']:
            answer += '\n\n'+'\n'.join(live['notes'])
        checked_at = knowledge.timestamp()
        basis = ('unsupported' if unsupported else 'mixed' if citations and live['notes'] else
                 'public_knowledge' if citations else 'live_data' if live['notes'] else 'no_evidence')
        answer = answer[:4000]
        if identifier:
            if is_new:
                db.scalar(select(User).where(User.id==user.id).with_for_update())
            row=owned_chat(db,user,identifier,active=not is_new)
            expected_status='pending' if is_new else 'active'
            if row.status!=expected_status or row.revision!=revision:
                raise HTTPException(409, '대화가 변경되었습니다. 삭제·종료 상태를 확인하고 새로 시도해 주세요.')
            if is_new:
                active_count=db.scalar(select(func.count()).select_from(Record).where(Record.kind==CHAT,Record.owner_id==user.id,Record.status=='active',Record.ends>now()))
                if active_count>=MAX_CONVERSATIONS:
                    raise HTTPException(409,'저장 가능한 대화 수에 도달했습니다. 기존 대화를 정리한 후 다시 시도해 주세요.')
            stamp = now()
            history = list(row.data.get('messages', []))[-(MAX_MESSAGES-2):]
            history.extend([{'role': 'user', 'content': body.question, 'created_at': release.timestamp(stamp)},
                            {'role': 'assistant', 'content': answer, 'created_at': checked_at}])
            data = {'messages': history, 'title': row.data.get('title') or body.question[:70], 'updated': stamp}
            changed = db.execute(update(Record).where(Record.kind == CHAT, Record.id == identifier,
                Record.owner_id==user.id,Record.status==expected_status,Record.revision==revision,
                Record.ends>stamp).values(data=data,status='active',ends=stamp+RETENTION,revision=Record.revision+1))
            if changed.rowcount != 1:
                raise HTTPException(409, '대화 저장 상태가 변경되었습니다. 다시 확인해 주세요.')
        db.commit()
    observation.outcome = mode
    observation.citations(citations)
    return {'answer': answer, 'citations': citations, 'actions': live['actions'], 'basis': basis,
            'live_checked_at': checked_at, 'generation': {'mode': mode, 'reason': reason, 'model': model},
            'conversation_id': identifier, 'request_id': request_id}


@router.get('/conversations')
def conversations(request: Request, limit: int = Query(20, ge=1, le=20), offset: int = Query(0, ge=0, le=20)):
    with session(write=True) as db:
        user = current_user(optional_user(request, db))
        cleanup_expired_conversations(db)
        rows = list(db.scalars(select(Record).where(Record.kind == CHAT, Record.owner_id == user.id,
            Record.status == 'active', Record.ends > now()).order_by(Record.ends.desc(), Record.id).limit(MAX_CONVERSATIONS)))
        rows = [row for row in rows if row.data.get('messages')]
        result = {'items': [summary(row) for row in rows[offset:offset+limit]], 'has_more': len(rows) > offset+limit}
        db.commit()
        return result


@router.get('/conversations/{identifier}')
def conversation(identifier: str, request: Request):
    with session(write=True) as db:
        user = current_user(optional_user(request, db))
        cleanup_expired_conversations(db)
        db.commit()
        row = owned_chat(db, user, identifier)
        return {**summary(row), 'messages': row.data.get('messages', []), 'remember': True}


def close_conversation(identifier, request, state):
    cleanup_expired_conversations()
    with session(write=True) as db:
        user = current_user(optional_user(request, db))
        cleanup_expired_conversations(db)
        row = owned_chat(db, user, identifier, active=False)
        if row.status == 'active':
            clear_chat(db, row, state)
        elif row.status != state:
            # Deleting an ended/opted-out tombstone is safe and idempotent.
            clear_chat(db, row, state)
        db.commit()
        return {'id': identifier, 'status': state, 'cleared': True}


@router.post('/conversations/{identifier}/end')
def end_conversation(identifier: str, request: Request):
    return close_conversation(identifier, request, 'ended')


@router.delete('/conversations/{identifier}')
def delete_conversation(identifier: str, request: Request):
    return close_conversation(identifier, request, 'deleted')
