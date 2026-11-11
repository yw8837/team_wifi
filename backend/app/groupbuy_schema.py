"""Read public Product facts without copying reviews, images, or sales copy."""
from html.parser import HTMLParser
import hashlib
import json
import re

from . import release
from .db import now


class ProductScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.buffer = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.capture = dict(attrs).get('type') == 'application/ld+json'
            self.buffer = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            try:
                self.documents.append(json.loads(''.join(self.buffer)))
            except ValueError:
                pass
            self.capture = False


def products(document):
    if isinstance(document, list):
        for value in document:
            yield from products(value)
    elif isinstance(document, dict):
        if document.get('@type') == 'Product':
            yield document
        yield from products(document.get('@graph', []))


def parse(html, source):
    parser = ProductScripts()
    parser.feed(html)
    candidates = [product for document in parser.documents for product in products(document)]
    if len(candidates) != 1:
        raise ValueError('One primary product is required')
    product = candidates[0]
    title = product.get('name', '')
    description = product.get('description', '')
    if not re.search(r'공동\s*구매|공구', title + ' ' + description):
        raise ValueError('Product-specific campaign evidence missing')
    title = re.sub(r'최대\s*\d+%\s*할인[^\w]*', '', title).strip()
    if not 3 <= len(title) <= 120:
        raise ValueError('Invalid product title')
    offer = product.get('offers', {})
    if not isinstance(offer, dict) or offer.get('priceCurrency') != 'KRW':
        raise ValueError('One KRW offer is required')
    price = float(offer.get('price', 0))
    if not price.is_integer() or not 0 < price <= 1_000_000_000:
        raise ValueError('Invalid price')
    state = offer.get('availability', '').rsplit('/', 1)[-1]
    if state not in ('InStock', 'OutOfStock', 'SoldOut', 'Discontinued'):
        raise ValueError('Availability unconfirmed')
    stamp = now()
    return {
        'source_id': source['id'], 'source_url': source['url'],
        'source_hash': hashlib.sha256(html.encode()).hexdigest(),
        'title': title, 'category': source.get('category', ''),
        'seller_name': source['seller'], 'seller_url': source['url'],
        'price': int(price), 'shipping_fee': None, 'minimum_quantity': None,
        'unit': '', 'expires_at': '', 'price_references': [],
        'source_checked_at': release.timestamp(stamp), 'source_fresh_until': stamp + 86400,
        'source_type': 'seller_page', 'source_parser': 'schema_product',
        'availability': 'listed' if state == 'InStock' else 'sold_out',
        'body': '판매처가 공동구매로 안내한 상품입니다. 표시 가격은 기본 구성 기준이며 옵션에 따라 달라질 수 있습니다.',
        'price_conditions': '배송비와 최종 구성은 판매처에서 확인하세요. 공구 마감 일시는 미확인입니다.',
        'is_demo': False, 'review_state': 'clear', 'updated_at': release.timestamp(stamp),
    }
