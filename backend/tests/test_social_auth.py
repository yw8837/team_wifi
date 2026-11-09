from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import pytest
from sqlalchemy import select
from app import config, social_auth as social
from app.db import SessionLocal, Record, User, now
from conftest import PASSWORD
from test_public_release import public_mode


@pytest.fixture
def oauth(public_mode, monkeypatch):
    monkeypatch.setattr(config, 'PUBLIC_ORIGIN', 'https://api.example.com')
    monkeypatch.setattr(config, 'PUBLIC_WEB_ORIGIN', 'https://app.example.com')
    for provider in ('GOOGLE', 'KAKAO'):
        monkeypatch.setenv(provider+'_CLIENT_ID', 'fixture-client')
        monkeypatch.setenv(provider+'_CLIENT_SECRET', 'fixture-secret')
    monkeypatch.setattr(social, 'global_write_guard', lambda *args: None)
    monkeypatch.setattr(social, 'exchange', lambda provider, code, flow: 'subject-'+code)
    return public_mode


def flow(c, provider='google', purpose='login', headers=None, code='new', platform='web'):
    verifier = 'a'*43
    r = c.post('/api/auth/social/'+provider+'/start', headers=headers, json={
        'challenge': social.challenge(verifier), 'purpose': purpose, 'platform': platform})
    assert r.status_code == 200, r.text
    started = r.json()
    query = parse_qs(urlsplit(started['authorization_url']).query)
    assert query['scope'] == ['openid']
    callback = c.get('/api/auth/social/'+provider+'/callback', params={'state': query['state'][0], 'code': code}, follow_redirects=False)
    assert callback.status_code == 303, callback.text
    assert 'access_token' not in callback.headers['location'] and 'fixture-secret' not in callback.headers['location']
    return {'flow_id': started['flow_id'], 'verifier': verifier}, query, callback


def test_kakao_other_account_requires_provider_login(oauth):
    client, _, _ = oauth
    body = {'challenge': social.challenge('a'*43), 'purpose': 'login', 'platform': 'web'}
    ordinary = client.post('/api/auth/social/kakao/start', json=body)
    assert ordinary.status_code == 200
    assert 'prompt' not in parse_qs(urlsplit(ordinary.json()['authorization_url']).query)
    switched = client.post('/api/auth/social/kakao/start', json={**body, 'force_login': True})
    assert switched.status_code == 200
    query = parse_qs(urlsplit(switched.json()['authorization_url']).query)
    assert query['prompt'] == ['login'] and query['scope'] == ['openid']
    assert query['state'] and query['nonce']
    assert client.post('/api/auth/social/kakao/start', json={**body, 'force_login': 'yes'}).status_code == 422


def enroll(c, proof):
    assert c.post('/api/auth/social/claim', json=proof).json()['status'] == 'onboarding'
    return c.post('/api/auth/social/claim', json={**proof, 'nickname': '소셜회원', 'terms_accepted': True,
                  'privacy_accepted': True, 'adult_confirmed': True})


def test_social_new_account_login_replay_and_no_email(oauth):
    c, _, _ = oauth
    proof, query, _ = flow(c)
    assert 'code_challenge' in query
    assert c.post('/api/auth/social/claim', json={**proof, 'verifier': 'b'*43}).status_code == 400
    result = enroll(c, proof)
    assert result.status_code == 200, result.text
    account = result.json()
    assert account['user']['email'] == '' and account['user']['has_password'] is False
    assert c.post('/api/auth/social/claim', json=proof).status_code == 400
    assert c.get('/api/auth/social/google/callback', params={'state': query['state'][0], 'code': 'new'}).status_code == 400
    again, _, _ = flow(c)
    signed_in = c.post('/api/auth/social/claim', json=again).json()
    assert signed_in['user']['id'] == account['user']['id']
    assert signed_in['access_token'] != account['access_token']


def test_existing_account_links_without_new_account_and_android_handoff(oauth):
    c, people, _ = oauth
    h = people['buyer']['headers']
    assert c.post('/api/auth/social/google/start', json={'challenge': 'x'*43, 'purpose': 'link'}).status_code == 401
    proof, _, callback = flow(c, 'kakao', 'link', h, platform='android')
    assert callback.headers['location'].startswith('kr.moduyuga.app://auth/complete?flow=')
    assert c.post('/api/auth/social/claim', headers=people['buyer2']['headers'], json=proof).status_code == 403
    assert c.post('/api/auth/social/claim', headers=h, json=proof).json()['status'] == 'linked'
    proof, _, _ = flow(c, 'kakao')
    assert c.post('/api/auth/social/claim', json=proof).json()['user']['id'] == people['buyer']['id']
    proof, _, _ = flow(c, 'kakao', 'link', people['buyer2']['headers'])
    assert c.post('/api/auth/social/claim', headers=people['buyer2']['headers'], json=proof).status_code == 409


def test_social_reauth_account_delete_and_subject_isolation(oauth):
    c, _, _ = oauth
    proof, _, _ = flow(c)
    account = enroll(c, proof).json()
    h = {'Authorization': 'Bearer '+account['access_token']}
    assert c.request('DELETE', '/api/me', headers=h, json={'password': 'wrong'}).status_code == 403
    proof, _, _ = flow(c, purpose='reauth', headers=h, code='different')
    assert c.post('/api/auth/social/claim', headers=h, json=proof).status_code == 403
    proof, _, _ = flow(c, purpose='reauth', headers=h)
    reauth = c.post('/api/auth/social/claim', headers=h, json=proof).json()['reauth_token']
    assert c.request('DELETE', '/api/me', headers=h, json={'reauth_token': reauth}).status_code == 200
    assert c.get('/api/me', headers=h).status_code == 401
    with SessionLocal() as db:
        assert not db.scalar(select(Record).where(Record.kind == social.IDENTITY, Record.owner_id == account['user']['id']))


def test_wrong_provider_state_expired_and_denial(oauth):
    c, _, _ = oauth
    response = c.post('/api/auth/social/google/start', json={'challenge': 'a'*43}).json()
    state = parse_qs(urlsplit(response['authorization_url']).query)['state'][0]
    assert c.get('/api/auth/social/kakao/callback', params={'state': state, 'code': 'new'}).status_code == 400
    with SessionLocal() as db:
        row = db.get(Record, response['flow_id']); row.ends = now()-1; db.commit()
    assert c.get('/api/auth/social/google/callback', params={'state': state, 'code': 'new'}).status_code == 400


def test_password_auth_roundtrip_and_duplicate_feedback(public_mode):
    c, _, _ = public_mode
    body = {'email': 'roundtrip@example.com', 'nickname': '가입확인', 'password': PASSWORD, 'track': 'buyer',
            'terms_accepted': True, 'privacy_accepted': True, 'adult_confirmed': True}
    created = c.post('/api/auth/register', json=body)
    assert created.status_code == 201 and created.json()['recovery_code']
    logged = c.post('/api/auth/login', json={'email': body['email'], 'password': PASSWORD})
    assert logged.status_code == 200
    assert logged.json()['user']['id'] == created.json()['user']['id']
    assert '가입된 계정' in c.post('/api/auth/register', json=body).json()['detail']
    assert c.post('/api/auth/login', json={'email': body['email'], 'password': 'wrong'}).status_code == 401


@pytest.mark.parametrize('change', [{'aud': 'attacker'}, {'iss': 'https://evil.example'}, {'nonce': 'wrong'}, {'exp': 1}, {'iat': 1}, {'azp': 'attacker'}])
def test_real_jwt_verification_rejects_wrong_claims(monkeypatch, change):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    claims = {'sub': '123', 'aud': 'client', 'iss': social.ENDPOINTS['google'][3], 'iat': now(), 'exp': now()+300, 'nonce': 'nonce', 'auth_time': now(), **change}
    encoded = jwt.encode(claims, key, algorithm='RS256')
    monkeypatch.setattr(social, 'settings', lambda provider: ('client', 'secret'))
    monkeypatch.setattr(social, 'jwks', lambda provider: SimpleNamespace(get_signing_key_from_jwt=lambda value: SimpleNamespace(key=key.public_key())))
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'id_token': encoded}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(social.httpx, 'Client', Client)
    with pytest.raises((jwt.PyJWTError, ValueError)):
        social.exchange('google', 'code', SimpleNamespace(data={'nonce': 'nonce', 'pkce': 'proof', 'purpose': 'reauth'}))

@pytest.mark.parametrize('platform', ['web', 'android'])
def test_expired_browser_callback_has_safe_recovery(oauth, platform):
    client, _, _ = oauth
    started = client.post('/api/auth/social/kakao/start', json={
        'challenge': 'a' * 43, 'platform': platform}).json()
    state = parse_qs(urlsplit(started['authorization_url']).query)['state'][0]
    with SessionLocal() as db:
        record = db.get(Record, started['flow_id'])
        record.ends = now() - 1
        db.commit()
    response = client.get('/api/auth/social/kakao/callback',
        params={'state': state, 'code': 'private-provider-code'},
        headers={'Accept': 'text/html'}, follow_redirects=False)
    assert response.status_code == 400
    assert response.headers['content-type'].startswith('text/html')
    assert '로그인을 다시 시작해 주세요' in response.text
    target = ('kr.moduyuga.app://auth/complete?flow=' + started['flow_id']
              if platform == 'android' else 'https://app.example.com/login')
    assert target in response.text
    assert state not in response.text and 'private-provider-code' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    with SessionLocal() as db:
        assert db.get(Record, started['flow_id']).status == 'pending'
