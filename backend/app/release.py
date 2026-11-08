"""Public information and community API. Never reads beta offers or transactions."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import delete, exists, func, select, update

from .community_dates import filter_created, korea_date_bounds

from . import config
from . import discovery
from .db import Record, Token, User, get_db, now, uid
from .schemas import Strict
from .security import admin_user, current_user, optional_user, throttle

CATALOG_PATH = Path(__file__).with_name('release_catalog.json')
DEMAND = 'release_demand'
COMMENT = 'release_comment'
INTEREST = 'release_interest'
SAVE = 'release_save'
REPORT = 'release_report'
NOTICE = 'release_notice'
PostType = Literal['question', 'experience', 'information', 'demand']


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


def preferences_for(db, user):
    item = db.scalar(select(Record).where(Record.kind == discovery.PREFERENCE, Record.owner_id == user.id))
    return discovery.Preferences.model_validate(item.data) if item else discovery.Preferences()


@router.get('/preferences')
def get_preferences(user=Depends(current_user), db=Depends(get_db)):
    return preferences_for(db, user)


@router.put('/preferences')
def set_preferences(body: discovery.Preferences, user=Depends(current_user), db=Depends(get_db)):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(Record).values(id=uid(), kind=discovery.PREFERENCE, owner_id=user.id,
        unique_key=user.id, data=body.model_dump(), status='active', created=now())
        .on_conflict_do_update(index_elements=['kind', 'unique_key'], set_={'data': body.model_dump()}))
    db.commit()
    return body


@router.delete('/preferences')
def clear_preferences(user=Depends(current_user), db=Depends(get_db)):
    db.execute(delete(Record).where(Record.kind == discovery.PREFERENCE, Record.owner_id == user.id))
    db.commit()
    return discovery.Preferences()


@router.get('/recommendations')
def recommended_offers(user=Depends(current_user), db=Depends(get_db)):
    return discovery.recommendations(catalog(), preferences_for(db, user), saved_ids(db, user))


@router.get('/admin/insights')
def service_insights(dataset: Literal['service', 'demo'] = 'service', user=Depends(admin_user), db=Depends(get_db)):
    import json
    entries = catalog()
    current_ids = [e['id'] for e in entries]
    demo_members = select(Record.owner_id).where(Record.kind == 'demo_actor', Record.owner_id.is_not(None))
    scope = Record.owner_id.in_(demo_members) if dataset == 'demo' else Record.owner_id.not_in(demo_members)
    # Keep simulated activity separate from actual service statistics.
    saves = visible_query(SAVE, None, scope, Record.parent_id.in_(current_ids)).order_by(None).subquery()
    total = db.scalar(select(func.count(func.distinct(saves.c.owner_id)))) or 0
    counts = dict(db.execute(select(saves.c.parent_id, func.count(func.distinct(saves.c.owner_id))).group_by(saves.c.parent_id)).all())
    a, b = saves.alias('a'), saves.alias('b')
    pairs_query = (select(a.c.parent_id, b.c.parent_id, func.count(func.distinct(a.c.owner_id)).label('n'))
        .join(b, (a.c.owner_id == b.c.owner_id) & (a.c.parent_id < b.c.parent_id))
        .group_by(a.c.parent_id, b.c.parent_id).having(func.count(func.distinct(a.c.owner_id)) >= discovery.MIN_COHORT))
    titles = {e['id']: e['title'] for e in entries}
    pairs = [{'first': titles[left], 'second': titles[right], 'accounts': n,
              'support': n / total, 'first_to_second': n / counts[left],
              'second_to_first': n / counts[right]} for left, right, n in db.execute(pairs_query)]
    pairs.sort(key=lambda row: (-row['accounts'], row['first'], row['second']))
    from .groupbuys import visible_query as visible_groupbuys
    shared_rows = visible_groupbuys(None, scope).subquery()
    demand_rows = visible_query(DEMAND, None, scope).order_by(None).subquery()
    interests = visible_query(INTEREST, None, scope).order_by(None).subquery()
    categories = []
    for category in discovery.CATEGORIES:
        ids = [e['id'] for e in entries if e['category'] == category]
        saved_count = db.scalar(select(func.count(func.distinct(saves.c.owner_id))).where(saves.c.parent_id.in_(ids))) or 0
        demand_condition = demand_rows.c.data['category'].as_string() == category
        writers = db.scalar(select(func.count(func.distinct(demand_rows.c.owner_id))).where(demand_condition)) or 0
        interest_count = db.scalar(select(func.count(func.distinct(interests.c.owner_id)))
            .join(demand_rows, interests.c.parent_id == demand_rows.c.id).where(demand_condition)) or 0
        groupbuy_authors=db.scalar(select(func.count(func.distinct(shared_rows.c.owner_id))).where(shared_rows.c.data['category'].as_string()==category)) or 0
        categories.append({'category': category, 'groupbuy_shared_accounts': discovery.masked_count(groupbuy_authors), 'saved_accounts': discovery.masked_count(saved_count),
            'demand_authors': discovery.masked_count(writers), 'interested_accounts': discovery.masked_count(interest_count)})
    evidence = json.loads(Path(__file__).with_name('discovery_evidence.json').read_text('utf-8'))
    return {'dataset': dataset, 'minimum_cohort': discovery.MIN_COHORT, 'saved_accounts': discovery.masked_count(total),
            'categories': categories, 'pairs': pairs[:20], 'evidence': evidence,
            'note': '현재 계정의 저장·수요·관심 신호입니다. 구매·매출·주문 예측이 아닙니다. 1~4계정의 집계는 숨깁니다.'}


@router.get('/offers')
def offers(q: str = Query('', max_length=100), category: str = Query('', max_length=40),
           limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
           user=Depends(optional_user), db=Depends(get_db)):
    saved = saved_ids(db, user)
    matches = [entry for entry in catalog() if (not category or entry['category'] == category) and
               (not q.strip() or q.strip().casefold() in (entry['title']+' '+entry['summary']+' '+entry['source_name']).casefold())]
    return [{**entry, 'saved': entry['id'] in saved} for entry in matches[offset:offset+limit]]


@router.get('/offers/{id}')
def offer(id: str, user=Depends(optional_user), db=Depends(get_db)):
    entry = offer_by_id(id)
    return {**entry, 'saved': id in saved_ids(db, user)}


def put_unique(db, kind, user_id, target_id, commit=True):
    # Database uniqueness handles duplicate and concurrent PUTs without fake counters.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    result = db.execute(insert(Record).values(id=uid(), kind=kind, owner_id=user_id, parent_id=target_id,
               unique_key=f'{user_id}:{target_id}', data={}, status='active', created=now())
               .on_conflict_do_nothing(index_elements=['kind', 'unique_key']))
    if commit:
        db.commit()
    return result.rowcount


@router.put('/offers/{id}/saved')
def save_offer(id: str, user=Depends(current_user), db=Depends(get_db)):
    entry = offer_by_id(id)
    created = put_unique(db, SAVE, user.id, id, commit=False)
    if created:
        from .growth import confirm_save
        confirm_save(db, user, id)
    db.commit()
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
    post_type: PostType = 'demand'
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=3000)
    category: str = Field(min_length=1, max_length=40)


class CommentInput(Strict):
    body: str = Field(min_length=2, max_length=1000)


class DemandEdit(DemandInput):
    revision: int = Field(ge=1, strict=True)


class CommentEdit(CommentInput):
    revision: int = Field(ge=1, strict=True)


class ReportInput(Strict):
    target_type: Literal['demand', 'comment', 'user', 'groupbuy']
    target_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=5, max_length=1000)


class ResolveInput(Strict):
    action: Literal['hide', 'remove', 'dismiss', 'suspend', 'needs_review']
    note: str = Field(min_length=2, max_length=1000)


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


def post_type(item):
    return item.data.get('post_type') or 'demand'


def demand_dto(db, item, user):
    interests = visible_query(INTEREST, None, Record.parent_id == item.id).order_by(None)
    comments = visible_query(COMMENT, user, Record.parent_id == item.id).order_by(None)
    is_demand = post_type(item) == 'demand'
    interest_count = db.scalar(select(func.count()).select_from(interests.subquery())) if is_demand else 0
    comment_count = db.scalar(select(func.count()).select_from(comments.subquery()))
    interested = bool(is_demand and user and db.scalar(interests.where(Record.owner_id == user.id).with_only_columns(Record.id).limit(1)))
    from .groupbuys import linked_dto
    # Explicit public allowlist: storage may contain legacy/internal metadata.
    return dict(linked_groupbuy=linked_dto(db,item,user),id=item.id, title=item.data['title'], body=item.data['body'], category=item.data['category'],
                post_type=post_type(item), updated_at=item.data.get('updated_at'),
                author=author(db, item), created_at=timestamp(item.created), revision=item.revision,
                interest_count=interest_count, interested=interested,
                comment_count=comment_count, own=bool(user and user.id == item.owner_id))


def comment_dto(db, item, user):
    return dict(id=item.id, body=item.data['body'], author=author(db, item),
                created_at=timestamp(item.created), updated_at=item.data.get('updated_at'),
                revision=item.revision, own=bool(user and user.id == item.owner_id))


def edit_owned_content(db, kind, id, body, user):
    item = content(db, kind, id, user)
    if item.owner_id != user.id:
        raise HTTPException(404, '본인이 작성한 내용을 찾을 수 없습니다.')
    if kind == COMMENT:
        parent = content(db, DEMAND, item.parent_id, user)
        if db.scalar(select(Record.id).where(Record.kind == 'block', Record.owner_id == parent.owner_id, Record.parent_id == user.id)):
            raise HTTPException(403, '이 게시물의 댓글을 수정할 수 없습니다.')
    if item.revision != body.revision:
        raise HTTPException(409, '다른 화면에서 수정된 내용이 있습니다. 작성 중인 내용은 보관한 뒤 최신 내용을 확인해 주세요.')
    values = body.model_dump(exclude={'revision'}, exclude_unset=True)
    if kind == DEMAND and 'post_type' not in values:
        values['post_type'] = post_type(item)
    if kind == DEMAND and post_type(item) == 'demand' and values['post_type'] != 'demand':
        if db.scalar(select(Record.id).where(Record.kind == INTEREST, Record.parent_id == item.id).limit(1)):
            raise HTTPException(409, '관심이 등록된 수요 글은 유형을 변경할 수 없습니다.')
    if kind == DEMAND and item.data.get('groupbuy_id'):
        values['groupbuy_id'] = item.data['groupbuy_id'] if values['post_type'] == 'demand' else None
    item.data = {**values, 'updated_at': timestamp(now())}
    item.revision += 1
    db.commit()
    return item


@router.get('/demands')
def demands(q: str = Query('', max_length=100), category: str = Query('', max_length=40),
            post_type: PostType | None = None, start_date: str | None = None, end_date: str | None = None,
            sort: Literal['recent', 'popular'] = 'recent',
            limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
            user=Depends(optional_user), db=Depends(get_db)):
    query = filter_created(visible_query(DEMAND, user), start_date, end_date)
    if post_type:
        query = query.where(func.coalesce(Record.data['post_type'].as_string(), 'demand') == post_type)
    if category:
        query = query.where(Record.data['category'].as_string() == category)
    if q.strip():
        # Escape SQL LIKE metacharacters; input is always a bound value.
        query = query.where((Record.data['title'].as_string()+' '+Record.data['body'].as_string()).icontains(q.strip(), autoescape=True))
    if sort == 'popular':
        # Use the same visible, available-account interests as demand_dto, before
        # pagination. Ties retain the normal stable newest-first ordering.
        interests = visible_query(INTEREST, None).order_by(None).subquery()
        counts = select(interests.c.parent_id, func.count().label('total')).group_by(interests.c.parent_id).subquery()
        query = query.outerjoin(counts, counts.c.parent_id == Record.id).order_by(None).order_by(
            func.coalesce(counts.c.total, 0).desc(), Record.created.desc(), Record.id)
    return [demand_dto(db, item, user) for item in db.scalars(query.limit(limit).offset(offset))]


@router.post('/demands', status_code=201)
def create_demand(body: DemandInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'question', subject=user.id)
    item = Record(kind=DEMAND, owner_id=user.id, data=body.model_dump())
    db.add(item)
    db.commit()
    return demand_dto(db, item, user)


@router.get('/activity')
def activity(tab: Literal['posts', 'comments', 'interests'] = 'posts', q: str = Query('', max_length=100),
             start_date: str | None = None, end_date: str | None = None,
             limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
             user=Depends(current_user), db=Depends(get_db)):
    kind = {'posts': DEMAND, 'comments': COMMENT, 'interests': INTEREST}[tab]
    query = filter_created(visible_query(kind, user, Record.owner_id == user.id), start_date, end_date)
    if tab != 'posts':
        parents = visible_query(DEMAND, user).order_by(None)
        if tab == 'interests':
            parents = parents.where(func.coalesce(Record.data['post_type'].as_string(), 'demand') == 'demand')
        if q.strip() and tab == 'interests':
            parents = parents.where((Record.data['title'].as_string()+' '+Record.data['body'].as_string()).icontains(q.strip(), autoescape=True))
        query = query.where(Record.parent_id.in_(parents.with_only_columns(Record.id)))
    if q.strip() and tab != 'interests':
        text = Record.data['body'].as_string()
        if tab == 'posts':
            text = Record.data['title'].as_string()+' '+text
        query = query.where(text.icontains(q.strip(), autoescape=True))
    rows = list(db.scalars(query.limit(limit+1).offset(offset)))
    items = []
    for item in rows[:limit]:
        if tab == 'comments':
            parent = db.get(Record, item.parent_id)
            items.append({'comment': comment_dto(db, item, user), 'post_id': parent.id, 'post_title': parent.data['title']})
        else:
            parent = item if tab == 'posts' else db.get(Record, item.parent_id)
            items.append({'post': demand_dto(db, parent, user)})
    return {'tab': tab, 'items': items, 'has_more': len(rows) > limit}


@router.get('/demands/{id}')
def demand(id: str, user=Depends(optional_user), db=Depends(get_db)):
    return demand_dto(db, content(db, DEMAND, id, user), user)


@router.put('/demands/{id}')
def edit_demand(id: str, body: DemandEdit, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    return demand_dto(db, edit_owned_content(db, DEMAND, id, body, user), user)


@router.delete('/demands/{id}')
def delete_demand(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = db.get(Record, id)
    if not item or item.kind != DEMAND or item.owner_id != user.id:
        raise HTTPException(404, '본인 게시물을 찾을 수 없습니다.')
    # Author deletion also removes replies, interest and associated report text.
    children = select(Record.id).where(Record.kind == COMMENT, Record.parent_id == id)
    db.execute(delete(Record).where(Record.kind == REPORT, Record.parent_id.in_(children)))
    db.execute(delete(Record).where(Record.kind.in_([COMMENT, INTEREST, REPORT, 'growth_exposure']), Record.parent_id == id))
    db.delete(item)
    db.commit()
    return {'message': '수요 제안을 삭제했습니다.'}


@router.put('/demands/{id}/interest')
def add_interest(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = content(db, DEMAND, id, user)
    if post_type(item) != 'demand':
        raise HTTPException(422, '수요 글에만 관심을 등록할 수 있습니다.')
    created = put_unique(db, INTEREST, user.id, id, commit=False)
    if created:
        from .growth import confirm_save
        confirm_save(db, user, id, conversion='interested')
    db.commit()
    return demand_dto(db, item, user)


@router.delete('/demands/{id}/interest')
def remove_interest(id: str, user=Depends(current_user), db=Depends(get_db)):
    item = content(db, DEMAND, id, user)
    db.execute(delete(Record).where(Record.kind == INTEREST, Record.parent_id == id, Record.owner_id == user.id))
    db.commit()
    return demand_dto(db, item, user)


@router.get('/demands/{id}/comments')
def comments(id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
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


@router.put('/comments/{id}')
def edit_comment(id: str, body: CommentEdit, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    return comment_dto(db, edit_owned_content(db, COMMENT, id, body, user), user)


@router.post('/reports', status_code=201)
def report(body: ReportInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'report', subject=user.id)
    if body.target_type == 'user':
        target = db.get(User, body.target_id)
        if not target or target.deleted:
            raise HTTPException(404, '신고할 사용자를 찾을 수 없습니다.')
    elif body.target_type == 'groupbuy':
        from .groupbuys import content as groupbuy_content
        target = groupbuy_content(db,body.target_id,lock=True)
    else:
        # Reports remain available even when the reporter blocked the author.
        content(db, DEMAND if body.target_type == 'demand' else COMMENT, body.target_id)
    key = f'{user.id}:{body.target_type}:{body.target_id}'
    existing = db.scalar(select(Record).where(Record.kind == REPORT, Record.unique_key == key))
    if existing:
        return {'id': existing.id, 'message': '이미 접수한 신고입니다.'}
    item = Record(kind=REPORT, owner_id=user.id, parent_id=body.target_id, unique_key=key, data=body.model_dump())
    db.add(item)
    if body.target_type == 'groupbuy':
        target.data = {**target.data, 'review_state': 'needs_review', 'updated_at': timestamp(now())}
        target.revision += 1
        db.flush()
        # The operator receives the report through the existing restricted queue.
        # The sharer receives a safe notice without the reporter's identity/text.
        db.add(Record(kind=NOTICE, owner_id=target.owner_id, parent_id=item.id,
                      data={'target_type':'groupbuy','target_id':target.id,'action':'needs_review',
                            'reason':'공구 정보 제보가 접수되었습니다. 판매처 조건을 확인해 주세요.'}))
    db.commit()
    return {'id': item.id, 'message': '신고가 접수되었습니다.'}


def report_dto(db, item):
    target_type = item.data['target_type']
    target = db.get(User if target_type == 'user' else Record, item.parent_id)
    preview, demand_id, nickname = '', None, ''
    if target_type == 'groupbuy':
        from .groupbuys import GROUPBUY, dto as groupbuy_dto
        groupbuy = groupbuy_dto(db,target) if target and target.kind == GROUPBUY else None
        return dict(id=item.id,groupbuy_id=item.parent_id,groupbuy=groupbuy,
            target_type='groupbuy',target_id=item.parent_id,target_preview=((target.data.get('title','')+' '+target.data.get('body','')).strip()[:300] if groupbuy else ''),
            author_nickname=groupbuy['author']['nickname'] if groupbuy else '',demand_id=None,
            reason=item.data['reason'],status=item.status,created_at=timestamp(item.created),
            resolved_at=item.data.get('resolved_at'),resolved_by=item.data.get('resolved_by'),
            action=item.data.get('action'),note=item.data.get('note',''))
    if target_type == 'user' and target and not target.deleted:
        preview = nickname = target.nickname
    elif target and target.kind in (DEMAND, COMMENT):
        preview = (target.data.get('title', '')+' '+target.data.get('body', '')).strip()[:300]
        demand_id = target.id if target.kind == DEMAND else target.parent_id
        account = db.get(User, target.owner_id)
        nickname = account.nickname if account and not account.deleted else '탈퇴한 회원'
    return dict(target_preview=preview, demand_id=demand_id, author_nickname=nickname, id=item.id, target_type=item.data['target_type'], target_id=item.parent_id,
                reason=item.data['reason'], status=item.status, created_at=timestamp(item.created),
                note=item.data.get('note', ''), action=item.data.get('action'),
                resolved_at=item.data.get('resolved_at'), resolved_by=item.data.get('resolved_by'))


@router.get('/admin/reports')
def admin_reports(q: str = Query('', max_length=100), start_date: str | None = None, end_date: str | None = None,
                  date_basis: Literal['received', 'action'] = 'received',
                  limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                  user=Depends(admin_user), db=Depends(get_db)):
    query = select(Record).where(Record.kind == REPORT)
    if date_basis == 'action':
        lower, upper = korea_date_bounds(start_date, end_date)
        action_at = Record.data['resolved_at'].as_string()
        query = query.where(action_at.is_not(None))
        if lower is not None:
            query = query.where(action_at >= timestamp(lower))
        if upper is not None:
            query = query.where(action_at < timestamp(upper))
    else:
        query = filter_created(query, start_date, end_date)
    if q.strip():
        query = query.where(Record.data['reason'].as_string().icontains(q.strip(), autoescape=True))
    return [report_dto(db, item) for item in db.scalars(query.order_by(Record.data['resolved_at'].as_string().desc() if date_basis == 'action' else Record.created.desc(), Record.id).limit(limit).offset(offset))]


@router.post('/admin/reports/{id}/resolve')
def resolve_report(id: str, body: ResolveInput, request: Request, user=Depends(admin_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    report = db.get(Record, id)
    if not report or report.kind != REPORT:
        raise HTTPException(404, '신고를 찾을 수 없습니다.')
    if report.status != 'active':
        raise HTTPException(409, '이미 처리된 신고입니다.')
    target_type = report.data['target_type']
    if target_type == 'groupbuy':
        from .groupbuys import resolve_existing
        return resolve_existing(db,report,body,user)
    if body.action == 'needs_review':
        raise HTTPException(422,'정보 확인 필요 표시는 공구 제보에만 적용할 수 있습니다.')
    target = db.get(User if target_type == 'user' else Record, report.parent_id)
    if not target or (target_type != 'user' and target.kind != (DEMAND if target_type == 'demand' else COMMENT)) or (target_type == 'user' and target.deleted):
        raise HTTPException(404, '신고 대상을 찾을 수 없습니다.')
    if target_type != 'user' and target.status == 'deleted' and body.action != 'dismiss':
        raise HTTPException(409, '이미 삭제된 콘텐츠입니다. 남은 신고는 기각으로 종료해 주세요.')
    if body.action in ('hide', 'remove'):
        if target_type == 'user':
            raise HTTPException(422, '사용자 신고는 이용정지 또는 기각으로 처리해 주세요.')
        target.status = 'hidden' if body.action == 'hide' else 'deleted'
        if body.action == 'remove':
            target.data = {}
            target.revision += 1
            if target_type == 'demand':
                # Delete the displayed content, retaining only IDs and audit linkage.
                db.execute(update(Record).where(Record.kind == COMMENT, Record.parent_id == target.id)
                           .values(status='deleted', data={}, revision=Record.revision+1))
    elif body.action == 'suspend':
        account = target if target_type == 'user' else db.get(User, target.owner_id)
        if not account or account.deleted or account.is_admin or account.id == user.id:
            raise HTTPException(422, '이 계정을 이용정지할 수 없습니다.')
        if not db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == account.id)):
            db.add(Record(kind='suspension', owner_id=account.id, unique_key=account.id, data={}))
        db.execute(delete(Token).where(Token.user_id == account.id))
    action_time = now()
    report.status = 'resolved'
    report.data = {**report.data, 'action': body.action, 'note': body.note,
                   'resolved_at': timestamp(action_time), 'resolved_by': user.id}
    db.add(Record(kind='audit', owner_id=user.id, parent_id=report.id, created=action_time,
                  data={'action': 'release-report-'+body.action, 'report_id': report.id,
                        'target_type': target_type, 'target_id': report.parent_id,
                        'reason': body.note, 'received_at': timestamp(report.created),
                        'acted_at': timestamp(action_time)}))
    if body.action in ('hide', 'remove', 'suspend'):
        account_id = target.id if target_type == 'user' else target.owner_id
        # Never copy removed text, reporter text or private moderator notes to a member notice.
        db.add(Record(kind=NOTICE, owner_id=account_id, parent_id=report.id, created=action_time,
                      data={'target_type': target_type, 'target_id': report.parent_id, 'action': body.action,
                            'reason': {'hide': '커뮤니티 운영정책에 따라 게시물이 숨김 처리되었습니다.',
                                       'remove': '커뮤니티 운영정책에 따라 콘텐츠가 삭제되었습니다.',
                                       'suspend': '커뮤니티 운영정책에 따라 계정 이용이 제한되었습니다.'}[body.action]}))
    db.commit()
    return report_dto(db, report)


def notice_dto(item):
    return {'id': item.id, 'report_id': item.parent_id, 'target_type': item.data['target_type'],
            'target_id': item.data['target_id'], 'action': item.data['action'], 'reason': item.data['reason'],
            'created_at': timestamp(item.created), 'acknowledged_at': item.data.get('acknowledged_at')}


@router.get('/notices')
def notices(start_date: str | None = None, end_date: str | None = None, pending_only: bool = False,
            limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
            user=Depends(current_user), db=Depends(get_db)):
    query = filter_created(select(Record).where(Record.kind == NOTICE, Record.owner_id == user.id), start_date, end_date)
    if pending_only:
        query=query.where(Record.data['acknowledged_at'].as_string().is_(None))
    rows = list(db.scalars(query.order_by(Record.created.desc(), Record.id).limit(limit+1).offset(offset)))
    return {'items': [notice_dto(item) for item in rows[:limit]], 'has_more': len(rows) > limit}


@router.post('/notices/{id}/ack')
def acknowledge_notice(id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'write', subject=user.id)
    item = db.scalar(select(Record).where(Record.kind == NOTICE, Record.id == id, Record.owner_id == user.id))
    if not item:
        raise HTTPException(404, '안내를 찾을 수 없습니다.')
    if not item.data.get('acknowledged_at'):
        item.data = {**item.data, 'acknowledged_at': timestamp(now())}
        db.commit()
    return notice_dto(item)


def delete_user_content(db, user_id, owned):
    """Erase linked content, reports and quoted moderator text without retention claims.

    Call before deleting owner/report metadata so even legacy audits linked only by
    report ID can be found. ``owned`` must include every account-owned record ID.
    """
    related_comments = list(db.scalars(select(Record.id).where(
        Record.kind.in_([COMMENT, 'question']), Record.parent_id.in_(owned))))
    targets = [user_id, *owned, *related_comments]
    reports = list(db.scalars(select(Record.id).where(Record.kind.in_([REPORT, 'report']),
        (Record.parent_id.in_(targets) | (Record.owner_id == user_id) |
         Record.id.in_(owned) | Record.data['target_id'].as_string().in_(targets)))))
    references = [*targets, *reports]
    linked_demands=list(db.scalars(select(Record).where(Record.kind==DEMAND,Record.data['groupbuy_id'].as_string().in_(owned))))
    for linked in linked_demands:
        linked.data={**linked.data,'groupbuy_id':None,'updated_at':timestamp(now())}
        linked.revision+=1
    # Current service has no monetary retention duty. Delete whole related audit
    # rows rather than retaining an actor/target link or a private quoted reason.
    db.execute(delete(Record).where(Record.kind == 'audit',
        ((Record.owner_id == user_id) | Record.parent_id.in_(references) |
         Record.data['target_id'].as_string().in_(targets) |
         Record.data['report_id'].as_string().in_(references) |
         Record.data['question_id'].as_string().in_(targets) |
         Record.data['campaign_id'].as_string().in_(targets) |
         (Record.data['user_id'].as_string() == user_id))))
    db.execute(delete(Record).where(Record.kind.in_([COMMENT, 'question', INTEREST, SAVE, REPORT,
                                                   'report', 'block', 'growth_exposure']),
                                   Record.parent_id.in_(targets)))
    db.execute(delete(Record).where(Record.kind.in_([REPORT, 'report']), Record.id.in_(reports)))
    db.execute(delete(Record).where(Record.kind == NOTICE,
        (Record.data['target_id'].as_string().in_(targets) | Record.parent_id.in_(reports))))
