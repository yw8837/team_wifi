"""Cheap guard boundaries; durable identity/transaction checks run on local PostgreSQL."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app import config, security


def request(path='/api/auth/login', method='POST', headers=()):
    return Request({'type': 'http', 'method': method, 'path': path, 'headers': headers,
                    'scheme': 'https', 'server': ('example.test', 443), 'client': ('192.0.2.1', 1000)})


@pytest.fixture
def guard_clock(monkeypatch):
    stamp = [1000.0]
    monkeypatch.setattr(security.time, 'monotonic', lambda: stamp[0])
    for bucket in security._global_attempts.values():
        bucket.clear()
    yield stamp
    for bucket in security._global_attempts.values():
        bucket.clear()


def test_expensive_auth_is_shared_and_rolling(guard_clock):
    paths = ['/api/auth/login', '/api/auth/recover', '/api/auth/recovery-code']
    for i in range(30):
        security.global_write_guard(request(paths[i % 3]))
    guard_clock[0] += 20.2
    with pytest.raises(HTTPException) as error:
        security.global_write_guard(request('/api/me', 'DELETE'))
    assert error.value.status_code == 429
    assert error.value.headers['Retry-After'] == '40'
    guard_clock[0] += 39.8
    security.global_write_guard(request())


def test_global_cardinality_stays_fixed_for_arbitrary_input(guard_clock):
    for i in range(120):
        security.global_write_guard(request(f'/unrecognized/{i}', headers=[(b'x-forwarded-for', str(i).encode())]))
    for i in range(1000):
        with pytest.raises(HTTPException):
            security.global_write_guard(request(f'/unrecognized/{i+120}'))
    assert set(security._global_attempts) == {'write', 'expensive-auth', 'register'}
    assert sum(map(len, security._global_attempts.values())) == 120


def test_signup_budget_and_rejected_guard_never_opens_database(monkeypatch, guard_clock):
    for _ in range(10):
        security.global_write_guard(request('/api/auth/register'))
    monkeypatch.setattr(security, 'SessionLocal', lambda: pytest.fail('Rejected global request opened DB'))
    with pytest.raises(HTTPException) as error:
        security.beta_write_guard(request('/api/auth/register', headers=[(b'authorization', b'Bearer arbitrary')]))
    assert error.value.status_code == 429


def test_account_marker_cannot_be_replaced_by_global_or_claimed_marker(monkeypatch):
    monkeypatch.setattr(config, 'BETA', True)
    req = request()
    req.state.rate_checked = {('global', '', 'question'), ('claimed-account', 'account-a', 'question')}
    with pytest.raises(RuntimeError):
        security.throttle(req, 'question', subject='account-a')
    req.state.rate_checked.add(('account', 'account-a', 'question'))
    security.throttle(req, 'question', subject='account-a')
    with pytest.raises(RuntimeError):
        security.throttle(req, 'question', subject='account-b')


def test_hmac_namespaces_and_subject_boundaries(monkeypatch):
    monkeypatch.setattr(config, 'RATE_LIMIT_SECRET', 'local-fixture-secret-never-production')
    keys = {security.rate_key(scope, subject, label, stamp) for scope, subject, label, stamp in [
        ('account', 'alice@example.com', 'login', 1200),
        ('claimed-account', 'alice@example.com', 'login', 1200),
        ('account', 'bob@example.com', 'login', 1200),
        ('account', 'alice@example.com', 'recover', 1200),
        ('account', 'alice@example.com', 'login', 1800)]}
    assert len(keys) == 5 and all(len(key) == 64 for key in keys)
