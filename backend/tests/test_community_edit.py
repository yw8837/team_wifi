"""Author editing keeps identity/counts and rejects stale or inaccessible writes."""
import pytest
from sqlalchemy import select
from app.db import Record, SessionLocal, Token, User
from app import security
from test_public_release import public_mode, post_demand


def payload(revision=1, **changes):
    return dict(title='수정한 육아용품 질문', body='세척 방법과 구성품을 함께 비교하고 싶어요.', category='육아생활', revision=revision, **changes)


def test_author_edit_is_shared_and_preserves_replies_and_interest(public_mode):
    c, p, _ = public_mode
    original = post_demand(c, p['buyer']['headers'])
    url = '/api/release/demands/' + original['id']
    c.put(url+'/interest', headers=p['buyer2']['headers'])
    comment = c.post(url+'/comments', headers=p['buyer2']['headers'], json={'body':'세척 주기도 궁금합니다.'}).json()
    changed = c.put(url, headers=p['buyer']['headers'], json=payload())
    assert changed.status_code == 200, changed.text
    data = changed.json()
    assert data['id'] == original['id'] and data['author'] == original['author']
    assert data['created_at'] == original['created_at'] and data['updated_at']
    assert data['revision'] == 2 and data['interest_count'] == data['comment_count'] == 1
    assert c.get(url).json()['title'] == payload()['title']
    assert c.get(url+'/comments').json()[0]['id'] == comment['id']
    assert c.put(url, headers=p['buyer']['headers'], json=payload()).status_code == 409
    assert c.get(url).json()['revision'] == 2


def test_comment_edit_persists_and_keeps_parent_count(public_mode):
    c, p, _ = public_mode
    original = post_demand(c, p['buyer']['headers'])
    parent = '/api/release/demands/' + original['id']
    comment = c.post(parent+'/comments', headers=p['buyer2']['headers'], json={'body':'기존 댓글 내용'}).json()
    url = '/api/release/comments/' + comment['id']
    edited = {'body':'<script>alert(1)</script> 수정한 질문', 'revision':1}
    assert c.put(url, headers=p['buyer']['headers'], json=edited).status_code == 404
    response = c.put(url, headers=p['buyer2']['headers'], json=edited)
    assert response.status_code == 200
    assert response.json()['revision'] == 2 and response.json()['updated_at']
    assert response.json()['created_at'] == comment['created_at']
    assert c.get(parent+'/comments').json()[0]['body'] == edited['body']
    assert c.get(parent).json()['comment_count'] == 1
    assert c.put(url, headers=p['buyer2']['headers'], json=edited).status_code == 409


@pytest.mark.parametrize('invalid', [
    {'title':' '}, {'body':'short'}, {'body':'x'*3001}, {'revision':0},
    {'revision':True}, {'revision':'1'}, {'owner_id':'someone'}, {'status':'active'},
])
def test_edit_validates_and_cannot_reassign_or_unhide(public_mode, invalid):
    c, p, _ = public_mode
    original = post_demand(c,p['buyer']['headers'])
    url = '/api/release/demands/' + original['id']
    assert c.put(url, headers=p['buyer']['headers'], json={**payload(),**invalid}).status_code == 422
    assert c.get(url).json()['title'] == original['title']


def test_edit_requires_owner_active_parent_and_active_content(public_mode):
    c, p, _ = public_mode
    original = post_demand(c,p['buyer']['headers'])
    url = '/api/release/demands/' + original['id']
    assert c.put(url,json=payload()).status_code == 401
    assert c.put(url,headers=p['buyer2']['headers'],json=payload()).status_code == 404
    assert c.put(url,headers=p['admin']['headers'],json=payload()).status_code == 404
    comment = c.post(url+'/comments',headers=p['buyer2']['headers'],json={'body':'기존 질문 내용'}).json()
    edit_url='/api/release/comments/'+comment['id']
    c.post('/api/blocks/'+p['buyer2']['id'], headers=p['buyer']['headers'])
    assert c.put(edit_url,headers=p['buyer2']['headers'],json={'body':'새 질문 내용','revision':1}).status_code == 403
    with SessionLocal() as db:
        db.get(Record,original['id']).status='hidden'
        db.commit()
    assert c.put(url,headers=p['buyer']['headers'],json=payload()).status_code == 404
    assert c.put(edit_url,headers=p['buyer2']['headers'],json={'body':'새 질문 내용','revision':1}).status_code == 404


def test_public_session_survives_eight_hours_but_logout_revokes(public_mode, monkeypatch):
    c, p, _ = public_mode
    stamp=security.now()
    with SessionLocal() as db:
        raw=security.issue_token(db,db.get(User,p['buyer']['id']))
        db.commit()
        token=db.get(Token,security.token_digest(raw))
        assert token.expires == stamp+30*24*3600
    headers={'Authorization':'Bearer '+raw}
    monkeypatch.setattr(security,'now',lambda:stamp+9*3600)
    assert c.get('/api/me',headers=headers).status_code == 200
    assert c.post('/api/auth/logout',headers=headers).status_code == 200
    assert c.get('/api/me',headers=headers).status_code == 401


def test_public_session_expires_after_thirty_days(public_mode, monkeypatch):
    c, p, _ = public_mode
    stamp=security.now()
    with SessionLocal() as db:
        raw=security.issue_token(db,db.get(User,p['buyer']['id']))
        recovery=security.issue_token(db,db.get(User,p['buyer']['id']),kind='recovery',lifetime=300)
        db.commit()
        assert db.get(Token,security.token_digest(recovery)).expires == stamp+300
    monkeypatch.setattr(security,'now',lambda:stamp+31*24*3600)
    assert c.get('/api/me',headers={'Authorization':'Bearer '+raw}).status_code == 401
