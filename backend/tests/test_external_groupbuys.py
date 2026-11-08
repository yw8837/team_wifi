import pytest
from sqlalchemy import select

from app import assistant_tools, community_demo, external_groupbuys, groupbuys
from app.db import Record, SessionLocal, now
from test_public_release import public_mode


def seller_html(soldout='F'):
    return """var product_name = '캔코 모아백 기저귀가방 공동구매';
    var product_price = '129000'; var product_sale_price = 109000;
    var is_soldout_icon = '%s'; var sIsNonmemberLimit = 'T';""" % soldout


def test_seller_parser_requires_verified_fields_and_rejects_redirects():
    entry = external_groupbuys.parse_cafe24(seller_html(), external_groupbuys.SOURCES[0])
    assert entry['price'] == 109000
    assert entry['expires_at'] == '' and entry['shipping_fee'] is None
    assert entry['availability'] == 'listed' and entry['is_demo'] is False
    assert entry['order_minimum'] is None and entry['order_step'] is None
    quantities = external_groupbuys.parse_cafe24(seller_html() + "var product_min = '1'; var buy_unit = '1';", external_groupbuys.SOURCES[0])
    assert quantities['order_minimum'] == quantities['order_step'] == 1
    assert quantities['minimum_quantity'] is None
    html = seller_html() + '''<select option_product_no="222"><option value="P00000IO000A">블랙</option></select>
        <select option_product_no="111"><option value="P00000AA000A">추가 상품</option></select>
        <select><option value="PA">SHIPPING TO : 파나마</option></select>'''
    assert external_groupbuys.parse_cafe24(html, external_groupbuys.SOURCES[0])['option_labels'] == ['블랙']
    assert '회원가입' in entry['price_conditions']
    assert external_groupbuys.parse_cafe24(seller_html('T'), external_groupbuys.SOURCES[0])['availability'] == 'sold_out'
    with pytest.raises(ValueError):
        external_groupbuys.parse_cafe24('<html>차단</html>', external_groupbuys.SOURCES[0])
    with pytest.raises(ValueError):
        external_groupbuys.parse_cafe24(seller_html() + 'var product_sale_price = 200;', external_groupbuys.SOURCES[0])
    for url in ('http://somi9726.cafe24.com/', 'https://127.0.0.1/', 'https://evil.example/'):
        with pytest.raises(ValueError):
            external_groupbuys.validate_url(url)


def test_fetch_comparison_matches_campaign_title_and_drops_failed_reference(monkeypatch):
    source = external_groupbuys.SOURCES[0]
    def page(request, *, groupbuy=True):
        html = seller_html().replace('캔코 모아백 기저귀가방 공동구매', '[애프리x캔코] 모아백 기저귀가방 공동구매')
        if not groupbuy:
            html = seller_html().replace(' 공동구매', '').replace('var product_sale_price = 109000;', '')
        html += '<tr><th>배송비</th><td>무료</td></tr>'
        return external_groupbuys.parse_cafe24(html, request, groupbuy=groupbuy)
    monkeypatch.setattr(external_groupbuys, 'fetch_page', page)
    entry = external_groupbuys.fetch(source)
    assert entry['shipping_fee'] == 0 and entry['comparison_quantity'] == 1
    assert entry['price_references'][0]['price'] == 129000
    assert entry['price_references'][0]['shipping_fee'] == 0
    def fail_reference(request, *, groupbuy=True):
        if not groupbuy:
            raise ValueError('Unknown seller page')
        return page(request)
    monkeypatch.setattr(external_groupbuys, 'fetch_page', fail_reference)
    assert external_groupbuys.fetch(source)['price_references'] == []


def test_import_updates_one_record_and_chat_excludes_demo_and_stale(public_mode):
    client, _, _ = public_mode
    entry = external_groupbuys.parse_cafe24(seller_html(), external_groupbuys.SOURCES[0])
    with SessionLocal.begin() as db:
        community_demo.seed(db)
        external_groupbuys.store(db, [entry])
        external_groupbuys.store(db, [entry])
        rows = list(db.scalars(select(Record).where(Record.unique_key == 'external:canco-222')))
        assert len(rows) == 1
        row = rows[0]
        identifier = row.id
        result = assistant_tools.live_read(db, None, '기저귀가방 공구')
        links = [action for action in result['actions'] if action['url'].startswith('/groupbuys/')]
        assert links == [{'label': entry['title'], 'url': '/groupbuys/' + identifier, 'kind': 'item'}]
        assert any('마감 미확인' in note and '109000' in note for note in result['notes'])
        assert result['verified_offer'] is True
    response = client.get('/api/release/groupbuys/' + identifier + '/public')
    assert response.status_code == 200 and '판매처 게시 확인' in response.text
    assert 'href="' + entry['seller_url'] + '"' in response.text
    answer = client.post('/api/release/assistant/ask', json={'question': '기저귀가방 공구 가격 얼마야?', 'remember': False})
    assert answer.status_code == 200
    assert answer.json()['generation']['reason'] is None
    assert '109000' in answer.json()['answer']
    assert '확인된 자료를 찾지 못했어요' not in answer.json()['answer']
    with SessionLocal.begin() as db:
        row = db.get(Record, identifier)
        row.ends = now() - 1
        db.flush()
        assert not any(action['url'] == '/groupbuys/' + identifier
                       for action in assistant_tools.live_read(db, None, '기저귀가방 공구')['actions'])
        row.status = 'hidden'
        external_groupbuys.store(db, [entry])
        assert row.status == 'hidden'
        external_groupbuys.retire_demo_listings(db)
        demo = db.get(Record, community_demo.identifier('groupbuy/0'))
        assert demo.status == 'hidden' and '가상' not in demo.data['title']
