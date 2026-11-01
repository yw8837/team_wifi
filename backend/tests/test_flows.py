from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select, update
from app import schemas as S
from app.db import RUNTIME, Record, SessionLocal, User, now
from app.main import put_application, withdraw_record
from conftest import PASSWORD, application


def body():
    return dict(title='검토할 공구', description='개발용 공구 등록 시험', category='육아생활', price=12000, shipping_fee=3000,
                unit='1개', minimum_quantity=2, stock=10, ends_at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat())


def test_guest_and_sensitive_data(setup):
    c, p, ids = setup
    for path in ['/api/campaigns', '/api/brands', '/api/brands/'+ids['brand'], '/api/campaigns/'+ids['campaign']]:
        r = c.get(path)
        assert r.status_code == 200
        assert 'PRIVATE' not in r.text and 'private@example.com' not in r.text
    assert c.get('/api/wallet').status_code == 401
    assert c.get('/api/admin/applications', headers=p['buyer']['headers']).status_code == 403


def test_register_rejects_escalation_and_consent(setup):
    c, _, _ = setup
    payload = dict(email='new@example.com', password=PASSWORD, nickname='새회원', track='seller', terms_accepted=True, privacy_accepted=True)
    assert c.post('/api/auth/register', json={**payload, 'is_admin': True}).status_code == 422
    assert c.post('/api/auth/register', json={**payload, 'terms_accepted': False}).status_code == 422
    r = c.post('/api/auth/register', json=payload)
    assert r.status_code == 201
    assert not r.json()['user']['is_admin'] and r.json()['user']['seller_status'] == 'draft'
    assert c.post('/api/auth/register', json=payload).status_code == 409


def test_login_logout_and_token_revocation(setup):
    c, _, _ = setup
    assert c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': 'incorrect'}).status_code == 401
    r = c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD})
    h = {'Authorization': 'Bearer '+r.json()['access_token']}
    assert c.get('/api/me', headers=h).status_code == 200
    assert c.post('/api/auth/logout', headers=h).status_code == 200
    assert c.get('/api/me', headers=h).status_code == 401


def test_reservation_revision_capacity_owner_and_withdrawal(setup):
    c, p, ids = setup
    path = '/api/campaigns/'+ids['campaign']+'/reservations'
    assert c.post(path, json={'quantity': 1, 'revision': 1}, headers=p['seller']['headers']).status_code == 403
    assert c.post(path, json={'quantity': 1, 'revision': 999}, headers=p['buyer']['headers']).status_code == 409
    assert c.post(path, json={'quantity': 11, 'revision': 1}, headers=p['buyer']['headers']).status_code == 409
    r = c.post(path, json={'quantity': 7, 'revision': 1}, headers=p['buyer']['headers'])
    assert r.status_code == 201
    assert c.post(path, json={'quantity': 1, 'revision': 1}, headers=p['buyer']['headers']).status_code == 409
    assert c.post(path, json={'quantity': 4, 'revision': 1}, headers=p['buyer2']['headers']).status_code == 409
    withdraw = '/api/reservations/'+r.json()['id']+'/withdraw'
    assert c.post(withdraw, headers=p['buyer2']['headers']).status_code == 404
    assert c.post(withdraw, headers=p['buyer']['headers']).status_code == 200
    assert c.post(withdraw, headers=p['buyer']['headers']).status_code == 200
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 0


def test_expired_campaign_cannot_reserve(setup):
    c, p, ids = setup
    with SessionLocal() as db:
        db.get(Record, ids['campaign']).ends = now()-1
        db.commit()
    assert c.post('/api/campaigns/'+ids['campaign']+'/reservations', json={'quantity': 1, 'revision': 1}, headers=p['buyer']['headers']).status_code == 409


def test_coupon_unique_and_cap_rollback(setup):
    c, p, ids = setup
    with SessionLocal() as db:
        db.get(Record, ids['coupon']).capacity = 2
        db.commit()
    path = '/api/coupons/'+ids['coupon']+'/claim'
    assert c.post(path, headers=p['buyer']['headers']).status_code == 201
    assert c.post(path, headers=p['buyer']['headers']).status_code == 409
    assert c.post(path, headers=p['buyer2']['headers']).status_code == 201
    assert c.post(path, headers=p['seller2']['headers']).status_code == 409
    assert c.get('/api/coupons').json()['items'][0]['issued_count'] == 2
    assert len(c.get('/api/wallet', headers=p['buyer']['headers']).json()['coupons']) == 1


def test_points_order_refund_and_negative_balance(setup):
    c, p, ids = setup
    payload = dict(user_id=p['buyer']['id'], campaign_id=ids['campaign'], external_reference='TEST-ORDER-001', eligible_amount=10000, status='confirmed')
    assert c.post('/api/admin/orders', json=payload, headers=p['buyer']['headers']).status_code == 403
    r = c.post('/api/admin/orders', json=payload, headers=p['admin']['headers'])
    assert r.status_code == 201
    assert c.post('/api/admin/orders', json=payload, headers=p['admin']['headers']).status_code == 409
    assert c.get('/api/wallet', headers=p['buyer']['headers']).json()['balance'] == 100
    with SessionLocal() as db:
        coupon = db.get(Record, ids['coupon'])
        coupon.data = {**coupon.data, 'points_cost': 50}
        db.commit()
    assert c.post('/api/coupons/'+ids['coupon']+'/claim', headers=p['buyer']['headers']).status_code == 201
    for _ in range(2):
        assert c.post('/api/admin/orders/'+r.json()['id']+'/refund', headers=p['admin']['headers']).status_code == 200
    w = c.get('/api/wallet', headers=p['buyer']['headers']).json()
    assert w['balance'] == -50 and len(w['ledger']) == 3
    assert c.post('/api/points/earn', json={'amount': 50000}, headers=p['buyer']['headers']).status_code == 404


def test_low_points_roll_back_coupon_stock(setup):
    c, p, ids = setup
    with SessionLocal() as db:
        coupon = db.get(Record, ids['coupon'])
        coupon.data = {**coupon.data, 'points_cost': 50}
        db.commit()
    assert c.post('/api/coupons/'+ids['coupon']+'/claim', headers=p['buyer']['headers']).status_code == 409
    assert c.get('/api/coupons').json()['items'][0]['issued_count'] == 0


def test_seller_pending_owner_and_publishing(setup):
    c, p, _ = setup
    assert c.post('/api/seller/campaigns', json=body(), headers=p['pending']['headers']).status_code == 403
    r = c.post('/api/seller/campaigns', json=body(), headers=p['seller']['headers'])
    assert r.status_code == 201
    id = r.json()['id']
    assert c.get('/api/campaigns/'+id).status_code == 404
    assert c.post('/api/seller/campaigns/'+id+'/submit', headers=p['seller2']['headers']).status_code == 404
    assert c.post('/api/seller/campaigns/'+id+'/submit', headers=p['seller']['headers']).status_code == 200
    assert c.get('/api/campaigns/'+id).status_code == 404
    assert c.post('/api/admin/campaigns/'+id+'/review', json={'decision': 'active', 'note': '개발용 검토'}, headers=p['admin']['headers']).status_code == 200
    assert c.get('/api/campaigns/'+id).status_code == 200


def test_draft_end_does_not_bypass_moderation(setup):
    c, p, _ = setup
    id = c.post('/api/seller/campaigns', json=body(), headers=p['seller']['headers']).json()['id']
    assert c.post('/api/seller/campaigns/'+id+'/end', headers=p['seller']['headers']).status_code == 200
    assert c.get('/api/campaigns/'+id).status_code == 404
    assert id not in [x['id'] for x in c.get('/api/campaigns').json()['items']]


def test_hidden_campaign_cannot_reappear(setup):
    c, p, ids = setup
    r = c.post('/api/reports', json={'target_type': 'campaign', 'target_id': ids['campaign'], 'reason': '개발용 신고 확인'}, headers=p['buyer']['headers'])
    assert c.post('/api/admin/reports/'+r.json()['id']+'/resolve', json={'action': 'hide'}, headers=p['admin']['headers']).status_code == 200
    assert c.post('/api/seller/campaigns/'+ids['campaign']+'/end', headers=p['seller']['headers']).status_code == 409
    assert c.get('/api/campaigns/'+ids['campaign']).status_code == 404


def test_application_staged_submit_review_lock(setup):
    c, p, _ = setup
    h = p['buyer']['headers']
    assert c.put('/api/seller/application', json={'brand_name': '임시'}, headers=h).status_code == 200
    assert c.post('/api/seller/application/submit', headers=h).status_code == 422
    assert c.put('/api/seller/application', json=application(), headers=h).status_code == 200
    assert c.post('/api/seller/application/submit', headers=h).status_code == 200
    assert c.put('/api/seller/application', json=application(), headers=h).status_code == 409
    review = '/api/admin/applications/'+p['buyer']['id']+'/review'
    assert c.post(review, json={'decision': 'needs_changes', 'note': '연락처 보완'}, headers=p['admin']['headers']).status_code == 200
    assert c.put('/api/seller/application', json=application(), headers=h).status_code == 200
    assert c.post('/api/seller/application/submit', headers=h).status_code == 200
    assert c.post(review, json={'decision': 'approved', 'note': '개발용 심사'}, headers=p['admin']['headers']).status_code == 200
    assert c.put('/api/seller/application', json=application(), headers=h).status_code == 409


def test_stale_application_cannot_modify_approved_identity(setup):
    _, p, _ = setup
    with SessionLocal() as db:
        u = db.get(User, p['buyer']['id'])
        u.seller_status = 'draft'
        db.add(Record(kind='application', owner_id=u.id, unique_key=u.id, data=application()))
        db.commit()
    with SessionLocal() as stale:
        u = stale.get(User, p['buyer']['id'])
        stale.commit()
        with SessionLocal() as newer:
            newer.get(User, u.id).seller_status = 'approved'
            newer.commit()
        try:
            put_application(S.Application(business_number=''), user=u, db=stale)
            assert False, 'stale write accepted'
        except HTTPException as e:
            assert e.status_code == 409


def test_reservation_aba_stale_withdrawal_is_rejected(setup):
    c, p, ids = setup
    path = '/api/campaigns/'+ids['campaign']+'/reservations'
    r = c.post(path, json={'quantity': 1, 'revision': 1}, headers=p['buyer']['headers']).json()
    with SessionLocal() as stale:
        old = stale.get(Record, r['id'])
        stale.commit()
        assert c.post('/api/reservations/'+r['id']+'/withdraw', headers=p['buyer']['headers']).status_code == 200
        assert c.post(path, json={'quantity': 10, 'revision': 1}, headers=p['buyer']['headers']).status_code == 201
        try:
            withdraw_record(stale, old)
            assert False, 'stale quantity mutation accepted'
        except HTTPException as e:
            assert e.status_code == 409
        stale.rollback()
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 10
    assert c.post('/api/reservations/'+r['id']+'/withdraw', headers=p['buyer']['headers']).status_code == 200
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 0


def test_concurrent_reservation_capacity(setup):
    c, p, ids = setup
    path = '/api/campaigns/'+ids['campaign']+'/reservations'
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda who: c.post(path, json={'quantity': 8, 'revision': 1}, headers=p[who]['headers']).status_code, ['buyer', 'buyer2']))
    assert sorted(results) == [201, 409]
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 8


def test_concurrent_coupon_capacity(setup):
    c, p, ids = setup
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda who: c.post('/api/coupons/'+ids['coupon']+'/claim', headers=p[who]['headers']).status_code, ['buyer', 'buyer2']))
    assert sorted(results) == [201, 409]
    assert c.get('/api/coupons').json()['items'][0]['issued_count'] == 1


def test_delete_account_anonymizes_and_revokes(setup):
    c, p, ids = setup
    h = p['buyer']['headers']
    c.post('/api/campaigns/'+ids['campaign']+'/reservations', json={'quantity': 2, 'revision': 1}, headers=h)
    assert c.request('DELETE', '/api/me', json={'password': 'wrong'}, headers=h).status_code == 403
    assert c.request('DELETE', '/api/me', json={'password': PASSWORD}, headers=h).status_code == 200
    assert c.get('/api/me', headers=h).status_code == 401
    assert c.get('/api/campaigns/'+ids['campaign']).json()['reserved_quantity'] == 0
    with SessionLocal() as db:
        u = db.get(User, p['buyer']['id'])
        assert u.deleted and u.email.endswith('@invalid.local') and not u.marketing


def test_seller_deletion_requires_closing_active_campaign(setup):
    c, p, _ = setup
    assert c.request('DELETE', '/api/me', json={'password': PASSWORD}, headers=p['seller']['headers']).status_code == 409


def test_reset_is_generic_single_use_revokes_sessions(setup):
    c, p, _ = setup
    a = c.post('/api/auth/reset-request', json={'email': 'buyer@example.com'})
    b = c.post('/api/auth/reset-request', json={'email': 'missing@example.com'})
    assert a.json() == b.json() and 'token' not in a.json()
    token = json.loads((RUNTIME / 'outbox' / (p['buyer']['id']+'.json')).read_text())['token']
    payload = {'token': token, 'password': 'Changed-Password-123'}
    assert c.post('/api/auth/reset', json=payload).status_code == 200
    assert c.post('/api/auth/reset', json=payload).status_code == 400
    assert c.get('/api/me', headers=p['buyer']['headers']).status_code == 401
    assert not (RUNTIME / 'outbox' / (p['buyer']['id']+'.json')).exists()


def test_community_block_report_and_author_spoof(setup):
    c, p, ids = setup
    path = '/api/campaigns/'+ids['campaign']+'/questions'
    assert c.post(path, json={'body': '안녕하세요', 'author_id': p['admin']['id']}, headers=p['buyer']['headers']).status_code == 422
    r = c.post(path, json={'body': '<script>alert(1)</script>'}, headers=p['buyer']['headers'])
    assert r.status_code == 201
    assert c.post('/api/blocks/'+p['buyer']['id'], headers=p['buyer2']['headers']).status_code == 200
    assert c.get(path, headers=p['buyer2']['headers']).json()['items'] == []
    r = c.post('/api/reports', json={'target_type': 'question', 'target_id': r.json()['id'], 'reason': '유해 내용 신고'}, headers=p['buyer2']['headers'])
    assert c.post('/api/admin/reports/'+r.json()['id']+'/resolve', json={'action': 'hide'}, headers=p['admin']['headers']).status_code == 200
    assert c.get(path).json()['items'] == []


def test_html_jsonld_escapes_untrusted_content(setup):
    c, _, ids = setup
    with SessionLocal() as db:
        r = db.get(Record, ids['campaign'])
        r.data = {**r.data, 'title': '</script><script>alert(1)</script>'}
        db.commit()
    html = c.get('/public/campaigns/'+ids['campaign']).text
    assert '<script>alert(1)</script>' not in html and 'noindex,nofollow' in html
    assert '\\u003c/script\\u003e' in html


def test_research_admin_boundary_and_feature_rejection(setup):
    c, p, _ = setup
    assert c.get('/api/research/summary', headers=p['buyer']['headers']).status_code == 403
    assert c.post('/api/research/purchase-intent', json={'PageValues': 10}, headers=p['admin']['headers']).status_code == 422


def test_login_throttling(setup):
    c, _, _ = setup
    for _ in range(20):
        assert c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': 'wrong'}).status_code == 401
    assert c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD}).status_code == 429


def test_minimum_quantity_states_are_not_payment_confirmation(setup):
    c, p, ids = setup
    path = '/api/campaigns/'+ids['campaign']
    assert c.get(path).json()['recruitment_status'] == 'collecting'
    r = c.post(path+'/reservations', json={'quantity': 2, 'revision': 1}, headers=p['buyer']['headers']).json()
    d = c.get(path).json()
    assert d['recruitment_status'] == 'minimum_met' and d['remaining_quantity'] == 8
    with SessionLocal() as db:
        db.get(Record, ids['campaign']).ends = now()-1
        db.commit()
    assert c.get(path).json()['recruitment_status'] == 'closed_met'
    c.post('/api/reservations/'+r['id']+'/withdraw', headers=p['buyer']['headers'])
    assert c.get(path).json()['recruitment_status'] == 'closed_shortfall'
