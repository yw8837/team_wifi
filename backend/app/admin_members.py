"""Operator member controls with fresh proof, revision checks and private audit."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import delete, exists, or_, select

from .community_dates import filter_created
from .db import Record, Token, User, get_db, now
from .release import timestamp
from .schemas import Strict
from .security import admin_user, passwords, throttle, token_digest

router = APIRouter(prefix='/api/release/admin/members', tags=['member administration'])
CONTROL = 'member_control'
AUDIT = 'member_change'


class AccessInput(Strict):
    revision: int = Field(ge=0)
    is_admin: bool
    suspended: bool
    reason: str = Field(min_length=2, max_length=1000)
    password: str = Field(default='', max_length=128)
    reauth_token: str = Field(default='', max_length=256)

    @field_validator('reason')
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('변경 사유를 입력해 주세요.')
        return value


def states(db, members):
    ids = [member.id for member in members]
    controls, suspended = {}, set()
    if ids:
        for record in db.scalars(select(Record).where(Record.owner_id.in_(ids), Record.kind.in_([CONTROL, 'suspension']))):
            if record.kind == CONTROL:
                controls[record.owner_id] = record
            else:
                suspended.add(record.owner_id)
    return controls, suspended


def member_dto(member, controls, suspended):
    control = controls.get(member.id)
    return dict(id=member.id, nickname=member.nickname, is_admin=member.is_admin,
                suspended=member.id in suspended, created_at=timestamp(member.created),
                updated_at=control.data.get('updated_at') if control else None,
                revision=control.revision if control else 0)


@router.get('')
def list_members(q: str = Query('', max_length=100), start_date: str | None = None, end_date: str | None = None,
                 role: Literal['all', 'member', 'operator'] = 'all',
                 status: Literal['all', 'active', 'suspended'] = 'all',
                 limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                 actor=Depends(admin_user), db=Depends(get_db)):
    query = select(User).where(User.deleted.is_(False))
    if q.strip():
        query = query.where(or_(User.nickname.icontains(q.strip(), autoescape=True),
                                User.id.icontains(q.strip(), autoescape=True)))
    if role != 'all':
        query = query.where(User.is_admin.is_(role == 'operator'))
    suspension = exists(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == User.id))
    if status != 'all':
        query = query.where(suspension if status == 'suspended' else ~suspension)
    query = filter_created(query, start_date, end_date, User.created)
    rows = list(db.scalars(query.order_by(User.created.desc(), User.id).limit(limit+1).offset(offset)))
    controls, suspended = states(db, rows[:limit])
    return {'items': [member_dto(member, controls, suspended) for member in rows[:limit]], 'has_more': len(rows)>limit}


def find_member(db, identifier, lock=False):
    query = select(User).where(User.id == identifier, User.deleted.is_(False))
    member = db.scalar(query.with_for_update() if lock else query)
    if not member:
        raise HTTPException(404, '회원을 찾을 수 없습니다.')
    return member


@router.get('/{id}')
def detail(id: str, history_limit: int = Query(20, ge=1, le=100), history_offset: int = Query(0, ge=0, le=10000),
           history_start_date: str | None = None, history_end_date: str | None = None,
           actor=Depends(admin_user), db=Depends(get_db)):
    member = find_member(db, id)
    controls, suspended = states(db, [member])
    query = filter_created(select(Record).where(Record.kind == AUDIT, Record.parent_id == id),
                           history_start_date, history_end_date)
    rows = list(db.scalars(query.order_by(Record.created.desc(), Record.id).limit(history_limit+1).offset(history_offset)))
    actor_ids = {record.owner_id for record in rows[:history_limit]}
    names = {user.id: user.nickname for user in db.scalars(select(User).where(User.id.in_(actor_ids)))}
    history = [dict(id=record.id, actor_id=record.owner_id, actor_nickname=names.get(record.owner_id, '탈퇴한 운영자'),
                    created_at=timestamp(record.created), reason=record.data['reason'],
                    before=record.data['before'], after=record.data['after']) for record in rows[:history_limit]]
    return {'member': member_dto(member, controls, suspended), 'history': history, 'history_has_more': len(rows)>history_limit}


@router.put('/{id}')
def change_access(id: str, body: AccessInput, request: Request, actor=Depends(admin_user), db=Depends(get_db)):
    throttle(request, 'write', subject=actor.id)
    proof = db.get(Token, token_digest(body.reauth_token)) if body.reauth_token else None
    valid_proof = bool(proof and proof.kind == 'social_reauth' and proof.user_id == actor.id and proof.expires > now())
    if not valid_proof and not passwords.verify(body.password, actor.password_hash):
        raise HTTPException(403, '본인 비밀번호 또는 연결된 소셜 계정의 재인증이 필요합니다.')
    member = find_member(db, id, lock=True)
    if member.id == actor.id:
        raise HTTPException(422, '본인의 운영 권한이나 이용 상태는 여기서 변경할 수 없습니다.')
    controls, suspended = states(db, [member])
    control = controls.get(member.id)
    if body.revision != (control.revision if control else 0):
        raise HTTPException(409, '다른 운영자가 변경했습니다. 새로고침 후 다시 확인해 주세요.')
    before = {'is_admin': member.is_admin, 'suspended': member.id in suspended}
    after = {'is_admin': body.is_admin, 'suspended': body.suspended}
    if before == after:
        raise HTTPException(422, '변경할 역할이나 이용 상태를 선택해 주세요.')
    if body.suspended and (member.is_admin or body.is_admin):
        raise HTTPException(422, '운영자 계정은 정지할 수 없습니다. 일반 회원으로 변경한 뒤 처리해 주세요.')
    if body.is_admin and member.id in suspended:
        raise HTTPException(422, '이용정지를 해제한 뒤 운영 권한을 부여해 주세요.')
    if valid_proof:
        db.delete(proof)
    member.is_admin = body.is_admin
    existing_suspension = db.scalar(select(Record).where(Record.kind == 'suspension', Record.owner_id == member.id))
    if body.suspended and not existing_suspension:
        db.add(Record(kind='suspension', owner_id=member.id, unique_key=member.id, data={}))
    elif not body.suspended and existing_suspension:
        db.delete(existing_suspension)
    changed_at = now()
    if control:
        control.revision += 1
        control.data = {'updated_at': timestamp(changed_at)}
    else:
        control = Record(kind=CONTROL, owner_id=member.id, unique_key=member.id,
                         data={'updated_at': timestamp(changed_at)})
        db.add(control)
    db.add(Record(kind=AUDIT, owner_id=actor.id, parent_id=member.id, created=changed_at,
                  data={'reason': body.reason, 'before': before, 'after': after}))
    # Require fresh login after privilege/status changes; do not discard recovery codes.
    db.execute(delete(Token).where(Token.user_id == member.id, Token.kind.in_(['session', 'social_reauth'])))
    db.commit()
    return {'member': member_dto(member, {member.id: control}, {member.id} if body.suspended else set()),
            'message': '회원의 역할과 이용 상태를 변경했습니다. 대상 회원은 다시 로그인해야 합니다.'}
