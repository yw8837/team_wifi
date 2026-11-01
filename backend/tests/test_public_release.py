"""Public release isolation and adversarial community/auth regression cases."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from fastapi import HTTPException
from app import config, release, security
from app.db import Record, SessionLocal, Token, User
from conftest import PASSWORD


@pytest.fixture
def public_mode(monkeypatch, setup, tmp_path):
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    # Domain tests are SQLite. The deployed PostgreSQL limiter is tested separately.
    monkeypatch.setattr('app.main.beta_write_guard', lambda *a, **k: None)
    monkeypatch.setattr('app.main.charge_claimed_account', lambda *a, **k: None)
    monkeypatch.setattr('app.main.throttle', lambda *a, **k: None)
    monkeypatch.setattr('app.release.throttle', lambda *a, **k: None)
    manifest = tmp_path / 'release_catalog.json'
    entry = dict(id='official-source-1', title='공식 육아용품 정보', category='육아생활', summary='외부 공식 정보를 참고하세요.',
                 source_name='공식 출처', source_url='https://example.org/baby', source_checked_at='2026-11-02T00:00:00Z',
                 entry_type='shopping_reference', price=None, shipping_fee=None, unit=None, expires_at=None,
                 comparison_notes=['판매처에서 현재 조건을 확인하세요.'], is_affiliate=False)
    manifest.write_text(json.dumps(dict(schema_version=1, checked_at='2026-11-02T00:00:00Z', entries=[entry])), encoding='utf-8')
    monkeypatch.setattr(release, 'CATALOG_PATH', manifest)
    return setup


def post_demand(c, headers, title='물티슈 공동구매 수요'):
    r = c.post('/api/release/demands', headers=headers, json={'title': title, 'body': '물티슈 구매 조건을 함께 비교하고 싶습니다.', 'category': '육아생활'})
    assert r.status_code == 201, r.text
    return r.json()


def test_public_catalog_cannot_read_beta_or_fallback(public_mode):
    c, p, ids = public_mode
    entries = c.get('/api/release/offers').json()
    assert len(entries) == 1 and entries[0]['price'] is None and entries[0]['expires_at'] is None
    assert not entries[0]['saved'] and entries[0]['entry_type'] == 'shopping_reference'
    assert c.get('/api/release/offers/'+ids['campaign']).status_code == 404
    assert c.get('/api/release/offers?q=NOT_PRESENT').json() == []
    assert c.get('/api/release/offers?category=다른것').json() == []
    assert c.get('/api/release/offers?limit=101').status_code == 422
    assert c.get('/api/release/offers?offset=-1').status_code == 422
    release.CATALOG_PATH.unlink()
    assert c.get('/api/release/offers').status_code == 503


@pytest.mark.parametrize('method,path', [
    ('get','/api/campaigns'), ('get','/api/hotdeals'), ('get','/api/brands'), ('get','/api/saved'),
    ('get','/api/reservations'), ('get','/api/wallet'), ('get','/api/coupons'), ('get','/api/seller/application'),
    ('get','/api/admin/reports'), ('get','/api/research/summary'), ('post','/api/admin/orders'),
    ('post','/api/admin/orders/does-not-exist/refund'), ('post','/api/reports'), ('get','/public/campaigns/test'),
])
def test_public_blocks_all_legacy_surfaces(public_mode, method, path):
    c, p, _ = public_mode
    assert getattr(c, method)(path, headers=p['admin']['headers']).status_code == 404


def test_saves_auth_isolation_and_idempotence(public_mode):
    c, p, _ = public_mode
    url = '/api/release/offers/official-source-1/saved'
    assert c.put(url).status_code == 401
    for _ in range(2):
        assert c.put(url, headers=p['buyer']['headers']).json()['saved']
    assert len(c.get('/api/release/saved', headers=p['buyer']['headers']).json()) == 1
    assert c.get('/api/release/saved', headers=p['buyer2']['headers']).json() == []
    assert not c.get('/api/release/offers/official-source-1', headers={'Authorization':'Bearer expired'}).json()['saved']
    for _ in range(2):
        assert c.delete(url, headers=p['buyer']['headers']).status_code == 200
    assert c.get('/api/release/saved', headers=p['buyer']['headers']).json() == []


def test_ugc_counts_unique_accounts_auth_and_idor(public_mode):
    c, p, _ = public_mode
    assert c.post('/api/release/demands', json={}).status_code in (401,422)
    d = post_demand(c, p['buyer']['headers'])
    assert d['own'] and d['interest_count'] == d['comment_count'] == 0
    url = '/api/release/demands/'+d['id']
    assert c.delete(url, headers=p['buyer2']['headers']).status_code == 404
    assert c.get(url).json()['own'] is False
    assert c.put(url+'/interest').status_code == 401
    for _ in range(2):
        assert c.put(url+'/interest', headers=p['buyer2']['headers']).json()['interest_count'] == 1
    assert not c.get(url).json()['interested']
    assert c.put(url+'/interest', headers=p['buyer']['headers']).json()['interest_count'] == 2
    assert c.delete(url+'/interest', headers=p['buyer2']['headers']).json()['interest_count'] == 1
    comment = c.post(url+'/comments', headers=p['buyer2']['headers'], json={'body':'단위당 가격도 비교해 주세요.'}).json()
    assert c.get(url).json()['comment_count'] == 1
    assert c.delete('/api/release/comments/'+comment['id'], headers=p['buyer']['headers']).status_code == 404
    assert c.delete('/api/release/comments/'+comment['id'], headers=p['buyer2']['headers']).status_code == 200
    assert c.get(url).json()['comment_count'] == 0
    assert len(c.get('/api/release/demands?q=물티슈').json()) == 1
    assert c.get('/api/release/demands?q=%25').json() == []
    assert c.post(url+'/comments', headers=p['buyer']['headers'], json={'body':'a'*1001}).status_code == 422
    assert c.post('/api/release/demands', headers=p['buyer']['headers'], json={'title':'abc', 'body':' ', 'category':'x'}).status_code == 422


def test_concurrent_interest_is_a_single_account(public_mode):
    c, p, _ = public_mode
    d = post_demand(c, p['buyer']['headers'])
    url='/api/release/demands/'+d['id']+'/interest'
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _: c.put(url, headers=p['buyer2']['headers']).status_code, range(2)))
    assert statuses == [200,200]
    assert c.get('/api/release/demands/'+d['id']).json()['interest_count'] == 1


def test_blocking_filters_lists_details_replies_and_unblock(public_mode):
    c, p, _ = public_mode
    d=post_demand(c,p['buyer']['headers'])
    other=post_demand(c,p['buyer2']['headers'], '기저귀 조건 비교 수요')
    own='/api/release/demands/'+d['id']
    foreign='/api/release/demands/'+other['id']
    c.post(own+'/comments',headers=p['buyer2']['headers'],json={'body':'차단할 질문입니다.'})
    assert c.post('/api/blocks/'+p['buyer2']['id'], headers=p['buyer']['headers']).status_code == 200
    assert c.get('/api/blocks',headers=p['buyer']['headers']).json()==[{'id':p['buyer2']['id'],'nickname':'buyer2'}]
    assert len(c.get('/api/release/demands',headers=p['buyer']['headers']).json())==1
    assert c.get(foreign,headers=p['buyer']['headers']).status_code == 404
    assert c.get(own+'/comments',headers=p['buyer']['headers']).json() == []
    assert c.get(own,headers=p['buyer']['headers']).json()['comment_count'] == 0
    assert c.post(own+'/comments',headers=p['buyer2']['headers'],json={'body':'추가 괴롭힘 시도'}).status_code == 403
    assert c.delete('/api/blocks/'+p['buyer2']['id'],headers=p['buyer']['headers']).status_code == 200
    assert len(c.get(own+'/comments',headers=p['buyer']['headers']).json()) == 1


def test_reports_admin_hide_dismiss_suspend_and_hostile_targets(public_mode):
    c,p,ids=public_mode
    d=post_demand(c,p['buyer']['headers'])
    payload={'target_type':'demand','target_id':d['id'],'reason':'신고 처리 동작을 검증합니다.'}
    assert c.post('/api/release/reports',json=payload).status_code == 401
    assert c.post('/api/release/reports',headers=p['buyer2']['headers'],json={**payload,'target_id':ids['campaign']}).status_code == 404
    report=c.post('/api/release/reports',headers=p['buyer2']['headers'],json=payload).json()
    assert c.post('/api/release/reports',headers=p['buyer2']['headers'],json=payload).json()['id']==report['id']
    endpoint='/api/release/admin/reports/'+report['id']+'/resolve'
    assert c.get('/api/release/admin/reports',headers=p['buyer']['headers']).status_code == 403
    assert c.post(endpoint,headers=p['buyer']['headers'],json={'action':'hide'}).status_code == 403
    assert c.post(endpoint,headers=p['admin']['headers'],json={'action':'hide','note':'운영 검토 완료'}).status_code == 200
    assert c.get('/api/release/demands/'+d['id']).status_code == 404
    assert c.post(endpoint,headers=p['admin']['headers'],json={'action':'dismiss'}).status_code == 409
    user_report=c.post('/api/release/reports',headers=p['buyer']['headers'],json={'target_type':'user','target_id':p['buyer2']['id'],'reason':'이용정지 검증 요청입니다.'}).json()
    endpoint='/api/release/admin/reports/'+user_report['id']+'/resolve'
    assert c.post(endpoint,headers=p['admin']['headers'],json={'action':'hide'}).status_code == 422
    assert c.post(endpoint,headers=p['admin']['headers'],json={'action':'suspend'}).status_code == 200
    assert c.get('/api/me',headers=p['buyer2']['headers']).status_code == 401
    assert c.post('/api/auth/login',json={'email':'buyer2@example.com','password':PASSWORD}).status_code == 401
    # Moderator can dismiss a valid user report, but cannot use legacy record IDs.
    r=c.post('/api/release/reports',headers=p['buyer']['headers'],json={'target_type':'user','target_id':p['seller']['id'],'reason':'검토 후 기각할 신고'}).json()
    assert c.post('/api/release/admin/reports/'+r['id']+'/resolve',headers=p['admin']['headers'],json={'action':'dismiss'}).status_code == 200
    assert c.post('/api/release/admin/reports/'+ids['campaign']+'/resolve',headers=p['admin']['headers'],json={'action':'hide'}).status_code == 404


def signup(c, **kw):
    payload=dict(email='public@example.com',password=PASSWORD,nickname='일반회원',track='buyer',terms_accepted=True,privacy_accepted=True,adult_confirmed=True)
    return c.post('/api/auth/register',json={**payload,**kw})


def test_public_signup_recovery_and_no_local_outbox(public_mode):
    c,p,_=public_mode
    assert signup(c, adult_confirmed=False).status_code == 422
    assert signup(c, terms_accepted=False).status_code == 422
    assert signup(c, privacy_accepted=False).status_code == 422
    assert signup(c, marketing_opt_in=True).status_code == 422
    assert signup(c, track='seller').status_code == 422
    assert signup(c,is_admin=True).status_code == 422
    response=signup(c)
    assert response.status_code == 201, response.text
    result=response.json()
    assert not result['user']['email_verified'] and not result['user']['is_admin']
    h={'Authorization':'Bearer '+result['access_token']}
    assert c.post('/api/auth/reset-request',json={'email':'public@example.com'}).status_code == 200
    from app.db import RUNTIME
    assert not (RUNTIME/'outbox'/f"{result['user']['id']}.json").exists()
    assert c.post('/api/auth/reset',json={'token':'x'*32,'password':PASSWORD}).status_code == 400
    assert c.post('/api/auth/recovery-code',headers=h,json={'password':'wrong'}).status_code == 403
    rotated=c.post('/api/auth/recovery-code',headers=h,json={'password':PASSWORD}).json()['recovery_code']
    assert rotated != result['recovery_code']
    recover={'email':'public@example.com','recovery_code':rotated,'password':PASSWORD+'new'}
    assert c.post('/api/auth/recover',json=recover).status_code == 200
    assert c.get('/api/me',headers=h).status_code == 401
    assert c.post('/api/auth/recover',json=recover).status_code == 400


def test_deletion_removes_public_records_and_incoming_references(public_mode):
    c,p,_=public_mode
    d=post_demand(c,p['buyer']['headers'])
    other=post_demand(c,p['buyer2']['headers'],'기저귀 조건 비교 수요')
    url='/api/release/demands/'+d['id']
    reply=c.post(url+'/comments',headers=p['buyer2']['headers'],json={'body':'부모글 삭제 시 제거할 질문'}).json()
    c.post('/api/release/demands/'+other['id']+'/comments',headers=p['buyer']['headers'],json={'body':'탈퇴 시 제거할 질문'} )
    c.put(url+'/interest',headers=p['buyer2']['headers'])
    c.put('/api/release/demands/'+other['id']+'/interest',headers=p['buyer']['headers'])
    c.post('/api/release/reports',headers=p['buyer2']['headers'],json={'target_type':'comment','target_id':reply['id'],'reason':'관련 신고도 삭제 확인'})
    c.post('/api/blocks/'+p['buyer']['id'],headers=p['buyer2']['headers'])
    assert c.request('DELETE','/api/me',headers=p['buyer']['headers'],json={'password':'wrong'}).status_code == 403
    assert c.request('DELETE','/api/me',headers=p['buyer']['headers'],json={'password':PASSWORD}).status_code == 200
    assert c.get(url).status_code == 404
    assert c.get('/api/release/demands/'+other['id']).json()['comment_count']==0
    assert c.get('/api/release/demands/'+other['id']).json()['interest_count']==0
    assert c.get('/api/blocks',headers=p['buyer2']['headers']).json()==[]
    with SessionLocal() as db:
        assert not db.scalar(select(Token).where(Token.user_id==p['buyer']['id']))
        assert not db.scalar(select(Record).where(Record.owner_id==p['buyer']['id']))
        assert not db.get(Record,reply['id'])
        assert not db.scalar(select(Record).where(Record.kind==release.REPORT))


def test_public_policy_uses_actual_locations_and_no_beta_promise(public_mode,monkeypatch):
    c,_,_=public_mode
    monkeypatch.setattr(config,'HOSTING_LOCATION','검증된 서버 위치')
    monkeypatch.setattr(config,'DATABASE_LOCATION','검증된 DB 위치')
    privacy=c.get('/legal/privacy').text
    assert '검증된 서버 위치' in privacy and '검증된 DB 위치' in privacy
    assert '최장 90일' not in privacy and '베타 종료 후' not in privacy
    assert '회원탈퇴 또는 본인 삭제까지' in privacy and 'HMAC' in privacy
    assert '비공개 베타' not in c.get('/legal/terms').text
    conf=c.get('/api/config').json()
    assert conf['public_release'] and not conf['beta_mode'] and not conf['invite_required']


def test_public_rate_guard_is_used_and_enforced(public_mode,monkeypatch):
    c,_,_=public_mode
    calls=[]
    def reject(request):
        calls.append(request.url.path)
        raise HTTPException(429,'fixture limit',headers={'Retry-After':'7'})
    monkeypatch.setattr('app.main.beta_write_guard',reject)
    r=signup(c)
    assert r.status_code==429 and r.headers['Retry-After']=='7' and calls==['/api/auth/register']
    # Public-release claimed auth must use durable buckets, not local IP throttle.
    monkeypatch.setattr(security,'SessionLocal',lambda: (_ for _ in ()).throw(RuntimeError('durable path')))
    with pytest.raises(RuntimeError,match='durable path'):
        security.charge_claimed_account(None,'login','x@example.com')


def test_release_disabled_in_local(setup):
    c,_,_=setup
    assert c.get('/api/release/offers').status_code == 404



def test_public_startup_requires_all_deployed_safeguards(monkeypatch):
    monkeypatch.setattr(config, 'MODE', 'public_release')
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    monkeypatch.setattr(config, 'BETA', False)
    monkeypatch.setattr(config, 'PUBLIC_ORIGIN', 'http://localhost')
    with pytest.raises(RuntimeError, match='HTTPS'):
        config.validate()
    monkeypatch.setattr(config, 'PUBLIC_ORIGIN', 'https://public.example.test')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///not-production.db')
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        config.validate()
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://fixture-only-not-used')
    monkeypatch.setattr(config, 'RATE_LIMIT_SECRET', '')
    with pytest.raises(RuntimeError, match='secret'):
        config.validate()
    monkeypatch.setattr(config, 'RATE_LIMIT_SECRET', 'fixture-not-used-for-production-12345678')
    monkeypatch.setattr(config, 'SUPPORT_EMAIL', '')
    with pytest.raises(RuntimeError, match='disclosure'):
        config.validate()
    monkeypatch.setattr(config, 'SUPPORT_EMAIL', 'test@example.com')
    monkeypatch.setattr(config, 'HOSTING_LOCATION', 'localhost fixture')
    monkeypatch.setattr(config, 'DATABASE_LOCATION', 'localhost fixture')
    config.validate()


def test_suspension_hides_all_authored_public_content(public_mode):
    c, p, _ = public_mode
    d = post_demand(c, p['buyer']['headers'])
    url = '/api/release/demands/'+d['id']
    c.put(url+'/interest', headers=p['buyer2']['headers'])
    c.post(url+'/comments', headers=p['buyer2']['headers'], json={'body':'정지 후 숨길 질문'})
    r = c.post('/api/release/reports', headers=p['buyer']['headers'], json={
        'target_type':'user', 'target_id':p['buyer2']['id'], 'reason':'계정 정지 후 노출 검증'}).json()
    assert c.post('/api/release/admin/reports/'+r['id']+'/resolve', headers=p['admin']['headers'], json={'action':'suspend'}).status_code == 200
    assert c.get(url).json()['interest_count'] == 0
    assert c.get(url).json()['comment_count'] == 0
    assert c.get(url+'/comments').json() == []


def test_malformed_manifest_cannot_leak_or_use_seed(public_mode):
    c, _, _ = public_mode
    raw = json.loads(release.CATALOG_PATH.read_text(encoding='utf-8'))
    raw['entries'][0]['source_url'] = 'javascript:alert(1)'
    release.CATALOG_PATH.write_text(json.dumps(raw), encoding='utf-8')
    response = c.get('/api/release/offers')
    assert response.status_code == 503 and 'javascript' not in response.text
