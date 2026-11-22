"""Read dates, price and order availability from the seller's group-buy form."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlsplit

from . import release
from .db import now
from .external_groupbuys import FRESH_SECONDS, NotGroupbuy


def campaign_key(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if parsed.path != '/m/goods/content.asp' or set(query) != {'gc', 'guid'}:
        return None
    if any(len(values) != 1 or not re.fullmatch(r'[1-9][0-9]{0,11}', values[0]) for values in query.values()):
        return None
    return {name: query[name][0] for name in ('gc', 'guid')}


class OrderForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}
        self.can_buy = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'input' and values.get('type') == 'hidden':
            name = values.get('id') or values.get('name')
            self.fields.setdefault(name, set()).add(values.get('value', ''))
        if tag == 'a':
            classes = (values.get('class') or '').split()
            if 'inbuy' in classes and 'gonggu-soldout-opt' not in classes and 'buyboxcheck(' in (values.get('onclick') or ''):
                self.can_buy = True

    def value(self, name):
        values = self.fields.get(name, set())
        if len(values) != 1:
            raise ValueError('Missing or inconsistent seller field: ' + name)
        return next(iter(values))


def parse(html, source):
    form = OrderForm()
    form.feed(html)
    key = campaign_key(source['url'])
    if not key or 'gongguCountdownEnd' not in form.fields or any(form.value(k) != v for k, v in key.items()):
        raise NotGroupbuy('Seller no longer identifies this campaign and product')
    kst = timezone(timedelta(hours=9))
    start, end = [int(datetime.strptime(form.value(k), '%Y-%m-%d %H:%M:%S').replace(tzinfo=kst).timestamp())
                  for k in ('gongguCountdownStart', 'gongguCountdownEnd')]
    title = form.value('title').strip()
    if not 3 <= len(title) <= 120 or end <= start or form.value('gongguStateEnded') not in ('0', '1'):
        raise ValueError('Unconfirmed campaign details')
    if any(form.value(name) != 'F' for name in ('nChkOpt_useFlag', 'nChkMultiOpt_useFlag', 'nChkTextOpt_useFlag')):
        raise ValueError('Requires option-level price verification')
    price, stock = int(form.value('price')), int(form.value('stock'))
    if not 0 < price <= 1_000_000_000 or stock < 0:
        raise ValueError('Invalid price or stock')
    stamp = now()
    active = start <= stamp < end and form.value('gongguStateEnded') == '0'
    availability = 'listed' if stock and form.value('IsStock') == 'T' and form.can_buy else 'sold_out'
    return {
        'title': title, 'source_id': source['id'], 'source_parser': 'celebrity',
        'category': source.get('category', ''), 'source_type': 'seller_page', 'seller_name': source['seller'],
        'source_url': source['url'], 'seller_url': source['url'], 'source_hash': sha256(html.encode()).hexdigest(),
        'price': price, 'shipping_fee': None, 'unit': '', 'minimum_quantity': None,
        'price_conditions': '단품 기준 가격이에요. 배송 조건은 판매처에서 확인하세요.',
        'body': '판매처 주문 화면에서 공구 기간과 단품 가격을 확인했어요.',
        'availability': availability if active else 'ended', 'expires_at': release.timestamp(end),
        'source_checked_at': release.timestamp(stamp), 'source_fresh_until': min(stamp + FRESH_SECONDS, end),
        'updated_at': release.timestamp(stamp), 'price_references': [], 'is_demo': False, 'review_state': 'clear',
    }
