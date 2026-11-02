from pathlib import Path
import runpy
import json
import re
import xml.etree.ElementTree as ET


def test_exported_guides_are_readable_without_js_and_truthful_schema(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/export-public-guides.py'))
    paths = module['export'](tmp_path)
    assert len(paths) == 4
    sitemap = ET.fromstring((tmp_path/'sitemap.xml').read_text('utf-8'))
    urls = [node.text for node in sitemap.iter() if node.tag.endswith('loc')]
    assert len(urls) == 4 and all('/guides' in url for url in urls)
    assert all('/my' not in url and '/auth' not in url for url in urls)
    for path in paths[1:]:
        html = (tmp_path/path.lstrip('/')).read_text('utf-8')
        assert '<h1>' in html and '<p class="answer">' in html and '<link rel="canonical"' in html
        assert 'type="module"' not in html and '<script src=' not in html
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html).group(1))
        assert schema['@type'] == 'Article' and schema['headline'] in html
        assert 'aggregateRating' not in schema and 'offers' not in schema
    robots = (tmp_path/'robots.txt').read_text('utf-8')
    assert 'Disallow: /auth/' in robots and 'Disallow: /my' in robots
