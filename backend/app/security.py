import hashlib
import hmac
import json
import math
import secrets
import threading
import time
from collections import defaultdict, deque
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from .db import Token, User, Record, RateBucket, SessionLocal, get_db, now
from . import config

class BoundedPasswordHash:
    """Keep Argon2 memory bounded on the 512MB beta instance."""
    def __init__(self):
        self.engine = PasswordHash.recommended()
        self.limit = threading.BoundedSemaphore(1)

    def hash(self, password):
        with self.limit:
            return self.engine.hash(password)

    def verify(self, password, hashed):
        with self.limit:
            return self.engine.verify(password, hashed)


passwords = BoundedPasswordHash()
DUMMY = passwords.hash('dummy-password-never-an-account')
_attempts = defaultdict(deque)
_lock = threading.Lock()
# Only these server-owned labels exist in memory. Rejected requests never grow a deque.
GLOBAL_LIMITS = {'write': 120, 'expensive-auth': 30, 'register': 10}
_global_attempts = {label: deque() for label in GLOBAL_LIMITS}
_global_lock = threading.Lock()
ACCOUNT_LIMITS = {'write': 60, 'question': 30, 'report': 20,
                  'recovery-code': 5, 'delete-account': 5}
CLAIMED_LIMITS = {'login': 10, 'recover': 5}


def rate_error(retry_after):
    return HTTPException(429, '요청이 많습니다. 잠시 후 다시 시도해 주세요.',
                         headers={'Retry-After': str(max(1, math.ceil(retry_after)))})


def global_write_guard(request):
    """Cheap rolling-minute guard before any DB access; single worker only.

    Restart/sleep resets this process-local budget. An attacker may consume the
    shared budget and delay all testers; account quotas do not prevent that DoS.
    """
    labels = ['write']
    if (request.method == 'POST' and request.url.path in (
            '/api/auth/register', '/api/auth/login', '/api/auth/recover', '/api/auth/recovery-code')) or (
            request.method == 'DELETE' and request.url.path == '/api/me'):
        labels.append('expensive-auth')
    if request.method == 'POST' and request.url.path == '/api/auth/register':
        labels.append('register')
    with _global_lock:
        stamp = time.monotonic()
        for bucket in _global_attempts.values():
            while bucket and bucket[0] <= stamp-60:
                bucket.popleft()
        waits = [_global_attempts[label][0]+60-stamp for label in labels
                 if len(_global_attempts[label]) >= GLOBAL_LIMITS[label]]
        if waits:
            raise rate_error(max(waits))
        for label in labels:
            _global_attempts[label].append(stamp)


def rate_key(scope, subject, label, stamp):
    # Namespace and subject are unambiguous; email/token/IP never become DB keys.
    value = json.dumps(['v2', scope, label, stamp//600, str(subject)], separators=(',', ':'))
    return hmac.new(config.RATE_LIMIT_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def charge_buckets(session, request, scope, subject, limits):
    """Commit only a dedicated, short limiter transaction before the action starts."""
    from sqlalchemy.dialects.postgresql import insert
    stamp = now()
    expires = (stamp//600+1)*600
    exceeded = False
    checked = set(getattr(request.state, 'rate_checked', set()))
    for label, limit in limits.items():
        marker = (scope, str(subject), label)
        if marker in checked:
            continue
        statement = insert(RateBucket).values(key=rate_key(scope, subject, label, stamp), count=1, expires=expires)
        total = session.scalar(statement.on_conflict_do_update(index_elements=[RateBucket.key],
                               set_={'count': RateBucket.count+1}).returning(RateBucket.count))
        exceeded |= total > limit
        checked.add(marker)
    session.execute(delete(RateBucket).where(RateBucket.expires <= stamp))
    # Commit even quota rejection and subsequent failed auth/domain actions.
    session.commit()
    if exceeded:
        raise rate_error(expires-now())
    request.state.rate_checked = checked


def beta_write_guard(request):
    global_write_guard(request)
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer ') or len(auth) > 250:
        return
    # This is quota identity, not authorization. Endpoints authenticate again in
    # their own transaction after this session has CLOSED, so revocation is fresh.
    with SessionLocal() as session:
        session.connection(execution_options={'isolation_level': 'READ COMMITTED'})
        try:
            user = optional_user(request, session)
        except HTTPException:
            return
        if not user:
            return
        limits = {'write': ACCOUNT_LIMITS['write']}
        path = request.url.path
        label = None
        if request.method == 'POST':
            if path.startswith('/api/release/demands/') and path.endswith('/comments'):
                label = 'question'
            elif path == '/api/release/demands':
                label = 'question'
            elif path.startswith('/api/campaigns/') and path.endswith('/questions') and path.count('/') == 4:
                label = 'question'
            else:
                label = {'/api/reports': 'report', '/api/release/reports': 'report', '/api/auth/recovery-code': 'recovery-code'}.get(path)
        elif request.method == 'DELETE' and path == '/api/me':
            label = 'delete-account'
        if label:
            limits[label] = ACCOUNT_LIMITS[label]
        charge_buckets(session, request, 'account', user.id, limits)


def charge_claimed_account(request, label, email):
    """Call after body validation, before first action query/hash (get_db is lazy on PG)."""
    if not config.deployed():
        return throttle(request, label, 10 if label == 'recover' else 20)
    with SessionLocal() as session:
        session.connection(execution_options={'isolation_level': 'READ COMMITTED'})
        charge_buckets(session, request, 'claimed-account', str(email).lower(), {label: CLAIMED_LIMITS[label]})

def token_digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()

def issue_token(db, user, kind='session', lifetime=8*3600):
    raw = secrets.token_urlsafe(32)
    db.add(Token(digest=token_digest(raw), user_id=user.id, kind=kind, expires=now()+lifetime))
    return raw

def throttle(request: Request, label, limit=20, *, subject=None):
    if config.deployed():
        if ('account', str(subject), label) not in getattr(request.state, 'rate_checked', set()):
            raise RuntimeError('Account quota must be checked before the action transaction.')
        return
    key = (request.client.host if request.client else 'local', label)
    with _lock:
        bucket = _attempts[key]
        while bucket and bucket[0] <= now()-600:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(429, '요청이 많습니다. 잠시 후 다시 시도해 주세요.')
        bucket.append(now())

def optional_user(request: Request, db=Depends(get_db)):
    auth = request.headers.get('Authorization', '')
    if not auth:
        return None
    if not auth.startswith('Bearer ') or len(auth) > 250:
        if request.method == 'GET':
            return None
        raise HTTPException(401, '다시 로그인해 주세요.')
    token = db.get(Token, token_digest(auth[7:]))
    if not token or token.kind != 'session' or token.expires <= now():
        if request.method == 'GET':
            return None
        raise HTTPException(401, '로그인이 만료되었습니다. 다시 로그인해 주세요.')
    user = db.get(User, token.user_id)
    if not user or user.deleted or db.scalar(select(Record.id).where(Record.kind == 'suspension', Record.owner_id == user.id)):
        if request.method == 'GET':
            return None
        raise HTTPException(401, '사용할 수 없는 계정입니다.')
    return user

def current_user(user=Depends(optional_user)):
    if not user:
        raise HTTPException(401, '로그인이 필요합니다.')
    return user

def approved_seller(user=Depends(current_user)):
    if user.seller_status != 'approved':
        raise HTTPException(403, '판매자 검토 승인 후 사용할 수 있습니다.')
    return user

def admin_user(user=Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, '관리자 권한이 필요합니다.')
    return user

def profile(user):
    return dict(id=user.id, email=user.email, nickname=user.nickname, is_admin=user.is_admin,
                seller_status=None if config.PUBLIC_RELEASE else user.seller_status, points_balance=0 if config.PUBLIC_RELEASE else user.points, email_verified=False)
