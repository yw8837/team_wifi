"""Extend the owned localhost beta harness with public-release PostgreSQL checks.

Run from E:/Team_Wifi with backend/.venv/Scripts/python.exe and the same --pg-bin /
--runtime arguments as scripts/verify-beta-postgres.py. Never reads remote config.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runpy


def checks(c, expect):
    from app import config, release, security
    from app.db import Record, RateBucket, SessionLocal, Token, User
    from sqlalchemy import delete, select

    config.BETA, config.PUBLIC_RELEASE = False, True
    for bucket in security._global_attempts.values():
        bucket.clear()
    with SessionLocal() as db:
        db.execute(delete(RateBucket))
        db.commit()

    password = 'Public-postgres-fixture-password-123'
    def signup(index):
        response = c.post('/api/auth/register', json=dict(email=f'public{index}@example.com', nickname=f'공개시험{index}',
            password=password, track='buyer', terms_accepted=True, privacy_accepted=True, adult_confirmed=True))
        expect(response.status_code == 201, 'public no-invite adult signup '+str(index))
        return response.json()
    first, second = signup(1), signup(2)
    h1, h2 = [{'Authorization':'Bearer '+account['access_token']} for account in (first, second)]
    renamed = c.put('/api/auth/profile', headers=h1, json={'nickname':'프로필변경'})
    expect(renamed.status_code == 200 and renamed.json() == {**first['user'], 'nickname':'프로필변경'}, 'profile changes only nickname PostgreSQL')
    expect(c.get('/api/me', headers=h1).json()['nickname'] == '프로필변경', 'profile persists PostgreSQL')
    expect(c.get('/api/me', headers=h2).json() == second['user'], 'profile account isolation PostgreSQL')
    expect(c.put('/api/auth/profile', headers=h1, json={'nickname':'권한변경', 'is_admin':True}).status_code == 422, 'profile rejects privilege change PostgreSQL')
    preferences = {'categories': ['기저귀·물티슈'], 'priority': 'unit_price'}
    expect(c.put('/api/release/preferences', headers=h1, json=preferences).status_code == 200, 'public preferences PostgreSQL upsert insert')
    preferences['priority'] = 'care'
    expect(c.put('/api/release/preferences', headers=h1, json=preferences).status_code == 200, 'public preferences PostgreSQL upsert update')
    expect(c.get('/api/release/preferences', headers=h1).json() == preferences, 'public preferences persisted')
    expect(c.get('/api/release/preferences', headers=h2).json()['categories'] == [], 'public preferences account isolation')
    expect(c.get('/api/release/recommendations', headers=h1).json()['basis'] == 'preferences', 'public recommendations use declared interests')
    expect(c.delete('/api/release/preferences', headers=h1).status_code == 200, 'public preferences reset')
    expect(c.get('/api/config').json()['public_release'] is True, 'public deployment config')
    expect(c.get('/api/health').json()['mode']=='public-release', 'public deployment health mode')
    expect(not first['user']['email_verified'], 'public does not claim email ownership')
    expect(c.get('/api/campaigns').status_code==404 and c.post('/api/admin/orders',headers=h1,json={}).status_code==404,
           'public legacy read and order mutation denied before domain/auth')
    catalog = c.get('/api/release/offers')
    expect(catalog.status_code==200 and all(entry['entry_type']=='shopping_reference' and entry['price'] is None for entry in catalog.json()),
           'checked-in public manifest only with no invented prices')
    offer_id = catalog.json()[0]['id']
    choices = {'categories': ['수유·이유식'], 'priority': 'composition', 'purpose': 'gift', 'budget_max': None}
    expect(c.post('/api/release/advisor/preview', json=choices).status_code == 200, 'anonymous advisor preview with deployed request guard')
    expect(c.put('/api/release/advisor', headers=h1, json=choices).status_code == 200, 'advisor PostgreSQL choice upsert')
    choices['priority'] = 'care'
    expect(c.put('/api/release/advisor', headers=h1, json=choices).status_code == 200, 'advisor PostgreSQL choice update')
    expect(c.get('/api/release/advisor', headers=h1).json()['choices'] == choices, 'advisor persisted choices')
    expect(not c.get('/api/release/advisor', headers=h2).json()['has_saved_choices'], 'advisor account isolation')
    expect(c.delete('/api/release/advisor', headers=h1).status_code == 200 and not c.get('/api/release/advisor', headers=h1).json()['has_saved_choices'], 'advisor explicit deletion')
    expect(c.get('/api/release/offers/'+offer_id+'/companions').status_code == 200, 'companion distinct aggregate PostgreSQL query')
    expect(c.get('/api/release/offers/'+offer_id+'/guide').json()['structured_data']['@type'] == 'Article', 'public reference schema scope')
    expect(c.post('/api/auth/login', json={'email':'public1@example.com','password':password}).status_code == 200,
           'public PostgreSQL registration and password login roundtrip')
    expect(c.put('/api/release/measurement/consent', headers=h1, json={'enabled':True}).status_code == 200,
           'measurement explicit opt in PostgreSQL')
    event = {'offer_id':offer_id, 'placement':'catalog', 'channel':'web', 'action':'view', 'visible_ms':1000}
    for _ in range(2):
        expect(c.post('/api/release/measurement/events',headers=h1,json=event).json()['recorded'], 'measurement PostgreSQL idempotent impression')
    expect(c.post('/api/release/measurement/events',headers=h1,json={**event,'action':'detail'}).json()['recorded'], 'measurement click after impression')
    for _ in range(2):
        expect(c.put('/api/release/offers/'+offer_id+'/saved',headers=h1).status_code==200, 'public saved idempotent PUT')
    expect(len(c.get('/api/release/saved',headers=h1).json())==1, 'one public saved record')
    with SessionLocal() as db:
        measured = list(db.scalars(select(Record).where(Record.kind == 'growth_exposure', Record.owner_id == first['user']['id'])))
        expect(len(measured) == 1 and measured[0].data['saved'], 'server-confirmed save attribution PostgreSQL')
    expect(c.put('/api/release/measurement/consent',headers=h1,json={'enabled':False}).status_code == 200, 'measurement opt out')
    with SessionLocal() as db:
        expect(not db.scalar(select(Record.id).where(Record.kind == 'growth_exposure',Record.owner_id == first['user']['id'])), 'opt out removes analysis records')
    response=c.post('/api/release/demands',headers=h1,json={'title':'기저귀 함께 비교하기','body':'기저귀 단위당 가격과 배송 조건을 비교합니다.','category':'기저귀·물티슈'})
    expect(response.status_code==201,'public demand write with durable quota')
    demand_id=response.json()['id']
    url='/api/release/demands/'+demand_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:c.put(url+'/interest',headers=h2).status_code,range(2)))
    expect(all(status in (200,409) for status in replies) and 200 in replies,'public concurrent interest serializable outcome')
    expect(c.put(url+'/interest',headers=h2).status_code==200 and c.get(url).json()['interest_count']==1,
           'public interest database uniqueness and retry idempotence')
    edit_body={'title':'수정한 기저귀 질문','body':'기저귀 단위당 가격과 구성품을 비교합니다.','category':'기저귀·물티슈','revision':1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        edits=list(pool.map(lambda _:c.put(url,headers=h1,json=edit_body).status_code,range(2)))
    expect(sorted(edits)==[200,409], 'concurrent edits reject stale revision PostgreSQL')
    expect(c.get(url).json()['revision']==2 and c.get(url).json()['interest_count']==1, 'edit preserves unique interests')
    expect(c.put(url,headers=h2,json={**edit_body,'revision':2}).status_code==404, 'edit rejects non-author PostgreSQL')
    reply=c.post(url+'/comments',headers=h1,json={'body':'작성자 댓글 검증'}).json()
    reply_url='/api/release/comments/'+reply['id']
    expect(c.put(reply_url,headers=h1,json={'body':'작성자 댓글 수정','revision':1}).status_code==200, 'comment edit with durable write quota')
    expect(c.put(reply_url,headers=h1,json={'body':'충돌한 댓글 수정','revision':1}).status_code==409, 'stale comment edit rejected PostgreSQL')
    expect(c.delete(reply_url,headers=h1).status_code==200, 'remove owned fixture comment')
    statuses=[c.post(url+'/comments',headers=h2,json={'body':f'실제 요청 제한 검증 질문 {i}'}).status_code for i in range(31)]
    expect(statuses==[201]*30+[429], 'public comments persistent per-account request quota')
    with SessionLocal() as db:
        expect(db.scalar(select(RateBucket.key)) is not None,'public rate buckets persisted in PostgreSQL')
    expect(c.post('/api/blocks/'+second['user']['id'],headers=h1).status_code==200,'public block write')
    expect(c.get(url+'/comments',headers=h1).json()==[],'public block filters comments')
    expect(c.delete('/api/blocks/'+second['user']['id'],headers=h1).status_code==200,'public unblock write')
    report=c.post('/api/release/reports',headers=h2,json={'target_type':'demand','target_id':demand_id,'reason':'운영자 숨김 처리 실제 DB 검증'} )
    expect(report.status_code==201,'public report durable quota')
    expect(c.get('/api/release/admin/reports',headers=h2).status_code==403,'public admin role enforcement')
    # Role belongs only to this disposable local fixture. No production users touched.
    with SessionLocal() as db:
        user=db.get(User,first['user']['id'])
        user.is_admin=True
        db.commit()
    insights = c.get('/api/release/admin/insights', headers=h1)
    expect(insights.status_code == 200 and insights.json()['saved_accounts'] is None,
           'public insights PostgreSQL aggregate and small-cohort suppression')
    expect(c.post('/api/release/admin/reports/'+report.json()['id']+'/resolve',headers=h1,json={'action':'hide','note':'로컬 검증'}).status_code==200,
           'public moderation hides real target')
    expect(c.get(url).status_code==404,'public hidden demand excluded')
    expect(c.request('DELETE','/api/me',headers=h1,json={'password':password}).status_code==200,'public account deletion')
    with SessionLocal() as db:
        expect(not db.scalar(select(Record.id).where(Record.owner_id==first['user']['id'])),'public deleted owner content removed')
        expect(not db.scalar(select(Record.id).where(Record.kind.in_([release.COMMENT,release.INTEREST,release.REPORT]),Record.parent_id==demand_id)),
               'public deletion cascades linked content')
        expect(not db.scalar(select(Token.digest).where(Token.user_id==first['user']['id'])),'public deletion revokes tokens')

    from verify_assistant_postgres import checks as extended_checks
    extended_checks(c, expect)


def source_snapshot(root):
    import hashlib
    files = [root/'scripts/verify-beta-postgres.py', Path(__file__),
             root/'backend/tests/verify_assistant_postgres.py',root/'backend/tests/verify_groupbuy_postgres.py', root/'backend/requirements.txt']
    files.extend(path for path in (root/'backend/app').iterdir() if path.suffix in ('.py', '.json'))
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


if __name__=='__main__':
    import argparse
    from datetime import datetime, timezone
    import importlib.metadata
    import json
    import os
    import socket
    import subprocess
    import sys
    os.environ.update(ASSISTANT_MODEL_ENABLED='false', ASSISTANT_OPIK_ENABLED='false')
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--evidence-dir', type=Path, default=root/'artifacts/beta')
    parser.add_argument('--port', type=int, default=55439)
    options,_=parser.parse_known_args()
    evidence=options.evidence_dir.resolve()
    if not evidence.is_relative_to(root):
        raise SystemExit('PostgreSQL evidence must stay within this workspace.')
    evidence.mkdir(parents=True,exist_ok=True)
    before=source_snapshot(root)
    started=datetime.now(timezone.utc).isoformat()
    (evidence/'postgres-source-before.json').write_text(json.dumps({'started_at':started,'sha256':before},
        ensure_ascii=False,indent=2),encoding='utf-8')
    status,error='failed',None
    try:
        harness=runpy.run_path(str(root/'scripts/verify-beta-postgres.py'))
        harness['run'](extra_checks=checks,evidence_name='postgres-community-assistant-results.json')
        status='pass'
    except BaseException as exc:
        error=type(exc).__name__  # No exception/SQL/credential content enters the artifact.
        raise
    finally:
        after=source_snapshot(root)
        changed=sorted(path for path in set(before)|set(after) if before.get(path)!=after.get(path))
        with socket.socket() as probe:
            probe.settimeout(.5)
            port_still_listening=probe.connect_ex(('127.0.0.1',options.port))==0
        proof={'status':status if not changed else status+'_source_changed','error_type':error,
            'started_at':started,'completed_at':datetime.now(timezone.utc).isoformat(),
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'workspace_dirty':True,'source_before_sha256':before,'source_after_sha256':after,
            'changed_during_run':changed,'source_unchanged_during_run':not changed,
            'postgres_port':options.port,'postgres_port_closed_after_run':not port_still_listening,
            'qa_ports_not_targeted':[55441,18180,18181],'guards_disabled':False,'quota_clock_patched':False,
            'quota_windows_waited_in_real_time':True,
            'transport':'Actual ASGI middleware and PostgreSQL; no deployed network server claim',
            'model_measurement':'Disabled-model fallback; inference barriers test DB races, not model quality or latency',
            'cloud_deployment_verified':False,'linux_file_journal_verified':False,
            'versions':{name:importlib.metadata.version(name) for name in ['fastapi','SQLAlchemy','psycopg','httpx']}}
        (evidence/'postgres-provenance.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    if changed:
        raise SystemExit('PG checks completed but source changed during execution; current-source gate remains open.')
