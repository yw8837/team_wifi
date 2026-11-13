import json

import pytest

from app import groupbuy_schema


def page(**changes):
    product = {'@type': 'Product', 'name': '유아 칫솔 공동구매',
        'description': '공동구매 전용 상품',
        'offers': {'price': 34980, 'priceCurrency': 'KRW', 'availability': 'https://schema.org/InStock'}}
    product.update(changes)
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


SOURCE = {'id': 'seller-1', 'url': 'https://www.doctornoah.net/shop_view?idx=545',
          'seller': '닥터노아 공식몰', 'category': '목욕·위생'}


def test_only_product_specific_campaign_is_imported():
    result = groupbuy_schema.parse(page(), SOURCE)
    assert result['price'] == 34980 and result['availability'] == 'listed'
    assert result['source_parser'] == 'schema_product'
    assert result['shipping_fee'] is None
    with pytest.raises(ValueError):
        groupbuy_schema.parse(page(name='일반 칫솔', description='매일 사용하는 칫솔') + '<footer>공동구매 참여 가능</footer>', SOURCE)
    with pytest.raises(ValueError):
        groupbuy_schema.parse(page() + page(), SOURCE)


@pytest.mark.parametrize('offer', [
    {'price': 1, 'priceCurrency': 'USD', 'availability': 'https://schema.org/InStock'},
    {'price': 0, 'priceCurrency': 'KRW', 'availability': 'https://schema.org/InStock'},
    {'price': 3000, 'priceCurrency': 'KRW'},
    [{'price': 3000, 'priceCurrency': 'KRW'}],
])
def test_invalid_offer_is_not_published(offer):
    with pytest.raises(ValueError):
        groupbuy_schema.parse(page(offers=offer), SOURCE)


def test_stock_status_is_preserved_and_source_content_is_not_copied():
    result = groupbuy_schema.parse(page(image=['https://example.com/photo.jpg'], review=[{'author': 'private'}],
        offers={'price': 10000, 'priceCurrency': 'KRW', 'availability': 'https://schema.org/OutOfStock'}), SOURCE)
    assert result['availability'] == 'sold_out'
    assert 'image' not in result and 'review' not in result

@pytest.mark.parametrize('changes', [
    {'name': None}, {'description': []},
    {'offers': {'price': None, 'priceCurrency': 'KRW', 'availability': 'InStock'}},
    {'offers': {'price': True, 'priceCurrency': 'KRW', 'availability': 'InStock'}},
    {'offers': {'price': 100, 'priceCurrency': 'KRW', 'availability': {}}},
])
def test_malformed_external_fields_are_rejected(changes):
    with pytest.raises(ValueError):
        groupbuy_schema.parse(page(**changes), SOURCE)


@pytest.mark.parametrize('title', [
    '유아 칫솔 공동구매 종료', '[마감] 유아 칫솔 공동구매',
    '유아 칫솔 공동구매 마감: 2020-01-01 00:00',
])
def test_explicit_campaign_closure_overrides_stock(title):
    assert groupbuy_schema.parse(page(name=title), SOURCE)['availability'] == 'ended'

@pytest.mark.parametrize('title', ['원목 공구놀이 장난감', '유아 공구세트 장난감', '유아 공구함 장난감'])
def test_tool_toys_are_not_campaign_evidence(title):
    with pytest.raises(ValueError):
        groupbuy_schema.parse(page(name=title, description='아이를 위한 공구놀이'), SOURCE)


@pytest.mark.parametrize('title', ['[공구종료] 유아 칫솔', '[공구마감] 유아 칫솔'])
def test_attached_closure_marker_remains_supported(title):
    assert groupbuy_schema.parse(page(name=title, description='유아용 칫솔'), SOURCE)['availability'] == 'ended'
