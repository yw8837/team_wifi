"""Synthetic provider HTTP exchanges; never reaches Naver or uses real credentials."""
from urllib.parse import parse_qs,urlsplit
import json

import httpx
import pytest
from sqlalchemy import select

from app import config,social_auth as social
from app.db import Record,SessionLocal,now
from test_public_release import public_mode
from test_social_auth import oauth

REAL_EXCHANGE=social.exchange


@pytest.fixture
def naver(oauth,monkeypatch):
    monkeypatch.setenv('NAVER_CLIENT_ID','synthetic-naver-client')
    monkeypatch.setenv('NAVER_CLIENT_SECRET','synthetic-naver-secret')
    monkeypatch.setattr(social,'exchange',REAL_EXCHANGE)
    monkeypatch.setattr(social,'jwks',lambda *args:pytest.fail('OAuth2 userinfo must not trust an ID token'))
    original=httpx.Client
    transport={'requests':[],'token':{'access_token':'SYNTHETIC-ACCESS-TOKEN','refresh_token':'SYNTHETIC-REFRESH-TOKEN','token_type':'bearer','expires_in':'3600'},
               'profile':{'resultcode':'00','message':'success','response':{'id':'synthetic-subject','email':'SYNTHETIC-PRIVATE@example.invalid','name':'SYNTHETIC-PRIVATE-NAME'}},
               'token_status':200,'profile_status':200}
    def respond(request):
        transport['requests'].append(request)
        if str(request.url)=='https://nid.naver.com/oauth2.0/token':
            return httpx.Response(transport['token_status'],json=transport['token'])
        assert str(request.url)=='https://openapi.naver.com/v1/nid/me'
        return httpx.Response(transport['profile_status'],json=transport['profile'])
    monkeypatch.setattr(social.httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    return oauth,transport


def start(c,purpose='login',headers=None,platform='web'):
    verifier='a'*43
    response=c.post('/api/auth/social/naver/start',headers=headers,json={'challenge':social.challenge(verifier),'purpose':purpose,'platform':platform})
    assert response.status_code==200,response.text
    result=response.json();query=parse_qs(urlsplit(result['authorization_url']).query)
    return {'flow_id':result['flow_id'],'verifier':verifier},query


def finish(c,query,**params):
    response=c.get('/api/auth/social/naver/callback',params={'state':query['state'][0],'code':'synthetic-code',**params},follow_redirects=False)
    assert response.status_code==303,response.text
    return response


def test_naver_is_hidden_until_both_server_credentials_are_present(public_mode,monkeypatch):
    c,_,_=public_mode
    monkeypatch.setattr(config,'PUBLIC_ORIGIN','https://api.example.com')
    monkeypatch.setattr(config,'PUBLIC_WEB_ORIGIN','https://app.example.com')
    monkeypatch.delenv('NAVER_CLIENT_ID',raising=False);monkeypatch.delenv('NAVER_CLIENT_SECRET',raising=False)
    assert 'naver' not in c.get('/api/auth/social/providers').json()['providers']
    monkeypatch.setenv('NAVER_CLIENT_ID','synthetic-client')
    assert 'naver' not in c.get('/api/auth/social/providers').json()['providers']
    response=c.post('/api/auth/social/naver/start',json={'challenge':'a'*43})
    assert response.status_code==503
    monkeypatch.setenv('NAVER_CLIENT_SECRET','synthetic-secret')
    assert 'naver' in c.get('/api/auth/social/providers').json()['providers']


def test_naver_code_state_token_and_profile_id_complete_signup_without_profile_retention(naver):
    (c,_,_),transport=naver
    proof,query=start(c)
    assert set(query)=={'client_id','redirect_uri','response_type','state'}
    assert query['redirect_uri']==['https://api.example.com/api/auth/social/naver/callback']
    callback=finish(c,query)
    assert callback.headers['location']=='https://app.example.com/auth/complete?flow='+proof['flow_id']
    token_request,profile_request=transport['requests']
    assert token_request.method=='POST' and not token_request.url.query
    payload=parse_qs(token_request.content.decode())
    assert payload['state']==query['state'] and payload['code']==['synthetic-code']
    assert payload['client_id']==['synthetic-naver-client'] and payload['client_secret']==['synthetic-naver-secret']
    assert profile_request.headers['Authorization']=='Bearer SYNTHETIC-ACCESS-TOKEN'
    with SessionLocal() as db:
        row=db.get(Record,proof['flow_id'])
        assert row.status=='ready' and row.data['subject']=='synthetic-subject'
        assert 'SYNTHETIC-' not in json.dumps({k:v for k,v in row.data.items() if k!='subject'})
        assert not {'nonce','pkce','access_token','refresh_token','email','name'}&set(row.data)
    assert c.post('/api/auth/social/claim',json={**proof,'verifier':'b'*43}).status_code==400
    assert c.post('/api/auth/social/claim',json=proof).json()['status']=='onboarding'
    account=c.post('/api/auth/social/claim',json={**proof,'nickname':'네이버회원','terms_accepted':True,'privacy_accepted':True,'age_confirmed':True}).json()
    assert account['status']=='authenticated' and account['user']['email']=='' and not account['user']['has_password']
    assert c.post('/api/auth/social/claim',json=proof).status_code==400
    assert c.get('/api/auth/social/naver/callback',params={'state':query['state'][0],'code':'synthetic-code'}).status_code==400
    assert len(transport['requests'])==2
    with SessionLocal() as db:
        assert not any('SYNTHETIC-PRIVATE' in str(row.data) or 'SYNTHETIC-ACCESS' in str(row.data) or 'SYNTHETIC-REFRESH' in str(row.data) for row in db.scalars(select(Record)))


@pytest.mark.parametrize('part,value',[
    ('token',[]),('token',{'error':'invalid_grant','access_token':'ignored'}),
    ('token',{'access_token':'bad\r\nInjected: value','token_type':'Bearer','expires_in':3600}),
    ('token',{'access_token':'opaque','token_type':'MAC','expires_in':3600}),
    ('token',{'access_token':'opaque','token_type':'Bearer','expires_in':True}),
    ('token',{'access_token':'opaque','token_type':'Bearer','expires_in':0}),
    ('token',{'access_token':'opaque','token_type':'Bearer','expires_in':'not-a-lifetime'}),
    ('profile',[]),('profile',{'resultcode':'024','response':{'id':'ignored'}}),
    ('profile',{'resultcode':'00','response':[]}),
    ('profile',{'resultcode':'00','response':{'id':123}}),
    ('profile',{'resultcode':'00','response':{'id':True}}),
    ('profile',{'resultcode':'00','response':{'id':''}}),
    ('profile',{'resultcode':'00','response':{'id':'contains whitespace'}}),
    ('profile',{'resultcode':'00','response':{'id':'x'*256}}),
])
def test_naver_rejects_invalid_token_and_userinfo_without_claimable_identity(naver,part,value):
    (c,_,_),transport=naver
    transport[part]=value
    proof,query=start(c)
    callback=finish(c,query)
    assert 'opaque' not in callback.headers['location'] and 'invalid_grant' not in callback.headers['location']
    assert c.post('/api/auth/social/claim',json=proof).status_code==400
    with SessionLocal() as db:
        row=db.get(Record,proof['flow_id'])
        assert row.status=='failed' and 'subject' not in row.data
        assert not list(db.scalars(select(Record).where(Record.kind==social.IDENTITY)))


@pytest.mark.parametrize('stage,status',[('token_status',401),('token_status',302),('profile_status',401),('profile_status',302)])
def test_naver_http_failure_or_redirect_fails_closed_without_reusing_code(naver,stage,status):
    (c,_,_),transport=naver
    transport[stage]=status
    proof,query=start(c)
    finish(c,query)
    calls=len(transport['requests'])
    assert c.post('/api/auth/social/claim',json=proof).status_code==400
    assert c.get('/api/auth/social/naver/callback',params={'state':query['state'][0],'code':'synthetic-code'}).status_code==400
    assert len(transport['requests'])==calls


@pytest.mark.parametrize('params',[{'error':'access_denied'},{'code':''}])
def test_naver_cancelled_callback_consumes_state_without_any_provider_request(naver,params):
    (c,_,_),transport=naver
    proof,query=start(c)
    finish(c,query,**params)
    assert not transport['requests']
    assert c.post('/api/auth/social/claim',json=proof).status_code==400
    with SessionLocal() as db:assert db.get(Record,proof['flow_id']).status=='failed'


def test_naver_state_provider_and_expired_flow_checked_before_network(naver):
    (c,_,_),transport=naver
    proof,query=start(c)
    assert c.get('/api/auth/social/naver/callback',params={'state':'wrong','code':'synthetic-code'}).status_code==400
    assert c.get('/api/auth/social/google/callback',params={'state':query['state'][0],'code':'synthetic-code'}).status_code==400
    with SessionLocal() as db:
        row=db.get(Record,proof['flow_id']);assert row.status=='pending';row.ends=now()-1;db.commit()
    assert c.get('/api/auth/social/naver/callback',params={'state':query['state'][0],'code':'synthetic-code'}).status_code==400
    assert not transport['requests']


def test_naver_link_duplicate_subjects_do_not_merge_accounts_or_other_providers(naver):
    (c,people,_),transport=naver
    subject=transport['profile']['response']['id']
    with SessionLocal() as db:
        db.add(Record(kind=social.IDENTITY,owner_id=people['buyer2']['id'],unique_key=social.identity_key('google',subject),data={'provider':'google','subject':subject}));db.commit()
    h=people['buyer']['headers']
    proof,query=start(c,'link',h);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=people['buyer2']['headers'],json=proof).status_code==403
    assert c.post('/api/auth/social/claim',headers=h,json=proof).json()['status']=='linked'
    same,query=start(c,'link',h);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=h,json=same).json()['status']=='linked'
    other,query=start(c,'link',people['buyer2']['headers']);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=people['buyer2']['headers'],json=other).status_code==409
    login,query=start(c);finish(c,query)
    assert c.post('/api/auth/social/claim',json=login).json()['user']['id']==people['buyer']['id']
    with SessionLocal() as db:
        identities=list(db.scalars(select(Record).where(Record.kind==social.IDENTITY)))
        assert len(identities)==2 and {r.data['provider']:r.owner_id for r in identities}=={'naver':people['buyer']['id'],'google':people['buyer2']['id']}


def test_naver_matching_email_and_untrusted_id_token_do_not_authorize_an_existing_account(naver):
    (c,people,_),transport=naver
    transport['token']['id_token']='unverified-attacker-token'
    transport['profile']['response']['email']='buyer@example.com'
    proof,query=start(c);finish(c,query)
    assert c.post('/api/auth/social/claim',json=proof).json()['status']=='onboarding'
    denied=c.post('/api/auth/social/claim',json={**proof,'nickname':'네이버회원','terms_accepted':True,'privacy_accepted':True,'age_confirmed':False})
    assert denied.json()['status']=='onboarding'
    with SessionLocal() as db:assert not list(db.scalars(select(Record).where(Record.kind==social.IDENTITY)))


def test_naver_mobile_handoff_preserves_operator_identity(naver):
    (c,people,_),_=naver
    linked,query=start(c,'link',people['admin']['headers']);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=people['admin']['headers'],json=linked).json()['status']=='linked'
    mobile,query=start(c,platform='android');callback=finish(c,query)
    assert callback.headers['location']=='kr.moduyuga.app://auth/complete?flow='+mobile['flow_id']
    response=c.post('/api/auth/social/claim',json=mobile)
    assert response.status_code==200 and response.json()['user']['id']==people['admin']['id']
    web,query=start(c);finish(c,query)
    assert c.post('/api/auth/social/claim',json=web).json()['user']['id']==people['admin']['id']


def test_naver_reauth_forces_login_is_owner_bound_and_supports_mobile_proof(naver):
    (c,people,_),_=naver
    h=people['buyer']['headers']
    linked,query=start(c,'link',h);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=h,json=linked).status_code==200
    proof,query=start(c,'reauth',h,platform='android')
    assert query['auth_type']==['reauthenticate'] and not {'prompt','nonce','scope'}&set(query)
    with SessionLocal() as db:
        row=db.get(Record,proof['flow_id']);assert 299<=row.ends-row.created<=301
    finish(c,query)
    assert c.post('/api/auth/social/claim',headers=people['buyer2']['headers'],json=proof).status_code==403
    assert c.post('/api/auth/social/claim',headers=h,json={**proof,'verifier':'b'*43}).status_code==400
    response=c.post('/api/auth/social/claim',headers=h,json=proof)
    assert response.status_code==200 and response.json()['status']=='reauthenticated' and response.json()['reauth_token']
    assert c.post('/api/auth/social/claim',headers=h,json=proof).status_code==400


def test_naver_reauth_rejects_stale_local_authentication_even_with_modified_ttl(naver):
    (c,people,_),transport=naver
    proof,query=start(c,'reauth',people['buyer']['headers'])
    with SessionLocal() as db:
        row=db.get(Record,proof['flow_id']);row.created=now()-301;row.ends=now()+60;db.commit()
    finish(c,query)
    assert not transport['requests']
    assert c.post('/api/auth/social/claim',headers=people['buyer']['headers'],json=proof).status_code==400


def test_naver_reauth_different_subject_cannot_issue_a_reauth_token(naver):
    (c,people,_),transport=naver
    h=people['buyer']['headers']
    proof,query=start(c,'link',h);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=h,json=proof).status_code==200
    transport['profile']['response']['id']='different-subject'
    proof,query=start(c,'reauth',h);finish(c,query)
    assert c.post('/api/auth/social/claim',headers=h,json=proof).status_code==403
