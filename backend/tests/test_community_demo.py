import json
from sqlalchemy import func, select

from app import community_demo, release
from app.db import Record, SessionLocal
from test_public_release import public_mode


def test_demo_seed_is_atomic_idempotent_and_separate_from_real_insights(public_mode):
    manifest = json.loads(release.CATALOG_PATH.read_text(encoding='utf-8'))
    manifest['entries'].append({**manifest['entries'][0], 'id': 'official-source-2'})
    release.CATALOG_PATH.write_text(json.dumps(manifest), encoding='utf-8')
    with SessionLocal.begin() as db:
        before = release.service_insights(user=None, db=db)
        receipt = community_demo.seed(db)
        assert receipt['created']['users'] == 8
        assert receipt['scenario']['groupbuys'] == 8
    with SessionLocal.begin() as db:
        second = community_demo.seed(db)
        assert second['created'] == {'users': 0, 'records': 0}
        actual = release.service_insights(user=None, db=db)
        assert actual['saved_accounts'] == before['saved_accounts']
        assert actual['categories'] == before['categories']
        demo = release.service_insights(dataset='demo', user=None, db=db)
        assert demo['dataset'] == 'demo' and demo['pairs']
        assert all(pair['accounts'] == 6 for pair in demo['pairs'])
        assert db.scalar(select(func.count()).select_from(Record).where(Record.kind == 'demo_actor')) == 8


def test_demo_public_detail_labels_fiction_and_has_no_seller_link(public_mode):
    client, _, _ = public_mode
    with SessionLocal.begin() as db:
        community_demo.seed(db)
    identifier = community_demo.identifier('groupbuy/0')
    response = client.get('/api/release/groupbuys/' + identifier)
    assert response.status_code == 200
    assert response.json()['is_demo'] is True
    assert response.json()['title'].startswith('[가상]')
    page = client.get('/api/release/groupbuys/' + identifier + '/public')
    assert page.status_code == 200
    assert page.headers['x-robots-tag'] == 'noindex, nofollow'
    assert 'href="https://example.com"' not in page.text
    assert '가상 시연 데이터' in page.text
    sitemap = client.get('/api/release/groupbuy-pages/sitemap.xml')
    assert '<sitemap>' not in sitemap.text
