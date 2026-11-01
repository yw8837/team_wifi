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
    expect(c.get('/api/config').json()['public_release'] is True, 'public deployment config')
    expect(c.get('/api/health').json()['mode']=='public-release', 'public deployment health mode')
    expect(not first['user']['email_verified'], 'public does not claim email ownership')
    expect(c.get('/api/campaigns').status_code==404 and c.post('/api/admin/orders',headers=h1,json={}).status_code==404,
           'public legacy read and order mutation denied before domain/auth')
    catalog = c.get('/api/release/offers')
    expect(catalog.status_code==200 and all(entry['entry_type']=='shopping_reference' and entry['price'] is None for entry in catalog.json()),
           'checked-in public manifest only with no invented prices')
    offer_id = catalog.json()[0]['id']
    for _ in range(2):
        expect(c.put('/api/release/offers/'+offer_id+'/saved',headers=h1).status_code==200, 'public saved idempotent PUT')
    expect(len(c.get('/api/release/saved',headers=h1).json())==1, 'one public saved record')
    response=c.post('/api/release/demands',headers=h1,json={'title':'기저귀 함께 비교하기','body':'기저귀 단위당 가격과 배송 조건을 비교합니다.','category':'기저귀·물티슈'})
    expect(response.status_code==201,'public demand write with durable quota')
    demand_id=response.json()['id']
    url='/api/release/demands/'+demand_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:c.put(url+'/interest',headers=h2).status_code,range(2)))
    expect(all(status in (200,409) for status in replies) and 200 in replies,'public concurrent interest serializable outcome')
    expect(c.put(url+'/interest',headers=h2).status_code==200 and c.get(url).json()['interest_count']==1,
           'public interest database uniqueness and retry idempotence')
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
    expect(c.post('/api/release/admin/reports/'+report.json()['id']+'/resolve',headers=h1,json={'action':'hide','note':'로컬 검증'}).status_code==200,
           'public moderation hides real target')
    expect(c.get(url).status_code==404,'public hidden demand excluded')
    expect(c.request('DELETE','/api/me',headers=h1,json={'password':password}).status_code==200,'public account deletion')
    with SessionLocal() as db:
        expect(not db.scalar(select(Record.id).where(Record.owner_id==first['user']['id'])),'public deleted owner content removed')
        expect(not db.scalar(select(Record.id).where(Record.kind.in_([release.COMMENT,release.INTEREST,release.REPORT]),Record.parent_id==demand_id)),
               'public deletion cascades linked content')
        expect(not db.scalar(select(Token.digest).where(Token.user_id==first['user']['id'])),'public deletion revokes tokens')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    harness=runpy.run_path(str(root/'scripts/verify-beta-postgres.py'))
    harness['run'](extra_checks=checks,evidence_name='public-release-postgres-results.json')
