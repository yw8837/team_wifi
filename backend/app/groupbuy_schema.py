"""Read public Product facts without copying reviews, images, or sales copy."""
from html.parser import HTMLParser
import hashlib
import json
import re

from . import release
from .db import now
from .external_groupbuys import CAMPAIGN_EVIDENCE, FRESH_SECONDS, NotGroupbuy, campaign_state


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


def variant_prices(html, title):
    scripts = ProductScripts()
    scripts.feed(html)
    groups = [d for d in scripts.documents if isinstance(d, dict)
              and d.get('@type') == 'ProductGroup' and d.get('name') == title]
    if len(groups) != 1:
        raise ValueError('Missing matching product group')
    result = []
    variants = groups[0].get('hasVariant')
    if not isinstance(variants, list):
        raise ValueError('Missing product configurations')
    for variant in variants:
        if not isinstance(variant, dict) or not isinstance(variant.get('offers'), dict):
            continue
        offer = variant['offers']
        name = variant.get('name', '')
        price = offer.get('price')
        if (not isinstance(name, str) or not name.startswith(title + ' ') or offer.get('availability') != 'https://schema.org/InStock'
                or offer.get('priceCurrency') != 'KRW' or type(price) is not int or not 0 < price <= 1_000_000_000):
            continue
        label = name[len(title):].strip()
        if label:
            result.append((label, price))
    if not result:
        raise ValueError('No verified purchasable configuration')
    return result


def parse(html, source):
    parser = ProductScripts()
    parser.feed(html)
    candidates = [product for document in parser.documents for product in products(document)]
    if len(candidates) != 1:
        raise ValueError('One primary product is required')
    product = candidates[0]
    title = product.get('name', '')
    description = product.get('description', '')
    if not isinstance(title, str) or not isinstance(description, str):
        raise ValueError('Product text must be a string')
    if not CAMPAIGN_EVIDENCE.search(title + ' ' + description):
        raise NotGroupbuy('Product-specific campaign evidence missing')
    title = re.sub(r'최대\s*\d+%\s*할인[^\w]*', '', title).strip()
    if not 3 <= len(title) <= 120:
        raise ValueError('Invalid product title')
    offer = product.get('offers', {})
    if not isinstance(offer, dict) or offer.get('priceCurrency') != 'KRW':
        raise ValueError('One KRW offer is required')
    raw_price = offer.get('price')
    if isinstance(raw_price, bool) or not isinstance(raw_price, (str, int, float)):
        raise ValueError('Price must be numeric')
    try:
        price = float(raw_price)
    except (ValueError, OverflowError):
        raise ValueError('Invalid price') from None
    if not price.is_integer() or not 0 < price <= 1_000_000_000:
        raise ValueError('Invalid price')
    availability = offer.get('availability')
    if not isinstance(availability, str):
        raise ValueError('Availability must be a string')
    state = availability.rsplit('/', 1)[-1]
    if state not in ('InStock', 'OutOfStock', 'SoldOut', 'Discontinued'):
        raise ValueError('Availability unconfirmed')
    # Imweb can advertise InStock even while checkout is closed or not yet open.
    markup = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
    checkout_closed = re.search(r'>\s*(?:판매 기간이 마감된 상품입니다|이 상품은 (?:현재 판매기간이 아닙니다|[0-9년월일 :]+부터 판매됩니다))\.\s*<', markup)
    stamp = now()
    ended, deadline = campaign_state(title, stamp)
    return {
        'source_id': source['id'], 'source_url': source['url'],
        'source_hash': hashlib.sha256(html.encode()).hexdigest(),
        'title': title, 'category': source.get('category', ''),
        'seller_name': source['seller'], 'seller_url': source['url'],
        'price': int(price), 'shipping_fee': None, 'minimum_quantity': None,
        'unit': '', 'expires_at': deadline.isoformat() if deadline else '', 'price_references': [],
        'source_checked_at': release.timestamp(stamp), 'source_fresh_until': stamp + FRESH_SECONDS,
        'source_type': 'seller_page', 'source_parser': 'schema_product',
        'availability': 'ended' if ended or checkout_closed else 'listed' if state == 'InStock' else 'sold_out',
        'body': '판매처가 공동구매로 안내한 상품입니다. 표시 가격은 기본 구성 기준이며 옵션에 따라 달라질 수 있습니다.',
        'price_conditions': '배송비와 최종 구성은 판매처에서 확인하세요.' + ('' if deadline else ' 공구 마감 일시는 미확인입니다.'),
        'is_demo': False, 'review_state': 'clear', 'updated_at': release.timestamp(stamp),
    }
