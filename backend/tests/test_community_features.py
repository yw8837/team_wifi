"""Community compatibility, period filters, activity isolation and safe moderation notices."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import select

from app.db import Record, SessionLocal, User
from app import release
from test_public_release import public_mode, post_demand

BASE = '/api/release'


def create(c, headers, post_type='question', title='함께 나누는 육아 질문'):
    response = c.post(BASE+'/demands', headers=headers, json={
        'title': title, 'body': '육아 경험과 정보를 함께 나누고 싶습니다.',
        'category': '육아생활', 'post_type': post_type})
    assert response.status_code == 201, response.text
    return response.json()


def set_created(id, value):
    with SessionLocal() as db:
        db.get(Record, id).created = int(datetime.fromisoformat(value).timestamp())
        db.commit()


def activity(c, headers, tab='posts', **params):
    response = c.get(BASE+'/activity', headers=headers, params={'tab': tab, **params})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('kind', ['question', 'experience', 'information', 'demand'])
def test_type_roundtrip_old_edit_and_public_allowlist(public_mode, kind):
    c, p, _ = public_mode
    original = create(c, p['buyer']['headers'], kind)
    url = BASE+'/demands/'+original['id']
    with SessionLocal() as db:
        row = db.get(Record, original['id'])
        row.data = {**row.data, 'internal_secret': 'NEVER-PUBLIC', 'status': 'hidden', 'own': False}
        db.commit()
    public = c.get(url).json()
    assert public['post_type'] == kind and 'internal_secret' not in public and 'status' not in public
    changed = c.put(url, headers=p['buyer']['headers'], json={
        'title': '이전 앱에서 수정한 글입니다', 'body': '이전 버전에서 유형 없이 저장하는 글입니다.', 'category': '육아생활', 'revision': 1})
    assert changed.status_code == 200, changed.text
    assert changed.json()['post_type'] == kind
    assert changed.json()['created_at'] == original['created_at']
    assert changed.json()['updated_at'] and changed.json()['own']
    assert c.get(BASE+'/demands', params={'post_type': kind}).json()[0]['id'] == original['id']
    assert c.put(url+'/interest', headers=p['buyer2']['headers']).status_code == (200 if kind == 'demand' else 422)


def test_legacy_missing_type_and_extra_fields(public_mode):
    c, p, _ = public_mode
    original = post_demand(c, p['buyer']['headers'])
    with SessionLocal() as db:
        row = db.get(Record, original['id'])
        row.data = {key: value for key, value in row.data.items() if key != 'post_type'}
        db.commit()
    assert c.get(BASE+'/demands?post_type=demand').json()[0]['post_type'] == 'demand'
    assert c.put(BASE+'/demands/'+original['id']+'/interest', headers=p['buyer2']['headers']).status_code == 200
    payload = {'title':'올바른 육아 정보', 'body':'내용은 정상이어도 내부 필드를 보낼 수 없습니다.', 'category':'육아생활'}
    for extra in [{'post_type':'operator'}, {'post_type':None}, {'owner_id':p['admin']['id']}, {'hidden':False}]:
        assert c.post(BASE+'/demands', headers=p['buyer']['headers'], json={**payload, **extra}).status_code == 422
    assert c.put(BASE+'/demands/'+original['id'], headers=p['buyer']['headers'],
                 json={**payload, 'post_type':'question', 'revision':1}).status_code == 409


def test_feed_korea_inclusive_boundaries_and_creation_after_edit(public_mode):
    c, p, _ = public_mode
    rows = [create(c, p['buyer']['headers'], title=f'기간을 확인하는 글 {i}') for i in range(4)]
    for row, stamp in zip(rows, ['2026-11-04T14:59:59+00:00', '2026-11-04T15:00:00+00:00',
                                '2026-11-05T14:59:59+00:00', '2026-11-05T15:00:00+00:00']):
        set_created(row['id'], stamp)
    params = {'start_date':'2026-11-05', 'end_date':'2026-11-05', 'post_type':'question', 'q':'기간', 'category':'육아생활'}
    response = c.get(BASE+'/demands', params=params)
    assert {r['id'] for r in response.json()} == {rows[1]['id'], rows[2]['id']}
    assert len(c.get(BASE+'/demands', params={**params, 'limit':1, 'offset':1}).json()) == 1
    edited = c.put(BASE+'/demands/'+rows[1]['id'], headers=p['buyer']['headers'], json={
        'title':'기간을 확인하는 수정 글', 'body':'수정 후에도 작성일 기준 기간에 포함됩니다.', 'category':'육아생활', 'revision':1})
    assert edited.status_code == 200
    assert {r['id'] for r in c.get(BASE+'/demands', params=params).json()} == {rows[1]['id'], rows[2]['id']}
    assert len(activity(c, p['buyer']['headers'], start_date='2026-11-05',end_date='2026-11-05',q='기간')['items']) == 2


@pytest.mark.parametrize('params', [
    {'start_date':'2026-11-06','end_date':'2026-11-05'}, {'start_date':'2026-02-30'},
    {'end_date':'11/05/2026'}, {'start_date':'2026-11-05T00:00:00Z'}, {'start_date':''},
])
def test_invalid_period_rejected_consistently(public_mode, params):
    c, p, _ = public_mode
    for path, headers in [('/demands', {}), ('/activity', p['buyer']['headers']),
                          ('/notices', p['buyer']['headers']), ('/admin/reports', p['admin']['headers'])]:
        assert c.get(BASE+path, headers=headers, params=params).status_code == 422


def test_activity_auth_isolation_and_visible_parent_before_paging(public_mode):
    c, p, _ = public_mode
    assert c.get(BASE+'/activity').status_code == 401
    a = create(c, p['buyer']['headers'], 'demand', title='보이는 부모 게시물')
    b = create(c, p['seller']['headers'], 'demand', title='숨겨지는 부모 게시물')
    cmt = []
    for post in [a,b]:
        cmt.append(c.post(BASE+'/demands/'+post['id']+'/comments', headers=p['buyer2']['headers'], json={'body':'나의 댓글 검색어'}).json())
        assert c.put(BASE+'/demands/'+post['id']+'/interest', headers=p['buyer2']['headers']).status_code == 200
    set_created(cmt[1]['id'], '2099-01-01T00:00:00+00:00')
    with SessionLocal() as db:
        db.get(Record,b['id']).status = 'hidden'
        db.commit()
    comments = activity(c,p['buyer2']['headers'],'comments',limit=1,q='댓글')
    assert not comments['has_more'] and comments['items'][0]['comment']['id'] == cmt[0]['id']
    assert comments['items'][0]['post_title'] == a['title']
    interests = activity(c,p['buyer2']['headers'],'interests',limit=1,q='부모')
    assert not interests['has_more'] and interests['items'][0]['post']['id'] == a['id']
    assert activity(c,p['buyer']['headers'],'comments')['items'] == []
    assert activity(c,p['buyer2']['headers'])['items'] == []
    assert c.post('/api/blocks/'+p['buyer']['id'],headers=p['buyer2']['headers']).status_code == 200
    assert activity(c,p['buyer2']['headers'],'comments')['items'] == []
    assert activity(c,p['buyer2']['headers'],'interests')['items'] == []


@pytest.mark.parametrize('unavailable', ['deleted','suspended'])
def test_activity_excludes_unavailable_parent_authors(public_mode, unavailable):
    c,p,_=public_mode
    post=create(c,p['buyer']['headers'],'demand')
    c.post(BASE+'/demands/'+post['id']+'/comments',headers=p['buyer2']['headers'],json={'body':'부모가 유효해야 보이는 댓글'})
    c.put(BASE+'/demands/'+post['id']+'/interest',headers=p['buyer2']['headers'])
    with SessionLocal() as db:
        if unavailable == 'deleted':
            db.get(User,p['buyer']['id']).deleted=True
        else:
            db.add(Record(kind='suspension',owner_id=p['buyer']['id'],unique_key=p['buyer']['id'],data={}))
        db.commit()
    for tab in ['comments','interests']:
        assert activity(c,p['buyer2']['headers'],tab)['items'] == []


def test_activity_has_more_and_interest_period_is_action_creation(public_mode):
    c,p,_=public_mode
    posts=[create(c,p['buyer']['headers'],'demand',title=f'검색할 게시물 {i}') for i in range(3)]
    first=activity(c,p['buyer']['headers'],limit=2,q='검색할')
    second=activity(c,p['buyer']['headers'],limit=2,offset=2,q='검색할')
    assert first['has_more'] and len(first['items'])==2 and not second['has_more'] and len(second['items'])==1
    assert len({r['post']['id'] for r in first['items']+second['items']})==3
    c.put(BASE+'/demands/'+posts[0]['id']+'/interest',headers=p['buyer2']['headers'])
    with SessionLocal() as db:
        interest=db.scalar(select(Record).where(Record.kind==release.INTEREST,Record.owner_id==p['buyer2']['id']))
        interest.created=int(datetime.fromisoformat('2026-11-04T15:00:00+00:00').timestamp())
        db.commit()
    assert len(activity(c,p['buyer2']['headers'],'interests',start_date='2026-11-05',end_date='2026-11-05')['items'])==1


def test_concurrent_old_client_edits_preserve_type(public_mode):
    c,p,_=public_mode
    post=create(c,p['buyer']['headers'],'experience')
    payload={'title':'동시에 저장하는 육아 경험','body':'서로 다른 화면에서 저장해도 충돌을 알려줍니다.','category':'육아생활','revision':1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:c.put(BASE+'/demands/'+post['id'],headers=p['buyer']['headers'],json=payload).status_code,range(2)))
    assert sorted(statuses)==[200,409]
    saved=c.get(BASE+'/demands/'+post['id']).json()
    assert saved['post_type']=='experience' and saved['revision']==2


def make_report(c,p,post,target_type='demand'):
    r=c.post(BASE+'/reports',headers=p['buyer2']['headers'],json={
        'target_type':target_type,'target_id':post['id'],'reason':'REPORT-PRIVATE-TEXT 신고 내용'})
    assert r.status_code==201,r.text
    return r.json()['id']


def test_moderation_exact_evidence_reason_safe_notice_ack_and_idor(public_mode, monkeypatch):
    monkeypatch.setattr(release, 'now', lambda: int(datetime.fromisoformat('2026-11-05T15:00:00+00:00').timestamp()))
    c,p,_=public_mode
    post=create(c,p['buyer']['headers'],'question',title='REMOVED-PRIVATE-TEXT 본문 제목')
    report_id=make_report(c,p,post)
    set_created(report_id,'2026-11-04T15:00:00+00:00')
    url=BASE+'/admin/reports/'+report_id+'/resolve'
    open_report=c.get(BASE+'/admin/reports',headers=p['admin']['headers']).json()[0]
    assert open_report['resolved_at'] is None and open_report['action'] is None
    for invalid in [{'action':'hide'}, {'action':'hide','note':' '}, {'action':'hide','note':'x','actor_id':p['buyer']['id']}]:
        assert c.post(url,headers=p['admin']['headers'],json=invalid).status_code==422
    resolved=c.post(url,headers=p['admin']['headers'],json={'action':'hide','note':'ADMIN-PRIVATE-TEXT 운영 검토'}).json()
    assert resolved['target_id']==post['id'] and resolved['target_type']=='demand' and resolved['id']==report_id
    assert resolved['created_at']==open_report['created_at'] and resolved['resolved_at']
    assert resolved['resolved_by']==p['admin']['id'] and resolved['action']=='hide'
    assert c.post(url,headers=p['admin']['headers'],json={'action':'dismiss','note':'다시 처리하기'}).status_code==409
    assert c.get(BASE+'/notices',headers=p['buyer2']['headers']).json()['items']==[]
    notices=c.get(BASE+'/notices',headers=p['buyer']['headers']).json()
    assert not notices['has_more'] and len(notices['items'])==1
    assert not any(secret in str(notices) for secret in ['REMOVED-PRIVATE-TEXT','REPORT-PRIVATE-TEXT','ADMIN-PRIVATE-TEXT'])
    notice=notices['items'][0]
    assert notice['report_id']==report_id and notice['target_id']==post['id'] and notice['target_type']=='demand'
    assert notice['created_at']==resolved['resolved_at'] and notice['acknowledged_at'] is None
    ack=BASE+'/notices/'+notice['id']+'/ack'
    assert c.post(ack,headers=p['buyer2']['headers']).status_code==404
    assert c.post(ack).status_code==401
    first=c.post(ack,headers=p['buyer']['headers']).json()
    assert first['acknowledged_at']
    assert c.post(ack,headers=p['buyer']['headers']).json()==first
    assert c.get(BASE+'/notices',headers=p['buyer']['headers'],params={'end_date':'2026-11-05'}).json()['items']==[]
    assert c.get(BASE+'/admin/reports',headers=p['admin']['headers'],params={'start_date':'2026-11-05','end_date':'2026-11-05'}).json()[0]['id']==report_id
    assert c.get(BASE+'/admin/reports',headers=p['admin']['headers'],params={'date_basis':'action','end_date':'2026-11-05'}).json()==[]
    with SessionLocal() as db:
        audit=db.scalar(select(Record).where(Record.kind=='audit',Record.parent_id==report_id))
        assert audit.owner_id==p['admin']['id'] and audit.data['target_id']==post['id']
        assert audit.data['target_type']=='demand' and audit.data['received_at']==open_report['created_at']
        assert audit.data['acted_at']==resolved['resolved_at'] and audit.data['reason']=='ADMIN-PRIVATE-TEXT 운영 검토'


def test_comment_notice_target_dismiss_and_account_erasure_purge(public_mode):
    c,p,_=public_mode
    post=create(c,p['buyer']['headers'])
    comment=c.post(BASE+'/demands/'+post['id']+'/comments',headers=p['seller']['headers'],json={'body':'숨김 처리될 PRIVATE 댓글'}).json()
    report_id=make_report(c,p,comment,'comment')
    assert c.post(BASE+'/admin/reports/'+report_id+'/resolve',headers=p['admin']['headers'],json={'action':'hide','note':'댓글 운영 검토'}).status_code==200
    notice=c.get(BASE+'/notices',headers=p['seller']['headers']).json()['items'][0]
    assert notice['target_type']=='comment' and notice['target_id']==comment['id']
    assert 'PRIVATE' not in str(notice)
    with SessionLocal() as db:
        release.delete_user_content(db,p['buyer']['id'],[post['id']])
        db.commit()
        assert not db.scalar(select(Record.id).where(Record.kind==release.NOTICE,Record.id==notice['id']))
    other=create(c,p['buyer']['headers'])
    dismissed=make_report(c,p,other)
    assert c.post(BASE+'/admin/reports/'+dismissed+'/resolve',headers=p['admin']['headers'],json={'action':'dismiss','note':'위반 근거가 없습니다'}).status_code==200
    assert c.get(BASE+'/notices',headers=p['buyer']['headers']).json()['items']==[]


@pytest.mark.parametrize('target_type', ['demand', 'comment'])
def test_admin_removal_erases_content_preserves_audit_and_isolates_notice(public_mode, target_type):
    c,p,_=public_mode
    post=create(c,p['buyer']['headers'], title='PRIVATE-REMOVAL 글')
    reply=c.post(BASE+'/demands/'+post['id']+'/comments', headers=p['buyer']['headers'],
                 json={'body':'PRIVATE-REMOVAL 댓글'}).json()
    target=post if target_type=='demand' else reply
    report_id=make_report(c,p,target,target_type)
    url=BASE+'/admin/reports/'+report_id+'/resolve'
    payload={'action':'remove','note':'PRIVATE-REASON 운영 규칙 위반'}
    assert c.post(url, headers=p['buyer']['headers'], json=payload).status_code==403
    assert c.post(url, headers=p['admin']['headers'], json={'action':'remove'}).status_code==422
    resolved=c.post(url, headers=p['admin']['headers'], json=payload)
    assert resolved.status_code==200, resolved.text
    assert resolved.json()['action']=='remove' and resolved.json()['target_preview']==''
    assert c.post(url, headers=p['admin']['headers'], json=payload).status_code==409
    notice=c.get(BASE+'/notices', headers=p['buyer']['headers']).json()['items'][0]
    assert notice['action']=='remove' and notice['target_id']==target['id'] and '삭제' in notice['reason']
    assert 'PRIVATE' not in str(notice)
    assert c.get(BASE+'/notices', headers=p['buyer2']['headers']).json()['items']==[]
    with SessionLocal() as db:
        stored=db.get(Record,target['id'])
        assert stored.status=='deleted' and stored.data=={} and stored.revision==2
        audit=db.scalar(select(Record).where(Record.kind=='audit',Record.parent_id==report_id))
        assert audit.data['action']=='release-report-remove' and audit.data['target_id']==target['id']
        if target_type=='demand':
            assert db.get(Record,reply['id']).data=={} and db.get(Record,reply['id']).status=='deleted'
    if target_type=='demand':
        assert c.get(BASE+'/demands/'+post['id']).status_code==404
        assert c.get(BASE+'/demands/'+post['id']+'/comments').status_code==404
        assert activity(c,p['buyer']['headers'],'posts')['items']==[]
    else:
        assert c.get(BASE+'/demands/'+post['id']).status_code==200
        assert c.get(BASE+'/demands/'+post['id']+'/comments').json()==[]
    assert activity(c,p['buyer']['headers'],'comments')['items']==[]


def test_admin_content_removal_cannot_delete_user_account(public_mode):
    c,p,_=public_mode
    report=make_report(c,p,{'id':p['buyer']['id']},'user')
    response=c.post(BASE+'/admin/reports/'+report+'/resolve', headers=p['admin']['headers'],
                    json={'action':'remove','note':'계정은 콘텐츠 삭제 대상 아님'})
    assert response.status_code==422
    with SessionLocal() as db:
        assert not db.get(User,p['buyer']['id']).deleted
        assert db.get(Record,report).status=='active'


def test_account_erasure_removes_connected_moderator_quotes_and_legacy_audits(public_mode):
    from conftest import PASSWORD
    c,p,_=public_mode
    own=create(c,p['buyer']['headers'],title='ERASE-PRIVATE-CONTENT 계정 글')
    other=create(c,p['seller']['headers'],title='다른 계정의 유지되는 글')
    reply=c.post(BASE+'/demands/'+own['id']+'/comments',headers=p['seller']['headers'],json={'body':'부모 삭제 시 연결되는 댓글'}).json()
    comment=c.post(BASE+'/demands/'+other['id']+'/comments',headers=p['buyer']['headers'],json={'body':'ERASE-PRIVATE-CONTENT 계정 댓글'}).json()
    report_ids=[]
    for target,kind in [(own,'demand'),(reply,'comment'),(comment,'comment')]:
        report_ids.append(make_report(c,p,target,kind))
    for report_id in report_ids:
        response=c.post(BASE+'/admin/reports/'+report_id+'/resolve',headers=p['admin']['headers'],
                        json={'action':'hide','note':'ERASE-PRIVATE-QUOTED 관리자 인용 사유'})
        assert response.status_code==200,response.text
    with SessionLocal() as db:
        legacy=Record(kind='report',owner_id=p['buyer2']['id'],parent_id=comment['id'],data={'reason':'ERASE-PRIVATE-LEGACY'})
        application=Record(kind='application',owner_id=p['buyer']['id'],data={'contact_email':'ERASE-PRIVATE-APPLICATION'})
        db.add_all([legacy,application]);db.flush()
        audits=[
            Record(kind='audit',owner_id=p['admin']['id'],parent_id=application.id,data={'action':'application-review','note':'ERASE-PRIVATE-QUOTED'}),
            Record(kind='audit',owner_id=p['admin']['id'],parent_id=legacy.id,data={'action':'old-review: ERASE-PRIVATE-QUOTED'}),
            Record(kind='audit',owner_id=p['admin']['id'],data={'report_id':report_ids[0],'note':'ERASE-PRIVATE-QUOTED'}),
            Record(kind='audit',owner_id=p['admin']['id'],data={'target_id':p['buyer']['id'],'reason':'ERASE-PRIVATE-QUOTED'}),
            Record(kind='audit',owner_id=p['admin']['id'],data={'question_id':comment['id'],'reason':'ERASE-PRIVATE-QUOTED'}),
        ]
        unrelated=Record(kind='audit',owner_id=p['admin']['id'],parent_id=other['id'],data={'action':'keep','reason':'KEEP-UNRELATED-REASON'})
        db.add_all([*audits,unrelated]);db.commit()
        deleted_audit_ids=[row.id for row in audits]
        keep_id=unrelated.id
    response=c.request('DELETE','/api/me',headers=p['buyer']['headers'],json={'password':PASSWORD})
    assert response.status_code==200,response.text
    with SessionLocal() as db:
        for id in deleted_audit_ids:assert db.get(Record,id) is None
        assert db.get(Record,keep_id).data['reason']=='KEEP-UNRELATED-REASON'
        assert db.get(Record,other['id']) is not None
        assert all('ERASE-PRIVATE' not in str(row.data) for row in db.scalars(select(Record)))
        assert not list(db.scalars(select(Record).where(Record.kind==release.REPORT,Record.id.in_(report_ids))))


def seed_notices(owner_id,count,acknowledged_newest=0):
    from app.db import now
    ids=[]
    with SessionLocal() as db:
        for index in range(count):
            row=Record(kind=release.NOTICE,owner_id=owner_id,parent_id='synthetic-report',created=now()-index,
                       data={'target_type':'demand','target_id':'synthetic-post','action':'hide','reason':'운영정책 안내',
                             'acknowledged_at':release.timestamp(now()) if index<acknowledged_newest else None})
            db.add(row);db.flush();ids.append(row.id)
        db.commit()
    return ids


def test_pending_notices_filter_acknowledged_rows_before_pagination(public_mode):
    c,p,_=public_mode
    ids=seed_notices(p['buyer']['id'],21,acknowledged_newest=20)
    history=c.get(BASE+'/notices',headers=p['buyer']['headers'],params={'limit':20}).json()
    assert len(history['items'])==20 and history['has_more']
    pending=c.get(BASE+'/notices',headers=p['buyer']['headers'],params={'limit':20,'pending_only':'true'}).json()
    assert [item['id'] for item in pending['items']]==[ids[-1]] and not pending['has_more']
    assert c.get(BASE+'/notices',headers=p['buyer2']['headers'],params={'pending_only':'true'}).json()['items']==[]
    assert c.get(BASE+'/notices',headers=p['buyer']['headers'],params={'pending_only':'invalid'}).status_code==422


def test_more_than_twenty_pending_notices_remain_reachable_after_ack(public_mode):
    c,p,_=public_mode
    ids=seed_notices(p['buyer']['id'],21)
    params={'pending_only':'true','limit':20,'offset':0}
    first=c.get(BASE+'/notices',headers=p['buyer']['headers'],params=params).json()
    assert len(first['items'])==20 and first['has_more'] and ids[-1] not in {item['id'] for item in first['items']}
    first_id=first['items'][0]['id']
    assert c.post(BASE+'/notices/'+first_id+'/ack',headers=p['buyer']['headers']).status_code==200
    second=c.get(BASE+'/notices',headers=p['buyer']['headers'],params=params).json()
    assert len(second['items'])==20 and not second['has_more']
    assert ids[-1] in {item['id'] for item in second['items']} and first_id not in {item['id'] for item in second['items']}
    for item in second['items']:
        assert c.post(BASE+'/notices/'+item['id']+'/ack',headers=p['buyer']['headers']).status_code==200
    assert c.get(BASE+'/notices',headers=p['buyer']['headers'],params=params).json()=={'items':[],'has_more':False}
    assert len(c.get(BASE+'/notices',headers=p['buyer']['headers'],params={'limit':100,'pending_only':'false'}).json()['items'])==21
