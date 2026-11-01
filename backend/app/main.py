"""Development marketplace API. All examples are demo transactions, never real payments."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from html import escape
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as PoolTimeout

from .db import RUNTIME, Record, Token, User, get_db, init_db, now
from .security import (DUMMY, admin_user, approved_seller, current_user, issue_token,
                       optional_user, passwords, profile, throttle, token_digest,
                       beta_write_guard, charge_claimed_account)
from . import schemas as S
from . import config, beta
from .http_safety import BodyLimitMiddleware


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title='모두의 육아 - 육아템 공동구매,핫딜 API', version='0.2.0', lifespan=lifespan,
              docs_url=None if config.BETA else '/docs', redoc_url=None if config.BETA else '/redoc',
              openapi_url=None if config.BETA else '/openapi.json')
app.add_middleware(BodyLimitMiddleware)
if config.BETA:
    from urllib.parse import urlsplit
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(config.PUBLIC_ORIGIN).hostname, 'localhost', '127.0.0.1'])


@app.middleware('http')
async def security_headers(request, call_next):
    if config.BETA and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        from starlette.concurrency import run_in_threadpool
        try:
            await run_in_threadpool(beta_write_guard, request)
        except HTTPException as error:
            return JSONResponse({'detail': error.detail}, status_code=error.status_code, headers=error.headers)
        except (OperationalError, PoolTimeout):
            return JSONResponse({'detail': '저장소가 혼잡합니다. 잠시 후 다시 시도해 주세요.'}, status_code=503,
                                headers={'Retry-After': '10'})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(status_code=409, content={'detail': '이미 처리된 요청입니다. 새로고침 후 확인해 주세요.'})


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Pydantic's default errors include the original input (including passwords).
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']} for error in exc.errors()]})


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_conflict(request, exc):
    if getattr(getattr(exc, 'orig', None), 'sqlstate', '') in ('40001', '40P01'):
        return JSONResponse(status_code=409, content={'detail': '다른 요청으로 상태가 변경되었습니다. 새로고침 후 다시 확인해 주세요.'})
    return JSONResponse(status_code=503, content={'detail': '저장소에 일시적으로 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.'})


def fail(message, status=409):
    raise HTTPException(status, message)


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def record(db, kind, id, owner=None):
    value = db.get(Record, id)
    if not value or value.kind != kind or (owner is not None and value.owner_id != owner):
        fail('항목을 찾을 수 없습니다.', 404)
    return value


def rows(db, kind, *where):
    return list(db.scalars(select(Record).where(Record.kind == kind, *where).order_by(Record.created.desc(), Record.id)))


def audit(db, user, action, target):
    db.add(Record(kind='audit', owner_id=user.id, parent_id=target, data={'action': action}))


def public_campaign(db, c, user=None):
    seller = db.get(User, c.owner_id)
    if c.status not in ('active', 'ended') or not c.data.get('published') or not seller or seller.seller_status != 'approved' or seller.deleted:
        if not user or (not user.is_admin and user.id != c.owner_id):
            fail('공개된 공동구매가 아닙니다.', 404)
    return c


def campaign_dto(db, c, user=None):
    d = c.data
    brand = db.get(Record, c.parent_id) if c.parent_id else None
    seller = db.get(User, c.owner_id)
    application = db.scalar(select(Record).where(Record.kind == 'application', Record.owner_id == c.owner_id))
    policies = application.data if application else {}
    saved = bool(user and db.scalar(select(Record.id).where(Record.kind == 'saved', Record.unique_key == f'{user.id}:{c.id}')))
    closed = c.status == 'ended' or c.ends <= now()
    reached = c.counter >= d['minimum_quantity']
    recruitment = ('closed_met' if reached else 'closed_shortfall') if closed else ('minimum_met' if reached else 'collecting')
    if not d.get('published') or c.status == 'hidden':
        recruitment = 'cancelled'
    return dict(id=c.id, brand_id=c.parent_id, title=d['title'], description=d['description'], category=d['category'],
                kind='group_buy', price=d['price'], shipping_fee=d['shipping_fee'], unit=d['unit'],
                minimum_quantity=d['minimum_quantity'], stock=c.capacity, reserved_quantity=c.counter,
                ends_at=iso(c.ends), status='ended' if c.status == 'active' and c.ends <= now() else c.status,
                revision=c.revision, is_demo=True, brand_name=brand.data['name'] if brand else '',
                seller_name=seller.nickname if seller and not seller.deleted else '탈퇴한 판매자',
                shipping_policy=policies.get('shipping_policy', ''), refund_policy=policies.get('refund_policy', ''),
                source_url=None, verified_at=iso(c.created), saved=saved,
                recruitment_status=recruitment, remaining_quantity=max(0, c.capacity-c.counter))


def brand_dto(b):
    return dict(id=b.id, name=b.data['name'], description=b.data.get('description', ''), logo_text=b.data['name'][:2])


def available_campaigns(db, user=None, q='', category='', brand_id=''):
    result = []
    for c in rows(db, 'campaign', Record.status.in_(['active', 'ended'])):
        seller = db.get(User, c.owner_id)
        if not c.data.get('published') or not seller or seller.deleted or seller.seller_status != 'approved':
            continue
        if category and c.data['category'] != category:
            continue
        if brand_id and c.parent_id != brand_id:
            continue
        if q and q.casefold() not in (c.data['title'] + c.data['description']).casefold():
            continue
        result.append(campaign_dto(db, c, user))
    return result


def reservation_dto(r):
    return dict(id=r.id, campaign_id=r.parent_id, title=r.data['title'], quantity=r.data['quantity'], status=r.status, created_at=iso(r.created))


def application_dto(db, user):
    a = db.scalar(select(Record).where(Record.kind == 'application', Record.owner_id == user.id))
    return dict(status=user.seller_status or 'draft', review_note=a.data.get('review_note', '') if a else '',
                fields={k: v for k, v in (a.data.items() if a else []) if k in S.Application.model_fields})


def valid_business_number(value):
    digits = re.sub(r'[- ]', '', value)
    if not re.fullmatch(r'\d{10}', digits) or len(set(digits)) == 1:
        return False
    n = list(map(int, digits))
    total = sum(a*b for a, b in zip(n[:9], [1, 3, 7, 1, 3, 7, 1, 3, 5])) + (n[8]*5)//10
    return (10-total % 10) % 10 == n[9]


def withdraw_record(db, r):
    changed = db.execute(update(Record).where(Record.id == r.id, Record.status == 'active', Record.revision == r.revision).values(status='withdrawn', revision=Record.revision+1).execution_options(synchronize_session=False)).rowcount
    if changed:
        db.execute(update(Record).where(Record.id == r.parent_id, Record.counter >= r.data['quantity']).values(counter=Record.counter-r.data['quantity']))
    elif r.status == 'active':
        fail('참여 상태가 변경되었습니다. 새로고침 후 다시 시도해 주세요.')


@app.get('/api/health')
def health(db=Depends(get_db)):
    from sqlalchemy import text
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'mode': 'closed-beta' if config.BETA else 'local-demo', 'payments_enabled': False}


@app.get('/api/config')
def public_config():
    return {'mode': 'closed-beta' if config.BETA else 'local-demo', 'invite_required': config.BETA,
            'payments_enabled': False, 'seller_real_data_enabled': not config.BETA,
            'legal': {k: '/legal/'+k for k in ('privacy', 'terms', 'deletion', 'support')}}


@app.post('/api/auth/register', status_code=201)
def register(body: S.Register, request: Request, db=Depends(get_db)):
    if not config.BETA:
        throttle(request, 'register')
    if not body.terms_accepted or not body.privacy_accepted:
        fail('필수 약관과 개인정보 처리에 동의해 주세요.', 422)
    if config.BETA:
        if not body.adult_confirmed:
            fail('비공개 베타는 만 18세 이상만 참여할 수 있습니다.', 422)
        if body.marketing_opt_in:
            fail('베타 기간에는 마케팅 수신을 신청할 수 없습니다.', 422)
        beta.redeem_invite(db, body.invite_code)
    u = User(email=str(body.email).lower(), password_hash=passwords.hash(body.password), nickname=body.nickname,
             seller_status='draft' if body.track == 'seller' else None, marketing=body.marketing_opt_in)
    db.add(u)
    db.flush()
    audit(db, u, 'beta-terms-20261101-privacy-20261101-adult-accepted' if config.BETA else 'terms-v1-and-privacy-v1-accepted', u.id)
    raw = issue_token(db, u)
    recovery = beta.recovery_code(db, u) if config.BETA else None
    db.commit()
    result = dict(access_token=raw, token_type='bearer', user=profile(u))
    if recovery:
        result['recovery_code'] = recovery
    return result


@app.post('/api/auth/login')
def login(body: S.Login, request: Request, db=Depends(get_db)):
    charge_claimed_account(request, 'login', body.email)
    u = db.scalar(select(User).where(User.email == str(body.email).lower(), User.deleted.is_(False)))
    okay = passwords.verify(body.password, u.password_hash if u else DUMMY)
    if not u or not okay or db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == u.id)):
        fail('이메일 또는 비밀번호를 확인해 주세요.', 401)
    raw = issue_token(db, u)
    db.commit()
    return dict(access_token=raw, token_type='bearer', user=profile(u))


@app.get('/api/me')
def me(user=Depends(current_user)):
    return profile(user)


@app.post('/api/auth/logout')
def logout(request: Request, user=Depends(current_user), db=Depends(get_db)):
    db.execute(delete(Token).where(Token.digest == token_digest(request.headers['Authorization'][7:])))
    db.commit()
    return {'message': '로그아웃했습니다.'}


@app.post('/api/auth/reset-request')
def reset_request(body: S.ResetRequest, request: Request, db=Depends(get_db)):
    if not config.BETA:
        throttle(request, 'reset-request', 10)
    if config.BETA:
        return {'message': '베타에서는 가입 시 보관한 복구코드로 비밀번호를 변경할 수 있습니다. 이메일은 발송하지 않습니다.'}
    u = db.scalar(select(User).where(User.email == str(body.email).lower(), User.deleted.is_(False)))
    if u:
        db.execute(delete(Token).where(Token.user_id == u.id, Token.kind == 'reset'))
        raw = issue_token(db, u, 'reset', 900)
        db.commit()
        outbox = RUNTIME / 'outbox'
        outbox.mkdir(exist_ok=True)
        # Local developer delivery only. Never log the token or return it over this endpoint.
        (outbox / f'{u.id}.json').write_text(json.dumps({'token': raw, 'expires_at': iso(now()+900)}, ensure_ascii=False), encoding='utf-8')
    return {'message': '계정이 존재하면 로컬 개발 outbox에 복구 안내가 생성됩니다. 이메일은 발송되지 않습니다.'}


@app.post('/api/auth/reset')
def reset_password(body: S.Reset, request: Request, db=Depends(get_db)):
    if not config.BETA:
        throttle(request, 'reset', 10)
    if config.BETA:
        fail('베타 계정 복구 화면에서 복구코드를 입력해 주세요.', 400)
    t = db.get(Token, token_digest(body.token))
    if not t or t.kind != 'reset' or t.expires <= now():
        fail('복구 토큰이 만료되었거나 유효하지 않습니다.', 400)
    removed = db.execute(delete(Token).where(Token.digest == t.digest, Token.kind == 'reset', Token.expires > now())).rowcount
    if removed != 1:
        fail('이미 사용한 복구 토큰입니다.', 400)
    u = db.get(User, t.user_id)
    if u.deleted:
        fail('사용할 수 없는 계정입니다.', 400)
    u.password_hash = passwords.hash(body.password)
    db.execute(delete(Token).where(Token.user_id == u.id))
    db.commit()
    path = RUNTIME / 'outbox' / f'{u.id}.json'
    path.unlink(missing_ok=True)
    return {'message': '비밀번호를 변경했습니다. 다시 로그인해 주세요.'}


@app.post('/api/auth/recover')
def recover_account(body: S.Recover, request: Request, db=Depends(get_db)):
    charge_claimed_account(request, 'recover', body.email)
    u = db.scalar(select(User).where(User.email == str(body.email).lower(), User.deleted.is_(False)))
    digest = token_digest(body.recovery_code)
    token = db.get(Token, digest)
    if not u or not token or token.kind != 'recovery' or token.user_id != u.id or token.expires <= now():
        fail('이메일과 복구코드를 확인해 주세요.', 400)
    removed = db.execute(delete(Token).where(Token.digest == digest, Token.kind == 'recovery', Token.expires > now())).rowcount
    if removed != 1:
        fail('이미 사용한 복구코드입니다.', 400)
    u.password_hash = passwords.hash(body.password)
    db.execute(delete(Token).where(Token.user_id == u.id))
    raw = beta.recovery_code(db, u)
    db.commit()
    return {'message': '비밀번호가 변경되었습니다. 새 복구코드를 보관하고 다시 로그인해 주세요.', 'recovery_code': raw}


@app.post('/api/auth/recovery-code')
def renew_recovery_code(body: S.Password, request: Request, user=Depends(current_user), db=Depends(get_db)):
    if not config.BETA:
        fail('비공개 베타 전용 기능입니다.', 404)
    throttle(request, 'recovery-code', subject=user.id)
    if not passwords.verify(body.password, user.password_hash):
        fail('비밀번호를 확인해 주세요.', 403)
    raw = beta.recovery_code(db, user)
    db.commit()
    return {'message': '이전 복구코드는 폐기되었습니다. 새 코드를 안전하게 보관해 주세요.', 'recovery_code': raw}


@app.delete('/api/me')
def delete_account(body: S.Password, user=Depends(current_user), db=Depends(get_db)):
    if not passwords.verify(body.password, user.password_hash):
        fail('비밀번호를 확인해 주세요.', 403)
    live = rows(db, 'campaign', Record.owner_id == user.id, Record.status.in_(['active', 'pending']))
    if live and not config.BETA:
        fail('진행 중이거나 검토 중인 공구를 먼저 종료해 주세요.')
    if config.BETA:
        # Seller departure cannot leave other testers' unpaid reservations active.
        for campaign in rows(db, 'campaign', Record.owner_id == user.id):
            for reservation in rows(db, 'reservation', Record.parent_id == campaign.id, Record.status == 'active'):
                withdraw_record(db, reservation)
    for r in rows(db, 'reservation', Record.owner_id == user.id, Record.status == 'active'):
        withdraw_record(db, r)
    db.execute(delete(Token).where(Token.user_id == user.id))
    db.execute(delete(Record).where(Record.owner_id == user.id, Record.kind.in_(['application', 'saved', 'block'])))
    for b in rows(db, 'brand', Record.owner_id == user.id):
        b.status = 'hidden'
    for q in rows(db, 'question', Record.owner_id == user.id):
        q.status = 'hidden'
        q.data = {'body': '탈퇴한 사용자의 글입니다.'}
    if config.BETA:
        # No financial retention duty is invented for unpaid test records.
        # Remove authored free text and all per-user beta records after withdrawing.
        owned = list(db.scalars(select(Record.id).where(Record.owner_id == user.id)))
        # Test coupons from a deleted issuer become harmless expired entries in each
        # recipient's wallet. Their own history survives without deleted seller text.
        db.execute(update(Record).where(Record.kind == 'user_coupon', Record.parent_id.in_(owned))
                   .values(status='expired', data={'code': '폐기됨'}))
        for reservation in rows(db, 'reservation', Record.parent_id.in_(owned)):
            reservation.data = {**reservation.data, 'title': '종료된 시험 공구'}
        db.execute(delete(Record).where(Record.kind.in_(['report', 'saved']), Record.parent_id.in_(owned)))
        db.execute(delete(Record).where(Record.owner_id == user.id))
        db.execute(delete(Record).where(Record.kind == 'report', Record.parent_id == user.id))
        user.points, user.created = 0, 0
    user.email, user.nickname = f'deleted-{user.id}@invalid.local', '탈퇴한 회원'
    user.password_hash, user.deleted, user.marketing = passwords.hash(secrets.token_urlsafe(32)), True, False
    user.seller_status = 'suspended' if user.seller_status else None
    if not config.BETA:
        audit(db, user, 'account-deleted', user.id)
    db.commit()
    (RUNTIME / 'outbox' / f'{user.id}.json').unlink(missing_ok=True)
    return {'message': '회원탈퇴가 완료되었습니다.'}


@app.get('/api/campaigns')
def campaigns(q: str = '', category: str = '', brand_id: str = '', user=Depends(optional_user), db=Depends(get_db)):
    return {'items': available_campaigns(db, user, q[:200], category, brand_id)}


@app.get('/api/campaigns/{id}')
def campaign(id: str, user=Depends(optional_user), db=Depends(get_db)):
    return campaign_dto(db, public_campaign(db, record(db, 'campaign', id), user), user)


@app.get('/api/brands')
def brands(db=Depends(get_db)):
    return {'items': [brand_dto(b) for b in rows(db, 'brand', Record.status == 'active')
                      if (u := db.get(User, b.owner_id)) and not u.deleted and u.seller_status == 'approved']}


@app.get('/api/brands/{id}')
def brand(id: str, user=Depends(optional_user), db=Depends(get_db)):
    b = record(db, 'brand', id)
    u = db.get(User, b.owner_id)
    if b.status != 'active' or not u or u.deleted or u.seller_status != 'approved':
        fail('브랜드를 찾을 수 없습니다.', 404)
    return {'brand': brand_dto(b), 'campaigns': available_campaigns(db, user, brand_id=id)}


@app.get('/api/hotdeals')
def hotdeals(q: str = '', category: str = '', db=Depends(get_db)):
    result = []
    for h in rows(db, 'hotdeal', Record.status != 'hidden'):
        d = h.data
        if category and category != d['category'] or q and q[:200].casefold() not in d['title'].casefold():
            continue
        result.append(dict(id=h.id, **d, ends_at=iso(h.ends), verified_at=iso(h.created),
                           status='ended' if h.ends <= now() else ('stale' if h.created < now()-86400 else h.status), is_demo=True))
    return {'items': result}


@app.put('/api/saved/{id}')
def save(id: str, user=Depends(current_user), db=Depends(get_db)):
    public_campaign(db, record(db, 'campaign', id))
    key = f'{user.id}:{id}'
    if not db.scalar(select(Record.id).where(Record.kind == 'saved', Record.unique_key == key)):
        db.add(Record(kind='saved', owner_id=user.id, parent_id=id, unique_key=key))
        db.commit()
    return {'message': '저장했습니다.'}


@app.delete('/api/saved/{id}')
def unsave(id: str, user=Depends(current_user), db=Depends(get_db)):
    db.execute(delete(Record).where(Record.kind == 'saved', Record.unique_key == f'{user.id}:{id}'))
    db.commit()
    return {'message': '저장을 취소했습니다.'}


@app.get('/api/saved')
def saved(user=Depends(current_user), db=Depends(get_db)):
    ids = {r.parent_id for r in rows(db, 'saved', Record.owner_id == user.id)}
    return {'items': [c for c in available_campaigns(db, user) if c['id'] in ids]}


@app.post('/api/campaigns/{id}/reservations', status_code=201)
def reserve(id: str, body: S.ReservationInput, user=Depends(current_user), db=Depends(get_db)):
    c = public_campaign(db, record(db, 'campaign', id))
    if c.owner_id == user.id:
        fail('본인 공구에는 참여할 수 없습니다.', 403)
    key = f'{user.id}:{id}'
    old = db.scalar(select(Record).where(Record.kind == 'reservation', Record.unique_key == key))
    if old and old.status == 'active':
        fail('이미 참여 중입니다. 참여내역을 확인해 주세요.')
    changed = db.execute(update(Record).where(Record.id == id, Record.status == 'active', Record.ends > now(),
                         Record.revision == body.revision, Record.counter+body.quantity <= Record.capacity)
                         .values(counter=Record.counter+body.quantity)).rowcount
    if not changed:
        fail('마감·재고·조건이 변경되었습니다. 새로고침 후 확인해 주세요.')
    if old:
        activated = db.execute(update(Record).where(Record.id == old.id, Record.status == 'withdrawn').values(
            status='active', data={'title': c.data['title'], 'quantity': body.quantity}, revision=Record.revision+1, created=now())).rowcount
        if not activated:
            fail('참여 상태가 변경되었습니다. 새로고침해 주세요.')
        r = old
        db.refresh(r)
    else:
        r = Record(kind='reservation', owner_id=user.id, parent_id=id, unique_key=key, data={'title': c.data['title'], 'quantity': body.quantity})
        db.add(r)
    db.commit()
    return reservation_dto(r)


@app.get('/api/reservations')
def reservations(user=Depends(current_user), db=Depends(get_db)):
    return {'items': [reservation_dto(r) for r in rows(db, 'reservation', Record.owner_id == user.id)]}


@app.post('/api/reservations/{id}/withdraw')
def withdraw(id: str, user=Depends(current_user), db=Depends(get_db)):
    r = record(db, 'reservation', id, user.id)
    withdraw_record(db, r)
    db.commit()
    db.refresh(r)
    return reservation_dto(r)


@app.get('/api/seller/application')
def get_application(user=Depends(current_user), db=Depends(get_db)):
    return application_dto(db, user)


@app.put('/api/seller/application')
def put_application(body: S.Application, user=Depends(current_user), db=Depends(get_db)):
    if config.BETA:
        fail('베타에서는 실제 사업자 정보를 받지 않습니다. 가상 판매자 신청을 이용해 주세요.', 403)
    return save_application(body, user, db)


def save_application(body, user, db):
    editable = db.execute(update(User).where(User.id == user.id, (User.seller_status.is_(None) | User.seller_status.in_(['draft', 'needs_changes']))).values(marketing=User.marketing)).rowcount
    if editable != 1:
        fail('현재 상태에서는 신청서를 수정할 수 없습니다.')
    a = db.scalar(select(Record).where(Record.kind == 'application', Record.owner_id == user.id))
    if not a:
        a = Record(kind='application', owner_id=user.id, unique_key=user.id)
        db.add(a)
    a.data = {**body.model_dump(), 'review_note': a.data.get('review_note', '') if a.data else ''}
    user.seller_status = user.seller_status or 'draft'
    db.commit()
    return application_dto(db, user)


@app.post('/api/seller/application/beta')
def put_beta_application(body: S.BetaApplication, user=Depends(current_user), db=Depends(get_db)):
    if not config.BETA:
        fail('비공개 베타 전용 기능입니다.', 404)
    fields = beta.virtual_application(body.brand_name, body.brand_description, body.seller_terms_accepted)
    return save_application(S.Application(**fields), user, db)


@app.post('/api/seller/application/submit')
def submit_application(user=Depends(current_user), db=Depends(get_db)):
    if user.seller_status not in ('draft', 'needs_changes'):
        fail('제출할 수 있는 신청 상태가 아닙니다.')
    a = db.scalar(select(Record).where(Record.kind == 'application', Record.owner_id == user.id))
    if not a:
        fail('사업자 정보를 먼저 저장해 주세요.', 422)
    d = a.data
    required = ['business_name', 'business_number', 'representative', 'contact_phone', 'contact_email', 'business_address',
                'return_address', 'shipping_policy', 'refund_policy', 'brand_name', 'brand_description', 'seller_terms_accepted']
    if any(not d.get(k) for k in required) or not (d.get('commerce_number') or d.get('commerce_exempt_reason')):
        fail('필수 사업자 정보, 배송·반품 조건과 판매자 약관을 확인해 주세요.', 422)
    if not valid_business_number(d['business_number']):
        fail('사업자등록번호 형식을 확인해 주세요. 번호 형식 확인은 사업자 인증을 대신하지 않습니다.', 422)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', d['contact_email']) or not re.fullmatch(r'[0-9+() -]{8,30}', d['contact_phone']):
        fail('연락처 형식을 확인해 주세요.', 422)
    changed = db.execute(update(User).where(User.id == user.id, User.seller_status.in_(['draft', 'needs_changes'])).values(seller_status='pending')).rowcount
    if changed != 1:
        fail('신청 상태가 변경되었습니다.')
    audit(db, user, 'seller-application-submitted', a.id)
    db.commit()
    db.refresh(user)
    return application_dto(db, user)


@app.get('/api/seller/campaigns')
def seller_campaigns(user=Depends(current_user), db=Depends(get_db)):
    return {'items': [campaign_dto(db, c, user) for c in rows(db, 'campaign', Record.owner_id == user.id)]}


@app.post('/api/seller/campaigns', status_code=201)
def create_campaign(body: S.CampaignInput, user=Depends(approved_seller), db=Depends(get_db)):
    if body.minimum_quantity > body.stock or not now() < body.ends_at.timestamp() <= now()+90*86400:
        fail('최소 모집수량·재고 또는 마감시간(90일 이내)을 확인해 주세요.', 422)
    brand = db.scalar(select(Record).where(Record.kind == 'brand', Record.owner_id == user.id))
    if not brand:
        fail('승인된 브랜드 정보가 없습니다.')
    d = body.model_dump(exclude={'stock', 'ends_at'})
    c = Record(kind='campaign', owner_id=user.id, parent_id=brand.id, status='draft', data=d, capacity=body.stock, ends=int(body.ends_at.timestamp()))
    db.add(c)
    db.commit()
    return campaign_dto(db, c, user)


@app.post('/api/seller/campaigns/{id}/submit')
def submit_campaign(id: str, user=Depends(approved_seller), db=Depends(get_db)):
    c = record(db, 'campaign', id, user.id)
    changed = db.execute(update(Record).where(Record.id == id, Record.status.in_(['draft', 'rejected']), Record.ends > now()).values(status='pending', revision=Record.revision+1)).rowcount
    if changed != 1:
        fail('제출할 수 없는 공구입니다.')
    db.commit()
    db.refresh(c)
    return campaign_dto(db, c, user)


@app.post('/api/seller/campaigns/{id}/end')
def end_campaign(id: str, user=Depends(current_user), db=Depends(get_db)):
    c = record(db, 'campaign', id, user.id)
    changed = db.execute(update(Record).where(Record.id == id, Record.status.in_(['draft', 'pending', 'active', 'ended', 'rejected']), Record.revision == c.revision).values(status='ended', revision=Record.revision+1)).rowcount
    if not changed:
        fail('현재 상태에서는 종료할 수 없습니다. 새로고침 후 확인해 주세요.')
    audit(db, user, 'campaign-ended', c.id)
    db.commit()
    return campaign_dto(db, c, user)


@app.get('/api/seller/reservations')
def seller_reservations(user=Depends(approved_seller), db=Depends(get_db)):
    ids = [c.id for c in rows(db, 'campaign', Record.owner_id == user.id)]
    return {'items': [{**reservation_dto(r), 'buyer_alias': '참여자-'+r.owner_id[:6]} for r in rows(db, 'reservation', Record.parent_id.in_(ids))]}


def coupon_dto(db, c, user=None):
    brand = db.get(Record, c.parent_id)
    claimed = bool(user and db.scalar(select(Record.id).where(Record.kind == 'user_coupon', Record.unique_key == f'{user.id}:{c.id}')))
    return dict(id=c.id, brand_id=c.parent_id, brand_name=brand.data['name'], **c.data, stock=c.capacity, issued_count=c.counter,
                ends_at=iso(c.ends), claimed=claimed, is_demo=True)


@app.post('/api/seller/coupons', status_code=201)
def create_coupon(body: S.CouponInput, user=Depends(approved_seller), db=Depends(get_db)):
    if body.ends_at.tzinfo is None or not now() < body.ends_at.timestamp() <= now()+90*86400 or body.points_cost != 0:
        fail('유효기간(90일 이내)을 확인해 주세요. 판매자는 마일리지 차감 쿠폰을 발행할 수 없습니다.', 422)
    if body.amount > body.min_spend and body.min_spend != 0:
        fail('할인금액이 최소 주문금액보다 클 수 없습니다.', 422)
    b = db.scalar(select(Record).where(Record.kind == 'brand', Record.owner_id == user.id))
    c = Record(kind='coupon', owner_id=user.id, parent_id=b.id, capacity=body.stock, ends=int(body.ends_at.timestamp()),
               data=body.model_dump(exclude={'stock', 'ends_at'}))
    db.add(c)
    db.commit()
    return coupon_dto(db, c, user)


@app.get('/api/coupons')
def coupons(user=Depends(optional_user), db=Depends(get_db)):
    result = []
    for c in rows(db, 'coupon', Record.status == 'active', Record.ends > now()):
        u = db.get(User, c.owner_id)
        if u and not u.deleted and u.seller_status == 'approved':
            result.append(coupon_dto(db, c, user))
    return {'items': result}


def owned_coupon_dto(db, r):
    c = db.get(Record, r.parent_id)
    if not c:
        return dict(id=r.id, coupon_id=r.parent_id, code='폐기됨', title='종료된 시험 쿠폰',
                    brand_name='삭제된 브랜드', amount=0, min_spend=0, ends_at=iso(r.created), status='expired', is_demo=True)
    brand = db.get(Record, c.parent_id)
    return dict(id=r.id, coupon_id=c.id, code=r.data['code'], title=c.data['title'], brand_name=brand.data['name'] if brand else '삭제된 브랜드',
                amount=c.data['amount'], min_spend=c.data['min_spend'], ends_at=iso(c.ends),
                status='expired' if r.status == 'available' and c.ends <= now() else r.status, is_demo=True)


@app.post('/api/coupons/{id}/claim', status_code=201)
def claim_coupon(id: str, user=Depends(current_user), db=Depends(get_db)):
    c = record(db, 'coupon', id)
    seller = db.get(User, c.owner_id)
    if not seller or seller.deleted or seller.seller_status != 'approved':
        fail('사용할 수 없는 쿠폰입니다.')
    cost = c.data['points_cost']
    changed = db.execute(update(Record).where(Record.id == id, Record.status == 'active', Record.ends > now(), Record.counter < Record.capacity).values(counter=Record.counter+1)).rowcount
    if not changed:
        fail('쿠폰이 소진되었거나 만료되었습니다.')
    # Also blocks negative balances from any redemption, including free claims.
    changed = db.execute(update(User).where(User.id == user.id, User.points >= cost, User.deleted.is_(False)).values(points=User.points-cost)).rowcount
    if changed != 1:
        fail('사용 가능한 마일리지가 부족합니다.')
    owned = Record(kind='user_coupon', owner_id=user.id, parent_id=id, unique_key=f'{user.id}:{id}', status='available', data={'code': 'DEMO-'+secrets.token_hex(5).upper()})
    db.add(owned)
    if cost:
        db.add(Record(kind='ledger', owner_id=user.id, parent_id=id, data={'delta': -cost, 'reason': '개발용 쿠폰 교환'}))
    db.commit()
    return owned_coupon_dto(db, owned)


@app.get('/api/wallet')
def wallet(user=Depends(current_user), db=Depends(get_db)):
    return dict(balance=user.points, ledger=[dict(id=r.id, **r.data, created_at=iso(r.created)) for r in rows(db, 'ledger', Record.owner_id == user.id)],
                coupons=[owned_coupon_dto(db, r) for r in rows(db, 'user_coupon', Record.owner_id == user.id)])


@app.get('/api/campaigns/{id}/questions')
def questions(id: str, user=Depends(optional_user), db=Depends(get_db)):
    public_campaign(db, record(db, 'campaign', id), user)
    blocked = {b.parent_id for b in rows(db, 'block', Record.owner_id == user.id)} if user else set()
    return {'items': [dict(id=r.id, author_id=r.owner_id, author_name=db.get(User, r.owner_id).nickname, body=r.data['body'], created_at=iso(r.created))
                      for r in rows(db, 'question', Record.parent_id == id, Record.status == 'active') if r.owner_id not in blocked]}


@app.post('/api/campaigns/{id}/questions', status_code=201)
def post_question(id: str, body: S.BodyInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'question', 30, subject=user.id)
    public_campaign(db, record(db, 'campaign', id))
    r = Record(kind='question', owner_id=user.id, parent_id=id, data={'body': body.body})
    db.add(r)
    db.commit()
    return dict(id=r.id, author_id=user.id, author_name=user.nickname, body=body.body, created_at=iso(r.created))


@app.post('/api/reports', status_code=201)
def report(body: S.ReportInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    throttle(request, 'report', 20, subject=user.id)
    if body.target_type == 'user':
        target = db.get(User, body.target_id)
        if not target or target.deleted or target.id == user.id:
            fail('신고할 수 없는 사용자입니다.', 422)
    else:
        target = record(db, body.target_type, body.target_id)
        public_campaign(db, target if target.kind == 'campaign' else record(db, 'campaign', target.parent_id))
    r = Record(kind='report', owner_id=user.id, parent_id=target.id, status='pending', data=body.model_dump())
    db.add(r)
    db.commit()
    return {'id': r.id, 'message': '신고를 접수했습니다.'}


@app.post('/api/blocks/{id}')
def block(id: str, user=Depends(current_user), db=Depends(get_db)):
    if id == user.id or not db.get(User, id):
        fail('차단할 수 없는 사용자입니다.', 422)
    key = f'{user.id}:{id}'
    if not db.scalar(select(Record.id).where(Record.kind == 'block', Record.unique_key == key)):
        db.add(Record(kind='block', owner_id=user.id, parent_id=id, unique_key=key))
        db.commit()
    return {'message': '이 사용자의 글을 숨겼습니다.'}


@app.get('/api/admin/applications')
def admin_applications(user=Depends(admin_user), db=Depends(get_db)):
    users = db.scalars(select(User).where(User.seller_status.is_not(None), User.deleted.is_(False)))
    return {'items': [dict(user_id=u.id, nickname=u.nickname, **application_dto(db, u)) for u in users]}


@app.post('/api/admin/applications/{id}/review')
def review_application(id: str, body: S.SellerReview, user=Depends(admin_user), db=Depends(get_db)):
    u = db.get(User, id)
    a = db.scalar(select(Record).where(Record.kind == 'application', Record.owner_id == id))
    if not u or u.deleted or not a:
        fail('신청서를 찾을 수 없습니다.', 404)
    allowed = ['approved'] if body.decision == 'suspended' else ['pending']
    changed = db.execute(update(User).where(User.id == id, User.seller_status.in_(allowed)).values(seller_status=body.decision)).rowcount
    if changed != 1:
        fail('검토할 수 없는 신청 상태입니다.')
    a.data = {**a.data, 'review_note': body.note}
    if body.decision == 'approved':
        brand = db.scalar(select(Record).where(Record.kind == 'brand', Record.owner_id == id))
        if not brand:
            db.add(Record(kind='brand', owner_id=id, unique_key=id, data={'name': a.data['brand_name'], 'description': a.data['brand_description']}))
    audit(db, user, 'seller-'+body.decision, id)
    db.commit()
    db.refresh(u)
    return application_dto(db, u)


@app.get('/api/admin/campaigns')
def admin_campaigns(user=Depends(admin_user), db=Depends(get_db)):
    return {'items': [campaign_dto(db, c, user) for c in rows(db, 'campaign')]}


@app.post('/api/admin/campaigns/{id}/review')
def review_campaign(id: str, body: S.CampaignReview, user=Depends(admin_user), db=Depends(get_db)):
    c = record(db, 'campaign', id)
    seller = db.get(User, c.owner_id)
    if seller.deleted or seller.seller_status != 'approved':
        fail('승인된 판매자가 아닙니다.')
    changed = db.execute(update(Record).where(Record.id == id, Record.status == 'pending', Record.ends > now()).values(status=body.decision, revision=Record.revision+1)).rowcount
    if changed != 1:
        fail('검토할 수 없는 공구 상태입니다.')
    if body.decision == 'active':
        c.data = {**c.data, 'published': True}
    audit(db, user, 'campaign-'+body.decision+': '+body.note, id)
    db.commit()
    db.refresh(c)
    return campaign_dto(db, c, user)


@app.get('/api/admin/reports')
def admin_reports(user=Depends(admin_user), db=Depends(get_db)):
    return {'items': [dict(id=r.id, **r.data, status=r.status, created_at=iso(r.created)) for r in rows(db, 'report')]}


@app.post('/api/admin/reports/{id}/resolve')
def resolve_report(id: str, body: S.ResolveReport, user=Depends(admin_user), db=Depends(get_db)):
    r = record(db, 'report', id)
    if r.status != 'pending':
        fail('이미 처리된 신고입니다.')
    if body.action == 'hide':
        if r.data['target_type'] == 'user':
            target = db.get(User, r.parent_id)
            if target and not target.deleted:
                if not db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == target.id)):
                    db.add(Record(kind='suspension', owner_id=target.id, unique_key=target.id, data={}))
                db.execute(delete(Token).where(Token.user_id == target.id))
                db.execute(update(Record).where(Record.owner_id == target.id, Record.kind.in_(['question', 'campaign'])).values(status='hidden', revision=Record.revision+1))
        else:
            target = db.get(Record, r.parent_id)
            if target:
                target.status = 'hidden'
                target.revision += 1
    r.status = 'resolved'
    audit(db, user, 'report-'+body.action, id)
    db.commit()
    return {'message': '신고를 처리했습니다.'}


def order_dto(r):
    return dict(id=r.id, user_id=r.owner_id, campaign_id=r.parent_id, status=r.status, **r.data, created_at=iso(r.created))


@app.post('/api/admin/orders', status_code=201)
def confirm_order(body: S.OrderInput, user=Depends(admin_user), db=Depends(get_db)):
    buyer = db.get(User, body.user_id)
    c = record(db, 'campaign', body.campaign_id)
    if not buyer or buyer.deleted or buyer.id == c.owner_id or c.status not in ('active', 'ended'):
        fail('구매자 또는 공구 상태를 확인해 주세요.', 422)
    award = body.eligible_amount//100
    r = Record(kind='order', owner_id=buyer.id, parent_id=c.id, unique_key=body.external_reference, status='confirmed',
               data={'external_reference': body.external_reference, 'eligible_amount': body.eligible_amount, 'awarded_points': award})
    db.add(r)
    db.flush()
    db.execute(update(User).where(User.id == buyer.id, User.deleted.is_(False)).values(points=User.points+award))
    db.add(Record(kind='ledger', owner_id=buyer.id, parent_id=r.id, unique_key='earn:'+r.id, data={'delta': award, 'reason': '관리자 확인 개발용 주문 적립'}))
    audit(db, user, 'demo-order-confirmed', r.id)
    db.commit()
    return order_dto(r)


@app.post('/api/admin/orders/{id}/refund')
def refund_order(id: str, user=Depends(admin_user), db=Depends(get_db)):
    r = record(db, 'order', id)
    changed = db.execute(update(Record).where(Record.id == id, Record.status == 'confirmed').values(status='refunded')).rowcount
    if changed:
        db.execute(update(User).where(User.id == r.owner_id).values(points=User.points-r.data['awarded_points']))
        db.add(Record(kind='ledger', owner_id=r.owner_id, parent_id=id, unique_key='refund:'+id,
                      data={'delta': -r.data['awarded_points'], 'reason': '개발용 주문 환불 적립 취소'}))
        audit(db, user, 'demo-order-refunded', id)
    db.commit()
    db.refresh(r)
    return order_dto(r)


_research = None


def research_module():
    global _research
    if _research is None:
        path = Path(__file__).resolve().parents[2] / 'ai-pipeline' / 'serving.py'
        if not path.exists():
            fail('분석 산출물이 준비되지 않았습니다.', 503)
        spec = importlib.util.spec_from_file_location('modu_research', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _research = module
    return _research


@app.get('/api/research/summary')
def research_summary(user=Depends(admin_user)):
    return research_module().get_summary()


@app.get('/api/research/bundles')
def research_bundles(user=Depends(admin_user)):
    return {'items': research_module().get_bundle_examples()}


@app.post('/api/research/purchase-intent')
def research_intent(body: dict, user=Depends(admin_user)):
    try:
        return research_module().predict_intent(body)
    except ValueError as exc:
        fail(str(exc), 422)


@app.get('/public/campaigns/{id}', response_class=HTMLResponse)
def public_html(id: str, db=Depends(get_db)):
    c = campaign_dto(db, public_campaign(db, record(db, 'campaign', id)))
    # Development fixtures are explicitly excluded from indexing. No fake merchant Product offers.
    schema = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': c['title'], 'description': c['description'], 'inLanguage': 'ko'}
    encoded = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(c['title'])+' | 모두의 육아 - 육아템 공동구매,핫딜 개발 미리보기</title><script type="application/ld+json">'+encoded+'</script><body><main><p>개발용 예시 · 실제 구매 불가</p><h1>'+escape(c['title'])+'</h1><p>'+escape(c['description'])+'</p><dl><dt>예시 단가</dt><dd>'+str(c['price'])+'원</dd><dt>배송비</dt><dd>'+str(c['shipping_fee'])+'원</dd><dt>단위</dt><dd>'+escape(c['unit'])+'</dd><dt>마감</dt><dd>'+escape(c['ends_at'])+'</dd></dl><h2>배송 조건</h2><p>'+escape(c['shipping_policy'])+'</p><h2>교환·반품</h2><p>'+escape(c['refund_policy'])+'</p><p>예약은 결제가 아닙니다. 모집 성립·실거래 여부를 보장하지 않습니다.</p></main></body></html>'


@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    return 'User-agent: *\nDisallow: /\n# Local development fixtures must not be indexed.\n'


@app.get('/sitemap.xml')
def sitemap():
    return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>', media_type='application/xml')


from .legal import router as legal_router
app.include_router(legal_router)

if config.STATIC_DIR:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    static_root = Path(config.STATIC_DIR).resolve()
    app.mount('/assets', StaticFiles(directory=static_root / 'assets'), name='assets')
    app.mount('/brand', StaticFiles(directory=static_root / 'brand'), name='brand')

    @app.get('/{path:path}')
    def web_app(path: str):
        if path.startswith(('api/', 'legal/', 'public/')) or path in ('docs', 'openapi.json', 'redoc'):
            fail('페이지를 찾을 수 없습니다.', 404)
        return FileResponse(static_root / 'index.html', media_type='text/html')


# The outermost CORS layer also covers rate-limit and body-limit error responses.
app.add_middleware(CORSMiddleware, allow_origins=config.ORIGINS,
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                   allow_headers=['Authorization', 'Content-Type'])
