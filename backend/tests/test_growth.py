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


def test_campaign_consent_dedup_privacy_retention_and_withdrawal(public_mode):
    c, people, _ = public_mode
    body = {'source': 'kakao', 'medium': 'social', 'campaign': 'community_launch', 'channel': 'web'}
    endpoint = '/api/release/measurement/campaign-visits'
    report_url = '/api/release/measurement/campaign-report'
    buyer = people['buyer']['headers']
    admin = people['admin']['headers']
    assert not c.post(endpoint, headers=buyer, json=body).json()['recorded']
    assert c.post(endpoint, headers=buyer, json={**body, 'source': 'private@example.com'}).status_code == 422
    assert c.get(report_url, headers=buyer).status_code == 403
    for name in ('buyer', 'buyer2', 'seller', 'seller2', 'pending'):
        headers = people[name]['headers']
        c.put('/api/release/measurement/consent', headers=headers, json={'enabled': True})
        for _ in range(2):
            assert c.post(endpoint, headers=headers, json=body).json()['recorded']
        if name == 'buyer':
            assert c.get(report_url, headers=admin).json()['rows'] == []
    assert c.get(report_url, headers=admin).json()['rows'] == [{**body, 'accounts': 5}]
    assert not c.post(endpoint, headers=admin, json=body).json()['recorded']
    with SessionLocal() as db:
        rows = list(db.scalars(select(Record).where(Record.kind == growth.CAMPAIGN_VISIT)))
        assert len(rows) == 5
    c.put('/api/release/measurement/consent', headers=buyer, json={'enabled': False})
    assert c.get(report_url, headers=admin).json()['rows'] == []
    with SessionLocal() as db:
        rows = list(db.scalars(select(Record).where(Record.kind == growth.CAMPAIGN_VISIT)))
        assert len(rows) == 4
        for row in rows:
            row.created = now() - 31 * 86400
        db.commit()
    c.get(report_url, headers=admin)
    with SessionLocal() as db:
        assert not db.scalar(select(Record.id).where(Record.kind == growth.CAMPAIGN_VISIT))


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


def test_visitor_dashboard_kst_period_dedup_funnel_and_privacy(public_mode, monkeypatch):
    from datetime import datetime
    c, people, _ = public_mode
    url = '/api/release/measurement/campaign-report'
    admin = people['admin']['headers']
    stamp = int(datetime.fromisoformat('2026-11-23T00:15:00+09:00').timestamp())
    monkeypatch.setattr(growth, 'now', lambda: stamp)
    assert c.get(url).status_code == 401
    assert c.get(url, headers=people['buyer']['headers']).status_code == 403
    assert c.get(url+'?period=today', headers=admin).json()['dashboard']['visitors'] == 0
    for name in ('buyer', 'buyer2', 'seller', 'seller2', 'pending'):
        h = people[name]['headers']
        c.put('/api/release/measurement/consent', headers=h, json={'enabled': True})
    with SessionLocal() as db:
        accounts = list(db.scalars(select(Record.owner_id).where(Record.kind == growth.CONSENT)))
        for i, account in enumerate(accounts):
            for label, ts in [('today', stamp-60), ('yesterday', stamp-3600), ('lastmonth', stamp-14*86400)]:
                db.add(Record(kind=growth.EXPOSURE, owner_id=account, unique_key=f'{i}:{label}', created=ts,
                              data={'placement':'groupbuy_detail', 'clicks':{'source':ts+10} if i == 0 else {}}))
            db.add(Record(kind=growth.CAMPAIGN_VISIT, owner_id=account, unique_key=f'campaign:{i}', created=stamp-100,
                          data={'source':'kakao','medium':'share','campaign':'groupbuy','channel':'web'}))
        db.commit()
    report = c.get(url+'?period=week', headers=admin).json()
    data = report['dashboard']
    assert (data['visitors'], data['detail_readers'], data['outbound']) == (5, 5, None)
    assert (data['start'], data['end']) == ('2026-11-17','2026-11-23')
    assert [d['accounts'] for d in data['days']] == [0,0,0,0,0,5,5]
    assert report['rows'][0]['accounts'] == 5
    prev = c.get(url+'?period=custom&start=2026-11-22&end=2026-11-22', headers=admin).json()
    assert prev['rows'] == [] and prev['dashboard']['days'] == [{'date':'2026-11-22','accounts':5,'web_opens':None}]
    assert len(c.get(url+'?period=month',headers=admin).json()['dashboard']['days']) == 30
    assert c.get(url+'?period=all',headers=admin).json()['dashboard']['start'] == '2026-10-24'
    for params in ('period=custom', 'period=custom&start=2026-11-24&end=2026-11-23',
                   'period=custom&start=2026-10-10&end=2026-11-23', 'period=today&start=2026-11-23'):
        assert c.get(url+'?'+params,headers=admin).status_code == 422
    with SessionLocal() as db:
        for row in db.scalars(select(Record).where(Record.kind == growth.EXPOSURE, Record.created == stamp-60)):
            row.data = {**row.data, 'clicks': {'source': stamp-5}}
        db.commit()
    assert c.get(url+'?period=today',headers=admin).json()['dashboard']['outbound'] == 5
    c.put('/api/release/measurement/consent',headers=people['buyer']['headers'],json={'enabled':False})
    hidden = c.get(url+'?period=today',headers=admin).json()
    assert hidden['dashboard']['visitors'] is None and hidden['dashboard']['days'][0]['accounts'] is None
    assert hidden['rows'] == []

def test_public_web_opens_and_opt_in_daily_members_are_separate(public_mode, monkeypatch):
    from datetime import datetime
    c, people, _ = public_mode
    window = '/api/release/measurement/campaign-report?period='
    opens = '/api/release/measurement/web-opens'
    member = '/api/release/measurement/member-visits'
    buyer, admin = people['buyer']['headers'], people['admin']['headers']
    origin = 'https://public.example'
    monkeypatch.setattr(growth.config, 'PUBLIC_WEB_ORIGIN', origin)
    stamp = int(datetime.fromisoformat('2026-11-23T23:59:30+09:00').timestamp())
    monkeypatch.setattr(growth, 'now', lambda: stamp)
    web = {'Origin': origin, 'X-Moduyuga-Client': 'web'}
    assert c.get(window + 'today', headers=admin).json()['dashboard']['web_opens'] is None
    assert c.post(opens).status_code == 403
    assert c.post(opens, headers={**web, 'Origin':'https://other.example'}).status_code == 403
    assert c.post(opens, headers={**web, **buyer}).status_code == 403
    assert c.post(opens, headers=web).status_code == 202
    assert c.post(opens + '?shared=true', headers=web).status_code == 202
    assert c.post(member).status_code == 401
    assert not c.post(member, headers=buyer).json()['recorded']
    assert not c.post(member, headers=admin).json()['recorded']
    before = c.get(window + 'week', headers=admin).json()['dashboard']
    assert before['visitors'] == 0 and before['web_opens'] == 2 and before['shared_opens'] == 1
    assert [d['web_opens'] for d in before['days']] == [None] * 6 + [2]
    c.put('/api/release/measurement/consent', headers=buyer, json={'enabled': True})
    for _ in range(2):
        assert c.post(member, headers=buyer).json()['recorded']
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Record).where(Record.kind == growth.MEMBER_DAY)))) == 1
        daily = db.scalar(select(Record).where(Record.kind == growth.WEB_OPENS))
        assert daily.owner_id is None and daily.unique_key == '2026-11-23' and daily.data == {}
    stamp += 60
    next_day = c.get(window + 'today', headers=admin).json()['dashboard']
    assert next_day['visitors'] == next_day['web_opens'] == 0
    assert c.post(member, headers=buyer).json()['recorded']
    both = c.get(window + 'week', headers=admin).json()['dashboard']
    assert both['visitors'] is None and [d['accounts'] for d in both['days'][-2:]] == [None, None]
    assert c.put('/api/release/measurement/consent', headers=buyer, json={'enabled': False}).status_code == 200
    after = c.get(window + 'week', headers=admin).json()['dashboard']
    assert after['visitors'] == 0 and after['web_opens'] == 2


def test_personal_link_estimate_is_private_and_never_adds_to_measured_visits(public_mode):
    from app.db import User
    c, people, _ = public_mode
    admin, buyer = people['admin']['headers'], people['buyer']['headers']
    day = growth.kst_date(now()).isoformat()
    target = '/api/release/measurement/link-estimates/' + day
    url = '/api/release/measurement/campaign-report?period=today'
    assert c.put(target, headers=buyer, json={'count':9}).status_code == 403
    assert c.put(target, headers=admin, json={'count':-1}).status_code == 422
    assert c.put(target, headers=admin, json={'count':9}).status_code == 200
    data = c.get(url, headers=admin).json()['dashboard']
    assert data['days'][0]['link_estimate'] == 9
    assert data['visitors'] == 0 and data['web_opens'] is None
    counts = {'visitors': 10, 'detail': 4, 'outbound': 3}
    assert c.put(target, headers=admin, json={'count':9, 'funnel':{**counts, 'outbound':8}}).status_code == 422
    assert c.put(target, headers=admin, json={'count':9, 'funnel':counts}).status_code == 200
    report = c.get(url, headers=admin).json()['dashboard']
    assert report['days'][0]['campaign_estimate'] == counts and report['visitors'] == 0
    assert c.put(target, headers=admin, json={'count':11}).status_code == 422
    buyer_id = c.get('/api/me', headers=buyer).json()['id']
    with SessionLocal() as db:
        db.get(User, buyer_id).is_admin = True
        db.commit()
    assert 'link_estimate' not in c.get(url, headers=buyer).json()['dashboard']['days'][0]
    assert c.put(target, headers=admin, json={'count':None}).status_code == 200
    assert 'link_estimate' not in c.get(url, headers=admin).json()['dashboard']['days'][0]
