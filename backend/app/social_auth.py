"""Server-side OIDC/OAuth2 with one-use state and client-bound, token-free redirects.

Provider credentials and tokens never reach the JS bundle, redirect URL or audit log.
An email match is never an account-link authorization. Only provider subject IDs
are retained; a social account does not require an email address.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
from functools import lru_cache
from html import escape
from typing import Literal
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import Field, StrictBool
from sqlalchemy import delete, select, update

from . import config
from .db import Record, User, get_db, now, uid
from .schemas import Strict
from .signup_policy import signup_age_confirmed, signup_consent_action
from .security import current_user, global_write_guard, issue_token, optional_user, profile, token_digest
from .client_policy import mobile_client

router = APIRouter(prefix='/api/auth/social')
Provider = Literal['google', 'kakao', 'naver']
FLOW = 'oauth_flow'
IDENTITY = 'oauth_identity'
DISABLED_PASSWORD = '!social-only'
ENDPOINTS = {
    'google': ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token',
               'https://www.googleapis.com/oauth2/v3/certs', 'https://accounts.google.com'),
    'kakao': ('https://kauth.kakao.com/oauth/authorize', 'https://kauth.kakao.com/oauth/token',
              'https://kauth.kakao.com/.well-known/jwks.json', 'https://kauth.kakao.com'),
    # Naver OAuth2 uses a server-side profile API rather than an OIDC ID token.
    'naver': ('https://nid.naver.com/oauth2.0/authorize', 'https://nid.naver.com/oauth2.0/token', None, None),
}
NAVER_PROFILE_URL = 'https://openapi.naver.com/v1/nid/me'


def settings(provider):
    prefix = {'google': 'GOOGLE', 'kakao': 'KAKAO', 'naver': 'NAVER'}[provider]
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
    force_login: StrictBool = False


class Claim(Strict):
    flow_id: str = Field(min_length=36, max_length=36)
    verifier: str = Field(pattern=r'^[A-Za-z0-9_-]{43,128}$')
    nickname: str = Field(default='', max_length=30)
    terms_accepted: bool = False
    privacy_accepted: bool = False
    age_confirmed: StrictBool | None = None
    adult_confirmed: StrictBool = False


@router.get('/providers')
def providers():
    return {'providers': [p for p in ENDPOINTS if enabled(p)]}


@router.get('/connections')
def connections(user=Depends(current_user), db=Depends(get_db)):
    return {'providers': [r.data['provider'] for r in db.scalars(select(Record).where(
        Record.kind == IDENTITY, Record.owner_id == user.id))], 'has_password': has_password(user)}


@router.post('/{provider}/start')
def start(provider: Provider, body: Start, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    if not enabled(provider):
        raise HTTPException(503, '이 로그인 연결을 준비 중입니다. 이메일 로그인을 이용해 주세요.')
    if body.purpose != 'login' and not user:
        raise HTTPException(401, '계정 연결은 먼저 로그인한 뒤 진행해 주세요.')
    db.execute(delete(Record).where(Record.kind == FLOW, Record.ends <= now()))
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    lifetime = 300 if provider == 'naver' and body.purpose == 'reauth' else 600
    flow = Record(kind=FLOW, unique_key=token_digest(state), owner_id=user.id if body.purpose != 'login' else None,
                  status='pending', ends=now()+lifetime, data={'provider': provider, 'nonce': nonce,
                  'proof': body.challenge, 'platform': body.platform, 'purpose': body.purpose, 'pkce': verifier,
                  'mobile_client': mobile_client(request, platform=body.platform)})
    db.add(flow)
    db.flush()
    params = dict(client_id=settings(provider)[0], redirect_uri=callback_url(provider), response_type='code',
                  scope='openid', state=state, nonce=nonce)
    if provider == 'naver':
        # OAuth2.0 has no ID-token nonce or documented PKCE here. The app's
        # one-use state and claim proof remain required. Scope is console-defined.
        params.pop('scope')
        params.pop('nonce')
        flow.data = {key: value for key, value in flow.data.items() if key not in {'nonce', 'pkce'}}
        if body.purpose == 'reauth':
            params['auth_type'] = 'reauthenticate'
    if provider == 'google':
        params.update(code_challenge=challenge(verifier), code_challenge_method='S256', prompt='select_account')
    if provider == 'kakao' and body.purpose == 'login' and body.force_login:
        params['prompt'] = 'login'
    if body.purpose == 'reauth' and provider != 'naver':
        params['prompt'] = 'login' if provider == 'kakao' else 'select_account'
    db.commit()
    return {'flow_id': flow.id, 'authorization_url': ENDPOINTS[provider][0]+'?'+urlencode(params)}


@lru_cache(maxsize=2)
def jwks(provider):
    return jwt.PyJWKClient(ENDPOINTS[provider][2], cache_jwk_set=True, lifespan=3600, timeout=10)


def exchange(provider, code, flow, *, state=None):
    if provider == 'naver':
        return exchange_naver(code, flow, state)
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


def exchange_naver(code, flow, state):
    """Resolve only response.id from a fresh client-authenticated code exchange.

    This OAuth2 adapter does not claim to verify an OIDC nonce or auth_time.
    Reauthentication requests force provider login and have a shorter local TTL.
    """
    if not isinstance(state, str) or not state or not hmac.compare_digest(token_digest(state), flow.unique_key):
        raise ValueError('Invalid state')
    if flow.data['purpose'] == 'reauth' and not now()-300 <= flow.created <= now()+30:
        raise ValueError('Fresh authentication required')
    client_id, client_secret = settings('naver')
    if not client_id or not client_secret:
        raise ValueError('Provider unavailable')
    payload = dict(grant_type='authorization_code', code=code, state=state,
                   client_id=client_id, client_secret=client_secret, redirect_uri=callback_url('naver'))
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        response = client.post(ENDPOINTS['naver'][1], data=payload)
        response.raise_for_status()
        token = response.json()
        if not isinstance(token, dict) or token.get('error'):
            raise ValueError('Invalid token response')
        access_token, token_type, expires = token.get('access_token'), token.get('token_type'), token.get('expires_in')
        if (not isinstance(access_token, str) or not 1 <= len(access_token) <= 4096 or
                not access_token.isascii() or re.search(r'[\x00-\x20\x7f]', access_token) or
                not isinstance(token_type, str) or token_type.casefold() != 'bearer'):
            raise ValueError('Invalid bearer token')
        if not ((type(expires) is int and expires > 0) or
                (isinstance(expires, str) and expires.isascii() and expires.isdigit() and len(expires) <= 10 and int(expires) > 0)):
            raise ValueError('Invalid token lifetime')
        response = client.get(NAVER_PROFILE_URL, headers={'Authorization': 'Bearer '+access_token})
        response.raise_for_status()
        profile_result = response.json()
    if not isinstance(profile_result, dict) or profile_result.get('resultcode') != '00':
        raise ValueError('Invalid profile response')
    details = profile_result.get('response')
    subject = details.get('id') if isinstance(details, dict) else None
    if (not isinstance(subject, str) or not 1 <= len(subject) <= 255 or
            not subject.isascii() or re.search(r'[\x00-\x20\x7f]', subject)):
        raise ValueError('Invalid subject')
    # Discard access/refresh tokens and every optional profile attribute.
    return subject


def login_recovery(flow):
    destination = config.PUBLIC_WEB_ORIGIN + '/login'
    label = '로그인 다시 시작'
    if flow and flow.data.get('platform') == 'android':
        destination = 'kr.moduyuga.app://auth/complete?flow=' + flow.id
        label = '앱으로 돌아가기'
    body = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>로그인 다시 시작 | 모두의 육아</title>
<style>body{{margin:0;background:#fffaf5;color:#4f382e;font:16px/1.6 system-ui,sans-serif}}
main{{box-sizing:border-box;max-width:480px;margin:10vh auto;padding:24px}}
h1{{font-size:26px;line-height:1.4}}p{{margin:16px 0}}a{{display:block;padding:14px 20px;
background:#b83d31;color:white;text-align:center;border-radius:12px;text-decoration:none;font-weight:700}}
a:focus-visible{{outline:3px solid #4f382e;outline-offset:4px}}</style></head>
<body><main><p>모두의 육아</p><h1>로그인을 다시 시작해 주세요</h1>
<p role="alert">로그인 요청의 유효시간이 지났거나 이미 사용된 요청이에요.</p>
<p>로그인 버튼을 누른 뒤 10분 안에 인증을 마쳐 주세요. 아래 버튼에서 다시 시작할 수 있어요.</p>
<a href="{escape(destination, quote=True)}">{label}</a></main></body></html>'''
    return HTMLResponse(body, status_code=400, headers={
        'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
        'X-Robots-Tag': 'noindex',
        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
    })


@router.get('/{provider}/callback')
def callback(provider: Provider, request: Request, state: str = '', code: str = '', error: str = '', db=Depends(get_db)):
    global_write_guard(request)
    if len(state) > 200 or len(code) > 4096:
        raise HTTPException(400, '유효하지 않은 로그인 응답입니다.')
    flow = db.scalar(select(Record).where(Record.kind == FLOW, Record.unique_key == token_digest(state)))
    if not flow or flow.ends <= now() or flow.status != 'pending' or flow.data.get('provider') != provider:
        if 'text/html' in request.headers.get('accept', ''):
            return login_recovery(flow if flow and flow.data.get('provider') == provider else None)
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
        result['subject'] = (exchange(provider, code, flow, state=state) if provider == 'naver'
                             else exchange(provider, code, flow))
        flow.status = 'ready'
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        flow.status = 'failed'
        result['failure_reason'] = ('nonce_mismatch' if isinstance(exc, ValueError) and str(exc) == 'Invalid nonce'
                                    else 'provider_denied' if error or not code else type(exc).__name__)
    flow.data = result
    db.commit()
    destination = 'kr.moduyuga.app://auth/complete' if result['platform'] == 'android' else config.PUBLIC_WEB_ORIGIN+'/auth/complete'
    return RedirectResponse(destination+'?flow='+flow.id, status_code=303, headers={'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})


@router.post('/claim')
def claim(body: Claim, request: Request, user=Depends(optional_user), db=Depends(get_db)):
    flow = db.get(Record, body.flow_id)
    if not flow or flow.kind != FLOW or flow.ends <= now() or not hmac.compare_digest(flow.data.get('proof', ''), challenge(body.verifier)):
        raise HTTPException(400, '로그인을 시작한 기기에서 다시 진행해 주세요.')
    if flow.status in ('pending', 'processing'):
        return {'status': 'pending'}
    if flow.status == 'failed':
        raise HTTPException(400, '카카오 인증을 확인하지 못했어요. 로그인 화면에서 다시 시도해 주세요.' if flow.data.get('provider') == 'kakao' else '소셜 인증을 확인하지 못했어요. 로그인 화면에서 다시 시도해 주세요.')
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
            if not (body.terms_accepted and body.privacy_accepted and signup_age_confirmed(body) and len(body.nickname) >= 2):
                return {'status': 'onboarding', 'provider': flow.data['provider']}
            account_id = uid()
            account = User(id=account_id, email='social-'+account_id+'@invalid.local', password_hash=DISABLED_PASSWORD, nickname=body.nickname)
            db.add(account)
            db.flush()
            db.add(Record(kind=IDENTITY, owner_id=account.id, unique_key=key, data={'provider': flow.data['provider'], 'subject': flow.data['subject']}))
            db.add(Record(kind='audit', owner_id=account.id, parent_id=account.id,
                          data={'action': signup_consent_action(body, social=True)}))
        result = {'status': 'authenticated', 'access_token': issue_token(db, account), 'user': profile(account)}
    changed = db.execute(update(Record).where(Record.id == flow.id, Record.status == 'ready').values(status='consumed', data={})).rowcount
    if changed != 1:
        raise HTTPException(409, '이미 처리된 로그인 요청입니다.')
    db.commit()
    return result
