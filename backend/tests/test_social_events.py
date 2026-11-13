from types import SimpleNamespace
import secrets

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app import social_auth as social, social_events as events
from app.db import Record, SessionLocal, User, now
from test_social_auth import oauth, flow, enroll
from test_public_release import public_mode


@pytest.fixture
def send_event(oauth, monkeypatch):
    c, _, _ = oauth
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(events, 'event_jwks', lambda: SimpleNamespace(
        get_signing_key_from_jwt=lambda encoded: SimpleNamespace(key=key.public_key())))
    def send(sub='subject-new', change=None, header=None, signing_key=None):
        claims = {'aud': 'fixture-client', 'iss': events.ISSUER, 'iat': now(), 'toe': now(),
                  'jti': secrets.token_urlsafe(24), 'sub': sub, 'events': {events.UNLINK: {
                      'subject': {'subject_type': 'iss-sub', 'iss': events.ISSUER, 'sub': sub},
                      'reason': 'UNLINK_FROM_APPS'}}, **(change or {})}
        encoded = jwt.encode(claims, signing_key or key, algorithm='RS256',
                             headers={'typ': 'secevent+jwt', **(header or {})})
        return c.post('/api/auth/social/kakao/events', content=encoded,
                      headers={'Content-Type': 'application/secevent+jwt'})
    return send


@pytest.mark.parametrize('change', [
    {'aud': 'another-app'}, {'iss': 'https://evil.example'}, {'iat': 1},
    {'iat': now()+3600}, {'events': []}, {'sub': 'different-user'}, {'jti': ''},
])
def test_set_rejects_untrusted_claims(oauth, send_event, change):
    assert send_event(change=change).status_code == 400
    c, people, _ = oauth
    assert c.get('/api/me', headers=people['buyer']['headers']).status_code == 200


def test_set_rejects_id_token_and_bad_signature(oauth, send_event):
    assert send_event(header={'typ': 'JWT'}).status_code == 400
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert send_event(signing_key=attacker).status_code == 400
    c, _, _ = oauth
    assert c.post('/api/auth/social/kakao/events', json={'sub': 'subject-new'}).status_code == 400


def test_unlink_preserves_password_account_revokes_sessions_and_stale_flow(oauth, send_event):
    c, people, _ = oauth
    h = people['buyer']['headers']
    proof, _, _ = flow(c, 'kakao', 'link', h)
    assert c.post('/api/auth/social/claim', headers=h, json=proof).json()['status'] == 'linked'
    stale, _, _ = flow(c, 'kakao')
    result = send_event(change={'jti': 'repeatable-event'})
    assert result.status_code == 202 and result.content == b''
    assert c.get('/api/me', headers=h).status_code == 401
    assert c.post('/api/auth/social/claim', json=stale).status_code == 400
    assert send_event(change={'jti': 'repeatable-event'}).status_code == 202
    with SessionLocal() as db:
        assert not db.get(User, people['buyer']['id']).deleted
        assert not db.scalar(select(Record.id).where(Record.kind == social.IDENTITY))
        receipts = list(db.scalars(select(Record).where(Record.kind == events.RECEIPT)))
        assert len(receipts) == 1 and receipts[0].data == {} and receipts[0].owner_id is None


def test_sole_social_account_unlink_erases_owned_content(oauth, send_event):
    c, _, _ = oauth
    proof, _, _ = flow(c, 'kakao')
    account = enroll(c, proof).json()
    with SessionLocal() as db:
        db.add(Record(kind='release_save', owner_id=account['user']['id'], parent_id='fixture', data={}))
        db.add(Record(kind='activity_consent', owner_id=account['user']['id'], data={'enabled': True}))
        db.commit()
    assert send_event().status_code == 202
    with SessionLocal() as db:
        user = db.get(User, account['user']['id'])
        assert user.deleted and user.nickname == '탈퇴한 회원'
        assert not db.scalar(select(Record.id).where(Record.owner_id == user.id))
    assert c.get('/api/me', headers={'Authorization': 'Bearer '+account['access_token']}).status_code == 401


def test_other_provider_and_newer_link_survive(oauth, send_event):
    c, _, _ = oauth
    proof, _, _ = flow(c, 'kakao')
    account = enroll(c, proof).json()
    h = {'Authorization': 'Bearer '+account['access_token']}
    linked, _, _ = flow(c, 'google', 'link', h)
    assert c.post('/api/auth/social/claim', headers=h, json=linked).status_code == 200
    with SessionLocal() as db:
        identity = db.scalar(select(Record).where(Record.kind == social.IDENTITY,
                              Record.unique_key == social.identity_key('kakao', 'subject-new')))
        identity.created = now()-5
        db.commit()
    assert send_event(change={'toe': now()-10}).status_code == 202
    assert c.get('/api/me', headers=h).status_code == 200
    assert send_event().status_code == 202
    with SessionLocal() as db:
        assert not db.get(User, account['user']['id']).deleted
        identities = list(db.scalars(select(Record).where(Record.kind == social.IDENTITY)))
        assert len(identities) == 1 and identities[0].data['provider'] == 'google'


def test_signed_other_event_acknowledged_without_account_change(oauth, send_event):
    c, people, _ = oauth
    assert send_event(change={'events': {'https://schemas.openid.net/secevent/risc/event-type/verification': {}}}).status_code == 202
    assert c.get('/api/me', headers=people['buyer']['headers']).status_code == 200


def test_key_service_outage_is_retryable(oauth, send_event, monkeypatch):
    def unavailable(encoded):
        raise jwt.PyJWKClientConnectionError('fixture outage')
    monkeypatch.setattr(events, 'decode_event', unavailable)
    result = send_event()
    assert result.status_code == 503 and result.headers['retry-after'] == '10'
