"""Allowlisted read tools. Member/community bodies never leave the application DB."""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from sqlalchemy import JSON, and_, case, cast, func, or_, select
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


def list_intent(question):
    """Recognize list requests, leaving advice and follow-up questions to retrieval."""
    text = re.sub(r'[?!.,~]+$', '', question.strip())
    suffix = r'(?:\s*(?:목록|리스트))?\s*(?:을|를)?\s*(?:보여\s*줘|보여\s*주세요|알려\s*줘|찾아\s*줘|조회|뭐\s*(?:있어|있나요|있을까)\s*(?:요)?|뭐야)?'
    if re.fullmatch(r'(?:지금\s*|현재\s*)?(?:진행\s*중인?\s*)?(?:공구|공동구매)' + suffix, text):
        return 'active'
    if re.fullmatch(r'(?:내가?\s*)?(?:찜한|찜해\s*둔|저장한)\s*(?:공구|공동구매)' + suffix, text):
        return 'saved'
    return None


# Product lookups match identifying words, not shopping or conversation boilerplate.
_SEARCH_WORDS = {
    '공구', '공동구매', '공동', '구매', '판매처', '판매가', '가격', '금액', '마감', '진행', '중인',
    '옵션', '구성', '판매', '현재', '최근', '관련', '정확히', '혹시', '얼마', '언제', '까지',
    '게시판', '게시글', '커뮤니티', '후기', '리뷰', '경험', '실사용', '질문', '목록', '어떤', '찾고', '싶어', '링크', '종료', '파는', '있을지',
}
_SEARCH_FILLER = re.compile(r'^(?:알려|보여|찾아|궁금|얼마|있나요|있을까|있을까요|인가요|이에요|해주세요|해줘|언제|끝나|하나요|살까|팔아|파나요|있는지|있을지|관련된)')
_COMMUNITY_REQUEST = re.compile(r'커뮤니티|게시판|게시글|후기|사용기|리뷰|경험|써\s*본|(?:관련|추천|수요|질문)\s*글')
_PRICE_REQUEST = re.compile(r'가격|금액|얼마(?!나)|판매가')
_DEAL_REQUEST = re.compile(r'공구|공동\s*구매|마감|판매처')


def subject_terms(question):
    """Keep one subject term per word, including numbered options such as 2종세트."""
    terms = []
    for word in re.findall(r'[가-힣a-z0-9]+', question.casefold()):
        stem = word
        for suffix in ('은요', '는요', '이랑', *knowledge.RETRIEVAL_SUFFIXES):
            if stem.endswith(suffix) and len(stem) - len(suffix) >= 2:
                stem = stem[:-len(suffix)]
                break
        if (len(stem) >= 2 and stem not in knowledge.RETRIEVAL_STOP_WORDS and stem not in _SEARCH_WORDS
                and not _SEARCH_FILLER.match(stem) and stem not in terms):
            terms.append(stem)
    return terms


def named_deal_query(db, query, terms):
    """All words must describe the same product or one of its individual options."""
    product = (func.coalesce(Record.data['title'].as_string(), '') + ' ' +
               func.coalesce(Record.data['seller_name'].as_string(), '') + ' ' +
               func.coalesce(Record.data['category'].as_string(), ''))
    unit = func.coalesce(Record.data['unit'].as_string(), '')
    labels = Record.data['option_labels']
    if db.get_bind().dialect.name == 'postgresql':
        # Missing keys and old records with JSON null have no option rows.
        labels = cast(labels, JSON)
        options = func.json_array_elements_text(case((func.json_typeof(labels) == 'array', labels)))
    else:
        options = func.json_each(labels)
    variants = options.table_valued('value').alias('variant')
    def matches(field):
        return and_(*(or_(product.icontains(term, autoescape=True), field.icontains(term, autoescape=True))
                      for term in terms))
    return query.where(or_(matches(unit), select(1).select_from(variants)
                           .where(matches(variants.c.value)).correlate(Record).exists()))


def offer_amount(entry, terms):
    """Only quote option amounts published by the seller, retaining their names."""
    seller_page = entry['source_type'] == 'seller_page'
    labels = entry.get('option_labels') or []
    if seller_page and labels:
        product = ' '.join((entry['title'], entry['seller_name'] or '', entry['category'] or '')).casefold()
        option_terms = [term for term in terms if term not in product]
        prices = []
        for label in labels:
            match = re.fullmatch(r'(.+?) · ([0-9][0-9,]*원)', label)
            if match and all(term in match[1].casefold() for term in option_terms):
                prices.append(label)
        if prices:
            return '옵션별 금액: ' + ' / '.join(prices[:5]), True
        if not all(term in (entry.get('unit') or '').casefold() for term in option_terms):
            return '요청한 옵션의 금액은 판매처에서 확인해 주세요.', False
    if entry['price'] is None:
        return '금액 미확인', False
    scope = ' (' + entry['unit'] + ' 기준)' if entry.get('unit') else ''
    return f"공유 금액 {entry['price']}원{scope}", seller_page


def live_read(db, user, question):
    actions, notes, references = [], [], []
    verified_offer = False
    tool_calls={}
    query = question.casefold()
    intent = list_intent(query)
    if intent == 'saved':
        from .groupbuys import saved_groupbuy_query
        if user is None:
            notes.append('찜한 공구는 로그인 후 확인할 수 있어요.')
            actions.append({'label':'로그인하기','url':'/login?returnTo=%2Fchat','kind':'login'})
        else:
            _tool_call('own_saved', tool_calls)
            rows = list(db.scalars(saved_groupbuy_query(user).limit(3)))
            notes.append('내가 찜한 공구 중 지금 진행 중인 상품이에요.' if rows else '진행 중인 공구 중에 내가 찜한 상품이 없어요.')
            actions.extend({'label':row.data['title'], 'url':'/groupbuys/'+row.id, 'kind':'item'} for row in rows)
            actions.append({'label':'찜한 공구 전체 보기','url':'/my/saved','kind':'saved'})
        return {'actions':actions,'notes':notes,'references':[], 'tool_calls':tool_calls,'verified_offer':False}
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
    subject = subject_terms(query)
    community_requested = bool(_COMMUNITY_REQUEST.search(query))
    asks_for_guidance = bool(re.search(r'비교|계산|기준|방법|보관|작성|신고|어떻게', query))
    amount_requested = bool(_PRICE_REQUEST.search(query)) and not asks_for_guidance
    product_lookup = bool(_DEAL_REQUEST.search(query)) or (amount_requested and bool(subject) and not own_requested)
    if community_requested and not (amount_requested or '마감' in query):
        product_lookup = False
    if product_lookup:
        from . import groupbuys
        from .db import now
        checked=groupbuys.display_time(release.timestamp(now()))
        query_rows=groupbuys.visible_query(user,Record.status=='active',Record.ends>now(),
            Record.data['is_demo'].as_boolean().is_not(True))
        if categories:query_rows=query_rows.where(Record.data['category'].as_string().in_(categories))
        _tool_call('public_groupbuys',tool_calls)
        if intent == 'active':
            actions.append({'label':'진행 중인 공구 전체 보기','url':'/','kind':'item'})
        elif 0 < len(subject) <= 12:
            query_rows = named_deal_query(db, query_rows, subject)
        else:
            query_rows = query_rows.where(False)
        groupbuy_rows = list(db.scalars(query_rows.order_by(Record.ends, Record.id).limit(3)))
        for position,row in enumerate(groupbuy_rows,1):
            entry=groupbuys.dto(db,row,user)
            actions.append({'label':entry['title'],'url':'/groupbuys/'+row.id,'kind':'item'})
            amount, seller_price_confirmed = offer_amount(entry, subject)
            verified_offer = verified_offer or seller_price_confirmed
            provenance = '판매처 공개 페이지 수집' if entry['source_type'] == 'seller_page' else '회원 공유·판매처 확정 아님'
            notes.append('공구 '+str(position)+' · '+entry['title']+' ('+provenance+'): '+amount+' · 마감 '+groupbuys.display_time(entry['expires_at'])+' · 출처 확인 '+groupbuys.display_time(entry['source_checked_at'])+' · DB 조회 '+checked+(' · 정보 확인 필요' if entry['review_state']=='needs_review' else '')+' · 조건은 연결한 공구와 판매처에서 다시 확인하세요.')
            for reference in entry.get('price_references', []):
                if (not seller_price_confirmed or entry['shipping_fee'] is None
                        or reference.get('shipping_fee') is None
                        or not entry.get('comparison_quantity')
                        or reference.get('quantity') != entry['comparison_quantity']):
                    continue
                regular = reference['price'] + reference['shipping_fee']
                deal = entry['price'] + entry['shipping_fee']
                if regular <= 0:
                    continue
                difference = regular - deal
                direction = '동일 금액' if difference == 0 else '저렴' if difference > 0 else '비쌈'
                notes.append(f"동일 기본 구성 비교 · {reference['seller_name']} 배송 포함 {regular:,}원 대비 공구 {deal:,}원 · {abs(difference):,}원({abs(difference)/regular*100:.1f}%) {direction} · 비교 출처 확인 {groupbuys.display_time(reference['checked_at'])}. 옵션·쿠폰·지역 배송비는 각 판매처에서 확인하세요.")
            references.append((row.id,row.revision))
        if not groupbuy_rows:notes.append('DB 조회 '+checked+' 기준 공개 가능한 진행 중 공구를 찾지 못했어요. 가격·재고·구매 가능 여부는 확정할 수 없어요.')
    community_only = community_requested and bool(subject) and not (product_lookup or own_requested or asks_for_guidance)
    community_terms = subject if community_requested else terms
    if 0 < len(community_terms) <= 12 and intent != 'active' and (community_requested or not product_lookup):
        conditions = [Record.data['title'].as_string().icontains(term, autoescape=True) |
                      Record.data['body'].as_string().icontains(term, autoescape=True) for term in community_terms]
        match = and_(*conditions) if community_requested else or_(*conditions)
        visible = release.visible_query(release.DEMAND, user, match)
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
        elif community_only:
            notes.append('해당 상품이나 주제에 맞는 공개 커뮤니티 글을 찾지 못했어요.')
    unique = {(a['kind'], a['url']): a for a in actions}
    return {'actions': list(unique.values())[:16], 'notes': notes, 'references': references,'tool_calls':tool_calls,
            'verified_offer': verified_offer,
            'named_price_lookup': bool(product_lookup and amount_requested and subject and not own_requested),
            'community_search_only': community_only and len(community_terms) <= 12}
