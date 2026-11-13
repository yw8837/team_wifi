"""Integrated requirements: group-buy sharing, demand ranking and pagination."""
import pytest
from sqlalchemy import select

from app import groupbuys, release
from app.db import Record, SessionLocal, User, now
from test_groupbuys import BASE, create, payload
from test_public_release import public_mode, post_demand


@pytest.fixture(autouse=True)
def no_quota(monkeypatch):
    monkeypatch.setattr(groupbuys, 'throttle', lambda *a, **k: None)
    monkeypatch.setattr(release, 'throttle', lambda *a, **k: None)


def test_groupbuy_optional_minimum_quantity_validation(public_mode):
    c, p, _ = public_mode
    item = create(c, p, minimum_quantity=5)
    assert c.get(BASE+'/'+item['id']).json()['minimum_quantity'] == 5
    assert create(c, p)['minimum_quantity'] is None
    for invalid in [0, -1, True, 1.5, '5']:
        assert c.post(BASE, headers=p['buyer']['headers'], json=payload(minimum_quantity=invalid)).status_code == 422


def test_default_twenty_and_stable_groupbuy_sort(public_mode):
    c, p, _ = public_mode
    data = payload()
    with SessionLocal() as db:
        rows = []
        for index in range(21):
            row = Record(kind=groupbuys.GROUPBUY, owner_id=p['buyer']['id'],
                         ends=now()+100+index, created=now()-index, data=data)
            db.add(row); db.flush(); rows.append(row.id)
        expired = Record(kind=groupbuys.GROUPBUY, owner_id=p['buyer']['id'], ends=now()-1, data=data)
        db.add(expired); db.commit()
    first = c.get(BASE).json()
    assert len(first['items']) == 20 and first['has_more']
    assert [row['id'] for row in first['items']] == rows[:20]
    assert [row['id'] for row in c.get(BASE, params={'offset':20}).json()['items']] == rows[20:]
    assert [row['id'] for row in c.get(BASE, params={'sort':'recent'}).json()['items']] == rows[:20]
    assert len(c.get(BASE+'/mine', headers=p['buyer']['headers']).json()['items']) == 20
    assert c.get(BASE, params={'sort':'unknown'}).status_code == 422


def test_popular_demands_rank_available_unique_interests_before_paging(public_mode):
    c, p, _ = public_mode
    posts = [post_demand(c, p['buyer']['headers'], title=f'인기 수요 정렬 {i}') for i in range(3)]
    for who in ['buyer2', 'seller']:
        assert c.put('/api/release/demands/'+posts[0]['id']+'/interest', headers=p[who]['headers']).status_code == 200
    for _ in range(2):
        c.put('/api/release/demands/'+posts[1]['id']+'/interest', headers=p['buyer2']['headers'])
    with SessionLocal() as db:
        for index, post in enumerate(posts):
            db.get(Record, post['id']).created = now()+index
        db.commit()
    path = '/api/release/demands'
    params = {'sort':'popular','post_type':'demand','limit':1}
    assert c.get(path, params=params).json()[0]['id'] == posts[0]['id']
    second = c.get(path, params={**params,'offset':1}).json()[0]
    assert second['id'] == posts[1]['id'] and second['interest_count'] == 1
    with SessionLocal() as db:
        db.get(User, p['seller']['id']).deleted = True
        db.commit()
    # Counts tie after erasure: the newer demand wins, matching its DTO count.
    first = c.get(path, params=params).json()[0]
    assert first['id'] == posts[1]['id'] and first['interest_count'] == 1
    assert c.get(path, params={'sort':'unknown'}).status_code == 422


def test_demands_and_comments_default_twenty_and_cascade(public_mode):
    c, p, _ = public_mode
    post = post_demand(c, p['buyer']['headers'])
    with SessionLocal() as db:
        for index in range(21):
            db.add(Record(kind=release.DEMAND, owner_id=p['buyer']['id'], data={
                'title':f'추가 수요 글 {index}', 'body':'충분한 내용의 수요 글입니다.', 'category':'육아생활'}))
            db.add(Record(kind=release.COMMENT, owner_id=p['buyer2']['id'], parent_id=post['id'], data={'body':f'댓글 내용 {index}'}))
        db.commit()
    assert len(c.get('/api/release/demands').json()) == 20
    comments = '/api/release/demands/'+post['id']+'/comments'
    assert len(c.get(comments).json()) == 20 and len(c.get(comments, params={'offset':20}).json()) == 1
    assert c.get('/api/release/demands/'+post['id']).json()['comment_count'] == 21
    c.put('/api/release/demands/'+post['id']+'/interest', headers=p['buyer2']['headers'])
    assert c.delete('/api/release/demands/'+post['id'], headers=p['buyer']['headers']).status_code == 200
    with SessionLocal() as db:
        assert not list(db.scalars(select(Record).where(Record.kind.in_([release.COMMENT, release.INTEREST]), Record.parent_id == post['id'])))


def test_any_member_links_visible_groupbuy_and_delete_clears_link(public_mode):
    c, p, _ = public_mode
    item = create(c, p)
    post = post_demand(c, p['buyer']['headers'])
    path = '/api/release/demands/'+post['id']
    linked = c.put(path+'/groupbuy', headers=p['buyer2']['headers'], json={'revision':1,'groupbuy_id':item['id']})
    assert linked.status_code == 200 and linked.json()['linked_groupbuy']['id'] == item['id']
    assert c.get('/api/release/demands').json()[0]['linked_groupbuy']['id'] == item['id']
    assert c.put(path+'/groupbuy', headers=p['buyer2']['headers'], json={'revision':2,'groupbuy_id':item['id']}).status_code == 409
    alternative = create(c, p, title='다른 관련 공구 정보')
    assert c.put(path+'/groupbuy', headers=p['buyer2']['headers'], json={'revision':2,'groupbuy_id':alternative['id']}).status_code == 409
    assert c.get(path).json()['revision'] == 2
    assert c.post(path+'/unlink-groupbuy', headers=p['buyer2']['headers'], json={'revision':2}).status_code == 404
    url = BASE+'/'+item['id']
    assert c.request('DELETE', url, headers=p['buyer2']['headers'], json={'revision':1}).status_code == 404
    assert c.request('DELETE', url, headers=p['buyer']['headers'], json={'revision':9}).status_code == 409
    assert c.request('DELETE', url, headers=p['buyer']['headers'], json={'revision':1}).status_code == 200
    assert c.get(url).status_code == 404
    cleared = c.get(path).json()
    assert cleared['linked_groupbuy'] is None and cleared['revision'] == 3


def test_information_report_immediately_flags_notifies_and_deduplicates(public_mode):
    c, p, _ = public_mode
    item = create(c, p)
    endpoint = BASE+'/'+item['id']+'/reports'
    first = c.post(endpoint, headers=p['buyer2']['headers'], json={'reason':'PRIVATE 제보 사유입니다.'})
    assert first.status_code == 201
    duplicate = c.post(endpoint, headers=p['buyer2']['headers'], json={'reason':'반복 제보 사유입니다.'})
    assert duplicate.json()['id'] == first.json()['id']
    public = c.get(BASE+'/'+item['id']).json()
    assert public['review_state'] == 'needs_review' and public['revision'] == 2
    notices = c.get('/api/release/notices', headers=p['buyer']['headers']).json()['items']
    assert len(notices) == 1 and notices[0]['target_id'] == item['id']
    assert 'PRIVATE' not in str(notices) and p['buyer2']['id'] not in str(notices)
    assert c.get('/api/release/notices', headers=p['buyer2']['headers']).json()['items'] == []
    queue = c.get('/api/release/admin/groupbuys/reports', headers=p['admin']['headers']).json()['items']
    assert queue[0]['id'] == first.json()['id']


def test_public_groupbuy_page_displays_shared_terms_and_updated_time(public_mode):
    c, p, _ = public_mode
    item = create(c, p, minimum_quantity=5)
    changed = c.put(BASE+'/'+item['id'], headers=p['buyer']['headers'], json={**payload(minimum_quantity=7),'revision':1})
    assert changed.status_code == 200
    page = c.get(BASE+'/'+item['id']+'/public')
    assert page.status_code == 200
    assert '<dt>최소 수량</dt><dd>7</dd>' in page.text
    assert '<dt>공유자</dt><dd>buyer</dd>' in page.text
    assert '<dt>수정 시각</dt><dd>' in page.text and '한국 시간' in page.text
    assert 'target="_blank" rel="nofollow ugc noreferrer noopener"' in page.text


def test_groupbuy_delete_erases_linked_audit_quotes_and_preserves_unrelated(public_mode):
    c, p, _ = public_mode
    item = create(c, p)
    report = c.post(BASE+'/'+item['id']+'/reports', headers=p['buyer2']['headers'],
                    json={'reason':'PRIVATE 신고 인용 사유입니다.'}).json()['id']
    with SessionLocal() as db:
        audits = [
            Record(kind='audit', owner_id=p['admin']['id'], parent_id=report, data={'reason':'PRIVATE 운영 사유'}),
            Record(kind='audit', owner_id=p['admin']['id'], parent_id=item['id'], data={'reason':'PRIVATE 과거 사유'}),
            Record(kind='audit', owner_id=p['admin']['id'], data={'target_id':item['id'],'reason':'PRIVATE 대상 사유'}),
            Record(kind='audit', owner_id=p['admin']['id'], data={'report_id':report,'reason':'PRIVATE 신고 사유'}),
        ]
        unrelated = Record(kind='audit', owner_id=p['admin']['id'], parent_id='unrelated-target',
                           data={'target_id':'unrelated-target','reason':'유지할 운영 이력'})
        db.add_all([*audits, unrelated]); db.commit()
        audit_ids = [row.id for row in audits]
        retained_id = unrelated.id
    response = c.request('DELETE', BASE+'/'+item['id'], headers=p['buyer']['headers'], json={'revision':2})
    assert response.status_code == 200
    with SessionLocal() as db:
        assert all(db.get(Record, identifier) is None for identifier in audit_ids)
        assert db.get(Record, report) is None
        assert db.get(Record, retained_id).data['reason'] == '유지할 운영 이력'
