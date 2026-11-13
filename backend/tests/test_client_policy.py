import pytest
from sqlalchemy import func, select
from app.db import Record, SessionLocal, Token
from app import social_auth
from conftest import PASSWORD
from test_public_release import public_mode
from test_social_auth import oauth, flow


@pytest.mark.parametrize('signal', [
    {'X-Moduyuga-Client': 'android'}, {'User-Agent': 'Mozilla Android Mobile'},
    {'User-Agent': 'Mozilla iPad'}, {'Sec-CH-UA-Mobile': '?1'},
    {'Origin': 'https://localhost'},
])
def test_mobile_operator_login_retains_server_role_checks(public_mode, signal):
    client, people, _ = public_mode
    admin_id = people['admin']['id']
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Token).where(Token.user_id == admin_id))
    result = client.post('/api/auth/login', headers=signal, json={'email': 'admin@example.com', 'password': PASSWORD})
    assert result.status_code == 200 and result.json()['user']['is_admin'] is True
    assert result.json()['access_token']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Token).where(Token.user_id == admin_id)) == before+1
    assert client.get('/api/me', headers={**people['admin']['headers'], **signal}).status_code == 200
    assert client.get('/api/release/admin/reports', headers={**people['buyer']['headers'], **signal}).status_code == 403
    assert client.get('/api/release/admin/reports', headers={**people['admin']['headers'], **signal}).status_code == 200
    assert client.post('/api/auth/login', headers=signal, json={'email': 'buyer@example.com', 'password': PASSWORD}).status_code == 200


def test_desktop_operator_still_works_and_wrong_password_is_not_enumerated(public_mode):
    client, _, _ = public_mode
    body = {'email': 'admin@example.com', 'password': PASSWORD}
    assert client.post('/api/auth/login', json=body).status_code == 200
    assert client.post('/api/auth/login', headers={'X-Moduyuga-Client': 'android'},
                       json={**body, 'password': 'incorrect'}).status_code == 401


@pytest.mark.parametrize('platform,headers', [('android', {}), ('web', {'User-Agent': 'Android Mobile'})])
def test_operator_social_login_supports_both_clients_with_same_identity(oauth, platform, headers):
    client, people, _ = oauth
    with SessionLocal() as db:
        db.add(Record(kind=social_auth.IDENTITY, owner_id=people['admin']['id'],
                      unique_key=social_auth.identity_key('kakao', 'subject-operator'),
                      data={'provider': 'kakao', 'subject': 'subject-operator'}))
        db.commit()
    proof, _, _ = flow(client, 'kakao', headers=headers, code='operator', platform=platform)
    result = client.post('/api/auth/social/claim', json=proof)
    assert result.status_code == 200 and result.json()['user']['id'] == people['admin']['id']
    desktop, _, _ = flow(client, 'kakao', code='operator')
    assert client.post('/api/auth/social/claim', json=desktop).json()['status'] == 'authenticated'
