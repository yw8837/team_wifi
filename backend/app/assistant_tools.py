"""Allowlisted read tools. Member/community bodies never leave the application DB."""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from sqlalchemy import or_, select
from . import release, advisor, knowledge
from .db import Record


_TOOL_CALLS=ContextVar('assistant_tool_calls',default=None)


@contextmanager
def capture_tool_calls(counts=None):
    """Request-local fixed tool counts, including a query that subsequently fails."""
    captured=counts if counts is not None else {}
    token=_TOOL_CALLS.set(captured)
    try:yield captured
    finally:_TOOL_CALLS.reset(token)


def _tool_call(name,local):
    local[name]=min(16,local.get(name,0)+1)
    captured=_TOOL_CALLS.get()
    if captured is not None:captured[name]=min(16,captured.get(name,0)+1)


def live_read(db, user, question):
    actions, notes, references = [], [], []
    tool_calls={}
    query = question.casefold()
    chat_settings=bool(re.search(r'대화|채팅|도우미',query) and re.search(r'저장|보관|삭제|종료',query))
    saved_requested=not chat_settings and bool(re.search(r'저장한|저장해.?둔|저장\s*목록|내\s*저장|내 목록|찜한|찜\s*목록',query))
    preferences_requested=not chat_settings and bool(re.search(r'내 조건|내 관심|관심 분야|선택한|고른|조건 찾기',query))
    recommendations_requested=not chat_settings and bool(re.search(r'추천|함께',query)) and not bool(re.search(r'글|게시|경험|커뮤니티',query))
    public_cohort_question=bool(re.search(r'함께\s*저장',query) and re.search(r'몇|최소|기준|계정|근거',query) and not re.search(r'내가|내 저장|나의',query))
    if public_cohort_question:saved_requested=recommendations_requested=False
    own_requested=saved_requested or preferences_requested or recommendations_requested
    categories=knowledge.explicit_categories(question)
    if own_requested:
        if not user:
            actions.append({'label': '로그인 후 내 기록 확인', 'url': '/login?returnTo=%2Fchat', 'kind': 'login'})
            notes.append('내 저장 목록과 선택 조건은 로그인 후 본인 계정에서 확인할 수 있어요.')
        else:
            _tool_call('public_catalog',tool_calls)
            entries = release.catalog()
            _tool_call('own_saved',tool_calls)
            saved = release.saved_ids(db, user)
            items=[entry for entry in entries if entry['id'] in saved and (not categories or entry['category'] in categories)][:8]
            if saved_requested:
                if categories:
                    scope=', '.join(categories)
                    notes.append('내 저장 목록에서 '+scope+' 분야로 찾은 공식 목록이에요.' if items else '내 저장 목록에 '+scope+' 분야의 목록이 없어요.')
                else:
                    notes.append('지금 내 저장 목록에서 확인한 공식 목록이에요.' if items else '지금 내 저장 목록은 비어 있어요.')
                actions.append({'label': '내 저장 목록', 'url': '/my/saved', 'kind': 'saved'})
                for entry in items:
                    actions.append({'label': entry['title'], 'url': '/offers/'+entry['id'], 'kind': 'item'})
            if preferences_requested:
                _tool_call('own_preferences',tool_calls)
                preferences = release.preferences_for(db, user)
                choices = db.scalar(select(Record).where(Record.kind == advisor.STATE, Record.owner_id == user.id))
                chosen_categories=(choices.data.get('categories',[]) if choices else preferences.categories)
                notes.append('직접 고른 관심 분야: '+', '.join(chosen_categories) if chosen_categories else '아직 선택한 관심 분야가 없어요.')
                actions.append({'label': '조건 찾기', 'url': '/advisor', 'kind': 'preferences'})
            if recommendations_requested and items:
                # Reuse the existing five-account threshold, never infer individual co-savers.
                _tool_call('public_catalog',tool_calls)
                result = advisor.companions(items[0]['id'], db)
                notes.append('함께 저장한 계정이 기준 이상인 목록이에요.' if result['basis'] == 'co_save'
                             else '함께 저장 근거가 충분하지 않아 같은 분야의 목록을 보여드려요.')
                for entry in result['items']:
                    if categories and entry['category'] not in categories:continue
                    actions.append({'label': entry['title'], 'url': '/offers/'+entry['id'], 'kind': 'item'})
    ignored = {'최근', '커뮤니티', '관련', '질문', '내가', '저장한', 'the', 'show'}
    ignored.update(knowledge.RETRIEVAL_STOP_WORDS)
    terms = sorted({feature[2:] for feature in knowledge.retrieval_features(query)
                    if feature.startswith('w:') and not any(feature[2:].startswith(word) for word in ignored)})[:12]
    if terms:
        conditions = [Record.data['title'].as_string().icontains(term, autoescape=True) |
                      Record.data['body'].as_string().icontains(term, autoescape=True) for term in terms]
        visible = release.visible_query(release.DEMAND, user, or_(*conditions))
        if categories:
            visible = visible.where(Record.data['category'].as_string().in_(categories))
        _tool_call('public_community',tool_calls)
        rows = list(db.scalars(visible.limit(5)))
        for row in rows:
            # A title is a link label only: never prompt material or factual support.
            actions.append({'label': str(row.data.get('title', '커뮤니티 글'))[:120],
                            'url': '/demands/'+row.id, 'kind': 'community'})
            references.append((row.id, row.revision))
        if rows:
            notes.append('질문 시점에 공개 가능한 관련 커뮤니티 글을 찾았어요. 회원 경험은 검증된 사실과 구분해 살펴보세요.')
    if re.search(r'공구|공동.?구매|마감|판매처',query):
        from . import groupbuys
        from .db import now
        checked=groupbuys.display_time(release.timestamp(now()))
        query_rows=groupbuys.visible_query(user,Record.status=='active',Record.ends>now(),
            Record.data['is_demo'].as_boolean().is_not(True))
        if categories:query_rows=query_rows.where(Record.data['category'].as_string().in_(categories))
        groupbuy_terms=[term for term in terms if term not in {'공구','공동구매','마감','판매처','진행','현재','알려줘','보여줘','찾아줘','구매','정보'}]
        if groupbuy_terms:
            query_rows=query_rows.where(or_(*[Record.data['title'].as_string().icontains(term,autoescape=True)|Record.data['body'].as_string().icontains(term,autoescape=True) for term in groupbuy_terms]))
        _tool_call('public_groupbuys',tool_calls)
        groupbuy_rows=list(db.scalars(query_rows.order_by(Record.ends,Record.id).limit(3)))
        for position,row in enumerate(groupbuy_rows,1):
            entry=groupbuys.dto(db,row,user)
            actions.append({'label':entry['title'],'url':'/groupbuys/'+row.id,'kind':'item'})
            amount='금액 미확인' if entry['price'] is None else '공유 금액 '+str(entry['price'])+'원'
            provenance = '판매처 공개 페이지 수집' if entry['source_type'] == 'seller_page' else '회원 공유·판매처 확정 아님'
            notes.append('공구 '+str(position)+' · '+entry['title']+' ('+provenance+'): '+amount+' · 마감 '+groupbuys.display_time(entry['expires_at'])+' · 출처 확인 '+groupbuys.display_time(entry['source_checked_at'])+' · DB 조회 '+checked+(' · 정보 확인 필요' if entry['review_state']=='needs_review' else '')+' · 조건은 연결한 공구와 판매처에서 다시 확인하세요.')
            references.append((row.id,row.revision))
        if not groupbuy_rows:notes.append('DB 조회 '+checked+' 기준 공개 가능한 진행 중 공구를 찾지 못했어요. 가격·재고·구매 가능 여부는 확정할 수 없어요.')
    unique = {(a['kind'], a['url']): a for a in actions}
    return {'actions': list(unique.values())[:16], 'notes': notes, 'references': references,'tool_calls':tool_calls}
