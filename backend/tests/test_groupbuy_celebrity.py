from datetime import datetime

import pytest
from app import external_groupbuys as collector, groupbuy_celebrity as seller, groupbuy_discovery as discovery


URL = 'https://minkang1.celebrity.place/m/goods/content.asp?gc=1663&guid=783059'


def test_shared_catalog_uses_only_matching_seller_and_both_ids():
    links = ('<a href="' + URL.replace('gc=1663&guid=783059', 'guid=783059&amp;gc=1663') + '">포트</a>'
             '<a href="' + URL + '&amp;gc=120">중복 키</a><a href="' + URL.replace('minkang1', 'other') + '">다른 판매처</a>')
    assert discovery.product_links(links, collector.KIDS_CATALOG, 'minkang1.celebrity.place') == [URL]


def test_orderable_single_item_and_campaign_boundaries(monkeypatch):
    fields = dict(gc='1663', guid='783059', title='코지엘 이유식포트', price='84800', stock='2', IsStock='T',
                  gongguCountdownStart='2026-11-19 00:00:00', gongguCountdownEnd='2026-11-26 23:59:00',
                  gongguStateEnded='0', nChkOpt_useFlag='F', nChkMultiOpt_useFlag='F', nChkTextOpt_useFlag='F')
    def parse(**change):
        html = ''.join(f'<input type="hidden" id="{k}" value="{v}">' for k,v in (fields | change).items())
        return seller.parse(html + '<a class="inbuy" onclick="buyboxcheck()">구매하기</a>',
                            {'id': 'item', 'url': URL, 'seller': '셀러브리티'})
    end = int(datetime.fromisoformat('2026-11-26T23:59:00+09:00').timestamp())
    monkeypatch.setattr(seller, 'now', lambda: end - 1)
    assert (parse()['availability'], parse()['price'], parse()['source_fresh_until']) == ('listed', 84800, end)
    assert parse(stock='0')['availability'] == 'sold_out'
    with pytest.raises(ValueError):
        parse(nChkOpt_useFlag='T')
    with pytest.raises(collector.NotGroupbuy):
        parse(gc='42')
    monkeypatch.setattr(seller, 'now', lambda: end)
    assert parse()['availability'] == 'ended'
