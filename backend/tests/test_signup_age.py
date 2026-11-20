"""Registration policy, legacy-client compatibility and truthful consent history."""
import pytest
from sqlalchemy import select
from app.db import SessionLocal, Record, User
from conftest import PASSWORD
from test_public_release import public_mode
from test_social_auth import oauth, flow


@pytest.mark.parametrize('age_fields,expected', [
    ({'age_confirmed': True}, 201),
    ({'age_confirmed': True, 'adult_confirmed': False}, 201),
    ({'age_confirmed': False}, 422),
    ({}, 422),
    ({'adult_confirmed': True}, 201),
    ({'adult_confirmed': False}, 422),
    ({'age_confirmed': False, 'adult_confirmed': True}, 422),
    ({'age_confirmed': None, 'adult_confirmed': True}, 422),
    ({'age_confirmed': 'true'}, 422),
    ({'age_confirmed': 1}, 422),
])
def test_email_signup_age_and_consent_history(public_mode, age_fields, expected):
    c, _, _ = public_mode
    body = dict(email='age-policy@example.com', password=PASSWORD, nickname='커뮤니티회원',
                track='buyer', terms_accepted=True, privacy_accepted=True, **age_fields)
    result = c.post('/api/auth/register', json=body)
    assert result.status_code == expected, result.text
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == body['email']))
        if expected != 201:
            assert user is None
            return
        consent = db.scalar(select(Record).where(Record.kind == 'audit', Record.owner_id == user.id))
        current = 'age_confirmed' in age_fields
        assert consent.data['action'] == (
            'public-terms-20261105-privacy-20261105-age14-self-confirmed' if current else
            'public-terms-20261102-privacy-20261102-legacy-age18-self-confirmed')
    # Existing login never asks the member to declare age again.
    assert c.post('/api/auth/login', json={'email': body['email'], 'password': PASSWORD}).status_code == 200


@pytest.mark.parametrize('provider', ['kakao', 'google'])
@pytest.mark.parametrize('age_fields,accepted', [
    ({'age_confirmed': True}, True),
    ({'adult_confirmed': True}, True),
    ({}, False),
    ({'age_confirmed': False, 'adult_confirmed': True}, False),
    ({'age_confirmed': None, 'adult_confirmed': True}, False),
])
def test_social_first_signup_and_retry_share_age_policy(oauth, provider, age_fields, accepted):
    c, _, _ = oauth
    proof, _, _ = flow(c, provider=provider)
    body = {**proof, 'nickname': '소셜회원', 'terms_accepted': True,
            'privacy_accepted': True, **age_fields}
    result = c.post('/api/auth/social/claim', json=body)
    assert result.status_code == 200, result.text
    if not accepted:
        assert result.json()['status'] == 'onboarding'
        with SessionLocal() as db:
            assert not db.scalar(select(Record.id).where(Record.kind == 'oauth_identity'))
            assert db.get(Record, proof['flow_id']).status == 'ready'
        # Confirming age later succeeds with the same pending OAuth flow.
        result = c.post('/api/auth/social/claim', json={**body, 'age_confirmed': True})
    assert result.json()['status'] == 'authenticated'
    with SessionLocal() as db:
        audit = db.scalar(select(Record).where(Record.kind == 'audit', Record.owner_id == result.json()['user']['id']))
        assert audit.data['action'] == (
            'social-terms-20261102-privacy-20261102-legacy-age18-self-confirmed'
            if accepted and 'age_confirmed' not in age_fields else
            'social-terms-20261105-privacy-20261105-age14-self-confirmed')
    again, _, _ = flow(c, provider=provider)
    assert c.post('/api/auth/social/claim', json=again).json()['status'] == 'authenticated'


def test_current_legal_documents_explain_age_self_declaration(public_mode):
    c, _, _ = public_mode
    terms = c.get('/legal/terms').text
    privacy = c.get('/legal/privacy').text
    for page in (terms, privacy):
        assert '만 14세 이상' in page
        assert '2026년 11월 6일' in page
    assert '만 18세 이상 이용자가' not in terms
    assert '이메일과 소셜 가입에 같은 기준' in terms
    assert '법정대리인의 동의·확인 절차는 제공하지 않습니다' in terms
    assert '생년월일·신분증을 수집하거나 본인·성인 인증을 수행하지 않습니다' in privacy
    assert '이전 가입·앱의 만 18세 이상 확인 기록' in privacy
