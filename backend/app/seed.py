"""Explicit local fixtures: python -m app.seed --demo. Never run on a real database."""
import argparse
import json
import secrets
from sqlalchemy import select
from .db import RUNTIME, URL, Record, SessionLocal, User, init_db, now
from .security import passwords


def seed():
    if not URL.startswith('sqlite'):
        raise SystemExit('Demo seeding is restricted to local SQLite.')
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            raise SystemExit('Database already contains users; refusing to overwrite.')
        accounts = {}
        users = {}
        for role, nickname in [('admin', '개발 관리자'), ('seller', '예시 판매자'), ('buyer', '예시 구매자')]:
            password = secrets.token_urlsafe(18)
            email = f'{role}@example.com'
            u = User(email=email, nickname=nickname, password_hash=passwords.hash(password), is_admin=role == 'admin',
                     seller_status='approved' if role == 'seller' else None)
            db.add(u)
            db.flush()
            accounts[role] = {'email': email, 'password': password, 'id': u.id}
            users[role] = u
        seller = users['seller']
        db.add(Record(kind='application', owner_id=seller.id, unique_key=seller.id, data={
            'business_name': '개발용 가상 판매처', 'brand_name': '육아생활 예시관', 'brand_description': 'UI와 권한 검증을 위한 가상 브랜드입니다.',
            'shipping_policy': '개발용 예시입니다. 실제 발송하지 않습니다.', 'refund_policy': '결제 없이 참여·철회 흐름을 시험합니다. 실제 교환·환불은 발생하지 않습니다.',
            'review_note': '개발용 초기 데이터; 실제 사업자 검증 아님'}))
        brand = Record(kind='brand', owner_id=seller.id, unique_key=seller.id, data={'name': '육아생활 예시관', 'description': '실거래 없는 개발용 브랜드관'})
        db.add(brand)
        db.flush()
        examples = [('기저귀 묶음 모집 예시', '기저귀·물티슈', 28000, '1팩'), ('이유식 보관용기 모집 예시', '수유·이유식', 16000, '3개 묶음'),
                    ('유아 목욕수건 모집 예시', '목욕·위생', 21000, '2장'), ('외출 파우치 모집 예시', '외출·안전', 12000, '1개'),
                    ('그림책 세트 모집 예시', '놀이·도서', 24000, '3권'), ('육아 수납함 모집 예시', '육아생활', 18000, '1개')]
        for title, category, price, unit in examples:
            db.add(Record(kind='campaign', owner_id=seller.id, parent_id=brand.id, capacity=30, ends=now()+7*86400,
                          data={'title': title, 'description': '개발용 예시 공동구매입니다. 참여를 눌러도 결제되지 않으며 실제 상품이 배송되지 않습니다.',
                                'category': category, 'price': price, 'shipping_fee': 3000, 'unit': unit, 'minimum_quantity': 5, 'published': True}))
        db.add(Record(kind='coupon', owner_id=seller.id, parent_id=brand.id, capacity=100, ends=now()+7*86400,
                      data={'title': '개발용 2,000원 혜택', 'amount': 2000, 'min_spend': 20000, 'points_cost': 0}))
        db.add(Record(kind='hotdeal', ends=now()+3*86400, data={'title': '물티슈 핫딜 정보 예시', 'category': '기저귀·물티슈', 'price': 19000,
                      'shipping_fee': 0, 'seller_name': '가상 외부 판매처', 'source_url': None, 'source_name': '개발용 큐레이션; 실제 원문 없음'}))
        db.commit()
        (RUNTIME / 'demo-accounts.json').write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding='utf-8')
        print('DEMO_SEED_PASS: 3 local accounts, 6 campaigns, 1 coupon, 1 curated example. Credentials in ignored runtime/demo-accounts.json.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', required=True)
    parser.parse_args()
    seed()
