"""IP-independent limiter regression using the owned localhost PostgreSQL harness.

Usage: python scripts/verify-rate-subject-postgres.py --pg-bin <bin> --runtime <ASCII temp parent>
No operational configuration or remote service is read; all accounts are synthetic.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runpy
import threading


def checks(c, expect):
    from app import security
    import app.main as main
    from app.db import SessionLocal, Record, User, Token, RateBucket, engine, now
    from sqlalchemy import delete, select

    password = 'Local-rate-fixture-password-123'
    hashed = security.passwords.hash(password)
    people = []
    with SessionLocal() as db:
        for i in range(9):
            user = User(email=f'rate{i}@example.com', nickname=f'fixture{i}', password_hash=hashed,
                        seller_status='approved' if i == 8 else None)
            db.add(user)
            db.flush()
            first = security.issue_token(db, user)
            second = security.issue_token(db, user)
            people.append({'id': user.id, 'email': user.email,
                           'headers': {'Authorization': 'Bearer '+first},
                           'alternate': {'Authorization': 'Bearer '+second}})
        seller = people[8]['id']
        campaign = Record(kind='campaign', owner_id=seller, capacity=100, ends=now()+86400,
            data={'title': '로컬 제한 회귀', 'description': '실거래 없는 로컬 시험', 'category': '육아생활',
                  'price': 1000, 'shipping_fee': 0, 'unit': '1개', 'minimum_quantity': 1, 'published': True})
        db.add(campaign)
        db.commit()
        campaign_id = campaign.id

    def reset():
        # Explicit local fixture reset between independent scenarios, never production.
        for bucket in security._global_attempts.values():
            bucket.clear()
        with SessionLocal() as db:
            db.execute(delete(RateBucket))
            db.commit()

    def count(scope, subject, label):
        with SessionLocal() as db:
            bucket = db.get(RateBucket, security.rate_key(scope, subject, label, now()))
            return bucket.count if bucket else 0

    path = '/api/campaigns/'+campaign_id+'/questions'
    a, b = people[:2]
    reset()
    statuses = [c.post(path, headers=a['headers'], json={'body': f'질문 {i}'}).status_code for i in range(31)]
    spoofed = {**a['alternate'], 'X-Forwarded-For': '203.0.113.91', 'CF-Connecting-IP': '198.51.100.4'}
    denied = c.post(path, headers=spoofed, json={'body': '위조 헤더 시험'})
    other = c.post(path, headers=b['headers'], json={'body': '같은 peer 다른 계정'})
    expect(statuses == [201]*30+[429] and denied.status_code == 429 and other.status_code == 201,
           'same peer accounts independent; spoofed forwarding and alternate valid token do not change identity')
    expect(count('account', a['id'], 'question') == 32 and count('account', b['id'], 'question') == 1,
           'account quota rejection persists with subject separation')
    expect(1 <= int(denied.headers['Retry-After']) <= 600, 'account Retry-After is remaining fixed window')

    reset()
    for i in range(7):
        c.post('/api/auth/logout', headers={'Authorization': f'Bearer random-invalid-{i}', 'X-Forwarded-For': str(i)})
    with SessionLocal() as db:
        expect(not db.scalar(select(RateBucket)), 'random bearer and forwarding headers create no account bucket')

    reset()
    results = [c.post('/api/auth/login', json={'email': a['email'].upper(), 'password': 'incorrect-password'}).status_code for _ in range(11)]
    expect(results == [401]*10+[429] and count('claimed-account', a['email'], 'login') == 11,
           'canonical claimed login failed passwords and 429 committed independently of action rollback')
    expect(c.post('/api/auth/login', json={'email': b['email'], 'password': password}).status_code == 200,
           'other claimed email remains usable on same peer')
    reset()
    payload = {'email': a['email'].upper(), 'recovery_code': 'invalid-local-recovery-code', 'password': password}
    results = [c.post('/api/auth/recover', json=payload).status_code for _ in range(6)]
    expect(results == [400]*5+[429] and count('claimed-account', a['email'], 'recover') == 6,
           'canonical claimed recovery failed codes and 429 committed independently of action rollback')

    for endpoint, method, label in [('/api/auth/recovery-code', 'POST', 'recovery-code'), ('/api/me', 'DELETE', 'delete-account')]:
        reset()
        results = [c.request(method, endpoint, headers=a['headers'], json={'password': 'incorrect-password'}).status_code for _ in range(6)]
        expect(results == [403]*5+[429] and count('account', a['id'], label) == 6,
               label+' failed password and quota rejection persist')

    reset()
    results = [c.post('/api/reports', headers=a['headers'], json={
        'target_type': 'question', 'target_id': 'missing-target', 'reason': '로컬 회귀 신고'}).status_code for _ in range(21)]
    expect(results == [404]*20+[429] and count('account', a['id'], 'report') == 21,
           'report20 quota survives domain 404 and quota rejection')

    reset()
    results = [c.put('/api/saved/'+campaign_id, headers=a['headers']).status_code for _ in range(61)]
    expect(results == [200]*60+[429] and count('account', a['id'], 'write') == 61,
           'general account60 write quota enforced independently of label quotas')

    reset()
    # Body validation happens before claimed-email bucket creation. Expensive global
    # budget still charges invalid bodies and stops random-email cardinality growth.
    statuses = [c.post('/api/auth/login', json={'email': f'invalid-{i}', 'password': password}).status_code for i in range(31)]
    with SessionLocal() as db:
        expect(statuses == [422]*30+[429] and not db.scalar(select(RateBucket)),
               'invalid emails consume fixed global auth budget without durable subject rows')
    expect(set(security._global_attempts) == {'write', 'expensive-auth', 'register'} and
           len(security._global_attempts['expensive-auth']) == 30, 'global cardinality fixed after arbitrary inputs')
    reset()
    statuses = [c.post('/api/auth/recover', json={**payload, 'email': f'unknown{i}@example.com'}).status_code for i in range(31)]
    with SessionLocal() as db:
        expect(statuses == [400]*30+[429] and len(list(db.scalars(select(RateBucket)))) == 30,
               'random valid claimed emails bounded by preceding global guard')
        db.add(RateBucket(key='0'*64, count=1, expires=now()-1))
        db.commit()
    reset_global = security._global_attempts
    for bucket in reset_global.values():
        bucket.clear()
    c.post('/api/auth/login', json={'email': b['email'], 'password': 'incorrect-password'})
    with SessionLocal() as db:
        expect(not db.get(RateBucket, '0'*64), 'expired durable subject rows cleaned on next quota transaction')

    # Intervene exactly after the short quota session closes, before endpoint auth.
    for index, mutation in [(2, 'logout'), (3, 'suspension'), (4, 'deletion')]:
        reset()
        real_guard = main.beta_write_guard
        target = people[index]
        def revoke_after_quota(request):
            real_guard(request)
            with SessionLocal() as db:
                if mutation == 'logout':
                    db.execute(delete(Token).where(Token.user_id == target['id']))
                elif mutation == 'suspension':
                    db.add(Record(kind='suspension', owner_id=target['id']))
                else:
                    db.get(User, target['id']).deleted = True
                db.commit()
        main.beta_write_guard = revoke_after_quota
        try:
            response = c.post(path, headers=target['headers'], json={'body': '권한 재검증 시험'})
        finally:
            main.beta_write_guard = real_guard
        with SessionLocal() as db:
            expect(response.status_code == 401 and not db.scalar(select(Record.id).where(
                Record.kind == 'question', Record.owner_id == target['id'])),
                mutation+' between quota and action cannot grant stale permission')

    reset()
    # Reproduce nested-pool starvation with all 7 real pool connections already
    # held by existing-reservation action transactions. No limiter may acquire an
    # eighth connection while those actions are open.
    reservation_path = '/api/campaigns/'+campaign_id+'/reservations'
    reserve_people = [a, b, people[5], people[6], people[7]]
    for person in reserve_people:
        c.post(reservation_path, headers=person['headers'], json={'quantity': 1, 'revision': 1})
    barrier = threading.Barrier(7)
    original_optional = security.optional_user
    original_current = main.current_user
    # FastAPI holds the original optional_user callable; wrap the current_user
    # dependency with the same user dependency so each barrier participant owns
    # its action connection before the endpoint checks existing reservations.
    from fastapi import Depends
    def synchronized_user(user=Depends(original_optional)):
        result = original_current(user)
        barrier.wait(timeout=10)
        return result
    app = main.app
    app.dependency_overrides[original_current] = synchronized_user
    timeout = engine.pool._timeout
    engine.pool._timeout = 0.75
    try:
        with ThreadPoolExecutor(max_workers=7) as pool:
            replies = list(pool.map(lambda i: c.post(reservation_path,
                headers=reserve_people[i % len(reserve_people)]['headers'],
                json={'quantity': 1, 'revision': 1}).status_code, range(7)))
        expect(replies == [409]*7, 'seven concurrent existing reservations complete without nested pool timeout')
    finally:
        app.dependency_overrides.pop(original_current, None)
        engine.pool._timeout = timeout
    expect(c.get('/api/health').status_code == 200 and engine.pool.checkedout() == 0,
           'health available and all action and limiter connections returned')


if __name__ == '__main__':
    harness = runpy.run_path(str(Path(__file__).with_name('verify-beta-postgres.py')))
    harness['run'](extra_checks=checks, evidence_name='rate-subject-results.json')
