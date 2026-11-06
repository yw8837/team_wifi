"""Portable real-PostgreSQL groupbuy checks within the existing owned lifecycle.

No cluster/process/port management, source edits, limiter bypass or external HTTP.
The caller owns startup, teardown, evidence and the actual ASGI client.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def checks(c,expect):
    from app import assistant_tools,groupbuys
    from app.db import Record,SessionLocal,User
    from app.security import issue_token,passwords
    from sqlalchemy import select
    from verify_assistant_postgres import pace

    tag='gb'+uuid4().hex[:12]
    secret='Synthetic-groupbuy-fixture-password-123'
    hashed=passwords.hash(secret)
    ids,headers=[],[]
    with SessionLocal() as db:
        # Synthetic fixture accounts belong only to the caller's disposable database.
        for index in range(4):
            user=User(email=f'{tag}-{index}@example.test',nickname=f'공구검증{index}',password_hash=hashed,is_admin=index==3)
            db.add(user);db.flush();ids.append(user.id)
            headers.append({'Authorization':'Bearer '+issue_token(db,user)})
        db.commit()
    def write(path,actor=None,body=None,method='POST'):
        pace()
        return c.request(method,path,headers=headers[actor] if actor is not None else {},json=body)
    body=dict(title='기저귀 실제 DB 공구 '+tag,body='모든 조건과 배송비는 외부 판매처에서 다시 확인하세요.',
        category='기저귀·물티슈',seller_name='합성 판매처',seller_url='https://seller.example.test/item',
        price=15000,shipping_fee=3000,unit='1팩',price_conditions='판매처 최종 조건 확인',
        expires_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),source_checked_at=datetime.now(timezone.utc).isoformat())
    api='/api/release/groupbuys'
    expect(write(api,body=body).status_code==401,'groupbuy anonymous mutation denied PostgreSQL')
    response=write(api,0,body)
    expect(response.status_code==201,'groupbuy member creates with actual write quota PostgreSQL')
    item=response.json();url=api+'/'+item['id']
    expect(c.get(url).json()['broker_notice']==groupbuys.BROKER_NOTICE,'groupbuy anonymous detail includes intermediary disclosure PostgreSQL')
    pace(2)
    with ThreadPoolExecutor(2) as pool:
        statuses=list(pool.map(lambda _:c.put(url,headers=headers[0],json={**body,'revision':1,'title':'기저귀 동시 수정 '+tag}).status_code,range(2)))
    expect(sorted(statuses)==[200,409],'groupbuy concurrent edits have single PostgreSQL winner: '+str(sorted(statuses)))
    expect(c.get(url).json()['revision']==2,'groupbuy revision increments exactly once PostgreSQL')
    demand=write('/api/release/demands',1,{'title':'기저귀 공구 수요 '+tag,'body':'동일 구성과 판매처 조건의 공구 연결을 희망합니다.','category':'기저귀·물티슈'})
    expect(demand.status_code==201,'groupbuy linked demand created under actual question quota PostgreSQL')
    demandurl='/api/release/demands/'+demand.json()['id']
    linked=write(demandurl+'/groupbuy',1,{'groupbuy_id':item['id'],'revision':1},'PUT')
    expect(linked.status_code==200 and linked.json()['linked_groupbuy']['id']==item['id'],'groupbuy visible ongoing information linked PostgreSQL')
    expect(write(demandurl+'/groupbuy',2,{'groupbuy_id':item['id'],'revision':2},'PUT').status_code==404,'groupbuy non-owner cannot edit demand link PostgreSQL')
    report=write(url+'/reports',2,{'reason':'공구 조건의 추가 확인이 필요합니다.'})
    expect(report.status_code==201,'groupbuy information report uses actual durable report quota PostgreSQL')
    report_id=report.json()['id'];resolve='/api/release/admin/groupbuys/reports/'+report_id+'/resolve'
    pace(2)
    with ThreadPoolExecutor(2) as pool:
        statuses=list(pool.map(lambda _:c.post(resolve,headers=headers[3],json={'action':'needs_review','note':'판매처 조건 재확인 요청'}).status_code,range(2)))
    expect(sorted(statuses)==[200,409],'groupbuy concurrent report resolution single PostgreSQL winner: '+str(sorted(statuses)))
    expect(c.get(url).json()['review_state']=='needs_review','groupbuy needs-review warning persists PostgreSQL')
    with SessionLocal() as db:
        expect(len(list(db.scalars(select(Record.id).where(Record.kind=='audit',Record.parent_id==report_id))))==1,'groupbuy moderation writes one audit only PostgreSQL')
    metric='/api/release/measurement'
    # Compare the relevant slice so earlier lifecycle checks retain their own evidence.
    baseline=[row for row in c.get(metric+'/report',headers=headers[3]).json()['rows'] if row['placement']=='groupbuy_detail' and row['channel']=='web']
    expect(write(metric+'/consent',1,{'enabled':True},'PUT').status_code==200,'groupbuy measurement explicit opt-in PostgreSQL')
    event={'groupbuy_id':item['id'],'placement':'groupbuy_detail','channel':'web','action':'view','visible_ms':1000}
    expect(write(metric+'/events',1,event).json()['recorded'],'groupbuy opt-in exposure recorded PostgreSQL')
    expect(write(metric+'/events',1,{**event,'action':'source'}).json()['recorded'],'groupbuy seller departure measured without purchase claim PostgreSQL')
    with SessionLocal() as db:
        live=assistant_tools.live_read(db,None,tag+' 공구 마감')
        expect(any(action['url']=='/groupbuys/'+item['id'] for action in live['actions']),'groupbuy assistant links current public DB result PostgreSQL')
    second=write(url+'/reports',1,{'reason':'잘못된 판매처 주소 확인 요청'}).json()['id']
    hidden=write('/api/release/admin/groupbuys/reports/'+second+'/resolve',3,{'action':'hide','note':'잘못된 판매처 주소 확인'})
    expect(hidden.status_code==200,'groupbuy operator hides reported information PostgreSQL')
    listed=c.get(api,params={'q':tag}).json()['items']
    expect(c.get(url).status_code==404 and not any(row['id']==item['id'] for row in listed),'groupbuy hidden information excluded before public list/detail PostgreSQL')
    expect(c.get(demandurl).json()['linked_groupbuy'] is None,'groupbuy hidden link no longer disclosed PostgreSQL')
    after=[row for row in c.get(metric+'/report',headers=headers[3]).json()['rows'] if row['placement']=='groupbuy_detail' and row['channel']=='web']
    expect(after==baseline,'groupbuy hidden target excluded from measurement slice PostgreSQL')
    mine=c.get(api+'/mine',headers=headers[0]).json()['items']
    expect(len(mine)==1 and mine[0]['status']=='hidden' and not mine[0]['can_edit'],'groupbuy owner sees hidden status without edit bypass PostgreSQL')
    expect(c.get('/api/release/admin/groupbuys/reports',headers=headers[2]).status_code==403,'groupbuy ordinary member cannot inspect moderation PostgreSQL')
    reviewed=c.get('/api/release/admin/groupbuys/reports',headers=headers[3],params={'status':'resolved','limit':100}).json()['items']
    original=next(row['groupbuy'] for row in reviewed if row['id']==second)
    expect(original['seller_url']==body['seller_url'],'groupbuy operator can inspect hidden original PostgreSQL')
    with SessionLocal() as db:
        expect(db.bind.dialect.name=='postgresql' and db.connection().get_isolation_level()=='SERIALIZABLE','groupbuy uses actual PostgreSQL serializable isolation')
