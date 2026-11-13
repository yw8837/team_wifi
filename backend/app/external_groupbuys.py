"""Bounded collection of public seller facts, with expiring verification receipts."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import re
import secrets
import uuid
from html import unescape
from urllib.parse import parse_qsl, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from sqlalchemy import select, text

from . import release
from .db import Record, User, now
from .security import passwords

SOURCES = (
    {'id': 'canco-222', 'url': 'https://somi9726.cafe24.com/product/detail.html?product_no=222',
     'seller': '캔코 공식몰', 'category': '외출·안전',
     'comparison_url': 'https://somi9726.cafe24.com/product/detail.html?product_no=172',
     'product_key': '캔코 모아백 기저귀가방'},
)
MAX_BYTES = 2_000_000
FRESH_SECONDS = 24 * 3600
CAMPAIGN_EVIDENCE = re.compile(r"공동\s*구매|공구(?:종료|마감)(?![가-힣])|(?<![가-힣])공구(?![가-힣])")
SELLERS = json.loads(Path(__file__).with_name('groupbuy_sellers.json').read_text(encoding='utf-8'))
ALLOWED_HOSTS = frozenset(seller['host'] for seller in SELLERS)


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS
            or parsed.port not in (None, 443) or parsed.username or parsed.password):
        raise ValueError('Seller URL is outside the reviewed source list')
    return url


class SellerRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch(source):
    if source.get('parser') == 'schema_product':
        from .groupbuy_schema import parse
        return parse(read_html(source['url']), source)
    entry = fetch_page(source)
    entry['price_references'] = []
    product_terms = source.get('product_key', '').split()
    if source.get('comparison_url') and product_terms and all(term in entry['title'] for term in product_terms):
        try:
            reference = fetch_page({**source, 'url': source['comparison_url']}, groupbuy=False)
            if all(term in reference['title'] for term in product_terms) and reference['availability'] == 'listed':
                entry['comparison_quantity'] = 1
                entry['price_references'].append({
                    'channel': 'online', 'seller_name': source['seller'] + ' 일반 판매',
                    'url': reference['seller_url'], 'price': reference['price'],
                    'shipping_fee': reference['shipping_fee'], 'quantity': 1,
                    'scope': source['product_key'] + ' 본품 1개 · 기본 옵션 가격',
                    'checked_at': reference['source_checked_at'],
                    'fresh_until': reference['source_fresh_until'],
                    'source_hash': reference['source_hash']})
        except (OSError, ValueError):
            pass  # A failed comparison fetch must not preserve an old price as fresh.
    return entry


def read_html(url):
    request = Request(validate_url(url), headers={
        'User-Agent': 'ModuYuga-SourceCheck/1.0', 'Accept': 'text/html'})
    with build_opener(SellerRedirect).open(request, timeout=20) as response:
        if response.headers.get_content_type() != 'text/html':
            raise ValueError('Seller response must be HTML')
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('Seller response exceeds size limit')
        return raw.decode('utf-8')


def fetch_page(source, *, groupbuy=True):
    return parse_cafe24(read_html(source['url']), source, groupbuy=groupbuy)


def campaign_state(title, stamp):
    ended = bool(re.search(r'\[(?:종료|마감)\]|(?:공동\s*구매|공구)\s*(?:종료|마감)(?:\s*$|\s*[\])】])|(?:종료된|마감된)\s*공구', title))
    deadline = None
    # Only an explicit campaign deadline is a closing time. A sale-price validity
    # variable may describe a discount period and must not close a campaign.
    deadline_match = re.search(r'마감\s*[:：]\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)', title)
    if deadline_match:
        try:
            deadline = datetime.fromisoformat(deadline_match.group(1))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone(timedelta(hours=9)))
            ended = ended or deadline.timestamp() <= stamp
        except ValueError:
            raise ValueError('Unrecognized campaign deadline')
    return ended, deadline


def parse_cafe24(html, source, *, groupbuy=True):
    def variable(name):
        match = re.search(r'\bvar\s+' + re.escape(name) + r"\s*=\s*'([^'\r\n]*)'", html)
        if not match:
            raise ValueError('Required seller field missing: ' + name)
        return unescape(match.group(1))

    title = variable('product_name')
    if (groupbuy and not CAMPAIGN_EVIDENCE.search(title)) or not 3 <= len(title) <= 120:
        raise ValueError('Seller page does not identify a group buy')
    base_price = variable('product_price')
    if not base_price.isdigit():
        raise ValueError('Unrecognized seller price')
    # Prefer the displayed sale price, and reject contradictory repeated values.
    prices = set(re.findall(r'\bvar\s+product_sale_price\s*=\s*(\d+)\s*;', html))
    if len(prices) > 1:
        raise ValueError('Conflicting sale prices')
    price = int(next(iter(prices), base_price))
    if not 0 < price <= 1_000_000_000:
        raise ValueError('Seller price outside supported range')
    soldout = variable('is_soldout_icon')
    if soldout not in ('T', 'F'):
        raise ValueError('Unknown seller availability')
    member_only = variable('sIsNonmemberLimit') == 'T'
    def quantity(name):
        matches = re.findall(r'\bvar\s+' + re.escape(name) + r"\s*=\s*'(\d+)'", html)
        values = set(matches)
        return int(matches[0]) if len(values) == 1 and 0 < int(matches[0]) <= 1_000_000_000 else None
    shipping_rows = [unescape(re.sub('<[^>]+>', ' ', row)) for row in
                     re.findall(r'<tr\b[^>]*>.*?</tr>', html, re.S) if '배송비' in row]
    shipping_free = bool(shipping_rows) and all(
        re.sub(r'\s+', '', row) == '배송비무료' for row in shipping_rows)
    plain = re.sub(r'\s+', ' ', unescape(re.sub('<[^>]+>', ' ', html)))
    delivery = re.search(r'배송 기간\s*:\s*(\d+일\s*~\s*\d+일)', plain)
    fulfillment = []
    if delivery:
        fulfillment.append('판매처 일반 배송 안내 ' + delivery.group(1) + ' · 옵션별 출고 일정은 별도 확인')
    if '산간벽지나 도서지방은 별도의 추가금액' in plain:
        fulfillment.append('도서산간은 추가 배송비가 발생할 수 있습니다.')
    product_number = dict(parse_qsl(urlsplit(source['url']).query)).get('product_no', '')
    option_selects = re.findall(r'<select\b[^>]*option_product_no="' + re.escape(product_number)
                               + r'"[^>]*>(.*?)</select>', html, re.S) if product_number else []
    options = [unescape(re.sub('<[^>]+>', '', value)).strip() for value in
               re.findall(r'<option\b[^>]*value="P[A-Z0-9]+"[^>]*>(.*?)</option>', ''.join(option_selects), re.S)]
    return_note = '단순 변심 교환·반품의 반송비는 구매자 부담으로 안내합니다. 적용 기한·제외 사유는 판매처 구매안내를 확인하세요.' if '상품반송 비용은 고객님께서 부담' in plain else ''
    stamp = now()
    ended, deadline = campaign_state(title, stamp)
    return {'source_id': source['id'], 'source_url': source['url'],
            'source_hash': hashlib.sha256(html.encode()).hexdigest(),
            'title': title, 'category': source['category'], 'seller_name': source['seller'],
            'seller_url': source['url'], 'price': price, 'shipping_fee': 0 if shipping_free else None,
            'minimum_quantity': None, 'unit': '', 'expires_at': deadline.isoformat() if deadline else '',
            'order_minimum': quantity('product_min'), 'order_step': quantity('buy_unit'),
            'fulfillment_notes': fulfillment, 'option_labels': list(dict.fromkeys(options))[:30],
            'return_note': return_note,
            'source_checked_at': release.timestamp(stamp), 'source_fresh_until': stamp + FRESH_SECONDS,
            'source_type': 'seller_page', 'availability': 'ended' if ended else 'sold_out' if soldout == 'T' else 'listed',
            'body': '판매처의 공동구매 페이지에서 확인한 상품입니다. 옵션별 구성과 배송비, 최종 결제금액은 판매처에서 확인하세요.',
            'price_conditions': ('판매처 회원가입·로그인 후 구매할 수 있습니다. ' if member_only else '')
                + ('판매처 표시 판매가와 마감 일시 기준입니다.' if deadline else '판매처 표시 판매가 기준입니다. 마감 일시는 공개 페이지에서 확인되지 않았습니다.'),
            'is_demo': False, 'review_state': 'clear', 'updated_at': release.timestamp(stamp)}


def lock_collection(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(72411309)'))


def store(db, entries):
    lock_collection(db)
    actor_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'moduyuga:source-collection'))
    actor = db.get(User, actor_id)
    if actor is None:
        actor = User(id=actor_id, email='source-collection@moduyuga.example', nickname='모두의 육아 정보',
                     password_hash=passwords.hash(secrets.token_urlsafe(48)), is_admin=False)
        db.add(actor)
        db.flush()
    updated = 0
    for entry in entries:
        key = 'external:' + entry['source_id']
        row = db.scalar(select(Record).where(Record.kind == 'release_groupbuy', Record.unique_key == key))
        if row and (row.owner_id != actor_id or row.data.get('source_type') != 'seller_page'):
            raise ValueError('Source record collision')
        if row and row.status == 'hidden':
            continue  # Collection never reverses an operator moderation decision.
        if row is None:
            row = Record(kind='release_groupbuy', unique_key=key, owner_id=actor_id)
            db.add(row)
        else:
            row.revision += 1
        row.data = {**entry, 'review_state': (row.data or {}).get('review_state', 'clear')}
        row.ends = entry['source_fresh_until']
        if entry.get('expires_at'):
            row.ends = min(row.ends, int(datetime.fromisoformat(entry['expires_at']).timestamp()))
        row.status = 'active' if entry['availability'] == 'listed' and row.ends > now() else 'ended'
        updated += 1
    return updated


def retire_demo_listings(db):
    """Retain the requested demo community while replacing its shopping listings."""
    rows = db.scalars(select(Record).where(Record.data['demo_dataset'].as_string() == 'moduyuga-community-demo-v1'))
    changed = 0
    for row in rows:
        data = dict(row.data)
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = value.replace('[가상] ', '').replace('[가상 댓글] ', '').replace('가상', '시연').replace('시연 시연', '시연용')
        if row.kind == 'release_groupbuy':
            row.status = 'hidden'
        if row.kind == 'demo_actor':
            actor = db.get(User, row.owner_id)
            actor.nickname = actor.nickname.removeprefix('[가상] ')
        if data != row.data or row.kind == 'release_groupbuy':
            row.data = data
            row.revision += 1
            changed += 1
    return changed
