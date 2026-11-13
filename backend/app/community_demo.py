"""Idempotent, explicitly labelled community demonstration records."""
import secrets
import uuid

from sqlalchemy import text

from .db import Record, User, now
from .security import passwords
from . import release

PREFIX = 'moduyuga-community-demo-v1'


def identifier(label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, PREFIX + '/' + label))


def seed(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(72411308)'))
    stamp = now()
    created = {'users': 0, 'records': 0}

    def record(label, kind, owner, data, *, parent=None, ends=0, status='active'):
        key = identifier(label)
        existing = db.get(Record, key)
        if existing:
            if existing.data.get('demo_dataset') != PREFIX:
                raise ValueError('Demo identifier belongs to another record')
            return existing
        item = Record(id=key, kind=kind, owner_id=owner, parent_id=parent,
                      unique_key=label, ends=ends, status=status,
                      data={**data, 'is_demo': True, 'demo_dataset': PREFIX}, created=stamp)
        db.add(item)
        db.flush()
        created['records'] += 1
        return item

    people = []
    names = ['봄이네', '달콩이네', '새싹아빠', '두부엄마', '도담이네', '햇살부부', '별이네', '구름아빠']
    for index, name in enumerate(names):
        key = identifier(f'person/{index}')
        email = f'community-demo-{index}@moduyuga.example'
        person = db.get(User, key)
        if person and person.email != email:
            raise ValueError('Demo identifier belongs to another user')
        if person is None:
            person = User(id=key, email=email, nickname=name,
                          password_hash=passwords.hash(secrets.token_urlsafe(48)), is_admin=False)
            db.add(person)
            db.flush()
            created['users'] += 1
        record(f'actor/{index}', 'demo_actor', person.id, {'label': '시연용 회원'})
        people.append(person)

    products = [
        ('기저귀 4단계 160매 구성 비교', '기저귀·물티슈', 39800, 0, '160매', 2),
        ('물티슈 80매 10팩 묶음', '기저귀·물티슈', 15900, 3000, '800매', 24),
        ('젖병 세척솔과 건조대 세트', '수유·이유식', 21900, 2500, '세척솔 2개·건조대 1개', 48),
        ('이유식 보관용기 6개 세트', '수유·이유식', 18900, 0, '150ml 6개', 72),
        ('유아 목욕수건 2장 구성', '목욕·위생', 24900, 3000, '2장', 96),
        ('외출용 기저귀 파우치', '외출·안전', 12900, 2500, '1개', 120),
        ('촉감 그림책 3권 세트', '놀이·도서', 27900, 0, '3권', 144),
        ('종료된 육아 수납함 공구', '육아생활', 19900, 3000, '2개', -24),
    ]
    buys = []
    for index, (title, category, price, shipping, unit, hours) in enumerate(products):
        end = stamp + hours * 3600
        buys.append(record(f'groupbuy/{index}', 'release_groupbuy', people[index].id, {
            'title': title, 'category': category,
            'body': '기능 시연을 위해 만든 시연 공구입니다. 가격·구성·마감은 시뮬레이션 값이며 실제 판매 및 배송은 없습니다. 배송비를 포함한 단가와 구성을 비교해 보세요.',
            'seller_name': '시연 육아용품 판매처', 'seller_url': 'https://example.com',
            'price': price, 'shipping_fee': shipping, 'unit': unit, 'minimum_quantity': 5,
            'price_conditions': '시연 시나리오 · 표시 금액은 통계·화면 검증용입니다.',
            'expires_at': release.timestamp(end), 'source_checked_at': release.timestamp(stamp),
            'updated_at': None, 'review_state': 'needs_review' if index == 5 else 'clear',
        }, ends=end, status='ended' if hours < 0 else 'active'))

    posts = [
        ('기저귀 단가를 함께 비교해요', '기저귀·물티슈', 'demand', '같은 단계와 매수를 기준으로 배송비까지 포함한 가격을 비교하고 싶어요.'),
        ('물티슈 성분과 구성을 살펴봐요', '기저귀·물티슈', 'demand', '한 팩의 매수와 전체 팩 수가 다른 구성들을 같은 기준으로 보고 싶어요.'),
        ('젖병 세척용품 공구 수요', '수유·이유식', 'demand', '세척솔과 건조대를 같이 준비할 수 있는 구성을 찾아보고 있어요.'),
        ('이유식 보관용기 선택 기준', '수유·이유식', 'question', '용량과 구성품, 관리 방법 중 어떤 순서로 비교하면 좋을까요?'),
        ('목욕수건 구성 비교 후기', '목욕·위생', 'experience', '시연용 후기입니다. 크기와 소재 표시를 먼저 확인하고 장당 가격을 비교하는 흐름을 보여줍니다.'),
        ('외출 파우치에 필요한 구성', '외출·안전', 'demand', '수납공간과 세척 방법을 확인할 수 있는 파우치가 있으면 좋겠어요.'),
        ('그림책 세트 선택 질문', '놀이·도서', 'question', '세트 권수와 책의 크기를 함께 비교하고 싶어요.'),
        ('육아용품 비교 체크리스트', '육아생활', 'information', '구성·규격·배송비·사용 및 관리 방법을 같은 순서로 확인해 보는 시연 안내입니다.'),
    ]
    for index, (title, category, post_type, body) in enumerate(posts):
        data = {'title': title, 'body': '[시연용 데이터] ' + body,
                'category': category, 'post_type': post_type, 'updated_at': None}
        if post_type == 'demand' and index < 3:
            data['groupbuy_id'] = buys[index].id
        post = record(f'post/{index}', release.DEMAND, people[index].id, data)
        for offset in range(2):
            person = people[(index + offset + 1) % len(people)]
            record(f'comment/{index}/{offset}', release.COMMENT, person.id,
                   {'body': '배송비와 전체 수량을 함께 비교해 보면 좋겠어요.', 'updated_at': None}, parent=post.id)
        if post_type == 'demand':
            for person in people[:6]:
                record(f'interest/{index}/{person.id}', release.INTEREST, person.id, {}, parent=post.id)
    offers = release.catalog()[:3]
    for person in people[:6]:
        for offer in offers:
            record(f'save/{person.id}/{offer["id"]}', release.SAVE, person.id, {}, parent=offer['id'])
    return {'dataset': PREFIX, 'created': created, 'scenario': {'members': 8, 'groupbuys': 8, 'posts': 8, 'comments': 16, 'interests': 24, 'saves': len(offers) * 6}}
