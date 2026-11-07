"""Current public group-buy pages and paginated sitemaps for the web rewrite."""
import json
from html import escape
from math import ceil
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, select
from . import config, release
from .db import Record, get_db

router=APIRouter(prefix='/api/release/groupbuy-pages',dependencies=[Depends(release.public_only)])
PAGE_SIZE=1000


def origin():
    # Never derive canonical URLs from the caller's Host/Forwarded headers.
    return config.PUBLIC_WEB_ORIGIN or 'https://moduyuga.onrender.com'


def page(row):
    from .groupbuys import BROKER_NOTICE, display_time
    canonical=origin()+'/groupbuys/'+quote(row['id'],safe='')+'/public'
    state='종료' if row['status']=='ended' else '진행 중'
    checked=display_time(row['source_checked_at']);queried=display_time(row['queried_at'])
    warning='<p class="notice">정보 확인 필요: 제보가 접수되었거나 추가 확인이 필요한 정보입니다. 판매처에서 현재 조건을 확인하세요.</p>' if row['review_state']=='needs_review' else ''
    schema={'@context':'https://schema.org','@type':'DiscussionForumPosting',
        'headline':row['title'],'text':row['body'],'datePublished':row['created_at'],
        'dateModified':row['updated_at'] or row['created_at'],'url':canonical,
        'author':{'@type':'Person','name':row['author']['nickname']},
        'about':{'@type':'Thing','name':row['category']}}
    encoded=json.dumps(schema,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    def price(value):return '확인되지 않음' if value is None else f'{value:,}원'
    body=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(row['title'])} · {state} | 모두의 육아</title><meta name="description" content="{escape(row['body'][:160],quote=True)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{escape(canonical,quote=True)}"><script type="application/ld+json">{encoded}</script><style>body{{margin:0;background:#fffcf8;color:#4f382e;font:16px/1.8 system-ui,sans-serif}}main{{max-width:760px;margin:auto;padding:24px}}a{{color:#a4362d}}a:focus-visible{{outline:3px solid #a4362d;outline-offset:4px}}h1,p,dd{{overflow-wrap:anywhere}}.body{{white-space:pre-wrap}}.notice{{padding:16px;background:#fff0dd}}dt{{font-weight:700}}dd{{margin:0 0 12px}}nav{{display:flex;gap:24px;flex-wrap:wrap}}nav a{{padding:12px 0}}</style></head><body><main><nav><a href="{origin()}/">모두의 육아 · 공구 찾기</a><a href="{origin()}/groupbuys/{quote(row['id'],safe='')}">앱·웹 상세로 이동</a></nav><p>{escape(row['category'])} · 회원이 공유한 정보</p><p>{state}</p><h1>{escape(row['title'])}</h1>{warning}<p class="body">{escape(row['body'])}</p><dl><dt>판매처</dt><dd>{escape(row['seller_name'])}</dd><dt>마감</dt><dd>{escape(display_time(row['expires_at']))}</dd><dt>공유 금액</dt><dd>{price(row['price'])}</dd><dt>배송비</dt><dd>{price(row['shipping_fee'])}</dd><dt>최소 수량</dt><dd>{row.get('minimum_quantity') if row.get('minimum_quantity') is not None else '공유된 최소 수량 없음'}</dd><dt>구성·단위</dt><dd>{escape(row['unit']) or '공유된 구성 정보 없음'}</dd><dt>적용 조건</dt><dd>{escape(row['price_conditions']) or '판매처에서 확인해 주세요.'}</dd><dt>출처 확인 시각</dt><dd>{escape(checked)}</dd><dt>현재 DB 조회 시각</dt><dd>{escape(queried)}</dd><dt>공유자</dt><dd>{escape(row['author']['nickname'])}</dd><dt>등록 시각</dt><dd>{escape(display_time(row['created_at']))}</dd><dt>수정 시각</dt><dd>{escape(display_time(row['updated_at'])) if row.get('updated_at') else '수정 이력 없음'}</dd></dl><p>회원이 공유한 가격·마감·조건이며 플랫폼이 판매나 재고를 보장하지 않습니다. 주문 전에 판매처의 현재 조건을 확인하세요.</p><a target="_blank" rel="nofollow ugc noreferrer noopener" href="{escape(row['seller_url'],quote=True)}">{escape(row['seller_name'])} 판매처에서 현재 조건 확인 ↗</a><h2>통신판매중개 고지</h2><p>{escape(BROKER_NOTICE)}</p><a href="{origin()}/legal/terms">이용약관</a></main></body></html>'''
    return HTMLResponse(body,headers={'Cache-Control':'no-store', 'X-Robots-Tag':'index, follow',
        'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})


def xml(content):
    return Response('<?xml version="1.0" encoding="UTF-8"?>'+content,media_type='application/xml',headers={'Cache-Control':'no-store'})


@router.get('/sitemap.xml')
def sitemap_index(db=Depends(get_db)):
    from .groupbuys import visible_query
    count=db.scalar(select(func.count()).select_from(visible_query().subquery()))
    urls=''.join('<sitemap><loc>'+origin()+f'/groupbuys/sitemaps/{n}'+'</loc></sitemap>' for n in range(1,ceil(count/PAGE_SIZE)+1))
    return xml('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+urls+'</sitemapindex>')


@router.get('/sitemaps/{page_number}')
def sitemap_page(page_number:int, db=Depends(get_db)):
    from .groupbuys import visible_query
    if not 1<=page_number<=100000:raise HTTPException(404,'공개 목록을 찾을 수 없습니다.')
    rows=db.scalars(visible_query().order_by(Record.id).offset((page_number-1)*PAGE_SIZE).limit(PAGE_SIZE)).all()
    if not rows:raise HTTPException(404,'공개 목록을 찾을 수 없습니다.')
    urls=''.join('<url><loc>'+origin()+'/groupbuys/'+quote(row.id,safe='')+'/public</loc><lastmod>'+escape(row.data.get('updated_at') or release.timestamp(row.created))+'</lastmod></url>' for row in rows)
    return xml('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+urls+'</urlset>')
