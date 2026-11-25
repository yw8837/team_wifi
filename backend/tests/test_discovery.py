"""Service integration: account isolation, explainable ordering, and aggregate privacy."""
import json
from copy import deepcopy
import pytest
from sqlalchemy import select
from app import discovery, release
from app.db import Record, SessionLocal, User
from conftest import PASSWORD
from test_public_release import public_mode


@pytest.fixture
def discovery_mode(public_mode):
    manifest = json.loads(release.CATALOG_PATH.read_text('utf-8'))
    base = manifest['entries'][0]
    entries = []
    for id, category in [('diapers', '기저귀·물티슈'), ('bottle', '수유·이유식'), ('bottle-two', '수유·이유식'), ('care', '목욕·위생')]:
        entries.append({**deepcopy(base), 'id': id, 'title': id, 'category': category})
    entries.append({**deepcopy(entries[1]), 'id': 'expired', 'expires_at': '2000-01-01T00:00:00Z'})
    manifest['entries'] = entries
    release.CATALOG_PATH.write_text(json.dumps(manifest), 'utf-8')
    return public_mode


def test_preferences_shared_across_sessions_private_and_reversible(discovery_mode):
    c, p, _ = discovery_mode
    first = p['buyer']['headers']
    second = {'Authorization': 'Bearer ' + c.post('/api/auth/login', json={'email': 'buyer@example.com', 'password': PASSWORD}).json()['access_token']}
    payload = {'categories': ['수유·이유식'], 'priority': 'unit_price'}
    assert c.put('/api/release/preferences', headers=first, json=payload).json() == payload
    assert c.get('/api/release/preferences', headers=second).json() == payload
    assert c.get('/api/release/preferences', headers=p['buyer2']['headers']).json()['categories'] == []
    result = c.get('/api/release/recommendations', headers=second).json()
    assert [o['id'] for o in result['items']] == ['bottle', 'bottle-two']
    assert result['items'][0]['reasons'] == ['직접 고른 관심 카테고리']
    assert '배송비' in result['focus'] and all(o['price'] is None for o in result['items'])
    c.put('/api/release/offers/bottle/saved', headers=first)
    result = c.get('/api/release/recommendations', headers=second).json()
    assert [o['id'] for o in result['items']] == ['bottle-two', 'bottle']
    assert c.delete('/api/release/preferences', headers=second).status_code == 200
    assert c.get('/api/release/preferences', headers=first).json()['categories'] == []
    assert len(c.get('/api/release/saved', headers=first).json()) == 1
    assert c.get('/api/release/recommendations', headers=first).json()['basis'] == 'saved'
    assert c.get('/api/release/recommendations', headers=p['buyer2']['headers']).json()['items'] == []


@pytest.mark.parametrize('payload', [
    {'categories': ['기저귀·물티슈'] * 2}, {'categories': ['unknown']},
    {'categories': list(discovery.CATEGORIES[:4])}, {'priority': 'purchase_probability'},
    {'categories': [], 'owner_id': 'other'}, {'categories': [], 'child_birthdate': '2025-01-01'},
])
def test_preference_overposting_and_invalid_choices_rejected(discovery_mode, payload):
    c, p, _ = discovery_mode
    assert c.put('/api/release/preferences', headers=p['buyer']['headers'], json=payload).status_code == 422


def test_preferences_require_auth_and_follow_account_deletion(discovery_mode):
    c, p, _ = discovery_mode
    for method, path in [('get', 'preferences'), ('put', 'preferences'), ('delete', 'preferences'), ('get', 'recommendations')]:
        assert getattr(c, method)('/api/release/'+path, **({'json': {}} if method == 'put' else {})).status_code == 401
    c.put('/api/release/preferences', headers=p['buyer']['headers'], json={'categories': ['外'], 'priority': 'care'})
    assert c.put('/api/release/preferences', headers=p['buyer']['headers'], json={'categories': ['목욕·위생'], 'priority': 'care'}).status_code == 200
    assert c.request('DELETE', '/api/me', headers=p['buyer']['headers'], json={'password': PASSWORD}).status_code == 200
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind == discovery.PREFERENCE, Record.owner_id == p['buyer']['id']))


def test_aggregate_privacy_deduplication_and_suspended_accounts(discovery_mode):
    c, p, _ = discovery_mode
    assert c.get('/api/release/admin/insights').status_code == 401
    assert c.get('/api/release/admin/insights', headers=p['buyer']['headers']).status_code == 403
    with SessionLocal() as db:
        for person in list(p.values())[:5]:
            # Even duplicate source rows must not inflate the number of accounts.
            for id in ['diapers', 'bottle', 'bottle']:
                db.add(Record(kind=release.SAVE, owner_id=person['id'], parent_id=id))
        db.add(Record(kind=release.SAVE, owner_id=p['admin']['id'], parent_id='care'))
        db.add(Record(kind=release.SAVE, owner_id=p['admin']['id'], parent_id='old-seed-campaign'))
        db.commit()
    response = c.get('/api/release/admin/insights', headers=p['admin']['headers'])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['saved_accounts'] == 6 and len(data['pairs']) == 1
    pair = data['pairs'][0]
    assert pair['accounts'] == 5 and pair['support'] == pytest.approx(5/6)
    assert pair['first_to_second'] == pair['second_to_first'] == 1
    assert next(x for x in data['categories'] if x['category'] == '목욕·위생')['saved_accounts'] is None
    assert all(person['id'] not in response.text for person in p.values())
    assert '@example.com' not in response.text
    with SessionLocal() as db:
        db.add(Record(kind='suspension', owner_id=p['buyer']['id']))
        db.commit()
    data = c.get('/api/release/admin/insights', headers=p['admin']['headers']).json()
    assert data['pairs'] == [] and data['saved_accounts'] == 5
    with SessionLocal() as db:
        db.get(User, p['buyer2']['id']).deleted = True
        db.commit()
    assert c.get('/api/release/admin/insights', headers=p['admin']['headers']).json()['saved_accounts'] is None


def test_demand_insights_exclude_hidden_posts_and_count_accounts(discovery_mode):
    c, p, _ = discovery_mode
    with SessionLocal() as db:
        d = Record(kind=release.DEMAND, owner_id=p['buyer']['id'], data={'category': '기저귀·물티슈'})
        db.add(d); db.flush(); demand_id = d.id
        for person in list(p.values())[:5]:
            db.add(Record(kind=release.INTEREST, parent_id=d.id, owner_id=person['id']))
        db.commit()
    data = c.get('/api/release/admin/insights', headers=p['admin']['headers']).json()
    bucket = next(x for x in data['categories'] if x['category'] == '기저귀·물티슈')
    assert bucket['interested_accounts'] == 5 and bucket['demand_authors'] is None
    with SessionLocal() as db:
        db.get(Record, demand_id).status = 'hidden'; db.commit()
    data = c.get('/api/release/admin/insights', headers=p['admin']['headers']).json()
    assert next(x for x in data['categories'] if x['category'] == '기저귀·물티슈')['interested_accounts'] == 0


def test_evidence_exposes_only_aggregates_and_keeps_historical_scope(discovery_mode):
    c, p, _ = discovery_mode
    e = c.get('/api/release/admin/insights', headers=p['admin']['headers']).json()['evidence']
    assert sum(e['d1']['discount_sensitivity'].values()) == e['d1']['rows'] == 1000
    assert sum(e['d1']['baby_discount_sensitivity'].values()) == e['d1']['baby_rows'] == 41
    assert e['d2']['matched_rows'] == e['d2']['rows'] == 541909
    assert e['d4']['rows'] == 12330 and e['d4']['purchased_sessions'] == 1908
    assert e['d4']['automatic_behavior_scoring'] is False
    assert 'Customer_ID' not in json.dumps(e)
