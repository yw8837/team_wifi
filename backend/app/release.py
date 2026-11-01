"""Public information and community API. Never reads beta offers or transactions."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import delete, exists, func, select

from . import config
from .db import Record, Token, User, get_db, now, uid
from .schemas import Strict
from .security import admin_user, current_user, optional_user, throttle

CATALOG_PATH = Path(__file__).with_name('release_catalog.json')
DEMAND = 'release_demand'
COMMENT = 'release_comment'
INTEREST = 'release_interest'
SAVE = 'release_save'
REPORT = 'release_report'


def public_only():
    if not config.PUBLIC_RELEASE:
        raise HTTPException(404, '공개 서비스에서 제공하지 않는 기능입니다.')


router = APIRouter(prefix='/api/release', dependencies=[Depends(public_only)])


class Offer(Strict):
    id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=3000)
    source_name: str = Field(min_length=1, max_length=100)
    source_url: str = Field(max_length=2048)
    source_checked_at: datetime
    entry_type: Literal['shopping_reference', 'verified_offer']
    price: int | None = Field(ge=0)
    shipping_fee: int | None = Field(ge=0)
    unit: str | None = Field(max_length=100)
    expires_at: datetime | None
    comparison_notes: list[str] = Field(max_length=20)
    is_affiliate: bool

    @field_validator('source_url')
    @classmethod
    def safe_url(cls, value):
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('A public HTTPS source is required.')
        return value

    @field_validator('source_checked_at', 'expires_at')
    @classmethod
    def utc_time(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('A timezone is required.')
        return value.astimezone(timezone.utc) if value is not None else None

    @field_validator('comparison_notes')
    @classmethod
    def bounded_notes(cls, values):
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError('Comparison notes must be nonempty and at most 1000 characters.')
        return values


class Manifest(Strict):
    schema_version: Literal[1]
    checked_at: datetime
    entries: list[Offer] = Field(max_length=200)


def catalog():
    # Fail closed: the checked-in manifest is the sole source, never DB seed data.
    try:
        manifest = Manifest.model_validate_json(CATALOG_PATH.read_text(encoding='utf-8'))
        if manifest.checked_at.tzinfo is None:
            raise ValueError('Missing manifest timezone')
        result = [entry.model_dump(mode='json') for entry in manifest.entries]
        if len({entry['id'] for entry in result}) != len(result):
            raise ValueError('Duplicate offer identifiers')
        return result
    except (OSError, ValueError):
        raise HTTPException(503, '확인한 외부 정보를 준비 중입니다. 잠시 후 다시 불러와 주세요.') from None


def offer_by_id(id):
    for offer in catalog():
        if offer['id'] == id:
            return offer
    raise HTTPException(404, '정보를 찾을 수 없습니다.')


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def saved_ids(db, user):
    return set(db.scalars(select(Record.parent_id).where(Record.kind == SAVE, Record.owner_id == user.id))) if user else set()


@router.get('/offers')
def offers(q: str = Query('', max_length=100), category: str = Query('', max_length=40),
           limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
           user=Depends(optional_user), db=Depends(get_db)):
    saved = saved_ids(db, user)
    matches = [entry for entry in catalog() if (not category or entry['category'] == category) and
               (not q.strip() or q.strip().casefold() in (entry['title']+' '+entry['summary']+' '+entry['source_name']).casefold())]
    return [{**entry, 'saved': entry['id'] in saved} for entry in matches[offset:offset+limit]]


@router.get('/offers/{id}')
def offer(id: str, user=Depends(optional_user), db=Depends(get_db)):
    entry = offer_by_id(id)
    return {**entry, 'saved': id in saved_ids(db, user)}


def put_unique(db, kind, user_id, target_id):
    # Database uniqueness handles duplicate and concurrent PUTs without fake counters.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(Record).values(id=uid(), kind=kind, owner_id=user_id, parent_id=target_id,
               unique_key=f'{user_id}:{target_id}', data={}, status='active', created=now())
               .on_conflict_do_nothing(index_elements=['kind', 'unique_key']))
    db.commit()


@router.put('/offers/{id}/saved')
def save_offer(id: str, user=Depends(current_user), db=Depends(get_db)):
    entry = offer_by_id(id)
    put_unique(db, SAVE, user.id, id)
    return {**entry, 'saved': True}


@router.delete('/offers/{id}/saved')
def unsave_offer(id: str, user=Depends(current_user), db=Depends(get_db)):
    db.execute(delete(Record).where(Record.kind == SAVE, Record.owner_id == user.id, Record.parent_id == id))
    db.commit()
    return {'message': '저장을 해제했습니다.'}


@router.get('/saved')
def saved_offers(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                 user=Depends(current_user), db=Depends(get_db)):
    saved = saved_ids(db, user)
    return [{**entry, 'saved': True} for entry in catalog() if entry['id'] in saved][offset:offset+limit]


class DemandInput(Strict):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=3000)
    category: str = Field(min_length=1, max_length=40)


class CommentInput(Strict):
    body: str = Field(min_length=2, max_length=1000)


class ReportInput(Strict):
    target_type: Literal['demand', 'comment', 'user']
    target_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=5, max_length=1000)


class ResolveInput(Strict):
    action: Literal['hide', 'dismiss', 'suspend']
    note: str = Field(default='', max_length=1000)


def author_available():
    return exists(select(User.id).where(User.id == Record.owner_id, User.deleted.is_(False),
           ~exists(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == User.id)).correlate(User)))


def visible_query(kind, user, *conditions):
    query = select(Record).where(Record.kind == kind, Record.status == 'active', author_available(), *conditions)
    if user:
        blocked = select(Record.parent_id).where(Record.kind == 'block', Record.owner_id == user.id)
        query = query.where(Record.owner_id.not_in(blocked))
    return query.order_by(Record.created.desc(), Record.id)


def content(db, kind, id, user=None):
    item = db.scalar(visible_query(kind, user, Record.id == id))
    if not item:
        raise HTTPException(404, '게시물을 찾을 수 없습니다.')
    if kind == COMMENT:
        content(db, DEMAND, item.parent_id, user)
    return item


def author(db, item):
    user = db.get(User, item.owner_id)
    return {'id': user.id, 'nickname': user.nickname}


def demand_dto(db, item, user):
    interests = visible_query(INTEREST, None, Record.parent_id == item.id).order_by(None)
    comments = visible_query(COMMENT, user, Record.parent_id == item.id).order_by(None)
    interest_count = db.scalar(select(func.count()).select_from(interests.subquery()))
    comment_count = db.scalar(select(func.count()).select_from(comments.subquery()))
    interested = bool(user and db.scalar(interests.where(Record.owner_id == user.id).with_only_columns(Record.id).limit(1)))
    return dict(id=item.id, **item.data, author=author(db, item), created_at=timestamp(item.created),
                interest_count=interest_count, interested=interested,
                comment_count=comment_count, own=bool(user and user.id == item.owner_id))


def comment_dto(db, item, user):
    return dict(id=item.id, body=item.data['body'], author=author(db, item),
                created_at=timestamp(item.created), own=bool(user and user.id == item.owner_id))


@router.get('/demands')
def demands(q: str = Query('', max_length=100), category: str = Query('', max_length=40),
            limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
            user=Depends(optional_user), db=Depends(get_db)):
    query = visible_query(DEMAND, user)
    if category:
        query = query.where(Record.data['category'].as_string() == category)
    if q.strip():
        # Escape SQL LIKE metacharacters; input is always a bound value.
        query = query.where((Record.data['title'].as_string()+' '+Record.data['body'].as_string()).icontains(q.strip(), autoescape=True))
    return [demand_dto(db, item, user) for item in db.scalars(query.limit(limit).offset(offset))]


@router.post('/demands', status_code=201)
def create_demand(body: DemandInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'question', subject=user.id)
    item = Record(kind=DEMAND, owner_id=user.id, data=body.model_dump())
    db.add(item)
    db.commit()
    return demand_dto(db, item, user)


@router.get('/demands/{id}')
def demand(id: str, user=Depends(optional_user), db=Depends(get_db)):
    return demand_dto(db, content(db, DEMAND, id, user), user)


@router.delete('/demands/{id}')
def delete_demand(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = db.get(Record, id)
    if not item or item.kind != DEMAND or item.owner_id != user.id:
        raise HTTPException(404, '본인 게시물을 찾을 수 없습니다.')
    # Author deletion also removes replies, interest and associated report text.
    children = select(Record.id).where(Record.kind == COMMENT, Record.parent_id == id)
    db.execute(delete(Record).where(Record.kind == REPORT, Record.parent_id.in_(children)))
    db.execute(delete(Record).where(Record.kind.in_([COMMENT, INTEREST, REPORT]), Record.parent_id == id))
    db.delete(item)
    db.commit()
    return {'message': '수요 제안을 삭제했습니다.'}


@router.put('/demands/{id}/interest')
def add_interest(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = content(db, DEMAND, id, user)
    put_unique(db, INTEREST, user.id, id)
    return demand_dto(db, item, user)


@router.delete('/demands/{id}/interest')
def remove_interest(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = content(db, DEMAND, id, user)
    db.execute(delete(Record).where(Record.kind == INTEREST, Record.parent_id == id, Record.owner_id == user.id))
    db.commit()
    return demand_dto(db, item, user)


@router.get('/demands/{id}/comments')
def comments(id: str, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
             user=Depends(optional_user), db=Depends(get_db)):
    content(db, DEMAND, id, user)
    return [comment_dto(db, item, user) for item in db.scalars(visible_query(COMMENT, user, Record.parent_id == id).limit(limit).offset(offset))]


@router.post('/demands/{id}/comments', status_code=201)
def create_comment(id: str, body: CommentInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'question', subject=user.id)
    parent = content(db, DEMAND, id, user)
    if db.scalar(select(Record.id).where(Record.kind == 'block', Record.owner_id == parent.owner_id, Record.parent_id == user.id)):
        raise HTTPException(403, '이 게시물에 질문을 작성할 수 없습니다.')
    item = Record(kind=COMMENT, owner_id=user.id, parent_id=id, data=body.model_dump())
    db.add(item)
    db.commit()
    return comment_dto(db, item, user)


@router.delete('/comments/{id}')
def delete_comment(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = db.get(Record, id)
    if not item or item.kind != COMMENT or item.owner_id != user.id:
        raise HTTPException(404, '본인 질문을 찾을 수 없습니다.')
    db.execute(delete(Record).where(Record.kind == REPORT, Record.parent_id == id))
    db.delete(item)
    db.commit()
    return {'message': '질문을 삭제했습니다.'}


@router.post('/reports', status_code=201)
def report(body: ReportInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'report', subject=user.id)
    if body.target_type == 'user':
        target = db.get(User, body.target_id)
        if not target or target.deleted:
            raise HTTPException(404, '신고할 사용자를 찾을 수 없습니다.')
    else:
        # Reports remain available even when the reporter blocked the author.
        content(db, DEMAND if body.target_type == 'demand' else COMMENT, body.target_id)
    key = f'{user.id}:{body.target_type}:{body.target_id}'
    existing = db.scalar(select(Record).where(Record.kind == REPORT, Record.unique_key == key))
    if existing:
        return {'id': existing.id, 'message': '이미 접수한 신고입니다.'}
    item = Record(kind=REPORT, owner_id=user.id, parent_id=body.target_id, unique_key=key, data=body.model_dump())
    db.add(item)
    db.commit()
    return {'id': item.id, 'message': '신고가 접수되었습니다.'}


def report_dto(db, item):
    target_type = item.data['target_type']
    target = db.get(User if target_type == 'user' else Record, item.parent_id)
    preview, demand_id, nickname = '', None, ''
    if target_type == 'user' and target and not target.deleted:
        preview = nickname = target.nickname
    elif target and target.kind in (DEMAND, COMMENT):
        preview = (target.data.get('title', '')+' '+target.data.get('body', '')).strip()[:300]
        demand_id = target.id if target.kind == DEMAND else target.parent_id
        account = db.get(User, target.owner_id)
        nickname = account.nickname if account and not account.deleted else '탈퇴한 회원'
    return dict(target_preview=preview, demand_id=demand_id, author_nickname=nickname, id=item.id, target_type=item.data['target_type'], target_id=item.parent_id,
                reason=item.data['reason'], status=item.status, created_at=timestamp(item.created), note=item.data.get('note', ''))


@router.get('/admin/reports')
def admin_reports(limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                  user=Depends(admin_user), db=Depends(get_db)):
    return [report_dto(db, item) for item in db.scalars(select(Record).where(Record.kind == REPORT)
            .order_by(Record.created.desc(), Record.id).limit(limit).offset(offset))]


@router.post('/admin/reports/{id}/resolve')
def resolve_report(id: str, body: ResolveInput, user=Depends(admin_user), db=Depends(get_db)):
    report = db.get(Record, id)
    if not report or report.kind != REPORT:
        raise HTTPException(404, '신고를 찾을 수 없습니다.')
    if report.status != 'active':
        raise HTTPException(409, '이미 처리된 신고입니다.')
    target_type = report.data['target_type']
    target = db.get(User if target_type == 'user' else Record, report.parent_id)
    if not target or (target_type != 'user' and target.kind != (DEMAND if target_type == 'demand' else COMMENT)) or (target_type == 'user' and target.deleted):
        raise HTTPException(404, '신고 대상을 찾을 수 없습니다.')
    if body.action == 'hide':
        if target_type == 'user':
            raise HTTPException(422, '사용자 신고는 이용정지 또는 기각으로 처리해 주세요.')
        target.status = 'hidden'
    elif body.action == 'suspend':
        account = target if target_type == 'user' else db.get(User, target.owner_id)
        if not account or account.deleted or account.is_admin or account.id == user.id:
            raise HTTPException(422, '이 계정을 이용정지할 수 없습니다.')
        if not db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == account.id)):
            db.add(Record(kind='suspension', owner_id=account.id, unique_key=account.id, data={}))
        db.execute(delete(Token).where(Token.user_id == account.id))
    report.status = 'resolved'
    report.data = {**report.data, 'action': body.action, 'note': body.note, 'resolved_at': timestamp(now())}
    db.add(Record(kind='audit', owner_id=user.id, parent_id=report.id, data={'action': 'release-report-'+body.action}))
    db.commit()
    return report_dto(db, report)


def delete_user_content(db, user_id, owned):
    """Remove public content and references, including other users' replies to deleted posts."""
    # owned IDs were collected before owner rows were removed by account deletion.
    related_comments = list(db.scalars(select(Record.id).where(Record.kind == COMMENT, Record.parent_id.in_(owned))))
    targets = [user_id, *owned, *related_comments]
    db.execute(delete(Record).where(Record.kind.in_([COMMENT, INTEREST, SAVE, REPORT, 'block']), Record.parent_id.in_(targets)))
