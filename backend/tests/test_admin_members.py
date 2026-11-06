from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import select

from app import admin_members
from app.db import Record, SessionLocal, Token, User, now
from app.security import issue_token
from conftest import PASSWORD
from test_public_release import public_mode

BASE = '/api/release/admin/members'


@pytest.fixture(autouse=True)
def isolate_domain_quota(monkeypatch):
    # Match public_mode's SQLite domain harness. Actual guards run in PostgreSQL.
    monkeypatch.setattr(admin_members, 'throttle', lambda *args, **kwargs: None)


def payload(**changes):
    return dict(revision=0, is_admin=False, suspended=True, reason='운영 정책에 따른 상태 변경', password=PASSWORD, **changes)


def test_member_list_detail_minimization_role_and_date_filters(public_mode):
    c,p,_ = public_mode
    assert c.get(BASE).status_code == 401
    assert c.get(BASE, headers=p['buyer']['headers']).status_code == 403
    with SessionLocal() as db:
        member=db.get(User,p['buyer']['id'])
        member.created=int(datetime.fromisoformat('2026-11-05T15:00:00+00:00').timestamp())
        db.commit()
    h=p['admin']['headers']
    listed=c.get(BASE,headers=h,params={'q':'buyer','start_date':'2026-11-06','end_date':'2026-11-06'}).json()
    assert p['buyer']['id'] in {item['id'] for item in listed['items']}
    assert all(set(item)=={'id','nickname','is_admin','suspended','created_at','updated_at','revision'} for item in listed['items'])
    operators=c.get(BASE,headers=h,params={'role':'operator'}).json()
    assert [item['id'] for item in operators['items']]==[p['admin']['id']]
    first=c.get(BASE,headers=h,params={'limit':1}).json()
    second=c.get(BASE,headers=h,params={'limit':1,'offset':1}).json()
    assert first['has_more'] and first['items'][0]['id']!=second['items'][0]['id']
    assert c.get(BASE,headers=h,params={'start_date':'2026-11-07','end_date':'2026-11-06'}).status_code==422
    assert c.get(BASE+'/'+p['buyer']['id'],headers=p['buyer']['headers']).status_code==403


def test_suspend_unsuspend_history_and_revocation(public_mode):
    c,p,_=public_mode
    h=p['admin']['headers']; identifier=p['buyer']['id']; url=BASE+'/'+identifier
    with SessionLocal() as db:
        recovery=issue_token(db,db.get(User,identifier),'recovery',3600)
        db.commit()
    first=c.put(url,headers=h,json=payload())
    assert first.status_code==200,first.text
    assert first.json()['member']['suspended'] and first.json()['member']['revision']==1
    assert c.get('/api/me',headers=p['buyer']['headers']).status_code==401
    assert c.get(BASE,headers=h,params={'status':'suspended'}).json()['items'][0]['id']==identifier
    second=c.put(url,headers=h,json={**payload(),'revision':1,'suspended':False,'reason':'운영 검토 후 제한 해제'})
    assert second.status_code==200 and not second.json()['member']['suspended']
    result=c.get(url,headers=h,params={'history_limit':1}).json()
    earlier=c.get(url,headers=h,params={'history_limit':1,'history_offset':1}).json()
    assert result['history_has_more'] and not earlier['history_has_more']
    assert result['history'][0]['id']!=earlier['history'][0]['id']
    history=result['history']+earlier['history']
    assert {entry['after']['suspended'] for entry in history}=={True,False}
    assert all(entry['actor_id']==p['admin']['id'] and entry['reason'] and entry['created_at'] for entry in history)
    with SessionLocal() as db:
        assert db.scalar(select(Token.digest).where(Token.user_id==identifier,Token.kind=='recovery'))
    assert c.put(url,headers=h,json=payload()).status_code==409


@pytest.mark.parametrize('overrides', [{'password':''},{'password':'wrong-password'},{'reason':' '},{'extra_field':True}])
def test_member_change_needs_fresh_proof_reason_and_strict_body(public_mode,overrides):
    c,p,_=public_mode
    response=c.put(BASE+'/'+p['buyer']['id'],headers=p['admin']['headers'],json={**payload(),**overrides})
    assert response.status_code in (403,422)
    with SessionLocal() as db:
        assert not db.scalar(select(Record.id).where(Record.kind==admin_members.AUDIT))


def test_role_change_preserves_recovery_disallows_self_and_operator_suspension(public_mode):
    c,p,_=public_mode
    h=p['admin']['headers']; url=BASE+'/'+p['buyer']['id']
    promoted=c.put(url,headers=h,json={**payload(),'suspended':False,'is_admin':True})
    assert promoted.status_code==200 and promoted.json()['member']['is_admin']
    assert c.get('/api/me',headers=p['buyer']['headers']).status_code==401
    assert c.put(url,headers=h,json={**payload(),'revision':1,'is_admin':True}).status_code==422
    assert c.put(BASE+'/'+p['admin']['id'],headers=h,json={**payload(),'suspended':False}).status_code==422
    assert c.put(url,headers=h,json={**payload(),'revision':1,'suspended':False}).status_code==200


def test_social_reauth_one_use_same_operator_and_expiry(public_mode):
    c,p,_=public_mode
    h=p['admin']['headers']; url=BASE+'/'+p['buyer']['id']
    with SessionLocal() as db:
        actor=db.get(User,p['admin']['id'])
        actor.password_hash='!social-only'
        proof=issue_token(db,actor,'social_reauth',300)
        other=issue_token(db,db.get(User,p['buyer2']['id']),'social_reauth',300)
        expired=issue_token(db,actor,'social_reauth',-1)
        db.commit()
    for invalid in (other,expired):
        assert c.put(url,headers=h,json={**payload(),'password':'','reauth_token':invalid}).status_code==403
    assert c.put(url,headers=h,json={**payload(),'password':'','reauth_token':proof}).status_code==200
    assert c.put(url,headers=h,json={**payload(),'revision':1,'suspended':False,'password':'','reauth_token':proof}).status_code==403


def test_member_revision_conflict_has_one_change_and_no_last_operator_loss(public_mode):
    c,p,_=public_mode
    url=BASE+'/'+p['buyer']['id']; h=p['admin']['headers']
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:c.put(url,headers=h,json=payload()).status_code,range(2)))
    assert sorted(statuses)==[200,409]
    assert len(c.get(url,headers=h).json()['history'])==1
    with SessionLocal() as db:
        assert db.get(User,p['admin']['id']).is_admin


def test_erasure_removes_member_audit_free_text(public_mode):
    c,p,_=public_mode
    identifier=p['buyer']['id']; h=p['admin']['headers']
    assert c.put(BASE+'/'+identifier,headers=h,json={**payload(),'is_admin':True,'suspended':False,'reason':'PRIVATE-MEMBER-NOTE'}).status_code==200
    login=c.post('/api/auth/login',json={'email':'buyer@example.com','password':PASSWORD})
    assert login.status_code==200,login.text
    deleted=c.request('DELETE','/api/me',headers={'Authorization':'Bearer '+login.json()['access_token']},json={'password':PASSWORD})
    assert deleted.status_code==200,deleted.text
    assert c.get(BASE+'/'+identifier,headers=h).status_code==404
    with SessionLocal() as db:
        assert not db.scalar(select(Record.id).where(Record.kind==admin_members.AUDIT,Record.parent_id==identifier))
