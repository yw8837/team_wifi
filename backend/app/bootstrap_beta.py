"""Explicit initialization of a NEW beta database. No automatic demo seeding."""
import argparse
import json
from pathlib import Path
import secrets
from sqlalchemy import select
from . import config
from .db import Record, SessionLocal, User, init_db, now
from .security import passwords, token_digest
from .beta import virtual_application


def initialize(output: Path, admin_email: str, invite_count=30):
    if not config.BETA:
        raise SystemExit('Only an explicitly configured beta database may be initialized.')
    if output.exists():
        raise SystemExit('Credential output exists; refusing to overwrite.')
    init_db()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve output before committing: failure to create the private file cannot lose secrets.
    with output.open('x', encoding='utf-8') as private_file:
        with SessionLocal() as db:
            if db.scalar(select(User.id).limit(1)):
                raise SystemExit('Database already contains accounts; refusing to seed.')
            secret = secrets.token_urlsafe(32)
            admin = User(email=admin_email.lower(), nickname='베타 운영자', password_hash=passwords.hash(secret), is_admin=True)
            seller = User(email='beta-seller@example.com', nickname='시험용 판매자', password_hash=passwords.hash(secrets.token_urlsafe(48)), seller_status='approved')
            db.add_all([admin,seller]); db.flush()
            brand = Record(kind='brand',owner_id=seller.id,unique_key=seller.id,
                data={'name':'육아생활 시험관','description':'실제 판매하지 않는 베타 상품과 참여 흐름을 확인해 보세요.'})
            db.add(brand); db.flush()
            db.add(Record(kind='application',owner_id=seller.id,unique_key=seller.id,
                data={**virtual_application('육아생활 시험관','베타 가상 브랜드입니다.',True),'review_note':'시험 데이터, 실제 입점 인증 아님'}))
            examples=[('기저귀 묶음 참여 시험','기저귀·물티슈',28000,'1팩'),('이유식 보관용기 참여 시험','수유·이유식',16000,'3개'),
                ('유아 목욕수건 참여 시험','목욕·위생',21000,'2장'),('외출 파우치 참여 시험','외출·안전',12000,'1개'),
                ('그림책 세트 참여 시험','놀이·도서',24000,'3권'),('육아 수납함 참여 시험','육아생활',18000,'1개')]
            for title,category,price,unit in examples:
                db.add(Record(kind='campaign',owner_id=seller.id,parent_id=brand.id,capacity=100,ends=now()+28*86400,
                    data={'title':title,'description':'비공개 베타 상품입니다. 참여해도 결제되지 않으며 실제 상품은 배송하지 않습니다.',
                        'category':category,'price':price,'shipping_fee':3000,'unit':unit,'minimum_quantity':5,'published':True}))
            db.add(Record(kind='coupon',owner_id=seller.id,parent_id=brand.id,capacity=100,ends=now()+28*86400,
                data={'title':'시험용 2,000원 쿠폰','amount':2000,'min_spend':20000,'points_cost':0}))
            db.add(Record(kind='hotdeal',ends=now()+28*86400,data={'title':'물티슈 핫딜 정보 표시 시험','category':'기저귀·물티슈',
                'price':19000,'shipping_fee':0,'seller_name':'가상 외부 판매처','source_url':None,'source_name':'시험 데이터 · 실제 원문 없음'}))
            invites=[]
            for _ in range(invite_count):
                raw=secrets.token_urlsafe(32)
                invites.append(raw)
                db.add(Record(kind='beta_invite',unique_key=token_digest(raw),ends=now()+30*86400,data={}))
            json.dump({'admin':{'email':admin_email,'password':secret},'single_use_invites':invites,
                'notice':'Private: do not commit, screenshot, log, or publish. Distribute one invitation per tester.'},private_file,indent=2)
            private_file.flush()
            db.commit()
    print(f'BETA_BOOTSTRAP_PASS: 6 test campaigns, {invite_count} single-use invitations. Credentials written only to the specified private file.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--admin-email',required=True)
    p.add_argument('--invites',type=int,default=30)
    a=p.parse_args()
    if not 1<=a.invites<=100 or '@' not in a.admin_email:
        raise SystemExit('Require 1..100 invitations and a valid admin email.')
    initialize(a.output,a.admin_email,a.invites)
