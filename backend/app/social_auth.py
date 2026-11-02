"""Server-side OIDC with one-use state and client-bound, token-free redirects.

Provider credentials and tokens never reach the JS bundle, redirect URL or audit log.
An email match is never an account-link authorization. Only provider subject IDs
are requested; a social account does not require an email address.
"""
import base64
import hashlib
import hmac
import os
import secrets
from functools import lru_cache
from typing import Literal
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import delete, select, update

from . import config
from .db import Record, User, get_db, now, uid
from .schemas import Strict
from .security import current_user, global_write_guard, issue_token, optional_user, profile, token_digest

router = APIRouter(prefix='/api/auth/social')
Provider = Literal['google', 'kakao']
FLOW = 'oauth_flow'
IDENTITY = 'oauth_identity'
DISABLED_PASSWORD = '!social-only'
ENDPOINTS = {
    'google': ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token',
               'https://www.googleapis.com/oauth2/v3/certs', 'https://accounts.google.com'),
    'kakao': ('https://kauth.kakao.com/oauth/authorize', 'https://kauth.kakao.com/oauth/token',
              'https://kauth.kakao.com/.well-known/jwks.json', 'https://kauth.kakao.com'),
}


def settings(provider):
    prefix = 'GOOGLE' if provider == 'google' else 'KAKAO'
    return (os.getenv(prefix+'_CLIENT_ID', ''), os.getenv(prefix+'_CLIENT_SECRET', ''))


def callback_url(provider):
    return config.PUBLIC_ORIGIN + '/api/auth/social/' + provider + '/callback'


def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()


def has_password(user):
    return user.password_hash != DISABLED_PASSWORD


def identity_key(provider, subject):
    return token_digest(provider + ':' + subject)


def enabled(provider):
    return bool(all(settings(provider)) and config.PUBLIC_ORIGIN and config.PUBLIC_WEB_ORIGIN and not config.BETA)


class Start(Strict):
    challenge: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')
    platform: Literal['web', 'android'] = 'web'
    purpose: Literal['login', 'link', 'reauth'] = 'login'


class Claim(Strict):
    flow_id: str = Field(min_length=36, max_length=36)
    verifier: str = Field(pattern=r'^[A-Za-z0-9_-]{43,128}$')
    nickname: str = Field(default='', max_length=30)
    terms_accepted: bool = False
    privacy_accepted: bool = False
    adult_confirmed: bool = False


@router.get('/providers')
def providers():
    return {'providers': [p for p in ENDPOINTS if enabled(p)]}


@router.get('/connections')
def connections(user=Depends(current_user), db=Depends(get_db)):
    return {'providers': [r.data['provider'] for r in db.scalars(select(Record).where(
        Record.kind == IDENTITY, Record.owner_id == user.id))], 'has_password': has_password(user)}


@router.post('/{provider}/start')
def start(provider: Provider, body: Start, user=Depends(optional_user), db=Depends(get_db)):
    if not enabled(provider):
        raise HTTPException(503, '이 로그인 연결을 준비 중입니다. 이메일 로그인을 이용해 주세요.')
    if body.purpose != 'login' and not user:
        raise HTTPException(401, '계정 연결은 먼저 로그인한 뒤 진행해 주세요.')
    db.execute(delete(Record).where(Record.kind == FLOW, Record.ends <= now()))
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    flow = Record(kind=FLOW, unique_key=token_digest(state), owner_id=user.id if body.purpose != 'login' else None,
                  status='pending', ends=now()+600, data={'provider': provider, 'nonce': nonce,
                  'proof': body.challenge, 'platform': body.platform, 'purpose': body.purpose, 'pkce': verifier})
    db.add(flow)
    db.flush()
    params = dict(client_id=settings(provider)[0], redirect_uri=callback_url(provider), response_type='code',
                  scope='openid', state=state, nonce=nonce)
    if provider == 'google':
        params.update(code_challenge=challenge(verifier), code_challenge_method='S256', prompt='select_account')
    if body.purpose == 'reauth':
        params['prompt'] = 'login' if provider == 'kakao' else 'select_account'
    db.commit()
    return {'flow_id': flow.id, 'authorization_url': ENDPOINTS[provider][0]+'?'+urlencode(params)}


@lru_cache(maxsize=2)
def jwks(provider):
    return jwt.PyJWKClient(ENDPOINTS[provider][2], cache_jwk_set=True, lifespan=3600, timeout=10)


def exchange(provider, code, flow):
    client_id, client_secret = settings(provider)
    payload = dict(grant_type='authorization_code', code=code, client_id=client_id,
                   client_secret=client_secret, redirect_uri=callback_url(provider))
    if provider == 'google':
        payload['code_verifier'] = flow.data['pkce']
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response = client.post(ENDPOINTS[provider][1], data=payload)
        response.raise_for_status()
        encoded = response.json()['id_token']
    if not isinstance(encoded, str) or len(encoded) > 16000:
        raise ValueError('Invalid ID token')
    signing_key = jwks(provider).get_signing_key_from_jwt(encoded)
    claims = jwt.decode(encoded, signing_key.key, algorithms=['RS256'], audience=client_id,
                        issuer=ENDPOINTS[provider][3], leeway=30,
                        options={'require': ['sub', 'iss', 'aud', 'exp', 'iat', 'nonce']})
    if not hmac.compare_digest(str(claims['nonce']), flow.data['nonce']):
        raise ValueError('Invalid nonce')
    if (claims.get('azp') and claims['azp'] != client_id) or (isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != client_id):
        raise ValueError('Invalid authorized party')
    if flow.data['purpose'] == 'reauth' and not now()-300 <= claims['iat'] <= now()+30:
        raise ValueError('Fresh authentication required')
    subject = claims['sub']
    if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
        raise ValueError('Invalid subject')
    # No access/refresh token, email, profile photo or provider display name is retained.
    return subject


@router.get('/{provider}/callback')
def callback(provider: Provider, request: Request, state: str = '', code: str = '', error: str = '', db=Depends(get_db)):
    global_write_guard(request)
    if len(state) > 200 or len(code) > 4096:
        raise HTTPException(400, '유효하지 않은 로그인 응답입니다.')
    flow = db.scalar(select(Record).where(Record.kind == FLOW, Record.unique_key == token_digest(state)))
    if not flow or flow.ends <= now() or flow.status != 'pending' or flow.data.get('provider') != provider:
        raise HTTPException(400, '로그인 요청이 만료되었거나 이미 처리되었습니다. 앱에서 다시 시작해 주세요.')
    changed = db.execute(update(Record).where(Record.id == flow.id, Record.status == 'pending').values(status='processing')).rowcount
    if changed != 1:
        raise HTTPException(400, '이미 처리된 로그인 요청입니다.')
    db.commit()  # Consume state before the outbound exchange; never retry a code.
    result = dict(flow.data)
    result.pop('pkce', None)
    result.pop('nonce', None)
    try:
        if error or not code:
            raise ValueError('Cancelled')
        result['subject'] = exchange(provider, code, flow)
        flow.status = 'ready'
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, TypeError):
        flow.status = 'failed'
    flow.data = result
    db.commit()
    destination = 'kr.moduyuga.app://auth/complete' if result['platform'] == 'android' else config.PUBLIC_WEB_ORIGIN+'/auth/complete'
    return RedirectResponse(destination+'?flow='+flow.id, status_code=303, headers={'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})


@router.post('/claim')
def claim(body: Claim, user=Depends(optional_user), db=Depends(get_db)):
    flow = db.get(Record, body.flow_id)
    if not flow or flow.kind != FLOW or flow.ends <= now() or not hmac.compare_digest(flow.data.get('proof', ''), challenge(body.verifier)):
        raise HTTPException(400, '로그인을 시작한 기기에서 다시 진행해 주세요.')
    if flow.status in ('pending', 'processing'):
        return {'status': 'pending'}
    if flow.status != 'ready':
        raise HTTPException(400, '로그인이 취소되었거나 만료되었습니다. 다시 시작해 주세요.')
    purpose = flow.data['purpose']
    if purpose != 'login' and (not user or user.id != flow.owner_id):
        raise HTTPException(403, '계정 연결을 시작한 회원으로 로그인해 주세요.')
    key = identity_key(flow.data['provider'], flow.data['subject'])
    revoked = db.scalar(select(Record).where(Record.kind == 'oauth_revocation', Record.unique_key == key))
    if revoked and flow.created <= revoked.data.get('occurred_at', 0):
        raise HTTPException(400, '연결 해제 전에 시작한 인증입니다. 다시 로그인해 주세요.')
    identity = db.scalar(select(Record).where(Record.kind == IDENTITY, Record.unique_key == key))
    if purpose == 'reauth':
        if not identity or identity.owner_id != user.id:
            raise HTTPException(403, '이 계정에 연결된 소셜 계정으로 인증해 주세요.')
        result = {'status': 'reauthenticated', 'reauth_token': issue_token(db, user, 'social_reauth', 300)}
    elif purpose == 'link':
        if identity and identity.owner_id != user.id:
            raise HTTPException(409, '이미 다른 회원에 연결된 소셜 계정입니다. 자동으로 합치지 않습니다.')
        if not identity:
            db.add(Record(kind=IDENTITY, owner_id=user.id, unique_key=key, data={'provider': flow.data['provider'], 'subject': flow.data['subject']}))
        result = {'status': 'linked'}
    else:
        if identity:
            account = db.get(User, identity.owner_id)
            if not account or account.deleted or db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == account.id)):
                raise HTTPException(403, '사용할 수 없는 계정입니다.')
        else:
            if not (body.terms_accepted and body.privacy_accepted and body.adult_confirmed and len(body.nickname) >= 2):
                return {'status': 'onboarding', 'provider': flow.data['provider']}
            account_id = uid()
            account = User(id=account_id, email='social-'+account_id+'@invalid.local', password_hash=DISABLED_PASSWORD, nickname=body.nickname)
            db.add(account)
            db.flush()
            db.add(Record(kind=IDENTITY, owner_id=account.id, unique_key=key, data={'provider': flow.data['provider'], 'subject': flow.data['subject']}))
            db.add(Record(kind='audit', owner_id=account.id, parent_id=account.id,
                          data={'action': 'social-terms-20261102-privacy-20261102-adult-accepted'}))
        result = {'status': 'authenticated', 'access_token': issue_token(db, account), 'user': profile(account)}
    changed = db.execute(update(Record).where(Record.id == flow.id, Record.status == 'ready').values(status='consumed', data={})).rowcount
    if changed != 1:
        raise HTTPException(409, '이미 처리된 로그인 요청입니다.')
    db.commit()
    return result
