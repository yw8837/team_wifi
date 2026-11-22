"""Read dated group buys and their orderable configurations from a reviewed mini-store."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

from . import release
from .db import now
from .external_groupbuys import FRESH_SECONDS, NotGroupbuy

KST = timezone(timedelta(hours=9))
STORE = 'https://sharequeens.store/minihome/wlsdud6580'
# Separate listings for the same player and high chair share the same configurations.
ALTERNATE_IDS = {'558', '850'}
TERMS = {
    '수유·이유식': ('하이체어', '컵빨대캡', '아넬라 퓨레', '키디밀', '마이키즈'),
    '외출·안전': ('알파카 인피니티 킥보드',),
    '놀이·도서': ('레인보우 피아노', '디즈니 그림명작', '생활동화', '세이펜',
                '사파 플레이어', '마이 비지북', '마이베이비북'),
    '육아생활': ('미꼬밴드', '장난감정리함'),
}


def campaign_sources(html, seller, classify):
    today = datetime.fromtimestamp(now(), KST).date()
    for card in re.split(r'<div\s+class="pl-card"\s+data-product-id="', html)[1:]:
        number = card.partition('"')[0]
        title = re.search(r'<p class="pl-card-name">([^<]+)</p>', card)
        dates = re.search(r'<p class="pl-card-date">\s*(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})\s*</p>', card)
        if not number.isdecimal() or number in ALTERNATE_IDS or not (title and dates):
            continue
        name = unescape(title[1]).strip()
        category = next((key for key, values in TERMS.items() if any(v in name for v in values)), None)
        category = category or classify(name)
        if not category:
            continue
        try:
            start, end = [datetime.strptime(value, '%Y.%m.%d').date() for value in dates.groups()]
        except ValueError:
            continue
        if start <= today <= end:
            yield {'id': 'sharequeens.store-' + number, 'url': STORE + '/product/' + number,
                   'seller': seller, 'category': category, 'parser': 'sharequeens',
                   'listed_title': name, 'dates': (start, end)}


class Product(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.options = []
        self.can_buy = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and a.get('property') in ('og:title', 'og:url'):
            self.meta[a['property']] = a.get('content', '')
        if tag != 'button':
            return
        classes = a.get('class', '').split()
        if ('disabled' in a or a.get('aria-disabled') == 'true' or 'hidden' in a
                or any(re.search('sold.?out|disabled', c, re.I) for c in classes)):
            return
        if 'pd-btn-buy' in classes and a.get('onclick') == 'pdBuyBtnClick()':
            self.can_buy = True
        if 'pd-option-choice' in classes and a.get('onclick') == 'selectPurchaseOption(this)':
            label = a.get('data-option-name', '').strip()
            price = a.get('data-option-price', '')
            if (label and price.isdecimal() and 0 < int(price) <= 1_000_000_000
                    and not re.search(r'품절|배송비|추가\s*(?:구매|옵션)', label)):
                self.options.append((label, int(price)))


def parse(html, source):
    if not source.get('dates'):
        raise ValueError('Current seller listing period unavailable')
    start, end = source['dates']
    product = Product()
    product.feed(html)
    title = product.meta.get('og:title', '')
    canonical = urlsplit(product.meta.get('og:url', ''))._replace(query='', fragment='').geturl()
    if canonical != source['url'] or source['listed_title'] != title:
        raise NotGroupbuy('Store and product identities differ')
    if not re.search(r'class="pd-price-label-main">\s*공구가\s*</span>', html):
        raise NotGroupbuy('Group-buy offer removed')
    period = re.search(r'class="pd-period-value">\s*(\d+)월\s*(\d+)일\s*~\s*(\d+)월\s*(\d+)일', html)
    if not period or tuple(map(int, period.groups())) != (start.month, start.day, end.month, end.day):
        raise ValueError('Listing and offer periods differ')
    if not product.can_buy or not product.options:
        raise NotGroupbuy('No available purchase option')
    displayed = re.search(r'class="pd-sale-price">\s*([0-9,]+)원\s*</span>', html)
    if not displayed:
        raise ValueError('Missing group-buy price')
    price = int(displayed[1].replace(',', ''))
    label = next((label for label, value in product.options if value == price), None)
    if not label:
        raise ValueError('No orderable configuration matches the advertised price')
    stamp = now()
    today = datetime.fromtimestamp(stamp, KST).date()
    cutoff = datetime.combine(end + timedelta(days=1), datetime.min.time(), KST)
    return {
        'source_id': source['id'], 'source_url': source['url'], 'seller_url': source['url'],
        'seller_name': source['seller'], 'source_type': 'seller_page', 'source_parser': 'sharequeens',
        'source_hash': sha256(html.encode()).hexdigest(), 'title': title, 'category': source['category'],
        'price': price, 'unit': label, 'option_labels': [f'{n} · {v:,}원' for n, v in product.options][:30],
        'price_conditions': f'{label} 기준입니다. 판매처 공구 기간은 {start:%Y.%m.%d}~{end:%Y.%m.%d}입니다.',
        'body': '판매처에서 옵션을 선택하고 로그인한 뒤 주문할 수 있습니다. 배송비는 판매처에서 확인하세요.',
        'shipping_fee': None, 'minimum_quantity': None, 'price_references': [], 'expires_at': '',
        'source_checked_at': release.timestamp(stamp), 'updated_at': release.timestamp(stamp),
        'source_fresh_until': min(stamp + FRESH_SECONDS, int(cutoff.timestamp())),
        'availability': 'listed' if start <= today <= end else 'ended',
        'is_demo': False, 'review_state': 'clear',
    }
