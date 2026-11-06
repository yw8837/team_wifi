"""Public group-buy information community; no marketplace transactions or URL fetches."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import socket

import pytest
from sqlalchemy import select
from app import assistant_tools, groupbuys, growth, release
from app.db import Record, SessionLocal, User, now
from test_public_release import public_mode, post_demand
from conftest import PASSWORD

BASE='/api/release/groupbuys'


@pytest.fixture(autouse=True)
def domain_quota(monkeypatch):
    # The PostgreSQL verification keeps the actual deployed middleware/quotas.
    monkeypatch.setattr(groupbuys,'throttle',lambda *a,**k:None)


def payload(**updates):
    value=dict(title='기저귀 공구 정보',body='동일한 구성과 판매처 조건을 확인해 주세요.',category='기저귀·물티슈',
        seller_name='공식 판매처',seller_url='https://seller.example.com/item',price=15000,shipping_fee=3000,
        unit='1팩',price_conditions='구성 및 배송 조건은 판매처에서 최종 확인',
        expires_at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),
        source_checked_at=datetime.now(timezone.utc).isoformat())
    return {**value,**updates}


def create(c,p,who='buyer',**updates):
    response=c.post(BASE,headers=p[who]['headers'],json=payload(**updates))
    assert response.status_code==201,response.text
    return response.json()


def test_anonymous_browse_private_mutation_and_public_allowlist(public_mode,monkeypatch):
    c,p,_=public_mode
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:(_ for _ in ()).throw(AssertionError('URL must not be fetched')))
    assert c.post(BASE,json=payload()).status_code==401
    item=create(c,p)
    assert item['own'] and item['can_edit'] and item['status']=='active'
    assert item['broker_notice']==groupbuys.BROKER_NOTICE and item['source_checked_at'] and item['queried_at']
    with SessionLocal() as db:
        row=db.get(Record,item['id']);row.data={**row.data,'internal_secret':'PRIVATE'};db.commit()
    result=c.get(BASE+'/'+item['id'])
    assert result.status_code==200 and not result.json()['own']
    assert 'internal_secret' not in result.text and PASSWORD not in result.text
    assert c.get(BASE+'/mine').status_code==401
    assert c.get(BASE+'/mine',headers=p['buyer2']['headers']).json()['items']==[]


@pytest.mark.parametrize('updates',[
    {'seller_url':'http://seller.example.com'},{'seller_url':'https://user:password@seller.example.com'},
    {'seller_url':'https://0177.0.0.1/x'},{'seller_url':'https://0x7f.0.0.1/x'},
    {'seller_url':'https://127.0.0.1/x'},{'seller_url':'https://[::1]/x'},{'seller_url':'https://localhost/x'},
    {'seller_url':'https://foo.local/x'},{'seller_url':'https://seller.example.com:444/x'},
    {'seller_url':'https://seller.example.com\\@localhost/x'},{'seller_url':'https://seller.example.com/\nfoo'},
    {'price':True},{'shipping_fee':-1},{'title':'   '},{'title':'  a  '},{'body':'x'},
    {'expires_at':'2026-01-01T00:00:00+09:00'},{'source_checked_at':'2099-01-01T00:00:00+09:00'},
    {'expires_at':'2099-01-01T00:00:00'},{'source_checked_at':'2026-01-01T00:00:00'},
    {'is_admin':True}, {'status':'active'},
])
def test_strict_safe_inputs(public_mode,updates):
    c,p,_=public_mode
    assert c.post(BASE,headers=p['buyer']['headers'],json=payload(**updates)).status_code==422


def test_visibility_precedes_pagination_search_status_and_sort(public_mode):
    c,p,_=public_mode
    blocked=create(c,p,who='buyer2',title='물티슈 검색 대상')
    suspended=create(c,p,who='seller',title='물티슈 검색 대상')
    hidden=create(c,p,who='seller2',title='물티슈 검색 대상')
    deleted=create(c,p,who='pending',title='물티슈 검색 대상')
    visible=create(c,p,title='물티슈 검색 대상',expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    second=create(c,p,title='다른 기저귀 공구')
    with SessionLocal() as db:
        db.add(Record(kind='block',owner_id=p['buyer']['id'],parent_id=p['buyer2']['id'],unique_key='block-fixture',data={}))
        db.add(Record(kind='suspension',owner_id=p['seller']['id'],unique_key=p['seller']['id'],data={}))
        db.get(Record,hidden['id']).status='hidden';db.get(User,p['pending']['id']).deleted=True;db.commit()
    listing=c.get(BASE,headers=p['buyer']['headers'],params={'limit':1,'q':'물티슈','category':'기저귀·물티슈'}).json()
    assert [r['id'] for r in listing['items']]==[visible['id']] and not listing['has_more']
    for item in (blocked,suspended,hidden,deleted):assert c.get(BASE+'/'+item['id'],headers=p['buyer']['headers']).status_code==404
    ordered=c.get(BASE,headers=p['buyer']['headers'],params={'limit':1}).json()
    assert ordered['items'][0]['id']==visible['id'] and ordered['has_more']
    assert c.post(BASE+'/'+visible['id']+'/end',headers=p['buyer']['headers'],json={'revision':1}).status_code==200
    assert visible['id'] not in {row['id'] for row in c.get(BASE).json()['items']}
    assert [r['id'] for r in c.get(BASE,headers=p['buyer']['headers'],params={'status':'ended'}).json()['items']]==[visible['id']]
    assert c.get(BASE,params={'q':'%_'}).json()['items']==[]
    assert c.get(BASE,params={'start_date':'2026-11-07','end_date':'2026-11-06'}).status_code==422


def test_owner_revision_update_end_and_concurrent_edit(public_mode):
    c,p,_=public_mode;item=create(c,p);url=BASE+'/'+item['id']
    assert c.put(url,headers=p['buyer2']['headers'],json={**payload(),'revision':1}).status_code==404
    with ThreadPoolExecutor(2) as pool:
        statuses=list(pool.map(lambda _:c.put(url,headers=p['buyer']['headers'],json={**payload(title='변경한 기저귀 공구'),'revision':1}).status_code,range(2)))
    assert sorted(statuses)==[200,409]
    changed=c.get(url).json();assert changed['revision']==2 and changed['updated_at']
    assert c.post(url+'/end',headers=p['buyer']['headers'],json={'revision':1}).status_code==409
    ended=c.post(url+'/end',headers=p['buyer']['headers'],json={'revision':2})
    assert ended.status_code==200 and ended.json()['status']=='ended'
    assert c.put(url,headers=p['buyer']['headers'],json={**payload(),'revision':3}).status_code==409
    assert c.post(url+'/end',headers=p['buyer']['headers'],json={'revision':3}).status_code==409


def test_actual_expiry_ends_and_cannot_link(public_mode):
    c,p,_=public_mode;item=create(c,p);demand=post_demand(c,p['buyer']['headers'])
    with SessionLocal() as db:db.get(Record,item['id']).ends=now()-1;db.commit()
    assert c.get(BASE+'/'+item['id']).json()['status']=='ended'
    assert c.get(BASE).json()['items']==[]
    assert c.put('/api/release/demands/'+demand['id']+'/groupbuy',headers=p['buyer']['headers'],json={'revision':1,'groupbuy_id':item['id']}).status_code==404


def test_demand_link_ownership_revision_visibility_and_edit_preservation(public_mode):
    c,p,_=public_mode;item=create(c,p);demand=post_demand(c,p['buyer']['headers']);url='/api/release/demands/'+demand['id']
    link={'revision':1,'groupbuy_id':item['id']}
    assert c.put(url+'/groupbuy',headers=p['buyer2']['headers'],json=link).status_code==404
    assert c.put(url+'/groupbuy',headers=p['buyer']['headers'],json={**link,'groupbuy_id':'missing'}).status_code==404
    linked=c.put(url+'/groupbuy',headers=p['buyer']['headers'],json=link)
    assert linked.status_code==200 and linked.json()['revision']==2 and linked.json()['linked_groupbuy']['id']==item['id']
    edit=c.put(url,headers=p['buyer']['headers'],json={'title':'변경된 공구 수요','body':'공구 연결을 유지한 수요 글 내용입니다.','category':'육아생활','revision':2})
    assert edit.status_code==200 and edit.json()['linked_groupbuy']['id']==item['id']
    assert c.post(url+'/unlink-groupbuy',headers=p['buyer']['headers'],json={'revision':2}).status_code==409
    assert c.post(url+'/unlink-groupbuy',headers=p['buyer']['headers'],json={'revision':3}).json()['linked_groupbuy'] is None
    assert c.put(url+'/groupbuy',headers=p['buyer']['headers'],json={'revision':4,'groupbuy_id':item['id']}).status_code==200
    with SessionLocal() as db:db.get(Record,item['id']).status='hidden';db.commit()
    assert c.get(url).json()['linked_groupbuy'] is None


def test_groupbuy_reports_admin_original_review_history_and_no_reprocessing(public_mode):
    c,p,_=public_mode;item=create(c,p);url=BASE+'/'+item['id']+'/reports';h=p['admin']['headers']
    assert c.post(url,json={'reason':'잘못된 판매처 정보'}).status_code==401
    first=c.post(url,headers=p['buyer2']['headers'],json={'reason':'잘못된 판매처 정보'})
    assert first.status_code==201
    assert c.post(url,headers=p['buyer2']['headers'],json={'reason':'다시 제보한 정보'}).json()['id']==first.json()['id']
    admin='/api/release/admin/groupbuys/reports'
    assert c.get(admin,headers=p['buyer']['headers']).status_code==403
    listing=c.get(admin,headers=h).json();assert listing['items'][0]['groupbuy']['seller_url']==item['seller_url']
    resolve=admin+'/'+first.json()['id']+'/resolve'
    marked=c.post(resolve,headers=h,json={'action':'needs_review','note':'판매처 추가 확인 필요'})
    assert marked.status_code==200 and marked.json()['resolved_by']==p['admin']['id']
    assert c.get(BASE+'/'+item['id']).json()['review_state']=='needs_review'
    assert c.post(resolve,headers=h,json={'action':'hide','note':'중복 처리 시도'}).status_code==409
    report=c.post(url,headers=p['seller']['headers'],json={'reason':'판매처 조건 다시 확인'}).json()['id']
    assert c.post(admin+'/'+report+'/resolve',headers=h,json={'action':'hide','note':'잘못된 판매처 주소'}).status_code==200
    assert c.get(BASE+'/'+item['id']).status_code==404
    mine=c.get(BASE+'/mine',headers=p['buyer']['headers']).json()['items'][0]
    assert mine['status']=='hidden' and not mine['can_edit']
    assert c.get(admin,headers=h,params={'status':'resolved'}).json()['items'][0]['groupbuy']['body']==item['body']
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Record).where(Record.kind=='audit',Record.data['target_id'].as_string()==item['id']))))==2
    assert c.get('/api/release/notices',headers=p['buyer']['headers']).json()['items']


def test_generic_report_route_handles_groupbuy_and_rejects_wrong_action(public_mode):
    c,p,_=public_mode;item=create(c,p)
    report=c.post('/api/release/reports',headers=p['buyer2']['headers'],json={'target_type':'groupbuy','target_id':item['id'],'reason':'공구 정보 내용 확인'}).json()['id']
    url='/api/release/admin/reports/'+report+'/resolve'
    assert c.post(url,headers=p['admin']['headers'],json={'action':'suspend','note':'잘못된 처리 유형'}).status_code==422
    dismissed=c.post(url,headers=p['admin']['headers'],json={'action':'dismiss','note':'확인한 결과 조치 불필요'})
    assert dismissed.status_code==200 and c.get(BASE+'/'+item['id']).status_code==200


def test_assistant_live_data_is_current_and_visibility_scoped(public_mode):
    c,p,_=public_mode;item=create(c,p)
    with SessionLocal() as db:
        result=assistant_tools.live_read(db,None,'기저귀 공구 마감 알려줘')
        assert any(a['url']=='/groupbuys/'+item['id'] for a in result['actions'])
        assert any('15000원' in note and '출처 확인' in note and 'DB 조회' in note for note in result['notes'])
        db.get(Record,item['id']).status='hidden';db.commit()
    with SessionLocal() as db:
        result=assistant_tools.live_read(db,None,'기저귀 공구 마감 알려줘')
        assert not any(a['url']=='/groupbuys/'+item['id'] for a in result['actions'])
        assert any('찾지 못했어요' in note for note in result['notes'])


def test_groupbuy_measurement_optin_source_and_hide_exclusion(public_mode):
    c,p,_=public_mode;item=create(c,p);h=p['buyer2']['headers']
    event=dict(groupbuy_id=item['id'],placement='groupbuy_detail',channel='web',action='view',visible_ms=1000)
    endpoint='/api/release/measurement/events'
    assert not c.post(endpoint,headers=h,json=event).json()['recorded']
    c.put('/api/release/measurement/consent',headers=h,json={'enabled':True})
    assert c.post(endpoint,headers=h,json=event).json()['recorded']
    assert c.post(endpoint,headers=h,json={**event,'action':'source'}).json()['recorded']
    assert c.post(endpoint,headers=h,json={**event,'offer_id':'official-source-1'}).status_code==422
    report=c.get('/api/release/measurement/report',headers=p['admin']['headers']).json()
    assert report['rows'][0]['source_accounts'] is None and report['rows'][0]['source_rate'] is None
    assert '구매 완료가 아닙니다' in report['limitations']
    with SessionLocal() as db:db.get(Record,item['id']).status='hidden';db.commit()
    assert c.get('/api/release/measurement/report',headers=p['admin']['headers']).json()['rows']==[]
    assert c.post(endpoint,headers=h,json=event).status_code==404


def test_erasure_removes_shared_text_reports_audit_measurement_and_link(public_mode):
    c,p,_=public_mode;item=create(c,p,who='buyer2');demand=post_demand(c,p['buyer']['headers']);url='/api/release/demands/'+demand['id']
    assert c.put(url+'/groupbuy',headers=p['buyer']['headers'],json={'groupbuy_id':item['id'],'revision':1}).status_code==200
    report=c.post(BASE+'/'+item['id']+'/reports',headers=p['seller']['headers'],json={'reason':'PRIVATE-REPORT'}).json()['id']
    assert c.post('/api/release/admin/groupbuys/reports/'+report+'/resolve',headers=p['admin']['headers'],json={'action':'needs_review','note':'PRIVATE-NOTE'}).status_code==200
    assert c.request('DELETE','/api/me',headers=p['buyer2']['headers'],json={'password':PASSWORD}).status_code==200
    assert c.get(BASE+'/'+item['id']).status_code==404 and c.get(url).json()['linked_groupbuy'] is None
    with SessionLocal() as db:
        assert not db.get(Record,report)
        assert not db.scalar(select(Record.id).where(Record.kind=='audit',Record.data['target_id'].as_string()==item['id']))
        assert db.get(Record,demand['id']).data.get('groupbuy_id') is None


def test_public_html_is_script_free_escaped_and_ends_honestly(public_mode):
    c,p,_=public_mode;item=create(c,p,title='<script>alert(1)</script>',body='<img src=x onerror=alert(1)> 회원이 공유한 원문입니다.')
    response=c.get(BASE+'/'+item['id']+'/public')
    assert response.status_code==200
    assert '<script>' not in response.text and '<img ' not in response.text and '&lt;script&gt;' in response.text
    assert groupbuys.BROKER_NOTICE in response.text and 'default-src' in response.headers['Content-Security-Policy']
    c.post(BASE+'/'+item['id']+'/end',headers=p['buyer']['headers'],json={'revision':1})
    assert '<p>종료</p>' in c.get(BASE+'/'+item['id']+'/public').text


def test_interest_insights_deduplicate_sharers_and_suppress_hidden_or_suspended(public_mode):
    c,p,_=public_mode
    shared=[create(c,p,who=who) for who in ('buyer','buyer2','seller','seller2','pending')]
    duplicate=create(c,p,who='buyer')
    def count():
        rows=c.get('/api/release/admin/insights',headers=p['admin']['headers']).json()['categories']
        return next(row for row in rows if row['category']=='기저귀·물티슈')['groupbuy_shared_accounts']
    assert count()==5
    with SessionLocal() as db:db.get(Record,duplicate['id']).status='hidden';db.commit()
    assert count()==5
    with SessionLocal() as db:
        db.add(Record(kind='suspension',owner_id=p['buyer2']['id'],unique_key=p['buyer2']['id'],data={}));db.commit()
    assert count() is None
