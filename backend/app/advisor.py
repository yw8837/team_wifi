"""Catalog-grounded selection and first-party associations, without transferred scores."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import delete, func, select

from . import discovery, release
from .db import Record, User, get_db, now, uid
from .security import current_user
from .catalog_content import active, guide
from .schemas import Strict

STATE = 'release_advisor'
router = APIRouter(prefix='/api/release', dependencies=[Depends(release.public_only)])


class Choices(discovery.Preferences):
    purpose: Literal['own', 'gift'] = 'own'
    budget_max: int | None = Field(default=None, ge=0, le=10000000, strict=True)


class Suggestion(release.Offer):
    saved: bool = False
    reason: str
    accounts: int | None = None


class Selection(Strict):
    choices: Choices
    items: list[Suggestion]
    unknown_price_count: int
    focus: str
    basis: Literal['declared_choices']
    note: str


class SavedSelection(Selection):
    has_saved_choices: bool


class Companions(Strict):
    items: list[Suggestion]
    basis: Literal['co_save', 'category', 'expired']
    minimum_cohort: int


def selection(entries, choices):
    candidates = [entry for entry in entries if active(entry) and
                  (not choices.categories or entry['category'] in choices.categories)]
    unknown = 0
    if choices.budget_max is not None:
        unknown = sum(entry['price'] is None or entry['shipping_fee'] is None for entry in candidates)
        candidates = [entry for entry in candidates if entry['price'] is not None and entry['shipping_fee'] is not None
                      and entry['price'] + entry['shipping_fee'] <= choices.budget_max]
    reason = '직접 고른 관심 분야' if choices.categories else '공식 출처가 있는 육아템 목록'
    focus = discovery.FOCUS[choices.priority]
    if choices.purpose == 'gift':
        focus += ' 선물은 받는 분이 이미 가진 구성과 교환 가능 여부를 먼저 확인하세요.'
    return {'choices': choices.model_dump(), 'items': [{**entry, 'saved': False, 'reason': reason} for entry in candidates[:6]],
            'unknown_price_count': unknown, 'focus': focus, 'basis': 'declared_choices',
            'note': '선택한 조건으로 좁힌 공식 참고 목록입니다. 구매 확률·최저가·연령 적합성을 예측하지 않습니다.'}


@router.post('/advisor/preview', response_model=Selection)
def preview(body: Choices):
    # No account, free text, behavioral tracking, or persistence for guest previews.
    return selection(release.catalog(), body)


@router.get('/advisor', response_model=SavedSelection)
def read_choices(user=Depends(current_user), db=Depends(get_db)):
    row = db.scalar(select(Record).where(Record.kind == STATE, Record.owner_id == user.id))
    choices = Choices.model_validate(row.data) if row else Choices()
    return {**selection(release.catalog(), choices), 'has_saved_choices': row is not None}


@router.put('/advisor', response_model=SavedSelection)
def save_choices(body: Choices, user=Depends(current_user), db=Depends(get_db)):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    # Validate the current catalog before committing changes.
    result = selection(release.catalog(), body)
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(Record).values(id=uid(), kind=STATE, owner_id=user.id, unique_key=user.id,
        data=body.model_dump(), status='active', created=now()).on_conflict_do_update(
        index_elements=['kind', 'unique_key'], set_={'data': body.model_dump()}))
    db.commit()
    return {**result, 'has_saved_choices': True}


@router.delete('/advisor')
def clear_choices(user=Depends(current_user), db=Depends(get_db)):
    db.execute(delete(Record).where(Record.kind == STATE, Record.owner_id == user.id))
    db.commit()
    return {'message': '조건 찾기를 끝내고 저장한 조건을 지웠습니다.'}


@router.get('/offers/{id}/guide')
def public_guide(id: str):
    return guide(release.offer_by_id(id))


@router.get('/offers/{id}/companions', response_model=Companions)
def companions(id: str, db=Depends(get_db)):
    entry = release.offer_by_id(id)
    entries = {item['id']: item for item in release.catalog() if active(item)}
    if id not in entries:
        return {'items': [], 'basis': 'expired', 'minimum_cohort': discovery.MIN_COHORT}
    # Only real active non-admin accounts; duplicated rows count once.
    saves = release.visible_query(release.SAVE, None, Record.parent_id.in_(entries),
        Record.owner_id.in_(select(User.id).where(User.is_admin.is_(False)))).order_by(None).subquery()
    a, b = saves.alias('a'), saves.alias('b')
    counts = (select(b.c.parent_id, func.count(func.distinct(a.c.owner_id)).label('n'))
        .join(b, a.c.owner_id == b.c.owner_id).where(a.c.parent_id == id, b.c.parent_id != id)
        .group_by(b.c.parent_id).having(func.count(func.distinct(a.c.owner_id)) >= discovery.MIN_COHORT)
        .order_by(func.count(func.distinct(a.c.owner_id)).desc(), b.c.parent_id).limit(3))
    pairs = list(db.execute(counts))
    if pairs:
        items = [{**entries[other], 'saved': False, 'accounts': count,
                  'reason': f'서로 다른 {count}계정이 두 목록을 함께 저장했어요.'} for other, count in pairs]
        basis = 'co_save'
    else:
        items = [{**item, 'saved': False, 'accounts': None, 'reason': '같은 분야의 공식 목록이에요.'}
                 for item in entries.values() if item['id'] != id and item['category'] == entry['category']][:3]
        basis = 'category'
    return {'items': items, 'basis': basis, 'minimum_cohort': discovery.MIN_COHORT}
