"""Run real PostgreSQL beta checks in an owned, disposable localhost cluster.

Requires the official PostgreSQL binaries, --pg-bin. Never connects to user DBs.
Raw local DB files and logs stay in ignored artifacts/beta/runtime.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]


def run(extra_checks=None, evidence_name='postgres-results.json'):
    parser = argparse.ArgumentParser()
    parser.add_argument('--pg-bin', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, help='Owned ASCII temp parent for Windows PostgreSQL initdb')
    args = parser.parse_args()
    pg = args.pg_bin.resolve()
    pg_version = subprocess.check_output([str(pg / ('pg_ctl.exe' if os.name == 'nt' else 'pg_ctl')), '--version'],
                                         text=True, timeout=15).strip()
    runtime = args.runtime.resolve() if args.runtime else ROOT / 'artifacts/beta/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    evidence = ROOT / 'artifacts/beta' / evidence_name
    results = []
    password = secrets.token_urlsafe(32)
    port = 55439
    with tempfile.TemporaryDirectory(prefix='pg-beta-', dir=runtime) as scratch:
        scratch = Path(scratch)
        data = scratch / 'data'
        pw = scratch / 'password.txt'
        pw.write_text(password, encoding='utf-8')
        def command(name, *values):
            # pg_ctl descendants can inherit PIPE handles on Windows and keep communicate()
            # waiting after pg_ctl exits. A regular file avoids that pipe-lifetime trap.
            output = scratch / 'command.log'
            def diagnostic():
                detail = output.read_text(encoding='cp949' if os.name == 'nt' else 'utf-8', errors='replace').replace(password, '[REDACTED]')[-1500:]
                server_log = scratch / 'postgres.log'
                if name == 'pg_ctl' and 'start' in values and server_log.is_file():
                    detail += '\nPostgreSQL log tail:\n' + server_log.read_text(encoding='utf-8', errors='replace').replace(password, '[REDACTED]')[-3000:]
                return detail
            with output.open('w', encoding='utf-8') as log:
                try:
                    completed = subprocess.run([str(pg / (name+'.exe' if os.name == 'nt' else name)), *map(str, values)],
                        stdin=subprocess.DEVNULL, stdout=log, stderr=log, timeout=60,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                except subprocess.TimeoutExpired:
                    log.flush()
                    raise RuntimeError(f'{name} timed out: ' + diagnostic()) from None
            if completed.returncode:
                raise RuntimeError(f'{name} failed: ' + diagnostic())
            return completed
        command('initdb', '-D', data, '-U', 'beta_test', '-A', 'scram-sha-256', '--pwfile', pw, '--encoding=UTF8', '--locale=C')
        started = False
        try:
            server_options = f'-h 127.0.0.1 -p {port} -c shared_buffers=32MB -c max_connections=25'
            if os.name != 'nt':
                # Debian's shared socket directory is not owned by the CI runner.
                server_options += ' -k ' + shlex.quote(str(scratch))
            command('pg_ctl', '-D', data, '-l', scratch/'postgres.log', '-o', server_options, '-w', 'start')
            started = True
            os.environ.update(MODU_ENV='beta', PUBLIC_ORIGIN='https://beta.example.test',
                DATABASE_URL=f'postgresql+psycopg://beta_test:{password}@127.0.0.1:{port}/postgres',
                RATE_LIMIT_SECRET=secrets.token_urlsafe(32), SUPPORT_EMAIL='test@example.com',
                HOSTING_LOCATION='localhost test fixture', DATABASE_LOCATION='localhost test fixture', RUNTIME_DIR=str(scratch/'app'))
            sys.path.insert(0, str(ROOT/'backend'))
            from fastapi.testclient import TestClient
            from app.db import SessionLocal, Record, User, Token, RateBucket, engine, now
            from app.security import token_digest, passwords, issue_token
            from app.main import app
            from sqlalchemy import select
            with TestClient(app, base_url='https://beta.example.test') as c:
                def expect(condition, label):
                    assert condition, label
                    results.append(label)
                codes = [secrets.token_urlsafe(32) for _ in range(4)]
                with SessionLocal() as db:
                    for code in codes:
                        db.add(Record(kind='beta_invite', unique_key=token_digest(code), ends=now()+3600, data={}))
                    u = User(email='seller@example.com', nickname='가상판매자', password_hash=passwords.hash(password), seller_status='approved')
                    db.add(u); db.flush()
                    b = Record(kind='brand', owner_id=u.id, unique_key=u.id, data={'name':'시험 브랜드'})
                    db.add(b); db.flush()
                    campaign = Record(kind='campaign', owner_id=u.id, parent_id=b.id, capacity=1, ends=now()+86400,
                        data={'title':'실제 PG 동시성 시험', 'description':'상품 배송 없는 시험', 'category':'육아생활', 'price':1000,
                              'shipping_fee':0, 'unit':'1개', 'minimum_quantity':1, 'published':True})
                    db.add(campaign); db.commit(); campaign_id = campaign.id
                def register(index, code):
                    return c.post('/api/auth/register', json={'email':f'beta{index}@example.com', 'nickname':f'시험{index}',
                        'password':password, 'track':'buyer', 'terms_accepted':True, 'privacy_accepted':True,
                        'invite_code':code, 'adult_confirmed':True})
                expect(c.get('/api/health').json()['mode']=='closed-beta', 'postgres health')
                expect(c.get('/docs').status_code==404, 'docs disabled')
                expect(c.get('/api/health', headers={'Host':'evil.example'}).status_code==400, 'untrusted host rejected')
                with ThreadPoolExecutor(max_workers=2) as pool:
                    responses = list(pool.map(lambda i: register(i, codes[0]), [0,1]))
                expect(sum(r.status_code==201 for r in responses)==1 and all(r.status_code in (201,400,409) for r in responses), 'invite concurrent single redemption')
                first = next(r.json() for r in responses if r.status_code==201)
                second = register(2, codes[1]).json()
                def auth(account): return {'Authorization':'Bearer '+account['access_token']}
                with ThreadPoolExecutor(max_workers=2) as pool:
                    reservation = list(pool.map(lambda account: c.post('/api/campaigns/'+campaign_id+'/reservations',
                        headers=auth(account), json={'quantity':1,'revision':1}), [first,second]))
                expect(sum(r.status_code==201 for r in reservation)==1 and all(r.status_code in (201,409) for r in reservation), 'no oversell under PostgreSQL concurrency')
                expect(c.get('/api/campaigns/'+campaign_id).json()['reserved_quantity']==1, 'capacity one persisted')
                change = c.post('/api/auth/recover', json={'email':first['user']['email'], 'recovery_code':first['recovery_code'], 'password':password+'new'})
                expect(change.status_code==200, 'recovery succeeds')
                expect(c.get('/api/me', headers=auth(first)).status_code==401, 'recovery revokes old session')
                expect(c.get('/api/campaigns', headers=auth(first)).status_code==200, 'stale session remains guest on public read')
                expect(c.post('/api/auth/recover', json={'email':first['user']['email'],'recovery_code':first['recovery_code'],'password':password}).status_code==400, 'old recovery replay rejected')
                renewal = c.post('/api/auth/recovery-code', headers=auth(second), json={'password':password})
                expect(renewal.status_code==200 and renewal.json()['recovery_code']!=second['recovery_code'], 'password-confirmed recovery code renewal')
                expect(c.get('/api/me', headers=auth(second)).status_code==200, 'renewal retains authenticated session')
                with SessionLocal() as db:
                    expect(not db.get(Token, token_digest(second['recovery_code'])), 'renewal revokes previous recovery hash')
                # Reproduce the former nested-pool deadlock at the real pool capacity.
                # Synchronize the middleware guard before it borrows a connection.
                import app.main as main
                barrier = threading.Barrier(7)
                real_guard, timeout = main.beta_write_guard, engine.pool._timeout
                def concurrent_guard(request):
                    barrier.wait(timeout=10)
                    return real_guard(request)
                main.beta_write_guard, engine.pool._timeout = concurrent_guard, 0.75
                try:
                    with ThreadPoolExecutor(max_workers=7) as pool:
                        replies = list(pool.map(lambda i: c.post('/api/campaigns/'+campaign_id+'/questions',
                            headers=auth(second),json={'body':f'동시 질문 시험 {i}'}).status_code,range(7)))
                    expect(201 in replies and all(status in (201,409) for status in replies), 'seven authenticated writes have no pool exhaustion')
                    expect(c.get('/api/health').status_code==200, 'health remains available after concurrent writes')
                finally:
                    main.beta_write_guard, engine.pool._timeout = real_guard, timeout
                expect(c.request('DELETE','/api/me',headers=auth(second),json={'password':password}).status_code==200, 'beta deletion')
                with SessionLocal() as db:
                    expect(not db.scalar(select(Token).where(Token.user_id==second['user']['id'])), 'deleted account tokens removed')
                    expect(not db.scalar(select(Record).where(Record.owner_id==second['user']['id'])), 'deleted account records removed')
                    expect(bool(db.scalar(select(RateBucket))), 'distributed rate buckets persisted')
                for _ in range(6):
                    response = c.post('/api/auth/recover', json={'email':'none@example.com','recovery_code':'invalid-code-long-enough','password':password})
                expect(response.status_code==429, 'recovery rate limited')
                # Persistent state survives a real PostgreSQL restart, not a mock.
                engine.dispose()
                command('pg_ctl', '-D', data, '-m', 'fast', '-w', 'restart')
                expect(c.get('/api/campaigns/'+campaign_id).status_code==200, 'data survives database restart')
                expect(c.post('/api/auth/login',content='x'*65537).status_code==413, 'oversize body rejected')
                for kind in ['privacy','terms','deletion','support']:
                    expect(c.get('/legal/'+kind).status_code==200, 'policy '+kind)
                if extra_checks:
                    extra_checks(c, expect)
            engine.dispose()
            evidence.write_text(json.dumps({'status':'pass','checks':results,'database':pg_version+' local dedicated cluster',
                'cloud_deployment_verified':False, 'cleanup':'cluster stopped; temporary directory removed on exit'},ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'POSTGRES_BETA_PASS: {len(results)} checks; evidence artifacts/beta/{evidence_name}')
        finally:
            if started:
                command('pg_ctl','-D',data,'-m','immediate','-w','stop')


if __name__ == '__main__':
    run()
