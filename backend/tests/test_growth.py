import pytest
from sqlalchemy import select
from app.db import SessionLocal, Record, now
from app import growth
from test_public_release import public_mode


def event(c, h, action='view', **extra):
    return c.post('/api/release/measurement/events', headers=h, json={
        'offer_id': 'official-source-1', 'placement': 'catalog', 'channel': 'web', 'action': action, 'visible_ms': 1000, **extra})


def test_measurement_consent_visibility_order_dedup_and_withdrawal(public_mode):
    c, p, _ = public_mode
    h = p['buyer']['headers']
    assert not event(c, h).json()['recorded']
    assert c.put('/api/release/measurement/consent', headers=h, json={'enabled': True}).json()['enabled']
    assert not event(c, h, 'detail').json()['recorded']
    assert not event(c, h, visible_ms=999).json()['recorded']
    for _ in range(2): assert event(c, h).json()['recorded']
    assert event(c, h, 'detail').json()['recorded']
    assert c.put('/api/release/offers/official-source-1/saved', headers=h).status_code == 200
    with SessionLocal() as db:
        rows = list(db.scalars(select(Record).where(Record.kind == growth.EXPOSURE)))
        assert len(rows) == 1 and rows[0].data['saved']
    report = c.get('/api/release/measurement/report', headers=p['admin']['headers']).json()['rows'][0]
    assert report['accounts'] is None and report['ctr'] is None and report['ctr_95_interval'] is None
    assert c.get('/api/release/measurement/report', headers=h).status_code == 403
    assert c.put('/api/release/measurement/consent', headers=h, json={'enabled': False}).status_code == 200
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind.in_([growth.CONSENT, growth.EXPOSURE])))


def test_existing_save_not_conversion_admin_exclusion_and_retention(public_mode):
    c, p, _ = public_mode
    h = p['buyer']['headers']
    c.put('/api/release/offers/official-source-1/saved', headers=h)
    c.put('/api/release/measurement/consent', headers=h, json={'enabled': True})
    event(c, h); event(c, h, 'detail')
    c.put('/api/release/offers/official-source-1/saved', headers=h)
    with SessionLocal() as db:
        row = db.scalar(select(Record).where(Record.kind == growth.EXPOSURE))
        assert not row.data['saved']
        row.created = now()-31*86400; db.commit()
    assert c.get('/api/release/measurement/report', headers=p['admin']['headers']).json()['rows'] == []
    assert not c.put('/api/release/measurement/consent', headers=p['admin']['headers'], json={'enabled': True}).json()['enabled']
    assert event(c, h, nickname='must not collect').status_code == 422
    assert event(c, h, 'save').status_code == 422


def test_wilson_interval_boundaries_and_no_fake_certainty():
    assert growth.wilson(0, 0) is None
    assert growth.wilson(0, 5)[1] > .4
    low, high = growth.wilson(50, 100)
    assert .40 < low < .41 and .59 < high < .60


def test_report_unique_accounts_and_small_numerator_suppression(public_mode):
    c, p, _ = public_mode
    eligible = [p[name]['headers'] for name in ('buyer','buyer2','seller','seller2','pending')]
    for h in eligible:
        c.put('/api/release/measurement/consent', headers=h, json={'enabled': True})
        event(c, h)
        event(c, h)
    event(c, eligible[0], 'detail')
    report = c.get('/api/release/measurement/report', headers=p['admin']['headers']).json()['rows'][0]
    assert report['accounts'] == 5 and report['clicked_accounts'] is None and report['ctr'] is None
    for h in eligible[1:]: event(c, h, 'detail')
    report = c.get('/api/release/measurement/report', headers=p['admin']['headers']).json()['rows'][0]
    assert report['accounts'] == report['clicked_accounts'] == 5
    assert report['ctr'] == 1 and report['ctr_95_interval'][0] < .6
    assert '판단 보류' in report['decision']


def test_demand_interest_confirmed_and_deleted_target_erases_measurement(public_mode):
    from test_public_release import post_demand
    c, p, _ = public_mode
    demand = post_demand(c, p['buyer']['headers'])
    h = p['buyer2']['headers']
    c.put('/api/release/measurement/consent', headers=h, json={'enabled': True})
    body = {'demand_id': demand['id'], 'placement': 'demand_detail', 'channel': 'android', 'action': 'view', 'visible_ms': 1000}
    assert c.post('/api/release/measurement/events', headers=h, json=body).json()['recorded']
    assert c.post('/api/release/measurement/events', headers=h, json={**body, 'action':'interest'}).json()['recorded']
    for _ in range(2): assert c.put('/api/release/demands/'+demand['id']+'/interest', headers=h).status_code == 200
    with SessionLocal() as db:
        rows = list(db.scalars(select(Record).where(Record.kind == growth.EXPOSURE, Record.parent_id == demand['id'])))
        assert len(rows) == 1 and rows[0].data['interested'] and not rows[0].data['saved']
    assert c.delete('/api/release/demands/'+demand['id'], headers=p['buyer']['headers']).status_code == 200
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind == growth.EXPOSURE, Record.parent_id == demand['id']))
