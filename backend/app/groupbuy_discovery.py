"""Discover Cafe24 campaigns on reviewed sellers and run a midnight collection."""
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.error import HTTPError

from sqlalchemy import select

from . import external_groupbuys as collector
from .db import Record, now

KST = timezone(timedelta(hours=9))
CATEGORY_TERMS = {
    '기저귀·물티슈': ('기저귀', '물티슈'),
    '수유·이유식': ('젖병', '분유', '이유식', '수유', '턱받이'),
    '목욕·위생': ('욕조', '목욕', '로션', '세정', '체온계'),
    '외출·안전': ('기저귀가방', '모아백', '유모차', '카시트', '아기띠', '안전문'),
    '놀이·도서': ('장난감', '그림책', '동화책', '교구'),
    '육아생활': ('아기침대', '아기이불', '수면조끼', '아기옷'),
}


def seconds_until_midnight(stamp=None):
    current = datetime.fromtimestamp(now() if stamp is None else stamp, KST)
    midnight = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - current).total_seconds()


def classify(title):
    # Match the specific bag category before the generic diaper keyword.
    if any(term in title for term in ('기저귀가방', '모아백')):
        return '외출·안전'
    matches = [category for category, terms in CATEGORY_TERMS.items()
               if any(term in title for term in terms)]
    return matches[0] if len(matches) == 1 else None


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.urls.append(href)


def product_links(html, base):
    parser = Links()
    parser.feed(html)
    products = set()
    for href in parser.urls:
        url = urljoin(base, unescape(href))
        try:
            collector.validate_url(url)
        except ValueError:
            continue
        parsed = urlsplit(url)
        if parsed.hostname != urlsplit(base).hostname:
            continue
        number = parse_qs(parsed.query).get('product_no', [''])[0]
        if not number:
            match = re.match(r'^/product/[^/]+/(\d+)(?:/|$)', parsed.path)
            number = match.group(1) if match else ''
        if number.isdigit():
            products.add('https://' + parsed.hostname + '/product/detail.html?' + urlencode({'product_no': number}))
    return sorted(products)


def collect(db=None):
    """Bounded discovery, plus recheck every already published source."""
    sources = {item['url']: dict(item) for item in collector.SOURCES}
    if db is not None:
        rows = db.scalars(select(Record).where(Record.kind == 'release_groupbuy',
                                             Record.data['source_type'].as_string() == 'seller_page'))
        for row in rows:
            data = row.data
            if row.status == 'hidden':
                continue
            sources.setdefault(data['source_url'], {
                'id': data['source_id'], 'url': data['source_url'],
                'seller': data['seller_name'], 'category': data['category']})
    failures, entries, rejected, removed = [], [], [], []
    sellers = {urlsplit(item['url']).hostname: item for item in collector.SOURCES}
    for host, seller in sellers.items():
        origin = 'https://' + host + '/'
        try:
            # The storefront and its product links stay within reviewed hosts.
            links = product_links(collector.read_html(origin), origin)
            for url in links[:100]:
                number = parse_qs(urlsplit(url).query)['product_no'][0]
                sources.setdefault(url, {'id': host + '-' + number, 'url': url,
                                         'seller': seller['seller'], 'category': ''})
        except (OSError, ValueError) as error:
            failures.append({'source_id': host, 'stage': 'discovery', 'error': type(error).__name__})
    for source in sources.values():
        try:
            entry = collector.fetch(source)
            category = classify(entry['title'])
            if not category:
                rejected.append({'source_id': source['id'], 'reason': 'category_unconfirmed'})
                continue
            entry['category'] = category
            entries.append(entry)
        except HTTPError as error:
            if error.code in (404, 410):
                removed.append(source['id'])
            else:
                failures.append({'source_id': source['id'], 'stage': 'fetch', 'error': 'HTTPError', 'status': error.code})
        except ValueError:
            rejected.append({'source_id': source['id'], 'reason': 'groupbuy_fields_unconfirmed'})
        except OSError as error:
            failures.append({'source_id': source['id'], 'stage': 'fetch', 'error': type(error).__name__})
    return {'entries': entries, 'failures': failures, 'rejected': rejected, 'removed': removed,
            'candidate_count': len(sources), 'checked_at': collector.release.timestamp(now())}


def expire(db, removed=()):
    """Keep history, but end stale public seller listings even when fetching failed."""
    rows = db.scalars(select(Record).where(Record.kind == 'release_groupbuy',
        Record.data['source_type'].as_string() == 'seller_page',
        Record.status == 'active', (Record.ends <= now()) |
        Record.unique_key.in_(['external:' + source_id for source_id in removed])))
    count = 0
    for row in rows:
        row.status = 'ended'
        row.revision += 1
        count += 1
    return count
