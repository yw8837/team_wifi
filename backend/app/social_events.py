"""Kakao signed Security Event Token receiver; never accepts an unsigned user ID.

Only User Unlinked changes accounts. A password/other-provider account survives;
an account with no remaining authentication method follows the existing erasure.
"""
from functools import lru_cache

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import delete, select
from starlette.concurrency import run_in_threadpool

from . import config
from .db import Record, Token, User, get_db, now
from .security import token_digest
from .social_auth import ENDPOINTS, IDENTITY, enabled, has_password, identity_key, settings

router = APIRouter(prefix='/api/auth/social/kakao')
UNLINK = 'https://schemas.openid.net/secevent/oauth/event-type/user-unlinked'
ISSUER = ENDPOINTS['kakao'][3]
RECEIPT = 'oauth_event'
REVOCATION = 'oauth_revocation'


@lru_cache(maxsize=1)
def event_jwks():
    return jwt.PyJWKClient(ENDPOINTS['kakao'][2], cache_jwk_set=True, lifespan=3600, timeout=2)


def decode_event(encoded):
    header = jwt.get_unverified_header(encoded)
    if header.get('typ') != 'secevent+jwt' or header.get('alg') != 'RS256':
        raise ValueError('Not a signed security event')
    key = event_jwks().get_signing_key_from_jwt(encoded)
    claims = jwt.decode(encoded, key.key, algorithms=['RS256'], audience=settings('kakao')[0],
                        issuer=ISSUER, leeway=30,
                        options={'require': ['aud', 'iss', 'iat', 'jti', 'events']})
    if not isinstance(claims['iat'], int) or not now()-86400 <= claims['iat'] <= now()+30:
        raise ValueError('Event timestamp outside acceptance window')
    if not isinstance(claims['jti'], str) or not 1 <= len(claims['jti']) <= 255:
        raise ValueError('Invalid event identifier')
    if not isinstance(claims['events'], dict):
        raise ValueError('Invalid events')
    if UNLINK in claims['events']:
        event = claims['events'][UNLINK]
        subject = event.get('subject', {}) if isinstance(event, dict) else {}
        sub = subject.get('sub')
        occurred = claims.get('toe', claims['iat'])
        if (subject.get('subject_type') != 'iss-sub' or subject.get('iss') != ISSUER or
                not isinstance(sub, str) or not 1 <= len(sub) <= 255 or
                claims.get('sub') != sub or not isinstance(occurred, int) or
                not 0 < occurred <= claims['iat']+30):
            raise ValueError('Invalid unlink subject or event time')
    return claims


def apply_event(claims, db):
    digest = token_digest(claims['jti'])
    if db.scalar(select(Record.id).where(Record.kind == RECEIPT, Record.unique_key == digest)):
        return
    db.execute(delete(Record).where(Record.kind.in_([RECEIPT, REVOCATION]), Record.ends <= now()))
    # No raw JWT, subject, email, nickname or IP is retained in the receipt.
    db.add(Record(kind=RECEIPT, unique_key=digest, ends=now()+86400, data={}))
    db.flush()
    event = claims['events'].get(UNLINK)
    if event is None:
        db.commit()
        return
    key = identity_key('kakao', event['subject']['sub'])
    occurred = claims.get('toe', claims['iat'])
    revoked = db.scalar(select(Record).where(Record.kind == REVOCATION, Record.unique_key == key))
    if revoked is None:
        db.add(Record(kind=REVOCATION, unique_key=key, ends=now()+86400, data={'occurred_at': occurred}))
    else:
        revoked.data = {'occurred_at': max(occurred, revoked.data['occurred_at'])}
        revoked.ends = now()+86400
    identity = db.scalar(select(Record).where(Record.kind == IDENTITY, Record.unique_key == key))
    # An old notification must not remove a link established after the event.
    if identity is None or identity.created > occurred:
        db.commit()
        return
    user = db.get(User, identity.owner_id)
    other = db.scalar(select(Record.id).where(Record.kind == IDENTITY,
                                             Record.owner_id == identity.owner_id, Record.id != identity.id))
    if user and not user.deleted and not has_password(user) and not other:
        from .main import erase_account
        erase_account(user, db)
        return
    db.execute(delete(Token).where(Token.user_id == identity.owner_id))
    db.delete(identity)
    db.commit()


@router.post('/events', status_code=202)
async def kakao_events(request: Request, db=Depends(get_db)):
    if not config.PUBLIC_RELEASE or not enabled('kakao'):
        return Response(status_code=404)
    raw = await request.body()
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/secevent+jwt' or not 1 <= len(raw) <= 16000:
        return JSONResponse({'err': 'invalid_request', 'description': 'Expected a bounded security event token.'}, status_code=400)
    try:
        claims = await run_in_threadpool(decode_event, raw.decode('ascii'))
    except jwt.PyJWKClientConnectionError:
        return Response(status_code=503, headers={'Retry-After': '10'})
    except (jwt.PyJWTError, ValueError, TypeError, KeyError, UnicodeError):
        return JSONResponse({'err': 'invalid_request', 'description': 'Security event validation failed.'}, status_code=400)
    await run_in_threadpool(apply_event, claims, db)
    return Response(status_code=202)
