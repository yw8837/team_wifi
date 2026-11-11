from datetime import datetime

from sqlalchemy import select

from app import external_groupbuys as collector, groupbuy_discovery as discovery
from app.db import Record, SessionLocal, now
from test_external_groupbuys import seller_html
from test_public_release import public_mode


def test_midnight_uses_korean_calendar():
    stamp = datetime.fromisoformat('2026-11-11T14:59:50+00:00').timestamp()
    assert discovery.seconds_until_midnight(stamp) == 10
    assert discovery.seconds_until_midnight(stamp + 10) == 86400


def test_discovery_deduplicates_urls_and_classifies():
    base = 'https://somi9726.cafe24.com/'
    html = '''<a href="/product/detail.html?product_no=333&amp;tracking=x">공구</a>
    <a href="/product/name/333/">다시</a><a href="https://evil.example/?product_no=1">외부</a>'''
    assert discovery.product_links(html, base) == [base + 'product/detail.html?product_no=333']
    assert discovery.classify('기저귀가방 공동구매') == '외출·안전'
    assert discovery.classify('물티슈 공구') == '기저귀·물티슈'
    assert discovery.classify('분유와 장난감 공구') is None
    assert discovery.classify('컴퓨터 공구') is None


def test_collect_discovers_new_campaign_and_rejects_regular_sale(monkeypatch):
    monkeypatch.setattr(collector, 'read_html', lambda url: '<a href="/product/detail.html?product_no=333">new</a>')
    def fetch(source):
        title = '아기 물티슈 공동구매' if source['id'].endswith('333') else '기저귀가방 공동구매'
        return collector.parse_cafe24(seller_html().replace('캔코 모아백 기저귀가방 공동구매', title), source)
    monkeypatch.setattr(collector, 'fetch', fetch)
    result = discovery.collect()
    assert len(result['entries']) == 2
    assert {row['category'] for row in result['entries']} == {'기저귀·물티슈', '외출·안전'}


def test_expiry_soldout_hidden_and_public_exclusion(public_mode):
    client, _, _ = public_mode
    source = collector.SOURCES[0]
    entry = collector.parse_cafe24(seller_html(), source)
    with SessionLocal.begin() as db:
        collector.store(db, [entry])
        row = db.scalar(select(Record).where(Record.unique_key == 'external:canco-222'))
        row.ends = now() - 1
        db.flush()
        assert discovery.expire(db) == 1
        assert row.status == 'ended'
    for status in ('all', 'active', 'ended'):
        assert client.get('/api/release/groupbuys', params={'status': status}).json()['items'] == []
    ended = collector.parse_cafe24(seller_html().replace('공동구매', '공동구매 종료'), source)
    assert ended['availability'] == 'ended'
    dated = collector.parse_cafe24(seller_html().replace('공동구매', '공동구매 마감: 2020-01-01 00:00'), source)
    assert dated['availability'] == 'ended'
    with SessionLocal.begin() as db:
        collector.store(db, [dated])
        row = db.scalar(select(Record).where(Record.unique_key == 'external:canco-222'))
        assert row.status == 'ended'
        row.status = 'hidden'
        collector.store(db, [entry])
        assert row.status == 'hidden'
