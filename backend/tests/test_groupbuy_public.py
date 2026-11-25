import json
import re
from html.parser import HTMLParser
from xml.etree import ElementTree
from app import groupbuy_public
from app.db import Record,SessionLocal,now
from test_groupbuys import BASE,create,domain_quota
from test_public_release import public_mode


def test_jsonld_is_data_and_never_interprets_member_html(public_mode):
    c,p,_=public_mode
    attack='문자열 </script><script>alert(1)</script> & <img src=x onerror=alert(1)>'
    item=create(c,p,title='공구 </script> 확인',body=attack)
    response=c.get(BASE+'/'+item['id']+'/public')
    assert response.status_code==200
    script=re.findall(r'<script type="application/ld\+json">(.*?)</script>',response.text)
    assert len(script)==1 and response.text.count('<script')==1
    data=json.loads(script[0])
    assert data['text']==attack and data['@type']=='DiscussionForumPosting'
    assert data['url']=='https://moduyuga.onrender.com/groupbuys/'+item['id']+'/public'
    assert 'offers' not in data and 'price' not in data
    assert '&lt;img' in response.text and '<img src=' not in response.text
    assert 'no-store' in response.headers['cache-control']
    assert 'default-src' in response.headers['content-security-policy']
    assert response.headers['x-robots-tag']=='index, follow'


def test_sitemap_paginates_current_public_records_and_removes_hidden(public_mode,monkeypatch):
    c,p,_=public_mode
    monkeypatch.setattr(groupbuy_public,'PAGE_SIZE',2)
    items=[create(c,p,title='공개 공구 '+str(i)) for i in range(3)]
    hidden=create(c,p,title='숨김 공구 정보')
    with SessionLocal() as db:
        db.get(Record,hidden['id']).status='hidden'
        db.get(Record,items[0]['id']).ends=now()-1
        db.commit()
    prefix='/api/release/groupbuy-pages'
    ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    index=ElementTree.fromstring(c.get(prefix+'/sitemap.xml').text)
    assert len(index.findall('s:sitemap',ns))==2
    pages=[c.get(prefix+'/sitemaps/'+str(i)) for i in (1,2)]
    urls=[loc.text for r in pages for loc in ElementTree.fromstring(r.text).findall('s:url/s:loc',ns)]
    assert len(urls)==3 and len(set(urls))==3
    assert all(hidden['id'] not in url for url in urls)
    assert c.get(prefix+'/sitemaps/3').status_code==404
    assert c.get(prefix+'/sitemaps/0').status_code==404
    assert '<p>종료</p>' in c.get(BASE+'/'+items[0]['id']+'/public').text
    assert c.get(BASE+'/'+hidden['id']+'/public').status_code==404
