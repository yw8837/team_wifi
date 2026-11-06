"""Guest legal access, working document navigation and honest deletion guidance."""
from html.parser import HTMLParser
import pytest
from app import config
import os
from pathlib import Path
import subprocess
import sys


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids, self.anchors, self.tags = [], [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.anchors.append(attrs.get('href', ''))


@pytest.mark.parametrize('kind', ['privacy', 'terms', 'deletion', 'support'])
def test_guest_policy_navigation_and_security(setup, monkeypatch, kind):
    client, _, _ = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    result = client.get('/legal/' + kind)
    assert result.status_code == 200
    assert "default-src 'none'" in result.headers['Content-Security-Policy']
    assert "frame-ancestors 'none'" in result.headers['Content-Security-Policy']
    doc = Document(result.text)
    assert len(doc.ids) == len(set(doc.ids))
    assert all(href[1:] in doc.ids for href in doc.anchors if href.startswith('#'))
    assert '/my' in doc.anchors and '/legal/deletion' in doc.anchors
    assert doc.tags.count('h1') == 1
    assert 'script' not in doc.tags
    assert '비공개 베타' not in result.text


def test_deletion_guidance_matches_real_controls_and_retention(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    html = client.get('/legal/deletion').text
    for label in ['계정 삭제 진행', '현재 비밀번호', '계정 영구 삭제', '저장 해제',
                  '신고·차단·삭제', '내 글 삭제', '내 댓글 삭제', '관심 취소', '차단 해제']:
        assert label in html
    assert '앱 삭제와 계정 삭제는 다릅니다' in html
    assert '임의 계정 ID와 탈퇴 상태' in html
    assert '다른 회원의 댓글' in html
    assert '/login?returnTo=%2Fsettings' in html and '/reset' in html
    deleted = html.split('3. 삭제되는 정보와 남는 기록</h2>', 1)[1].split('<h2>', 1)[0]
    assert '본인 공구 정보·커뮤니티 글·댓글' in deleted and '저장 대화' in deleted



def test_privacy_discloses_groupbuy_measurement_without_external_browsing(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    response = client.get('/legal/privacy')
    assert response.status_code == 200
    measurement = response.text.split('<dt>선택 동의한 활동 분석</dt>', 1)[1].split('</dd>', 1)[0]
    assert '공구·육아템·수요 글 ID' in measurement
    assert '클릭 종류(판매처 이동 포함)' in measurement
    assert '외부 사이트에서의 방문·열람 내역은 분석 항목에 넣지 않습니다' in measurement
    assert '별도 선택한 일반 회원만' in measurement
    assert '최근 30일' in measurement and '동의를 끄면 본인 분석 기록을 즉시 삭제' in measurement


def test_privacy_escapes_runtime_disclosures(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    monkeypatch.setattr(config, 'HOSTING_LOCATION', '<script>server</script>')
    monkeypatch.setattr(config, 'DATABASE_LOCATION', 'DB & location')
    monkeypatch.setattr(config, 'SUPPORT_EMAIL', 'help+"<>@example.org')
    html = client.get('/legal/privacy').text
    assert '<script>' not in html
    assert '&lt;script&gt;server&lt;/script&gt;' in html
    assert 'DB &amp; location' in html
    assert 'help+&quot;&lt;&gt;@example.org' in html
    assert 'HMAC' in html and '10분' in html and '90일' in html and '30일' in html
    assert '8시간' not in html


def test_unknown_legal_document_remains_404(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(config, 'PUBLIC_RELEASE', True)
    assert client.get('/legal/not-a-document').status_code == 404


@pytest.mark.parametrize('origin,valid', [
    ('https://moduyuga.onrender.com', True),
    ('https://moduyuga.onrender.com.evil.invalid/path', False),
    ('http://moduyuga.onrender.com', False),
    ('https://name:secret@example.org', False),
    ('*', False),
])
def test_separate_web_origin_requires_one_https_origin(origin, valid):
    env = dict(os.environ, MODU_ENV='local', PUBLIC_WEB_ORIGIN=origin)
    result = subprocess.run([sys.executable, '-c', 'from app.config import ORIGINS; print(ORIGINS)'],
                            env=env, capture_output=True, text=True, timeout=30)
    assert (result.returncode == 0) == valid
    if valid:
        assert origin in result.stdout and '*' not in result.stdout


def test_static_policies_use_same_source_and_no_database(tmp_path):
    root = Path(__file__).resolve().parents[2]
    # CI temp directories may be external: choose a dedicated ignored project path.
    import tempfile
    with tempfile.TemporaryDirectory(dir=root / '.runtime' if (root / '.runtime').exists() else root, prefix='.policy-export-') as work:
        env = dict(os.environ, MODU_ENV='local', SUPPORT_EMAIL='support@example.org',
                   HOSTING_LOCATION='Render · Singapore', DATABASE_LOCATION='Neon · Singapore',
                   DATABASE_URL='invalid-and-must-never-be-used')
        result = subprocess.run([sys.executable, str(root/'scripts/export-public-policies.py'), '--output-dir', work],
                                env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        for kind in ['privacy', 'terms', 'support', 'deletion']:
            html = (Path(work)/'legal'/kind/'index.html').read_text(encoding='utf-8')
            assert 'Content-Security-Policy' in html and 'support@example.org' in html
            assert 'script' not in Document(html).tags
