import json
from copy import deepcopy

import pytest
from sqlalchemy import select

from app import advisor, release
from app.db import Record, SessionLocal, User
from conftest import PASSWORD
from test_discovery import discovery_mode
from test_public_release import public_mode


def test_preview_has_no_storage_and_never_guesses_unknown_prices(discovery_mode):
    c, _, _ = discovery_mode
    response = c.post('/api/release/advisor/preview', json={'categories': ['수유·이유식'], 'purpose': 'gift'})
    assert response.status_code == 200
    data = response.json()
    assert [item['id'] for item in data['items']] == ['bottle', 'bottle-two']
    assert '교환' in data['focus'] and data['basis'] == 'declared_choices'
    data = c.post('/api/release/advisor/preview', json={'categories': ['수유·이유식'], 'budget_max': 10000}).json()
    assert data['items'] == [] and data['unknown_price_count'] == 2
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind == advisor.STATE))


def test_budget_includes_shipping_and_expired_entries_are_excluded(discovery_mode):
    c, _, _ = discovery_mode
    manifest = json.loads(release.CATALOG_PATH.read_text('utf-8'))
    for e in manifest['entries']:
        e['price'], e['shipping_fee'] = 8000, 3000
    manifest['entries'][0]['shipping_fee'] = 0
    release.CATALOG_PATH.write_text(json.dumps(manifest), 'utf-8')
    data = c.post('/api/release/advisor/preview', json={'budget_max': 10000}).json()
    assert [item['id'] for item in data['items']] == ['diapers']
    assert data['unknown_price_count'] == 0
    assert data['over_budget_count'] == 3
    assert '배송비 포함 예산 상한을 넘는' in data['note']


@pytest.mark.parametrize('payload', [{'budget_max': -1}, {'budget_max': True}, {'budget_max': '1000'},
    {'categories': ['수유·이유식'] * 2}, {'purpose': 'newborn'}, {'child_name': 'private'},
    {'priority': 'purchase_score'}, {'owner_id': 'someone-else'}, {'scroll_depth': 90}])
def test_preview_rejects_unsupported_and_personal_fields(discovery_mode, payload):
    c, _, _ = discovery_mode
    assert c.post('/api/release/advisor/preview', json=payload).status_code == 422


def test_saved_choices_persist_across_sessions_are_private_and_clearable(discovery_mode):
    c, p, _ = discovery_mode
    body = {'categories': ['수유·이유식'], 'priority': 'composition', 'purpose': 'gift', 'budget_max': None}
    for method in ('get', 'put', 'delete'):
        assert getattr(c, method)('/api/release/advisor', **({'json': body} if method == 'put' else {})).status_code == 401
    first = p['buyer']['headers']
    assert c.put('/api/release/advisor', headers=first, json=body).json()['has_saved_choices'] is True
    second = {'Authorization': 'Bearer ' + c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD}).json()['access_token']}
    assert c.get('/api/release/advisor', headers=second).json()['choices'] == body
    assert not c.get('/api/release/advisor', headers=p['buyer2']['headers']).json()['has_saved_choices']
    assert c.delete('/api/release/advisor', headers=first).status_code == 200
    assert not c.get('/api/release/advisor', headers=second).json()['has_saved_choices']
    c.put('/api/release/advisor', headers=first, json=body)
    assert c.request('DELETE', '/api/me', headers=first, json={'password': PASSWORD}).status_code == 200
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind == advisor.STATE, Record.owner_id == p['buyer']['id']))


def test_companions_only_claim_real_distinct_nonadmin_active_co_saves(discovery_mode):
    c, p, _ = discovery_mode
    path = '/api/release/offers/bottle/companions'
    result = c.get(path).json()
    assert result['basis'] == 'category' and result['items'][0]['id'] == 'bottle-two'
    assert result['items'][0]['accounts'] is None
    with SessionLocal() as db:
        for i in range(5):
            u = User(email=f'real-{i}@example.org', nickname='회원', password_hash='unused')
            db.add(u); db.flush()
            for target in ('bottle', 'diapers', 'diapers'):
                db.add(Record(kind=release.SAVE, owner_id=u.id, parent_id=target))
        last = u.id
        db.add(Record(kind=release.SAVE, owner_id=p['admin']['id'], parent_id='bottle'))
        db.add(Record(kind=release.SAVE, owner_id=p['admin']['id'], parent_id='diapers'))
        db.commit()
    response = c.get(path)
    result = response.json()
    assert result['basis'] == 'co_save' and result['items'][0]['accounts'] == 5
    assert result['items'][0]['id'] == 'diapers'
    assert '@example.org' not in response.text and last not in response.text
    with SessionLocal() as db:
        db.add(Record(kind='suspension', owner_id=last)); db.commit()
    assert c.get(path).json()['basis'] == 'category'
    assert c.get('/api/release/offers/expired/companions').json()['items'] == []
    assert c.get('/api/release/offers/missing/companions').status_code == 404


def test_guide_schema_matches_reference_scope(discovery_mode):
    c, _, _ = discovery_mode
    result = c.get('/api/release/offers/bottle/guide').json()
    assert result['structured_data']['@type'] == 'Article'
    assert result['canonical_url'].endswith('/items/bottle.html')
    assert all(key not in result['structured_data'] for key in ('offers', 'aggregateRating', 'lowPrice'))
    assert c.get('/api/release/offers/expired/guide').json()['expired'] is True


def test_new_measurement_placements_respect_opt_in(discovery_mode):
    c, p, _ = discovery_mode
    h = p['buyer']['headers']
    payload = {'offer_id': 'bottle', 'channel': 'web', 'action': 'view', 'visible_ms': 1000}
    for placement in ('companion', 'advisor', 'compare_cta'):
        assert not c.post('/api/release/measurement/events', headers=h, json={**payload, 'placement': placement}).json()['recorded']
    c.put('/api/release/measurement/consent', headers=h, json={'enabled': True})
    for placement, action in [('companion', 'detail'), ('advisor', 'detail'), ('compare_cta', 'calculator')]:
        assert c.post('/api/release/measurement/events', headers=h, json={**payload, 'placement': placement}).json()['recorded']
        assert c.post('/api/release/measurement/events', headers=h, json={**payload, 'placement': placement, 'action': action}).json()['recorded']
    assert c.post('/api/release/measurement/events', headers=h, json={**payload, 'placement': 'compare_cta', 'action': 'save'}).status_code == 422


def test_budget_exclusion_counts_are_disjoint_and_match_active_selected_categories(discovery_mode):
    c, _, _ = discovery_mode
    manifest = json.loads(release.CATALOG_PATH.read_text('utf-8'))
    entries = manifest['entries']
    entries[1]['price'], entries[1]['shipping_fee'] = 8000, 2000
    entries[2]['price'], entries[2]['shipping_fee'] = 8000, 2001
    entries.append({**deepcopy(entries[1]), 'id': 'unknown-shipping', 'shipping_fee': None})
    release.CATALOG_PATH.write_text(json.dumps(manifest), 'utf-8')
    body = {'categories': ['수유·이유식'], 'budget_max': 10000}
    data = c.post('/api/release/advisor/preview', json=body).json()
    assert [item['id'] for item in data['items']] == ['bottle']
    assert data['unknown_price_count'] == data['over_budget_count'] == 1
    assert '금액을 확인하지 못한' in data['note']
    data = c.post('/api/release/advisor/preview', json={'categories': ['수유·이유식']}).json()
    assert data['unknown_price_count'] == data['over_budget_count'] == 0
    assert len(data['items']) == 3
