from datetime import datetime

import pytest

from app import groupbuy_discovery, groupbuy_sharequeens as store
from app.external_groupbuys import NotGroupbuy


def card(number='916', title='유모차', dates='2026.12.30 ~ 2027.01.01'):
    return (f'<div class="pl-card" data-product-id="{number}"><p class="pl-card-name">{title}</p>'
            f'<p class="pl-card-date">{dates}</p></div>')


def sources(monkeypatch, html):
    stamp = datetime.fromisoformat('2026-12-31T18:00:00+09:00').timestamp()
    monkeypatch.setattr(store, 'now', lambda: stamp)
    return list(store.campaign_sources(html, '현브로마켓', groupbuy_discovery.classify))


def test_discovers_only_current_parenting_products(monkeypatch):
    html = (card() + card('850') + card('102', '보리 소고기') + card('103', dates='2025.12.30 ~ 2026.01.01')
            + card('104', dates='2027.01.01 ~ 2027.01.02'))
    [item] = sources(monkeypatch, html)
    assert item['url'] == store.STORE + '/product/916'
    assert item['category'] == '외출·안전'


def test_confirm_identity_order_controls_period_and_price(monkeypatch):
    [source] = sources(monkeypatch, card())
    option = ('<button class="pd-option-choice" onclick="selectPurchaseOption(this)" '
              'data-option-name="기본형" data-option-price="298000"></button>')
    html = (f'<meta property="og:url" content="{source["url"]}?market_ref=opaque">'
            '<meta property="og:title" content="유모차"><span class="pd-price-label-main">공구가</span>'
            '<span class="pd-sale-price">298,000원</span><span class="pd-period-value">12월 30일 ~ 1월 1일</span>'
            '<button class="pd-btn-buy" onclick="pdBuyBtnClick()"></button>' + option)
    entry = store.parse(html + option.replace('기본형', '블루').replace('<button ', '<button disabled '), source)
    assert entry['option_labels'] == ['기본형 · 298,000원']
    assert entry['availability'] == 'listed'
    assert entry['source_fresh_until'] <= datetime.fromisoformat('2027-01-02T00:00:00+09:00').timestamp()
    with pytest.raises(NotGroupbuy):
        store.parse(html.replace('class="pd-btn-buy"', 'disabled class="pd-btn-buy"'), source)
    with pytest.raises(NotGroupbuy):
        store.parse(html.replace('공구가', '판매가'), source)
    with pytest.raises(ValueError):
        store.parse(html.replace('298,000원', '1,000원'), source)
    with pytest.raises(ValueError):
        store.parse(html.replace('1월 1일', '1월 3일'), source)
    with pytest.raises(NotGroupbuy):
        store.parse(html.replace('/916?', '/917?'), source)
