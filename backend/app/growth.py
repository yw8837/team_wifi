"""Opt-in first-party measurement. Reports are account cohorts, never purchase scores."""
import math
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import delete, or_, select

from .db import Record, User, get_db, now, uid
from .schemas import Strict
from .security import admin_user, current_user
from .release import public_only

CONSENT = 'growth_consent'
EXPOSURE = 'growth_exposure'
RETENTION = 30 * 86400
router = APIRouter(prefix='/api/release/measurement', dependencies=[Depends(public_only)])


class Consent(Strict):
    enabled: bool


class Event(Strict):
    offer_id: str = Field(default='', max_length=36)
    demand_id: str = Field(default='', max_length=36)
    groupbuy_id: str = Field(default='', max_length=36)
    placement: Literal['catalog', 'personal', 'detail', 'demand_list', 'demand_detail', 'companion', 'advisor', 'compare_cta', 'groupbuy_list', 'groupbuy_detail']
    channel: Literal['web', 'android']
    action: Literal['view', 'detail', 'source', 'calculator', 'save', 'interest']
    visible_ms: int = Field(ge=0, le=600000)

    @model_validator(mode='after')
    def target(self):
        demand = self.placement.startswith('demand_')
        groupbuy = self.placement.startswith('groupbuy_')
        if sum(bool(value) for value in (self.offer_id,self.demand_id,self.groupbuy_id))!=1 or (demand and not self.demand_id) or (groupbuy and not self.groupbuy_id) or (not demand and not groupbuy and not self.offer_id):
            raise ValueError('A single matching target is required.')
        return self


def opted_in(db, user):
    return bool(db.scalar(select(Record.id).where(Record.kind == CONSENT, Record.owner_id == user.id))) and not user.is_admin


@router.get('/consent')
def consent(user=Depends(current_user), db=Depends(get_db)):
    return {'enabled': opted_in(db, user), 'eligible': not user.is_admin}


@router.put('/consent')
def set_consent(body: Consent, user=Depends(current_user), db=Depends(get_db)):
    if body.enabled and not user.is_admin:
        if not opted_in(db, user):
            db.add(Record(kind=CONSENT, owner_id=user.id, unique_key=user.id, data={'version': '20261102'}))
    else:
        db.execute(delete(Record).where(Record.owner_id == user.id, Record.kind.in_([CONSENT, EXPOSURE])))
    db.commit()
    return {'enabled': body.enabled and not user.is_admin, 'eligible': not user.is_admin}


def purge(db):
    db.execute(delete(Record).where(Record.kind == EXPOSURE, Record.created < now()-RETENTION))


@router.post('/events', status_code=202)
def event(body: Event, user=Depends(current_user), db=Depends(get_db)):
    from .release import offer_by_id, content, DEMAND
    if not opted_in(db, user):
        return {'recorded': False}
    if body.groupbuy_id:
        from .groupbuys import content as groupbuy_content
        groupbuy_content(db,body.groupbuy_id,user)
    elif body.demand_id:
        content(db, DEMAND, body.demand_id, user)
    else:
        offer_by_id(body.offer_id)
    target = body.groupbuy_id or body.demand_id or body.offer_id
    allowed = {'catalog': {'view', 'detail'}, 'personal': {'view', 'detail'}, 'detail': {'view', 'source', 'calculator', 'save'},
               'companion': {'view', 'detail'}, 'advisor': {'view', 'detail'}, 'compare_cta': {'view', 'source', 'calculator'},
               'demand_list': {'view', 'detail'}, 'demand_detail': {'view', 'interest'},
               'groupbuy_list': {'view','detail'},'groupbuy_detail': {'view','source'}}
    if body.action not in allowed[body.placement]:
        raise HTTPException(422, '이 위치에서 제공하지 않는 행동입니다.')
    purge(db)
    # KST calendar day; one unit per account/item/placement/platform/day.
    day = (now()+9*3600)//86400
    key = f'{user.id}:{target}:{body.placement}:{body.channel}:{day}'
    row = db.scalar(select(Record).where(Record.kind == EXPOSURE, Record.unique_key == key))
    if body.action == 'view':
        if body.visible_ms < 1000:
            return {'recorded': False}
        if not row:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
            db.execute(insert(Record).values(id=uid(), kind=EXPOSURE, unique_key=key, owner_id=user.id,
                parent_id=target, created=now(), data={'placement': body.placement, 'channel': body.channel, 'clicks': {}, 'saved': False, 'interested': False})
                .on_conflict_do_nothing(index_elements=['kind', 'unique_key']))
    else:
        if not row or row.created < now()-86400:
            return {'recorded': False}
        data = dict(row.data)
        data['clicks'] = {**data['clicks'], body.action: now()}
        row.data = data
    db.commit()
    return {'recorded': True}


def confirm_save(db, user, offer_id, conversion='saved'):
    """Called by the save mutation in the same transaction, only on a new save.

    A click is not a conversion. Attribute to the latest measured click in 30min.
    Consent withdrawal deletes these rows; there is no retrospective backfill.
    """
    if not opted_in(db, user):
        return
    rows = list(db.scalars(select(Record).where(Record.kind == EXPOSURE, Record.owner_id == user.id,
                                               Record.parent_id == offer_id, Record.created >= now()-86400)))
    candidates = [(max(r.data.get('clicks', {}).values(), default=0), r) for r in rows]
    candidates = [(stamp, row) for stamp, row in candidates if stamp >= now()-1800]
    if candidates:
        _, row = max(candidates, key=lambda pair: (pair[0], pair[1].data.get('placement') in ('detail', 'demand_detail'), pair[1].id))
        row.data = {**row.data, conversion: True}


def wilson(successes, count):
    if not count:
        return None
    p, z = successes/count, 1.95996398454
    denominator = 1+z*z/count
    center = (p+z*z/(2*count))/denominator
    margin = z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/denominator
    return [max(0, center-margin), min(1, center+margin)]


@router.get('/report')
def report(user=Depends(admin_user), db=Depends(get_db)):
    purge(db)
    # Deleted/suspended/admin accounts never contribute to the operational report.
    suspension = select(Record.owner_id).where(Record.kind == 'suspension')
    from . import release
    from .groupbuys import visible_query as visible_groupbuys
    public_groupbuys=visible_groupbuys().with_only_columns(Record.id)
    public_demands=release.visible_query(release.DEMAND,None).with_only_columns(Record.id).order_by(None)
    groupbuy_places=['groupbuy_list','groupbuy_detail'];demand_places=['demand_list','demand_detail']
    visible_target=or_(
        Record.data['placement'].as_string().in_(groupbuy_places)&Record.parent_id.in_(public_groupbuys),
        Record.data['placement'].as_string().in_(demand_places)&Record.parent_id.in_(public_demands),
        Record.data['placement'].as_string().not_in(groupbuy_places+demand_places))
    rows = db.scalars(select(Record).join(User, User.id == Record.owner_id).where(
        Record.kind == EXPOSURE, User.deleted.is_(False), User.is_admin.is_(False),
        ~User.id.in_(suspension), visible_target))
    groups = defaultdict(lambda: {'exposed': set(), 'clicked': set(), 'saved': set(), 'interested': set(), 'actions': defaultdict(set)})
    for row in rows:
        data = row.data
        group = groups[(data['placement'], data['channel'])]
        group['exposed'].add(row.owner_id)
        if data['clicks']:
            group['clicked'].add(row.owner_id)
        if data['saved']:
            group['saved'].add(row.owner_id)
        if data.get('interested'):
            group['interested'].add(row.owner_id)
        for action in data['clicks']:
            group['actions'][action].add(row.owner_id)
    result = []
    for (placement, channel), group in sorted(groups.items()):
        n, clicks, saves = (len(group[k]) for k in ('exposed', 'clicked', 'saved'))
        # Suppress small nonzero numerators too: no leakage by percentage or interval.
        visible_clicks = n >= 5 and (clicks == 0 or clicks >= 5)
        visible_saves = n >= 5 and (saves == 0 or saves >= 5)
        interests = len(group['interested'])
        visible_interests = n >= 5 and (interests == 0 or interests >= 5)
        sources=len(group['actions'].get('source',set()))
        visible_sources=n>=5 and (sources==0 or sources>=5)
        interval = wilson(clicks, n) if visible_clicks else None
        enough = n >= 200 and clicks >= 20 and n-clicks >= 20
        result.append({'placement': placement, 'channel': channel, 'accounts': n if n >= 5 else None,
            'clicked_accounts': clicks if visible_clicks else None, 'saved_accounts': saves if visible_saves else None,
            'source_accounts':sources if visible_sources else None,'source_rate':sources/n if visible_sources else None,
            'ctr': clicks/n if visible_clicks else None, 'ctr_95_interval': interval,
            'save_rate': saves/n if visible_saves else None,
            'interested_accounts': interests if visible_interests else None, 'interest_rate': interests/n if visible_interests else None,
            'actions': {action: len(accounts) if len(accounts) >= 5 else None for action, accounts in group['actions'].items()},
            'decision': '관찰 자료 확보 · 위치·관심 차이를 통제한 별도 실험 후 문구를 결정하세요.' if enough else '표본 수집 중 · 효과 판단 보류'})
    db.commit()
    return {'window_days': 30, 'rows': result, 'minimum_cohort': 5,
            'definition': '최근 30일·동의한 일반 회원. 위치·플랫폼별 노출 계정 중 클릭한 계정 비율. 계정은 각 집단에서 한 번만 집계.',
            'limitations': '50% 이상 1초 연속 보임을 클라이언트가 보고합니다. 자동화·보고 조작을 완전히 검증할 수 없습니다. 비동의·비회원은 제외되며 전체 이용자를 대표하지 않습니다. 판매처 이동은 구매 완료가 아닙니다. 위치별 집단은 중복될 수 있어 합산할 수 없습니다. 관찰 구간은 A/B 검정이나 인과 효과가 아닙니다.',
            'search': '검색 노출·CTR은 Search Console 등 검색 도구의 별도 자료가 필요합니다. AI 답변 노출·인용은 이 서비스 클릭 로그로 측정할 수 없습니다.'}
