import hashlib
import hmac
import secrets
import threading
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

def token_digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()

def issue_token(db, user, kind='session', lifetime=8*3600):
    raw = secrets.token_urlsafe(32)
    db.add(Token(digest=token_digest(raw), user_id=user.id, kind=kind, expires=now()+lifetime))
    return raw

def throttle(request: Request, label, limit=20):
    if config.BETA:
        # Middleware performs beta checks before authentication opens a transaction.
        # Endpoints may retain local-mode checks without acquiring a second connection.
        checked = getattr(request.state, 'rate_checked', set())
        if label in checked:
            return
        # One atomic upsert shared by every process. Raw IP addresses are not persisted.
        from sqlalchemy.dialects.postgresql import insert
        stamp = now()
        source = request.client.host if request.client else 'unknown'
        key = hmac.new(config.RATE_LIMIT_SECRET.encode(), f'{source}:{label}:{stamp//600}'.encode(), hashlib.sha256).hexdigest()
        with SessionLocal() as session:
            # Rate-limit transactions do not need application SERIALIZABLE snapshots.
            session.connection(execution_options={'isolation_level': 'READ COMMITTED'})
            statement = insert(RateBucket).values(key=key, count=1, expires=(stamp//600+1)*600)
            total = session.scalar(statement.on_conflict_do_update(index_elements=[RateBucket.key],
                                   set_={'count': RateBucket.count+1}).returning(RateBucket.count))
            session.execute(delete(RateBucket).where(RateBucket.expires < stamp-600))
            session.commit()
        if total > limit:
            raise HTTPException(429, '요청이 많습니다. 잠시 후 다시 시도해 주세요.', headers={'Retry-After': '600'})
        request.state.rate_checked = checked | {label}
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
                seller_status=user.seller_status, points_balance=user.points, email_verified=False)
