"""Private inquiry placeholders, exact seller authority and revision-safe answers."""
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Query
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app import config, private_inquiries as Q
from app.db import Record, SessionLocal, User, get_db
from app.schemas import BodyInput
from app.security import current_user, optional_user


@pytest.fixture
def inquiries(setup,monkeypatch):
    _,p,ids=setup
    monkeypatch.setattr(config,'PUBLIC_RELEASE',False)
    monkeypatch.setattr(config,'BETA',False)
    app=FastAPI()
    app.include_router(Q.router)
    @app.get('/api/campaigns/{id}/questions')
    def listing(id:str,limit:int=Query(10,ge=1,le=100),offset:int=Query(0,ge=0),user=Depends(optional_user),db=Depends(get_db)):
        return Q.list_questions(db,id,user,limit,offset)
    @app.post('/api/campaigns/{id}/questions',status_code=201)
    def create(id:str,body:BodyInput,user=Depends(current_user),db=Depends(get_db)):
        return Q.create_question(db,id,body,user)
    with TestClient(app) as c:
        yield c,p,ids


def question(c,p,ids,private=True,person='buyer',**changes):
    response=c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p[person]['headers'],json={
        'title':'PRIVATE-TITLE 제목','body':'PRIVATE-BODY 문의 내용','private':private,**changes})
    assert response.status_code==201,response.text
    return response.json()


def test_private_original_only_author_exact_seller_and_admin(inquiries):
    c,p,ids=inquiries
    item=question(c,p,ids)
    endpoint='/api/campaigns/'+ids['campaign']+'/questions'
    for headers in [{},p['buyer2']['headers'],p['seller2']['headers']]:
        response=c.get(endpoint,headers=headers)
        assert response.status_code==200
        entry=response.json()['items'][0]
        assert not entry['can_view'] and entry['private'] and entry['status']=='pending'
        assert not any(key in entry for key in ['title','body','answer','author_name','author_id'])
        assert 'PRIVATE-' not in response.text
        assert c.get('/api/questions/'+item['id'],headers=headers).status_code==404
    for person in ['buyer','seller','admin']:
        detail=c.get('/api/questions/'+item['id'],headers=p[person]['headers'])
        assert detail.status_code==200 and detail.json()['body']=='PRIVATE-BODY 문의 내용'
        assert detail.json()['title']=='PRIVATE-TITLE 제목'


def test_old_body_only_request_stays_public_and_dto_is_allowlisted(inquiries):
    c,p,ids=inquiries
    response=c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p['buyer']['headers'],json={'body':'구형 공개 문의'})
    assert response.status_code==201
    item=response.json()
    assert item['private'] is False and item['title']=='상품 문의' and item['created_at']
    with SessionLocal() as db:
        row=db.get(Record,item['id']);row.data={**row.data,'internal_secret':'DO-NOT-SERIALIZE'};db.commit()
    public=c.get('/api/questions/'+item['id'])
    assert public.status_code==200 and public.json()['body']=='구형 공개 문의' and 'internal_secret' not in public.json()


def test_exact_seller_answer_acl_revision_and_private_answer_protection(inquiries):
    c,p,ids=inquiries
    item=question(c,p,ids)
    url='/api/questions/'+item['id']+'/answer'
    payload={'body':'PRIVATE-ANSWER 판매자 답변','revision':1}
    assert c.put(url,json=payload).status_code==401
    assert c.put(url,headers=p['buyer2']['headers'],json=payload).status_code==404
    for person in ['buyer','admin']:
        assert c.put(url,headers=p[person]['headers'],json=payload).status_code==403
    answered=c.put(url,headers=p['seller']['headers'],json=payload)
    assert answered.status_code==200,answered.text
    data=answered.json()
    assert data['answer']==payload['body'] and data['revision']==2 and data['created_at']==item['created_at']
    assert data['answered_at'] and data['answer_updated_at']
    assert c.put(url,headers=p['seller']['headers'],json=payload).status_code==409
    updated=c.put(url,headers=p['seller']['headers'],json={'body':'수정한 PRIVATE-ANSWER','revision':2}).json()
    assert updated['revision']==3 and updated['answered_at']==data['answered_at']
    public=c.get('/api/campaigns/'+ids['campaign']+'/questions').json()['items'][0]
    assert public['status']=='answered' and 'answer' not in public
    with SessionLocal() as db:
        audits=list(db.scalars(select(Record).where(Record.kind=='audit',Record.parent_id==item['id'])))
        assert len(audits)==2 and all('PRIVATE' not in str(row.data) for row in audits)
    assert c.delete(url,headers=p['seller']['headers']).status_code==405


def test_concurrent_answers_only_one_revision_wins(inquiries):
    c,p,ids=inquiries
    item=question(c,p,ids)
    url='/api/questions/'+item['id']+'/answer'
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:c.put(url,headers=p['seller']['headers'],json={'body':'동시 답변 저장','revision':1}).status_code,range(2)))
    assert sorted(statuses)==[200,409]
    assert c.get('/api/questions/'+item['id'],headers=p['seller']['headers']).json()['revision']==2


def test_latest_three_preview_and_ten_item_pages_count_private_existence(inquiries):
    c,p,ids=inquiries
    items=[question(c,p,ids,private=(i%2==0)) for i in range(11)]
    with SessionLocal() as db:
        for i,item in enumerate(items):db.get(Record,item['id']).created=1000+i
        db.commit()
    url='/api/campaigns/'+ids['campaign']+'/questions'
    preview=c.get(url,params={'limit':3}).json()
    assert len(preview['items'])==3 and preview['has_more']
    assert [r['id'] for r in preview['items']]==[r['id'] for r in reversed(items[-3:])]
    first=c.get(url).json();second=c.get(url,params={'offset':10}).json()
    assert len(first['items'])==10 and first['has_more'] and len(second['items'])==1 and not second['has_more']
    assert 'PRIVATE-' not in c.get(url,params={'limit':1}).text


@pytest.mark.parametrize('invalid',[{'title':''},{'body':' '},{'private':'true'},{'owner_id':'somebody'},{'answer':'injected'}])
def test_invalid_submission_keeps_existing_records_and_rejects_extras(inquiries,invalid):
    c,p,ids=inquiries
    original=question(c,p,ids,private=False)
    response=c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p['buyer']['headers'],json={
        'title':'정상 제목','body':'기존 글이 보존되어야 합니다','private':True,**invalid})
    assert response.status_code==422
    assert c.get('/api/campaigns/'+ids['campaign']+'/questions').json()['items'][0]['id']==original['id']


def test_deleted_author_hidden_parent_blocked_user_and_wrong_ids(inquiries):
    c,p,ids=inquiries
    item=question(c,p,ids,private=False)
    with SessionLocal() as db:
        db.add(Record(kind='block',owner_id=p['seller']['id'],parent_id=p['buyer2']['id'],data={}))
        db.commit()
    assert c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p['buyer2']['headers'],json={'body':'차단 후 문의'}).status_code==403
    assert c.get('/api/questions/'+ids['campaign']).status_code==404
    with SessionLocal() as db:
        db.get(User,p['buyer']['id']).deleted=True;db.commit()
    assert c.get('/api/campaigns/'+ids['campaign']+'/questions').json()['items']==[]
    assert c.get('/api/questions/'+item['id']).status_code==404
    with SessionLocal() as db:
        db.get(Record,ids['campaign']).status='hidden';db.commit()
    assert c.get('/api/campaigns/'+ids['campaign']+'/questions').status_code==404


def test_dormant_detail_and_answer_never_open_in_public_release(inquiries,monkeypatch):
    c,p,ids=inquiries
    item=question(c,p,ids)
    monkeypatch.setattr(config,'PUBLIC_RELEASE',True)
    assert c.get('/api/questions/'+item['id'],headers=p['admin']['headers']).status_code==404
    assert c.put('/api/questions/'+item['id']+'/answer',headers=p['seller']['headers'],json={'body':'닫힌 기능','revision':1}).status_code==404


def test_suspended_parent_seller_hides_inquiry_and_prevents_creation(inquiries):
    c,p,ids=inquiries
    item=question(c,p,ids,private=False)
    with SessionLocal() as db:
        db.add(Record(kind='suspension',owner_id=p['seller']['id'],unique_key=p['seller']['id'],data={}))
        db.commit()
    assert c.get('/api/campaigns/'+ids['campaign']+'/questions').status_code==404
    assert c.get('/api/questions/'+item['id']).status_code==404
    assert c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p['buyer']['headers'],json={'body':'공개할 수 없는 부모 문의'}).status_code==404
