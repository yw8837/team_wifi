import json
from datetime import datetime
import pytest
from app import groupbuy_srookpay as seller

url = 'https://shop.srookpay.com/luxiai/Detail/SLU93540156'
source = {'url': url, 'id': 'reviewed', 'seller': '판매처', 'category': '놀이·도서'}


@pytest.fixture
def product(monkeypatch):
    monkeypatch.setattr(seller, 'now', lambda: int(datetime(2026, 11, 22, 12, tzinfo=seller.KST).timestamp()))
    variant = {'value1': '어드벤트 캘린더 2종', 'value2': '윈터빌리지', 'price': 38900, 'stock': 1,
               'is_invisible': False, 'is_add_price': False}
    return {'code': 'SLU93540156', 'name': seller.REVIEWED_CAMPAIGNS[url]['title'], 'timesale_able': True,
            'price': 19900, 'timesale_start': '2026-11-22T00:00:00', 'timesale_end': '2026-11-28T10:00:00',
            'timesale_status': 'timedeal', 'status': '2', 'option': [{'type': 'option_stock',
            'data': [dict(variant, value1='소품', price=19900), variant]}]}


def parse(item):
    return seller.parse('_qna_goods_data = {}; _qna_goods_data = ' + json.dumps(item) + ';', source)


def test_prices_only_matching_available_options(product):
    entry = parse(product)
    assert entry['availability'] == 'listed' and entry['price'] == 38900 and entry['unit'] == '윈터빌리지'
    assert datetime.fromisoformat(entry['expires_at']).astimezone(seller.KST).day == 28
    product['option'][0]['data'][1]['stock'] = 0
    assert parse(product)['availability'] == 'sold_out'


def test_campaign_change_and_end(product, monkeypatch):
    monkeypatch.setattr(seller, 'now', lambda: int(datetime(2026, 11, 28, tzinfo=seller.KST).timestamp()))
    assert parse(product)['availability'] == 'ended'
    product['name'] = '일반 판매'
    with pytest.raises(seller.NotGroupbuy):
        parse(product)

