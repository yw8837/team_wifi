"""Beta auth/policy cases use disposable fixtures; PostgreSQL is checked separately."""
from concurrent.futures import ThreadPoolExecutor
import secrets
import pytest
from sqlalchemy import select
from app import config
from app.db import Record, Token, SessionLocal, User, now
from app.security import token_digest
from conftest import PASSWORD


@pytest.fixture
def beta_mode(monkeypatch, setup):
    monkeypatch.setattr(config, 'BETA', True)
    # This SQLite test suite isolates domain behavior, not the PostgreSQL limiter.
    monkeypatch.setattr('app.main.throttle', lambda *args, **kwargs: None)
    return setup


def invitation():
    raw = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        db.add(Record(kind='beta_invite', unique_key=token_digest(raw), ends=now()+3600, data={}))
        db.commit()
    return raw


def signup(c, code, email='beta@example.com', **overrides):
    return c.post('/api/auth/register', json=dict(email=email, password=PASSWORD, nickname='베타회원', track='buyer',
        terms_accepted=True, privacy_accepted=True, invite_code=code, adult_confirmed=True, **overrides))


def test_invitation_one_use_no_email_verification_claim(beta_mode):
    c, _, _ = beta_mode
    assert signup(c, '').status_code == 422
    code = invitation()
    response = signup(c, code)
    assert response.status_code == 201
    result = response.json()
    assert not result['user']['email_verified'] and len(result['recovery_code']) >= 32
    assert signup(c, code, 'another@example.com').status_code == 400
    with SessionLocal() as db:
        assert db.get(Token, token_digest(result['recovery_code'])).kind == 'recovery'
        assert not db.get(Token, result['recovery_code'])


def test_invitation_concurrency(beta_mode):
    c, _, _ = beta_mode
    code = invitation()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda i: signup(c, code, f'beta{i}@example.com').status_code, range(2)))
    assert results.count(201) == 1
    assert all(status in (201, 400, 409) for status in results)


def test_recovery_rotation_revokes_all_sessions(beta_mode):
    c, _, _ = beta_mode
    result = signup(c, invitation()).json()
    h = {'Authorization': 'Bearer '+result['access_token']}
    payload = {'email': 'beta@example.com', 'recovery_code': result['recovery_code'], 'password': PASSWORD+'new'}
    assert c.post('/api/auth/recover', json={**payload, 'email': 'wrong@example.com'}).status_code == 400
    changed = c.post('/api/auth/recover', json=payload)
    assert changed.status_code == 200
    assert changed.json()['recovery_code'] != result['recovery_code']
    assert c.get('/api/me', headers=h).status_code == 401
    assert c.post('/api/auth/recover', json=payload).status_code == 400
    assert c.post('/api/auth/login', json={'email': 'beta@example.com', 'password': PASSWORD}).status_code == 401
    assert c.post('/api/auth/login', json={'email': 'beta@example.com', 'password': PASSWORD+'new'}).status_code == 200


def test_recovery_code_renewal_checks_password_and_keeps_session(beta_mode):
    c, _, _ = beta_mode
    result = signup(c, invitation()).json()
    h = {'Authorization': 'Bearer '+result['access_token']}
    assert c.post('/api/auth/recovery-code', json={'password': PASSWORD}).status_code == 401
    assert c.post('/api/auth/recovery-code', headers=h, json={'password': 'wrong-password'}).status_code == 403
    renewed = c.post('/api/auth/recovery-code', headers=h, json={'password': PASSWORD})
    assert renewed.status_code == 200
    raw = renewed.json()['recovery_code']
    assert raw != result['recovery_code'] and len(raw) >= 32
    assert c.get('/api/me', headers=h).status_code == 200
    with SessionLocal() as db:
        assert not db.get(Token, token_digest(result['recovery_code']))
        assert db.get(Token, token_digest(raw)).kind == 'recovery'
    assert c.post('/api/auth/recover', json={'email': 'beta@example.com', 'recovery_code': raw, 'password': PASSWORD+'new'}).status_code == 200


def test_seller_real_data_rejected_and_virtual_submit(beta_mode):
    c, p, _ = beta_mode
    h = p['buyer']['headers']
    assert c.put('/api/seller/application', headers=h, json={'business_address': 'REAL ADDRESS'}).status_code == 403
    draft = {'brand_name': '시험브랜드', 'brand_description': '가상 판매자 시험 설명', 'seller_terms_accepted': False}
    assert c.post('/api/seller/application/beta', headers=h, json=draft).status_code == 200
    assert c.post('/api/seller/application/submit', headers=h).status_code == 422
    r = c.post('/api/seller/application/beta', headers=h, json={
        'brand_name': '시험브랜드', 'brand_description': '가상 판매자 시험 설명', 'seller_terms_accepted': True})
    assert r.status_code == 200
    assert r.json()['fields']['business_address'] == '실제 주소 수집하지 않음'
    assert c.post('/api/seller/application/submit', headers=h).status_code == 200


def test_seller_deletion_cancels_other_test_reservations(beta_mode):
    c, p, ids = beta_mode
    reservation = c.post('/api/campaigns/'+ids['campaign']+'/reservations', headers=p['buyer']['headers'], json={'quantity': 1, 'revision': 1})
    assert reservation.status_code == 201
    assert c.request('DELETE','/api/me',headers=p['seller']['headers'],json={'password':PASSWORD}).status_code == 200
    assert c.get('/api/reservations',headers=p['buyer']['headers']).json()['items'][0]['status']=='withdrawn'
    assert c.get('/api/campaigns/'+ids['campaign']).status_code==404


def test_seller_deletion_invalidates_claimed_coupons_without_breaking_wallet(beta_mode):
    c, p, ids = beta_mode
    h = p['buyer']['headers']
    assert c.post('/api/coupons/'+ids['coupon']+'/claim', headers=h).status_code == 201
    assert c.get('/api/wallet', headers=h).json()['coupons'][0]['status'] == 'available'
    assert c.request('DELETE', '/api/me', headers=p['seller']['headers'], json={'password': PASSWORD}).status_code == 200
    wallet = c.get('/api/wallet', headers=h)
    assert wallet.status_code == 200
    coupon = wallet.json()['coupons'][0]
    assert coupon['status'] == 'expired' and coupon['code'] == '폐기됨'
    assert '예시' not in coupon['title'] and coupon['amount'] == 0
    assert c.post('/api/coupons/'+ids['coupon']+'/claim', headers=h).status_code == 404


def test_beta_deletion_removes_records_and_recovery(beta_mode):
    c, _, ids = beta_mode
    result = signup(c, invitation()).json()
    h = {'Authorization': 'Bearer '+result['access_token']}
    assert c.post('/api/campaigns/'+ids['campaign']+'/reservations', headers=h, json={'quantity': 2, 'revision': 1}).status_code == 201
    assert c.post('/api/campaigns/'+ids['campaign']+'/questions', headers=h, json={'body': '삭제할 개인 질문'}).status_code == 201
    assert c.request('DELETE', '/api/me', headers=h, json={'password': PASSWORD}).status_code == 200
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 0
    assert c.get('/api/me', headers=h).status_code == 401
    with SessionLocal() as db:
        assert not db.scalar(select(Token).where(Token.user_id == result['user']['id']))
        assert not db.scalar(select(Record).where(Record.owner_id == result['user']['id']))
        assert db.get(User, result['user']['id']).email.endswith('@invalid.local')


def test_user_report_resolution_revokes_and_blocks(setup):
    c, p, ids = setup
    r = c.post('/api/reports', headers=p['buyer']['headers'], json={
        'target_type': 'user', 'target_id': p['buyer2']['id'], 'reason': '불법 게시 신고 시험'})
    assert r.status_code == 201
    assert c.post('/api/admin/reports/'+r.json()['id']+'/resolve', headers=p['admin']['headers'], json={'action': 'hide'}).status_code == 200
    assert c.get('/api/me', headers=p['buyer2']['headers']).status_code == 401
    assert c.post('/api/auth/login', json={'email': 'buyer2@example.com', 'password': PASSWORD}).status_code == 401


def test_public_browsing_survives_stale_token(setup):
    c, _, _ = setup
    headers = {'Authorization': 'Bearer invalid-stale-token'}
    assert c.get('/api/campaigns', headers=headers).status_code == 200
    assert c.get('/api/me', headers=headers).status_code == 401
    assert c.post('/api/auth/logout', headers=headers).status_code == 401


def test_body_limit_and_safe_policy_pages(setup):
    c, _, _ = setup
    assert c.post('/api/auth/login', content='x'*65537).status_code == 413
    assert c.post('/api/auth/login', content='{bad json', headers={'Content-Type': 'application/json'}).status_code == 422
    for kind in ('privacy', 'terms', 'deletion', 'support'):
        response = c.get('/legal/'+kind)
        assert response.status_code == 200 and 'Team_Wifi' in response.text
        assert 'frame-ancestors' in response.headers['content-security-policy']
    assert c.get('/legal/unknown').status_code == 404
    assert c.get('/api/config').json()['payments_enabled'] is False
    response = c.post('/api/auth/login', json={'email':'bad','password':'do-not-echo','extra':'do-not-echo'})
    assert response.status_code==422 and 'do-not-echo' not in response.text
    response = c.post('/api/auth/login',content='x'*65537,headers={'Origin':'https://localhost'})
    assert response.headers['access-control-allow-origin']=='https://localhost'
