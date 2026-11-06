"""Member-shared group-buy information; external sellers handle every transaction."""
from datetime import datetime, timedelta, timezone
from html import escape
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import Field, field_validator
from sqlalchemy import case, delete, select

from . import release
from .community_dates import filter_created
from .db import Record, User, get_db, now
from .schemas import Strict
from .security import admin_user, current_user, optional_user, throttle

GROUPBUY = 'release_groupbuy'
BROKER_NOTICE = '플랫폼은 통신판매중개자로서 거래 당사자가 아닙니다. 상품 정보와 거래 책임은 각 판매처에 있으며 결제·배송·환불은 판매처에서 진행합니다.'
router = APIRouter(prefix='/api/release', dependencies=[Depends(release.public_only)])


class GroupbuyInput(Strict):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=3000)
    category: str = Field(min_length=1, max_length=40)
    seller_name: str = Field(min_length=1, max_length=100)
    seller_url: str = Field(max_length=2048)
    price: int | None = Field(default=None, ge=0, le=1000000000, strict=True)
    shipping_fee: int | None = Field(default=None, ge=0, le=1000000000, strict=True)
    minimum_quantity: int | None = Field(default=None, ge=1, le=1000000000, strict=True)
    unit: str = Field(default='', max_length=100)
    price_conditions: str = Field(default='', max_length=1000)
    expires_at: datetime
    source_checked_at: datetime

    @field_validator('title', 'body', 'category', 'seller_name', mode='before')
    @classmethod
    def meaningful(cls, value):
        if not isinstance(value,str):return value
        value=value.strip()
        if not value:raise ValueError('내용을 입력해 주세요.')
        return value

    @field_validator('seller_url')
    @classmethod
    def https_seller(cls, value):
        try:
            url=urlsplit(value)
            host=(url.hostname or '').rstrip('.').casefold()
            if url.scheme!='https' or not host or url.username or url.password or '\\' in value or any(ord(c)<=32 for c in value):raise ValueError()
            if url.port not in (None,443) or host=='localhost' or host.endswith(('.localhost','.local')):raise ValueError()
            try:
                address=ipaddress.ip_address(host)
            except ValueError:address=None
            if address and not address.is_global:raise ValueError()
            if not address:
                ascii_host=host.encode('idna').decode('ascii')
                labels=ascii_host.split('.')
                if len(labels)<2 or not re.fullmatch(r'[a-z][a-z0-9-]*',labels[-1]) or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels):raise ValueError()
        except (ValueError,UnicodeError):raise ValueError('공개 판매처의 HTTPS 주소를 입력해 주세요.') from None
        # This is a link only: no fetching, DNS resolution, preview or redirect probing.
        return value

    @field_validator('expires_at','source_checked_at')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:raise ValueError('시간대가 포함된 일시가 필요합니다.')
        return value.astimezone(timezone.utc)


class Revision(Strict):
    revision: int = Field(ge=1, strict=True)


class GroupbuyEdit(GroupbuyInput):
    revision: int = Field(ge=1, strict=True)


class LinkInput(Revision):
    groupbuy_id: str = Field(min_length=1,max_length=36)


class InformationReport(Strict):
    reason: str = Field(min_length=5,max_length=1000)


class ReviewInput(Strict):
    action: Literal['hide','needs_review','dismiss']
    note: str = Field(min_length=2,max_length=1000)


def visible_query(user=None, *conditions, own_hidden=False):
    query=select(Record).where(Record.kind==GROUPBUY,release.author_available(),*conditions)
    query=query.where(Record.status.in_(['active','ended','hidden'] if own_hidden else ['active','ended']))
    if user:
        blocked=select(Record.parent_id).where(Record.kind=='block',Record.owner_id==user.id)
        query=query.where(Record.owner_id.not_in(blocked))
    return query


def content(db, identifier, user=None, *, lock=False, active=False):
    query=visible_query(user,Record.id==identifier)
    if active:query=query.where(Record.status=='active',Record.ends>now())
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    item=db.scalar(query)
    if not item:raise HTTPException(404,'공개된 공구 정보를 찾을 수 없습니다.')
    return item


def active_actor(db,user,*,operator=False):
    actor=db.scalar(select(User).where(User.id==user.id).with_for_update().execution_options(populate_existing=True))
    if not actor or actor.deleted or db.scalar(select(Record.id).where(Record.kind=='suspension',Record.owner_id==user.id)):
        raise HTTPException(401,'사용할 수 없는 계정입니다.')
    if operator and not actor.is_admin:raise HTTPException(403,'운영 권한이 필요합니다.')
    return actor


def display_time(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M (한국 시간)')


def dto(db,item,user=None):
    data=item.data
    status='hidden' if item.status=='hidden' else 'ended' if item.status=='ended' or item.ends<=now() else 'active'
    return dict(id=item.id,**{key:data.get(key) for key in GroupbuyInput.model_fields},
        author=release.author(db,item),created_at=release.timestamp(item.created),updated_at=data.get('updated_at'),
        revision=item.revision,own=bool(user and user.id==item.owner_id),status=status,
        can_edit=bool(user and user.id==item.owner_id and status=='active'),
        review_state=data.get('review_state','clear'),queried_at=release.timestamp(now()),broker_notice=BROKER_NOTICE)


def linked_dto(db,demand,user):
    identifier=demand.data.get('groupbuy_id')
    if not identifier:return None
    item=db.scalar(visible_query(user,Record.id==identifier,Record.status=='active',Record.ends>now()))
    return dto(db,item,user) if item else None


def listing(db,user,q,category,status,sort,limit,offset,start_date,end_date,mine=False):
    query=visible_query(user,*( [Record.owner_id==user.id] if mine else []),own_hidden=mine)
    query=filter_created(query,start_date,end_date)
    if status=='active':query=query.where(Record.status=='active',Record.ends>now())
    elif status=='ended':query=query.where((Record.status=='ended')|((Record.status=='active')&(Record.ends<=now())))
    if category:query=query.where(Record.data['category'].as_string()==category)
    if q.strip():query=query.where((Record.data['title'].as_string()+' '+Record.data['body'].as_string()).icontains(q.strip(),autoescape=True))
    if sort=='ending':query=query.order_by(case(((Record.status=='active')&(Record.ends>now()),0),else_=1),Record.ends,Record.created.desc(),Record.id)
    else:query=query.order_by(Record.created.desc(),Record.id)
    rows=list(db.scalars(query.limit(limit+1).offset(offset)))
    return {'items':[dto(db,row,user) for row in rows[:limit]],'has_more':len(rows)>limit,'queried_at':release.timestamp(now())}


@router.get('/groupbuys')
def groupbuys(q:str=Query('',max_length=100),category:str=Query('',max_length=40),
    status:Literal['active','ended','all']='active',sort:Literal['ending','recent']='ending',
    start_date:str|None=None,end_date:str|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),
    user=Depends(optional_user),db=Depends(get_db)):
    return listing(db,user,q,category,status,sort,limit,offset,start_date,end_date)


@router.get('/groupbuys/mine')
def mine(q:str=Query('',max_length=100),category:str=Query('',max_length=40),
    status:Literal['active','ended','all']='all',sort:Literal['ending','recent']='recent',
    start_date:str|None=None,end_date:str|None=None,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),
    user=Depends(current_user),db=Depends(get_db)):
    return listing(db,user,q,category,status,sort,limit,offset,start_date,end_date,True)


def input_data(body):
    if body.expires_at.timestamp()<=now():raise HTTPException(422,'마감 시각은 현재 이후로 입력해 주세요.')
    if body.source_checked_at.timestamp()>now()+300:raise HTTPException(422,'출처 확인 시각은 미래로 입력할 수 없습니다.')
    return body.model_dump(mode='json',exclude={'revision'})


@router.post('/groupbuys',status_code=201)
def create(body:GroupbuyInput,request:Request,user=Depends(current_user),db=Depends(get_db)):
    throttle(request,'write',subject=user.id);active_actor(db,user)
    item=Record(kind=GROUPBUY,owner_id=user.id,ends=int(body.expires_at.timestamp()),data=input_data(body))
    db.add(item);db.commit()
    return dto(db,item,user)


@router.get('/groupbuys/{id}')
def detail(id:str,user=Depends(optional_user),db=Depends(get_db)):
    return dto(db,content(db,id,user),user)


def owned(db,id,user,revision):
    active_actor(db,user)
    item=content(db,id,user,lock=True)
    if item.owner_id!=user.id:raise HTTPException(404,'본인이 공유한 공구 정보를 찾을 수 없습니다.')
    if item.revision!=revision:raise HTTPException(409,'다른 화면에서 변경되었습니다. 최신 정보를 확인해 주세요.')
    if item.status!='active' or item.ends<=now():raise HTTPException(409,'종료된 공구 정보는 수정하거나 다시 종료할 수 없습니다.')
    return item


@router.put('/groupbuys/{id}')
def edit(id:str,body:GroupbuyEdit,request:Request,user=Depends(current_user),db=Depends(get_db)):
    throttle(request,'write',subject=user.id)
    item=owned(db,id,user,body.revision)
    item.data={**input_data(body),'review_state':item.data.get('review_state','clear'),'updated_at':release.timestamp(now())}
    item.ends=int(body.expires_at.timestamp());item.revision+=1;db.commit()
    return dto(db,item,user)


@router.post('/groupbuys/{id}/end')
def end(id:str,body:Revision,request:Request,user=Depends(current_user),db=Depends(get_db)):
    throttle(request,'write',subject=user.id)
    item=owned(db,id,user,body.revision)
    item.status='ended';item.revision+=1;item.data={**item.data,'updated_at':release.timestamp(now())};db.commit()
    return dto(db,item,user)


@router.post('/groupbuys/{id}/reports',status_code=201)
def report_information(id:str,body:InformationReport,request:Request,user=Depends(current_user),db=Depends(get_db)):
    return release.report(release.ReportInput(target_type='groupbuy',target_id=id,reason=body.reason),request,user,db)


@router.delete('/groupbuys/{id}')
def remove(id:str,body:Revision,request:Request,user=Depends(current_user),db=Depends(get_db)):
    throttle(request,'write',subject=user.id);active_actor(db,user)
    item=db.scalar(select(Record).where(Record.kind==GROUPBUY,Record.id==id).with_for_update().execution_options(populate_existing=True))
    if not item or item.owner_id!=user.id:raise HTTPException(404,'본인이 공유한 공구 정보를 찾을 수 없습니다.')
    if item.revision!=body.revision:raise HTTPException(409,'다른 화면에서 변경되었습니다. 최신 정보를 확인해 주세요.')
    # Shared links must not outlive the deleted information. Preserve each demand.
    for demand in db.scalars(select(Record).where(Record.kind==release.DEMAND,Record.data['groupbuy_id'].as_string()==id).with_for_update()):
        demand.data={**demand.data,'groupbuy_id':None,'updated_at':release.timestamp(now())};demand.revision+=1
    reports=list(db.scalars(select(Record.id).where(Record.kind==release.REPORT,Record.parent_id==id)))
    # Remove quoted moderator text with the content. Keeping orphaned audit
    # references would make later account erasure unable to locate those notes.
    references=[id,*reports]
    db.execute(delete(Record).where(Record.kind=='audit',
        Record.parent_id.in_(references)|
        (Record.data['target_id'].as_string()==id)|
        Record.data['report_id'].as_string().in_(reports)))
    db.execute(delete(Record).where(Record.kind==release.NOTICE,(Record.data['target_id'].as_string()==id)|Record.parent_id.in_(reports)))
    db.execute(delete(Record).where(Record.kind==release.REPORT,Record.parent_id==id))
    db.delete(item);db.commit()
    return {'message':'공구 정보를 삭제했습니다.'}


@router.put('/demands/{id}/groupbuy')
def link(id:str,body:LinkInput,request:Request,user=Depends(current_user),db=Depends(get_db)):
    return change_link(id,body.revision,body.groupbuy_id,request,user,db)


@router.post('/demands/{id}/unlink-groupbuy')
def unlink(id:str,body:Revision,request:Request,user=Depends(current_user),db=Depends(get_db)):
    return change_link(id,body.revision,None,request,user,db)


def change_link(id,revision,groupbuy_id,request,user,db):
    throttle(request,'write',subject=user.id);active_actor(db,user)
    # Match remove(): lock the group before its demand references. Unlinking
    # does not lock a group later, so cannot reverse this order.
    if groupbuy_id:content(db,groupbuy_id,user,lock=True,active=True)
    item=db.scalar(release.visible_query(release.DEMAND,user,Record.id==id).with_for_update().execution_options(populate_existing=True))
    if not item:raise HTTPException(404,'공개된 수요를 찾을 수 없습니다.')
    if groupbuy_id is None and item.owner_id!=user.id:raise HTTPException(404,'본인 수요를 찾을 수 없습니다.')
    if release.post_type(item)!='demand':raise HTTPException(422,'공구 수요에만 연결할 수 있습니다.')
    if item.revision!=revision:raise HTTPException(409,'다른 화면에서 변경되었습니다. 최신 수요를 확인해 주세요.')
    if item.data.get('groupbuy_id')==groupbuy_id:raise HTTPException(409,'이미 같은 연결 상태입니다.')
    if groupbuy_id and item.owner_id!=user.id and linked_dto(db,item,None):
        raise HTTPException(409,'이미 연결된 진행 중 공구가 있습니다. 작성자만 연결을 변경할 수 있습니다.')
    item.data={**item.data,'groupbuy_id':groupbuy_id,'updated_at':release.timestamp(now())};item.revision+=1;db.commit()
    return release.demand_dto(db,item,user)


@router.get('/admin/groupbuys/reports')
def reports(status:Literal['active','resolved','all']='active',limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),
    user=Depends(admin_user),db=Depends(get_db)):
    query=select(Record).where(Record.kind==release.REPORT,Record.data['target_type'].as_string()=='groupbuy')
    if status!='all':query=query.where(Record.status==status)
    rows=list(db.scalars(query.order_by(Record.created.desc(),Record.id).limit(limit+1).offset(offset)))
    return {'items':[release.report_dto(db,row) for row in rows[:limit]],'has_more':len(rows)>limit}


@router.post('/admin/groupbuys/reports/{id}/resolve')
def review(id:str,body:ReviewInput,request:Request,user=Depends(admin_user),db=Depends(get_db)):
    row=db.scalar(select(Record).where(Record.id==id,Record.kind==release.REPORT,Record.data['target_type'].as_string()=='groupbuy'))
    if not row:raise HTTPException(404,'공구 정보 제보를 찾을 수 없습니다.')
    return release.resolve_report(id,release.ResolveInput(**body.model_dump()),request,user,db)


def resolve_existing(db,report,body,user):
    active_actor(db,user,operator=True)
    report=db.scalar(select(Record).where(Record.id==report.id).with_for_update().execution_options(populate_existing=True))
    if report.status!='active':raise HTTPException(409,'이미 처리된 제보입니다.')
    if body.action not in ('hide','needs_review','dismiss'):raise HTTPException(422,'공구 제보는 숨김·정보 확인 필요·조치 없이 종결로 처리해 주세요.')
    target=db.scalar(select(Record).where(Record.kind==GROUPBUY,Record.id==report.parent_id).with_for_update().execution_options(populate_existing=True))
    if not target:raise HTTPException(404,'공구 정보를 찾을 수 없습니다.')
    stamp=release.timestamp(now())
    if body.action=='hide':target.status='hidden';target.revision+=1
    if body.action=='needs_review':target.data={**target.data,'review_state':'needs_review','updated_at':stamp};target.revision+=1
    report.status='resolved';report.data={**report.data,'action':body.action,'note':body.note,'resolved_at':stamp,'resolved_by':user.id}
    db.add(Record(kind='audit',owner_id=user.id,parent_id=report.id,data={'action':'groupbuy-'+body.action,'report_id':report.id,'target_id':target.id,'reason':body.note,'acted_at':stamp}))
    if body.action in ('hide','needs_review'):
        db.add(Record(kind=release.NOTICE,owner_id=target.owner_id,parent_id=report.id,data={'target_type':'groupbuy','target_id':target.id,'action':body.action,'reason':'공구 정보가 숨김 처리되었습니다.' if body.action=='hide' else '공구 정보의 추가 확인이 필요합니다.'}))
    db.commit()
    return release.report_dto(db,report)


@router.get('/groupbuys/{id}/public',response_class=HTMLResponse)
def public_page(id:str,db=Depends(get_db)):
    from .groupbuy_public import page
    return page(dto(db,content(db,id)))
