"""Read a reviewed Srookpay campaign and price only the matching, available options."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from . import release
from .db import now
from .external_groupbuys import FRESH_SECONDS, NotGroupbuy, REVIEWED_CAMPAIGNS

KST = timezone(timedelta(hours=9))


def parse(html, source):
    rule = REVIEWED_CAMPAIGNS.get(source['url'])
    if not rule:
        raise NotGroupbuy('Campaign has not been reviewed')
    code = source['url'].rsplit('/', 1)[-1]
    items = []
    for match in re.finditer(r'\b_qna_goods_data\s*=\s*(?=\{)', html):
        data, _ = json.JSONDecoder().raw_decode(html[match.end():])
        if data.get('code') == code:
            items.append(data)
    if len(items) != 1:
        raise ValueError('Expected one matching seller product')
    item = items[0]
    if item.get('name') != rule['title'] or item.get('timesale_able') is not True:
        raise NotGroupbuy('Seller campaign changed')
    times = []
    for key in ('timesale_start', 'timesale_end'):
        value = item.get(key)
        if not isinstance(value, str):
            raise ValueError('Unconfirmed seller campaign period')
        moment = datetime.fromisoformat(value)
        times.append((moment if moment.tzinfo else moment.replace(tzinfo=KST)).timestamp())
    last_day = datetime.fromisoformat(rule['last_day']).replace(tzinfo=KST) + timedelta(days=1)
    closes = min(int(times[1]), int(last_day.timestamp()))
    groups = item.get('option')
    if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], dict):
        raise ValueError('Unrecognized option groups')
    if groups[0].get('type') != 'option_stock' or not isinstance(groups[0].get('data'), list):
        raise ValueError('Unrecognized option pricing')
    options = [v for v in groups[0]['data'] if isinstance(v, dict) and v.get('value1') == rule['option_group']
               and v.get('is_invisible') is False and v.get('is_add_price') is False
               and isinstance(v.get('value2'), str) and v['value2']
               and type(v.get('price')) is int and 0 < v['price'] <= 1_000_000_000
               and type(v.get('stock')) is int]
    if not options:
        raise NotGroupbuy('Reviewed product options are no longer offered')
    available = sorted((v for v in options if v['stock'] > 0), key=lambda v: v['price'])
    stamp = now()
    active = (item.get('status') == '2' and item.get('timesale_status') == 'timedeal'
              and times[0] <= stamp < closes)
    option = available[0] if available else options[0]
    return {
        'source_id': source['id'], 'source_url': source['url'], 'seller_url': source['url'],
        'source_type': 'seller_page', 'source_parser': 'srookpay', 'seller_name': source['seller'],
        'source_hash': hashlib.sha256(html.encode()).hexdigest(), 'category': source['category'],
        'title': item['name'], 'price': option['price'], 'unit': option['value2'],
        'option_labels': [f"{v['value2']} · {v['price']:,}원" for v in available],
        'shipping_fee': None, 'minimum_quantity': None, 'price_references': [],
        'source_checked_at': release.timestamp(stamp), 'source_fresh_until': min(stamp + FRESH_SECONDS, closes),
        'expires_at': release.timestamp(closes), 'updated_at': release.timestamp(stamp),
        'availability': 'ended' if not active else 'listed' if available else 'sold_out',
        'price_conditions': option['value2'] + ' 기준이에요. 다른 구성과 배송비는 판매처에서 확인하세요.',
        'body': '판매처에서 공동구매 기간과 선택 가능한 구성을 확인한 상품이에요.',
        'is_demo': False, 'review_state': 'clear',
    }

