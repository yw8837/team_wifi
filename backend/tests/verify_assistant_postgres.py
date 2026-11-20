"""Additional real PostgreSQL community/chat/quota checks; no limiter bypass.

ASGI clients use the actual middleware and database. Model/Opik are explicitly
not measured here: inference barriers wrap the normal disabled-model fallback.
Quota saturation runs across independent Python processes, each below its
unchanged process-local ceiling, against one dedicated disposable PostgreSQL DB.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
BASE = '/api/release/assistant'
QUESTION = '젖병 용량과 소재 비교'


def pace(reserve=1, assistant=False):
    from app import security
    announced=False
    while True:
        stamp=time.monotonic();wait=0
        with security._global_lock:
            for name in ['write']+(['assistant'] if assistant else []):
                active=[value for value in security._global_attempts[name] if value>stamp-60]
                excess=len(active)+reserve-security.GLOBAL_LIMITS[name]
                if excess>0:wait=max(wait,active[excess-1]+60-stamp+.05)
        if wait<=0:return
        if not announced:
            print('WAIT_UNCHANGED_GLOBAL_GUARD_SECONDS',round(wait,2),flush=True);announced=True
        time.sleep(min(wait,30))


def quota_worker():
    # A subprocess must never accidentally target QA, a deployment or remote DB.
    url=urlsplit(os.environ.get('DATABASE_URL',''))
    if url.hostname!='127.0.0.1' or url.port in (55441,5432) or os.environ.get('COMMUNITY_PG_DISPOSABLE')!='1':
        raise SystemExit('Dedicated disposable PostgreSQL marker required')
    payload=json.load(sys.stdin)
    os.environ.update(MODU_ENV='public_release',ASSISTANT_MODEL_ENABLED='false',ASSISTANT_OPIK_ENABLED='false')
    sys.path.insert(0,str(ROOT/'backend'))
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import engine
    while time.time()<payload['start_at']:time.sleep(.01)
    with TestClient(app,base_url='https://beta.example.test',client=(payload['peer'],42000)) as client:
        def ask(_):
            return client.post(BASE+'/ask',headers=payload.get('headers',{}),
                               json={'question':'아기 증상과 약 복용 판단','remember':False}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses=list(pool.map(ask,range(payload['count'])))
    engine.dispose()
    print(json.dumps({'statuses':statuses,'postgresql':True,'guards_disabled':False}))


def processes(payloads,expect):
    workers=[]
    start_at=time.time()+5
    environment={**os.environ,'MODU_ENV':'public_release','COMMUNITY_PG_DISPOSABLE':'1'}
    for payload in payloads:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--quota-worker'],
            cwd=ROOT,env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        process.stdin.write(json.dumps({**payload,'start_at':start_at}));process.stdin.close();process.stdin=None
        workers.append(process)
    results=[]
    try:
        for worker in workers:
            out,err=worker.communicate(timeout=50)
            expect(worker.returncode==0,'quota subprocess exits successfully: '+str(worker.returncode))
            result=json.loads(out)
            expect(result['postgresql'] and not result['guards_disabled'],'quota subprocess keeps real PostgreSQL and guards')
            results.extend(result['statuses'])
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate();worker.wait(timeout=10)
    return results


def checks(client,expect):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from sqlalchemy import select,text
    from app import assistant,assistant_tools,config,model_runtime,security
    from app.db import Record,RateBucket,SessionLocal,Token,User,engine,now
    from app.main import app
    expect(engine.dialect.name=='postgresql' and config.PUBLIC_RELEASE and config.deployed(),
           'extended checks use deployed public-release real PostgreSQL')
    expect(os.getenv('ASSISTANT_MODEL_ENABLED')=='false','PG lifecycle evidence excludes unmeasured model inference')
    password='Dedicated-PG-synthetic-only-password-123'
    hashed=security.passwords.hash(password)
    def person(name,admin=False):
        with SessionLocal() as db:
            user=User(email='extended-'+name+'@example.com',nickname='격리검증 '+name,password_hash=hashed,is_admin=admin)
            db.add(user);db.flush();token=security.issue_token(db,user);db.commit()
            return {'id':user.id,'email':user.email,'headers':{'Authorization':'Bearer '+token}}
    a,b,admin,quota,doomed=[person(name,name=='admin') for name in ['a','b','admin','quota','doomed']]
    pace()
    login=client.post('/api/auth/login',json={'email':a['email'],'password':password})
    expect(login.status_code==200,'independent password login obtains second session PostgreSQL: '+str(login.status_code))
    second_headers={'Authorization':'Bearer '+login.json()['access_token']}
    with TestClient(app,base_url='https://beta.example.test') as independent:
        expect(independent.get('/api/me',headers=second_headers).json()['id']==a['id'],
               'independent ASGI session resolves shared account in PostgreSQL')
    def write(path,method='POST',headers=None,body=None):
        pace();return client.request(method,path,headers=headers or {},json=body)
    articles=[]
    for kind in ['question','experience','information','demand']:
        response=write('/api/release/demands',headers=a['headers'],body={
            'post_type':kind,'title':'격리PG 커뮤니티 '+kind,'body':'합성 육아 정보를 실제 PostgreSQL에서 검증합니다.','category':'육아생활'})
        expect(response.status_code==201,'PostgreSQL post type create '+kind);articles.append(response.json())
    info=articles[2];demand=articles[3]
    response=write('/api/release/demands/'+info['id'],'PUT',a['headers'],{
        'title':info['title'],'body':info['body'],'category':info['category'],'revision':1})
    expect(response.status_code==200 and response.json()['post_type']=='information',
           'old-client PostgreSQL edit preserves stored post type')
    expect(write('/api/release/demands/'+info['id']+'/interest','PUT',b['headers']).status_code==422,
           'PostgreSQL rejects non-demand interest')
    expect(write('/api/release/demands/'+demand['id']+'/interest','PUT',b['headers']).status_code==200,
           'PostgreSQL demand interest remains compatible')
    with SessionLocal() as db:
        for item,stamp in zip(articles,['2026-11-04T14:59:59+00:00','2026-11-04T15:00:00+00:00',
                                        '2026-11-05T14:59:59+00:00','2026-11-05T15:00:00+00:00']):
            db.get(Record,item['id']).created=int(datetime.fromisoformat(stamp).timestamp())
        db.commit()
    query={'q':'격리PG','start_date':'2026-11-05','end_date':'2026-11-05'}
    response=client.get('/api/release/demands',params=query)
    expect({row['id'] for row in response.json()}=={articles[1]['id'],articles[2]['id']},
           'PostgreSQL KST inclusive date boundaries use creation time')
    expect(client.get('/api/release/demands',params={'start_date':'2026-11-06','end_date':'2026-11-05'}).status_code==422,
           'PostgreSQL feed rejects reversed dates')
    activity=client.get('/api/release/activity',headers=second_headers,params={**query,'tab':'posts','limit':1}).json()
    expect(len(activity['items'])==1 and activity['has_more'],'independent session activity uses filtered PostgreSQL pagination')
    reply=write('/api/release/demands/'+demand['id']+'/comments',headers=b['headers'],body={'body':'합성 부모 가시성 댓글'})
    expect(reply.status_code==201,'PostgreSQL activity comment fixture created')
    expect(write('/api/blocks/'+a['id'],headers=b['headers']).status_code==200,'PostgreSQL activity parent author block')
    expect(client.get('/api/release/activity?tab=comments',headers=b['headers']).json()['items']==[],
           'PostgreSQL comment activity excludes blocked parent before page')
    expect(write('/api/blocks/'+a['id'],'DELETE',b['headers']).status_code==200,'PostgreSQL activity unblock')
    report=write('/api/release/reports',headers=b['headers'],body={
        'target_type':'demand','target_id':info['id'],'reason':'합성 신고 원문은 알림에 복제하지 않습니다.'})
    expect(report.status_code==201,'PostgreSQL reasoned report created')
    report_id=report.json()['id']
    resolved=write('/api/release/admin/reports/'+report_id+'/resolve',headers=admin['headers'],
                   body={'action':'hide','note':'SYNTHETIC_PRIVATE_ADMIN_NOTE 운영 검토'})
    expect(resolved.status_code==200 and resolved.json()['resolved_at'],'PostgreSQL moderation action records actual timestamp')
    notices=client.get('/api/release/notices',headers=a['headers']).json()['items']
    notice=next(row for row in notices if row['report_id']==report_id)
    expect(notice['target_id']==info['id'] and 'SYNTHETIC_PRIVATE_ADMIN_NOTE' not in json.dumps(notice),
           'PostgreSQL notice preserves exact target without private removed text')
    expect(write('/api/release/notices/'+notice['id']+'/ack',headers=b['headers']).status_code==404,
           'PostgreSQL notice acknowledgement rejects another account')
    first_ack=write('/api/release/notices/'+notice['id']+'/ack',headers=second_headers)
    second_ack=write('/api/release/notices/'+notice['id']+'/ack',headers=a['headers'])
    expect(first_ack.status_code==200 and second_ack.json()==first_ack.json(),'PostgreSQL notice duplicate acknowledgement is idempotent')

    # Fixed real clock windows, never clear/patch/disable the limiter to saturate it.
    remaining=600-now()%600
    if remaining<30:
        print('WAIT_REAL_QUOTA_WINDOW_SECONDS',remaining+1,flush=True);time.sleep(remaining+1)
    pace(assistant=True)
    invalid=client.post(BASE+'/ask',headers=quota['headers'],json={'question':'x'})
    expect(invalid.status_code==422,'failed assistant input is precharged before PostgreSQL domain validation')
    saturated=processes([{'headers':quota['headers'],'peer':'198.51.100.90','count':11},
                         {'headers':quota['headers'],'peer':'198.51.100.90','count':10}],expect)
    expect(saturated.count(200)==19 and saturated.count(429)==2,
           'real concurrent process assistant account quota: '+str({code:saturated.count(code) for code in set(saturated)}))
    restarted=processes([{'headers':quota['headers'],'peer':'198.51.100.90','count':1}],expect)
    expect(restarted==[429],'assistant account quota survives real Python process restart')
    with SessionLocal() as db:
        bucket=db.get(RateBucket,security.rate_key('account',quota['id'],'assistant',now()))
        expect(bucket is not None and bucket.count==23,'PostgreSQL stores failed and rejected assistant attempts durably')
    anonymous=processes([{'peer':'198.51.100.91','count':11} for _ in range(3)],expect)
    expect(anonymous.count(200)==30 and anonymous.count(429)==3,
           'real concurrent process anonymous peer quota: '+str({code:anonymous.count(code) for code in set(anonymous)}))

    def ask(headers=None,**extra):
        pace(assistant=True)
        return client.post(BASE+'/ask',headers=headers or {},json={'question':QUESTION,**extra})
    temporary=ask()
    expect(temporary.status_code==200 and temporary.json()['conversation_id'] is None,
           'PostgreSQL anonymous assistant defaults to temporary conversation')
    with SessionLocal() as db:
        expect(not db.scalar(select(Record.id).where(Record.kind==assistant.CHAT)),
               'quota and temporary assistant requests store no conversations')
    saved=ask(a['headers'],remember=True)
    expect(saved.status_code==200 and saved.json()['conversation_id'],'PostgreSQL explicit conversation opt in')
    identifier=saved.json()['conversation_id']
    with TestClient(app,base_url='https://beta.example.test') as independent:
        detail=independent.get(BASE+'/conversations/'+identifier,headers=second_headers)
    expect(detail.status_code==200 and len(detail.json()['messages'])==2,
           'saved PostgreSQL conversation resumes in independent authenticated session')
    expect(client.get(BASE+'/conversations/'+identifier,headers=b['headers']).status_code==404,
           'PostgreSQL saved conversation cross-account IDOR denied')
    original_generate=model_runtime.generate
    @contextmanager
    def held_generation(parties=1):
        ready=threading.Barrier(parties+1);resume=threading.Event()
        def held(question,chunks):
            ready.wait(timeout=15)
            if not resume.wait(20):raise AssertionError('bounded PG inference barrier timed out')
            return original_generate(question,chunks)
        model_runtime.generate=held
        try:yield ready,resume
        finally:resume.set();model_runtime.generate=original_generate
    pace(2,assistant=True)
    with held_generation(2) as (ready,resume),ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(client.post,BASE+'/ask',headers=a['headers'],json={
            'question':QUESTION,'remember':True,'conversation_id':identifier}) for _ in range(2)]
        ready.wait(timeout=15)
        with SessionLocal() as db:
            held_transactions=db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='idle in transaction' AND pid<>pg_backend_pid()"))
        expect(held_transactions==0,'actual pg_stat_activity shows no idle SQL transaction during held generation')
        resume.set();statuses=[future.result(timeout=20).status_code for future in futures]
    expect(sorted(statuses)==[200,409],'real PostgreSQL simultaneous saved asks reject stale revision: '+str(statuses))
    with SessionLocal() as db:
        row=db.get(Record,identifier)
        expect(len(row.data['messages'])==4 and row.revision==3,'PostgreSQL concurrent asks append exactly one message pair')
    def race(headers,conversation,action,label,allowed):
        pace(2,assistant=True)
        with held_generation() as (ready,resume),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(client.post,BASE+'/ask',headers=headers,json={
                'question':QUESTION,'remember':True,'conversation_id':conversation})
            ready.wait(timeout=15);action();resume.set();response=future.result(timeout=20)
        expect(response.status_code in allowed,label+': '+str(response.status_code))
    race(a['headers'],identifier,lambda:expect(write(BASE+'/conversations/'+identifier+'/end',headers=second_headers).status_code==200,
         'independent PostgreSQL session ends pending conversation'),'late ask cannot recreate ended PostgreSQL conversation',{409})
    with SessionLocal() as db:
        row=db.get(Record,identifier);expect(row.status=='ended' and row.data=={},'ended PostgreSQL conversation retains no text')
    opt=ask(a['headers'],remember=True).json()['conversation_id']
    opted=ask(a['headers'],remember=False,conversation_id=opt)
    expect(opted.status_code==200 and opted.json()['conversation_id'] is None,'PostgreSQL opt out invalidates stored conversation')
    with SessionLocal() as db:expect(db.get(Record,opt).data=={},'PostgreSQL opt out immediately erases text')
    with SessionLocal() as db:
        before_failed={row.id for row in db.scalars(select(Record).where(Record.kind==assistant.CHAT,Record.owner_id==a['id']))
                       if row.status in ('active','pending') and not row.data.get('messages')}
    real_live_read=assistant_tools.live_read
    calls=[]
    def fail_final_read(db,user,question):
        calls.append('read')
        if len(calls)==2:
            raise HTTPException(503,'합성 최종 조회 실패로 예약 슬롯 정리를 검증합니다.')
        return real_live_read(db,user,question)
    assistant_tools.live_read=fail_final_read
    try:
        failed_new=ask(a['headers'],remember=True)
    finally:
        assistant_tools.live_read=real_live_read
    expect(failed_new.status_code==503 and len(calls)==2,'new PostgreSQL saved-chat request exercises real final transaction failure')
    with SessionLocal() as db:
        after_failed={row.id for row in db.scalars(select(Record).where(Record.kind==assistant.CHAT,Record.owner_id==a['id']))
                      if row.status in ('active','pending') and not row.data.get('messages')}
    expect(after_failed==before_failed,'failed PostgreSQL saved-chat reservation cleanup commits despite API 503')
    expiring=ask(a['headers'],remember=True).json()['conversation_id']
    def expire():
        with SessionLocal() as db:db.get(Record,expiring).ends=now()-1;db.commit()
    race(a['headers'],expiring,expire,'late ask cannot resurrect expired PostgreSQL conversation',{404})
    expect(client.get(BASE+'/conversations',headers=a['headers']).status_code==200,'PostgreSQL expired history access cleanup')
    with SessionLocal() as db:expect(db.get(Record,expiring) is None,'PostgreSQL expired text is physically removed')
    revoking=ask(a['headers'],remember=True).json()['conversation_id']
    race(a['headers'],revoking,lambda:expect(write('/api/auth/logout',headers=a['headers']).status_code==200,
         'PostgreSQL logout revokes pending request session'),'late PostgreSQL answer reauthenticates revoked token',{401})
    expect(client.get('/api/me',headers=a['headers']).status_code==401 and client.get('/api/me',headers=second_headers).status_code==200,
           'PostgreSQL revokes only logged-out token and preserves independent session')
    deleting=ask(doomed['headers'],remember=True).json()['conversation_id']
    race(doomed['headers'],deleting,lambda:expect(write('/api/me','DELETE',doomed['headers'],{'password':password}).status_code==200,
         'PostgreSQL account erasure completes during pending answer'),'late answer cannot recreate erased account chat',{401})
    with SessionLocal() as db:
        expect(db.get(Record,deleting) is None and not db.scalar(select(Token.digest).where(Token.user_id==doomed['id'])),
               'PostgreSQL account erasure removes chats and all tokens')
    expect(model_runtime.generate is original_generate,'inference barrier instrumentation is restored')

    from verify_groupbuy_postgres import checks as groupbuy_checks
    groupbuy_checks(client,expect)


if __name__=='__main__' and sys.argv[1:]==['--quota-worker']:
    quota_worker()
