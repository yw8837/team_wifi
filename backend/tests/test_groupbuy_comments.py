from sqlalchemy import select

from app.db import Record, SessionLocal
from test_groupbuys import BASE, create, domain_quota
from test_public_release import public_mode


def test_comments_lifecycle_activity_report_and_parent_deletion(public_mode, domain_quota):
    client, people, _ = public_mode
    item = create(client, people)
    path = BASE + '/' + item['id']
    author = people['buyer2']['headers']
    assert client.post(path + '/comments', json={'body': '사용 경험 궁금해요'}).status_code == 401
    response = client.post(path + '/comments', headers=author, json={'body': '사용 경험 궁금해요'})
    assert response.status_code == 201, response.text
    comment = response.json()
    comment_path = '/api/release/comments/' + comment['id']
    assert client.get(path + '/comments').json()[0]['body'] == '사용 경험 궁금해요'
    assert client.put(comment_path, headers=people['buyer']['headers'], json={'body': '다른 사람 수정', 'revision': 1}).status_code == 404
    assert client.put(comment_path, headers=author, json={'body': '세척 방법도 궁금해요', 'revision': 1}).status_code == 200
    assert client.put(comment_path, headers=author, json={'body': '지난 화면 수정', 'revision': 1}).status_code == 409
    activity = client.get('/api/release/activity?tab=comments', headers=author).json()['items']
    assert activity[0]['parent_kind'] == 'groupbuy' and activity[0]['post_id'] == item['id']
    report = client.post('/api/release/reports', headers=people['buyer']['headers'], json={
        'target_type': 'comment', 'target_id': comment['id'], 'reason': '댓글 내용 확인 요청입니다'})
    assert report.status_code == 201
    with SessionLocal() as db:
        from app.release import report_dto
        data = report_dto(db, db.get(Record, report.json()['id']))
        assert data['groupbuy_id'] == item['id'] and data['demand_id'] is None
    response = client.request('DELETE', path, headers=people['buyer']['headers'], json={'revision': 1})
    assert response.status_code == 200, response.text
    assert client.get(path + '/comments').status_code == 404
    assert client.get('/api/release/activity?tab=comments', headers=author).json()['items'] == []
    with SessionLocal() as db:
        assert db.get(Record, comment['id']) is None
        assert db.get(Record, report.json()['id']) is None


def test_comments_respect_hidden_ended_and_blocked_parents(public_mode, domain_quota):
    client, people, _ = public_mode
    item = create(client, people)
    path = BASE + '/' + item['id']
    author = people['buyer2']['headers']
    client.post(path + '/end', headers=people['buyer']['headers'], json={'revision': 1})
    response = client.post(path + '/comments', headers=author, json={'body': '종료 후 사용 경험'})
    assert response.status_code == 201
    comment = response.json()
    with SessionLocal.begin() as db:
        db.add(Record(kind='block', owner_id=people['buyer']['id'], parent_id=people['buyer2']['id']))
    assert client.post(path + '/comments', headers=author, json={'body': '차단된 사용자 댓글'}).status_code == 403
    assert client.get(path + '/comments', headers=people['buyer']['headers']).json() == []
    with SessionLocal.begin() as db:
        db.get(Record, item['id']).status = 'hidden'
    assert client.get(path + '/comments').status_code == 404
    assert client.put('/api/release/comments/' + comment['id'], headers=author,
                      json={'body': '숨겨진 공구의 수정', 'revision': 1}).status_code == 404
    assert client.get('/api/release/activity?tab=comments', headers=author).json()['items'] == []
    assert client.delete('/api/release/comments/' + comment['id'], headers=author).status_code == 200
