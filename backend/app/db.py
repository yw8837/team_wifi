"""Local persistent development storage. All money and inventory mutations are server owned."""
import os
import time
import uuid
from pathlib import Path
from fastapi import Request
from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from . import config

RUNTIME = Path(os.getenv('RUNTIME_DIR', Path(__file__).resolve().parents[1] / 'runtime'))
RUNTIME.mkdir(parents=True, exist_ok=True)
URL = os.getenv('DATABASE_URL', f'sqlite:///{(RUNTIME / "modu.db").as_posix()}')
engine = create_engine(URL, connect_args={'check_same_thread': False, 'timeout': 30} if URL.startswith('sqlite') else {'connect_timeout': 10}, pool_pre_ping=True, hide_parameters=True,
                       **({} if URL.startswith('sqlite') else {'isolation_level': 'SERIALIZABLE', 'pool_size': 5, 'max_overflow': 2}))
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_config(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')

SessionLocal = sessionmaker(engine, expire_on_commit=False)

def uid():
    return str(uuid.uuid4())

def now():
    return int(time.time())

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    nickname: Mapped[str] = mapped_column(String(30))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    seller_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[int] = mapped_column(Integer, default=now)

class Token(Base):
    __tablename__ = 'tokens'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    expires: Mapped[int] = mapped_column(Integer)

class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    expires: Mapped[int] = mapped_column(Integer, index=True)

class Record(Base):
    """Versioned aggregates; private data never serialized without a resource serializer."""
    __tablename__ = 'records'
    __table_args__ = (UniqueConstraint('kind', 'unique_key'), Index('ix_kind_parent', 'kind', 'parent_id'), Index('ix_kind_owner', 'kind', 'owner_id'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    unique_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='active')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    counter: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    ends: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created: Mapped[int] = mapped_column(Integer, default=now)

def init_db():
    # PostgreSQL advisory lock serializes first boot across revisions/instances.
    with engine.begin() as connection:
        if URL.startswith('postgresql'):
            connection.execute(text('SELECT pg_advisory_xact_lock(72411301)'))
        Base.metadata.create_all(connection)

def get_db(request: Request):
    with SessionLocal() as session:
        try:
            # Acquire SQLite's write lock BEFORE authentication/state reads. Production PostgreSQL
            # uses serializable transactions; a conflicting request must retry from new state.
            if URL.startswith('sqlite') and request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
                session.execute(text('BEGIN IMMEDIATE'))
            yield session
        except Exception:
            session.rollback()
            raise
