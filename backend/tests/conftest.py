import os
from pathlib import Path
import tempfile

TEST_RUNTIME = tempfile.TemporaryDirectory(prefix='moduyuga-tests-')
os.environ['RUNTIME_DIR'] = TEST_RUNTIME.name
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(TEST_RUNTIME.name) / 'test.db').as_posix()

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal, Record, User, now
from app.security import _attempts, issue_token, passwords

PASSWORD = 'Test-Only-Password-123'
HASH = passwords.hash(PASSWORD)


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_RUNTIME.cleanup()


@pytest.fixture
def setup():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    _attempts.clear()
    people = {}
    with SessionLocal() as db:
        for name in ['buyer', 'buyer2', 'seller', 'seller2', 'pending', 'admin']:
            u = User(email=name+'@example.com', nickname=name, password_hash=HASH, is_admin=name == 'admin',
                     seller_status='approved' if name in ['seller', 'seller2'] else 'pending' if name == 'pending' else None)
            db.add(u)
            db.flush()
            people[name] = {'id': u.id, 'headers': {'Authorization': 'Bearer '+issue_token(db, u)}}
        seller = people['seller']['id']
        b = Record(kind='brand', owner_id=seller, unique_key=seller, data={'name': '예시 브랜드', 'description': '시험'})
        db.add(b)
        db.flush()
        db.add(Record(kind='application', owner_id=seller, unique_key=seller, data={'business_number': 'PRIVATE-BUSINESS-NUMBER',
                      'contact_email': 'private@example.com', 'business_address': 'PRIVATE ADDRESS', 'shipping_policy': '예시 배송', 'refund_policy': '예시 환불'}))
        c = Record(kind='campaign', owner_id=seller, parent_id=b.id, capacity=10, ends=now()+86400,
                   data={'title': '예시 공구', 'description': '실제 거래 없는 시험입니다', 'category': '육아생활', 'price': 10000,
                         'shipping_fee': 0, 'unit': '1개', 'minimum_quantity': 2, 'published': True})
        coupon = Record(kind='coupon', owner_id=seller, parent_id=b.id, capacity=1, ends=now()+86400,
                        data={'title': '예시 혜택', 'amount': 1000, 'min_spend': 10000, 'points_cost': 0})
        db.add_all([c, coupon])
        db.commit()
        ids = {'campaign': c.id, 'coupon': coupon.id, 'brand': b.id}
    with TestClient(app) as client:
        yield client, people, ids


def application():
    return dict(business_name='가상 개발업체', business_number='1234567891', representative='예시대표', contact_phone='01000000000',
                contact_email='seller@example.com', business_address='개발용 주소', return_address='개발용 반품주소', commerce_number='',
                commerce_exempt_reason='개발용 예시', shipping_policy='실제 배송 없음', refund_policy='실제 결제 없음',
                brand_name='예시브랜드', brand_description='개발용 가상 브랜드', seller_terms_accepted=True)
