import pytest
from sqlalchemy import select
from app.db import Record, SessionLocal, User
from test_public_release import public_mode, post_demand
from test_social_auth import oauth, flow, enroll


def test_kakao_profile_preserves_identity_data_roles_and_other_sessions(oauth):
    c, people, _ = oauth
    proof, _, _ = flow(c, 'kakao')
    account = enroll(c, proof).json()
    headers = {'Authorization': 'Bearer '+account['access_token']}
    old_user = account['user']
    assert old_user['has_password'] is False
    assert c.put('/api/release/offers/official-source-1/saved', headers=headers).status_code == 200
    preferences = {'categories': ['기저귀·물티슈'], 'priority': 'unit_price'}
    assert c.put('/api/release/preferences', headers=headers, json=preferences).status_code == 200
    demand = post_demand(c, headers)
    with SessionLocal() as db:
        identity = db.scalar(select(Record).where(Record.kind == 'oauth_identity', Record.owner_id == old_user['id']))
        before = (identity.id, identity.unique_key, identity.data.copy())
    response = c.put('/api/auth/profile', headers=headers, json={'nickname': '  바뀐이름  '})
    assert response.status_code == 200, response.text
    assert response.json() == {**old_user, 'nickname': '바뀐이름'}
    # Independent Android-style sign-in still resolves the same account.
    proof, _, _ = flow(c, 'kakao', platform='android')
    second = c.post('/api/auth/social/claim', json=proof).json()
    assert second['user'] == response.json()
    second_headers = {'Authorization': 'Bearer '+second['access_token']}
    assert c.get('/api/me', headers=second_headers).json() == response.json()
    assert len(c.get('/api/release/saved', headers=second_headers).json()) == 1
    assert c.get('/api/release/preferences', headers=second_headers).json() == preferences
    assert c.get('/api/release/demands/'+demand['id']).json()['author']['nickname'] == '바뀐이름'
    assert c.get('/api/release/saved', headers=people['buyer']['headers']).json() == []
    with SessionLocal() as db:
        identity = db.scalar(select(Record).where(Record.kind == 'oauth_identity', Record.owner_id == old_user['id']))
        assert (identity.id, identity.unique_key, identity.data) == before
        assert db.get(User, old_user['id']).password_hash == '!social-only'
    assert c.put('/api/auth/profile', headers=headers, json={'nickname': '바뀐이름'}).json() == response.json()


def test_profile_auth_ownership_and_field_allowlist(public_mode):
    c, people, _ = public_mode
    headers = people['buyer']['headers']
    original = c.get('/api/me', headers=headers).json()
    other = c.get('/api/me', headers=people['buyer2']['headers']).json()
    assert c.put('/api/auth/profile', json={'nickname':'다른이름'}).status_code == 401
    for extra in ({'id':other['id']}, {'user_id':other['id']}, {'email':'other@example.com'}, {'is_admin':True}, {'seller_status':'approved'}):
        assert c.put('/api/auth/profile', headers=headers, json={'nickname':'다른이름', **extra}).status_code == 422
    assert c.get('/api/me', headers=headers).json() == original
    assert c.get('/api/me', headers=people['buyer2']['headers']).json() == other
    assert c.put('/api/auth/profile', headers=people['admin']['headers'], json={'nickname':'운영이름'}).json()['is_admin'] is True


@pytest.mark.parametrize('nickname', ['', ' ', '가', '가'*31, '이름\n줄', '이름\x00', '이름\u202e'])
def test_invalid_profile_keeps_previous_name(public_mode, nickname):
    c, people, _ = public_mode
    headers = people['buyer']['headers']
    before = c.get('/api/me', headers=headers).json()
    assert c.put('/api/auth/profile', headers=headers, json={'nickname':nickname}).status_code == 422
    assert c.get('/api/me', headers=headers).json() == before
