"""Indexable, source-linked answers. No private data, invented offers or live scores.

Run after Vite. Explicit .html URLs work on the existing static deployment without
introducing a new server route. The API host remains noindex to avoid duplicates.
"""
import argparse
from html import escape
import json
from pathlib import Path
import runpy
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://moduyuga.onrender.com'
UPDATED = '2026-11-04'
CATALOG = json.loads((ROOT/'backend/app/release_catalog.json').read_text('utf-8'))['entries']
CONTENT = runpy.run_path(str(ROOT/'backend/app/catalog_content.py'))
GUIDES = [
    {'slug': 'diaper-unit-price', 'title': '기저귀 가격은 어떻게 비교하나요?',
     'answer': '같은 단계·형태·규격을 맞추고, 실제 지불할 상품 금액과 배송비의 합을 총 매수로 나눠 1매당 가격을 비교하세요. 할인율만으로 더 저렴한 상품인지 판단할 수 없습니다.',
     'sections': [('계산 순서', '① 같은 단계와 밴드형·팬티형을 맞춥니다. ② 팩 수 × 팩당 매수로 총 매수를 구합니다. ③ 적용 가능한 쿠폰을 반영한 상품 금액에 배송비를 더합니다. ④ 총액 ÷ 총 매수를 계산합니다.'),
                  ('가상 계산 예시', 'A: 상품 10,000원 + 배송비 3,000원, 40매 → 1매당 325원. B: 상품 15,000원 + 배송비 0원, 50매 → 1매당 300원. 같은 규격일 때 B의 단가가 낮습니다. 이 숫자는 계산 설명용이며 실제 판매 가격이 아닙니다.'),
                  ('가격 외에 확인할 조건', '사용 단계·핏·소재 설명과 교환·반품 조건을 함께 확인하세요. 아이에게 적합한지는 개인별로 다릅니다. 본 페이지는 의학·안전 적합성 판단을 제공하지 않습니다.')],
     'sources': ['momq-diapers'], 'cta': ('/calculator', '우리 조건으로 단가 계산하기')},
    {'slug': 'bottle-composition', 'title': '젖병 세트와 단품은 무엇을 비교해야 하나요?',
     'answer': '용량·소재·제품 세대를 먼저 맞춘 다음, 젖병과 젖꼭지의 개수, 포함 부속품, 별도로 구입해야 하는 항목을 비교하세요. 세트라는 이름만으로 더 유리한 구성이라고 볼 수 없습니다.',
     'sections': [('한 줄에 놓고 비교할 항목', '제품 세대 / 용량 / 소재 / 젖병 수 / 젖꼭지 수와 단계 / 포함 부속품 / 배송비 / 교환·반품 조건을 같은 순서로 적어 보세요.'),
                  ('사용과 관리 확인', '세척·소독 방법과 교체 안내는 해당 제품의 공식 설명서에서 확인하세요. 판매 페이지에 없는 조건을 추정하지 마세요.'),
                  ('구성에 맞춰 비교하기', '필요한 부속품을 추가했을 때 총액이 얼마인지 계산한 후 비교하세요. 같은 용량과 구성인지 확인하기 전에는 단순 개당 가격만으로 순위를 매기지 않습니다.')],
     'sources': ['doubleheart-bottles'], 'cta': ('/my/preferences', '내 비교 기준 설정하기')},
    {'slug': 'data-method', 'title': '모두의 육아는 데이터를 어떻게 활용하나요?',
     'answer': '제공 자료의 통계·한계를 확인한 뒤, 직접 선택한 관심 분야와 비교 기준을 서비스에 적용합니다. 실제 서비스에서는 계정별 저장·관심을 중복 제거하고, 동의한 회원의 노출·클릭·저장 완료를 구분해 분석합니다. 이를 구매 확률이나 매출 예측으로 표시하지 않습니다.',
     'sections': [('소비자 1,000명 자료', '할인 민감도는 매우 민감 350명, 다소 민감 319명, 민감하지 않음 331명으로 나뉘었습니다. 육아용품 표본은 41명뿐입니다. 한국 보호자를 대표한다고 볼 수 없어, 일률적인 할인 점수 대신 관심 분야 최대 3개와 가격·구성·사용 및 관리 기준을 직접 고르게 했습니다.'),
                  ('소매 거래 자료의 중복과 동시구매', '541,909행의 소매 자료는 1,067,371행 자료의 두 번째 시트와 중복되어 합산에서 제외했습니다. 2009~2011년 영국 소매 거래의 동시구매 분석 방식을 참고해 서비스에서는 함께 저장한 육아템 조합을 살핍니다. 서로 다른 5명 이상이 함께 저장한 조합만 운영자에게 보이며 주문·구매 실적으로 해석하지 않습니다.'),
                  ('쇼핑 세션 12,330개 자료', '구매 세션 1,908개를 포함하지만 세션 종료 시점의 기록입니다. 실시간 구매 점수로 쓰면 미래 정보가 섞일 수 있어 적용하지 않습니다. 직접 선택한 비교 기준 안내와 단가 계산으로 연결합니다.'),
                  ('실제 서비스에서 검증할 것', '선택 동의한 일반 회원의 화면 노출과 CTA 클릭을 측정합니다. 같은 계정은 위치·플랫폼별 최근 30일 집단에서 한 번만 세고, 저장 완료는 서버가 신규 저장을 확인했을 때만 연결합니다. 1~4명 집계는 숨깁니다. 관찰 CTR은 개선의 인과 효과나 A/B 실험 결과가 아닙니다.'),
                  ('자료의 한계와 운영 책임', '소비자 자료의 표집 모집단은 확인되지 않았습니다. 해외 소매·세션 자료를 현재 국내 육아 시장의 수요로 환산하지 않습니다. 관심 설정이 없는 회원을 임의의 개인 성향으로 분류하지 않으며, 운영 Team_Wifi가 실제 활동과 출처를 검토합니다.')],
     'sources': [], 'cta': ('/my/preferences', '내 관심 육아템과 비교 기준 고르기')},
]

STYLE = '''body{margin:0;background:#fffcf8;color:#49362d;font:17px/1.8 system-ui,sans-serif;word-break:keep-all}*{box-sizing:border-box}header,main,footer{max-width:880px;margin:auto;padding:24px}a{color:#96372f;text-underline-offset:4px}a:focus-visible{outline:3px solid #96372f;outline-offset:4px}header{border-bottom:1px solid #eaded3;display:flex;justify-content:space-between;gap:20px}h1{font-size:clamp(28px,5vw,40px);line-height:1.35;letter-spacing:-.03em}h2{font-size:23px;margin-top:38px}.answer{background:#fff1de;padding:24px;border-radius:16px;font-size:19px}small,.meta{color:#746157;font-size:14px}.cta{display:inline-flex;padding:12px 20px;background:#96372f;color:white;border-radius:10px;min-height:48px;text-decoration:none}li{margin:12px 0}.guide{padding:20px 0;border-bottom:1px solid #eaded3}footer{border-top:1px solid #eaded3;margin-top:32px}table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #eaded3}@media(max-width:500px){header,main,footer{padding:20px}.answer{padding:20px}}'''


def page(title, description, path, content, structured=None):
    schema = '' if not structured else '<script type="application/ld+json">'+json.dumps(structured, ensure_ascii=False).replace('<', '\\u003c')+'</script>'
    canonical = ORIGIN+path
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | 모두의 육아</title>
<meta name="description" content="{escape(description, quote=True)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{canonical}">
<meta property="og:type" content="article"><meta property="og:title" content="{escape(title, quote=True)}"><meta property="og:description" content="{escape(description, quote=True)}"><meta property="og:url" content="{canonical}"><style>{STYLE}</style>{schema}</head>
<body><header><a href="/">모두의 육아</a><a href="/guides.html">육아템 선택 가이드</a></header><main>{content}</main><footer><p>운영·작성 Team_Wifi · 업데이트 {UPDATED}<br>실제 주문·결제·배송을 제공하지 않습니다.</p><a href="/legal/support">문의·정정 요청</a> · <a href="/legal/privacy">개인정보 처리방침</a></footer></body></html>'''


def export(output):
    paths = ['/guides.html']
    for guide in GUIDES:
        path = '/guides/'+guide['slug']+'.html'
        paths.append(path)
        sources = [entry for entry in CATALOG if entry['id'] in guide['sources']]
        body = '<p class="meta">선택 기준 · 공식 출처 확인</p><h1>'+escape(guide['title'])+'</h1><p class="answer">'+escape(guide['answer'])+'</p>'
        body += ''.join('<section><h2>'+escape(title)+'</h2><p>'+escape(text)+'</p></section>' for title, text in guide['sections'])
        if sources:
            body += '<h2>공식 출처와 확인 시점</h2><ul>'+''.join('<li><a href="'+escape(entry['source_url'], quote=True)+'" rel="noopener noreferrer">'+escape(entry['source_name'])+'</a> · 출처 확인 '+escape(CONTENT['checked_time'](entry))+'<br><small>현재 가격·재고와 제품 조건은 원문을 확인하세요.</small></li>' for entry in sources)+'</ul>'
        else:
            body += '<h2>분석 자료</h2><p>프로젝트 제공 파일: Ecommerce_Consumer_Behavior_Analysis_Data.csv, online_retail.csv, online_retail_II.xlsx, online_shoppers_intention.csv. 원본 개인별 행은 공개하지 않습니다. 제공 파일 분석 결과를 요약했으며 표집과 현재 시장 대표성에 한계가 있습니다.</p>'
        body += '<p><a class="cta" href="'+guide['cta'][0]+'">'+escape(guide['cta'][1])+'</a></p>'
        schema = {'@context': 'https://schema.org', '@type': 'Article', 'headline': guide['title'], 'description': guide['answer'],
                  'dateModified': UPDATED, 'author': {'@type': 'Organization', 'name': 'Team_Wifi'}, 'mainEntityOfPage': ORIGIN+path,
                  'citation': [entry['source_url'] for entry in sources], 'inLanguage': 'ko-KR'}
        target = output/path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(guide['title'], guide['answer'], path, body, schema), 'utf-8')
    for entry in CATALOG:
        detail = CONTENT['guide'](entry)
        path = CONTENT['guide_path'](entry)
        # An expired reference remains readable but is excluded from discovery maps.
        if not detail['expired']:
            paths.append(path)
        title = entry['title']
        body = '<p class="meta">'+escape(entry['category'])+' · 공식 참고 목록</p><h1>'+escape(title)+'</h1><p class="answer">'+escape(entry['summary'])+'</p>'
        body += '<h2>비교할 때 확인할 것</h2><ul>'+''.join('<li>'+escape(note)+'</li>' for note in entry['comparison_notes'])+'</ul>'
        body += '<h2>확인된 정보와 남은 확인</h2><p>'+escape(detail['limitations'])+'</p>'
        body += '<p>가격: '+(f"{entry['price']:,}원" if entry['price'] is not None else '미확인 · 판매처에서 확인')+' · 배송비: '+(f"{entry['shipping_fee']:,}원" if entry['shipping_fee'] is not None else '미확인')+'</p>'
        if detail['expired']:
            body += '<p>이 안내의 기한이 지났습니다. 현재 판매 조건으로 사용하지 마세요.</p>'
        body += '<h2>공식 출처</h2><p><a href="'+escape(entry['source_url'], quote=True)+'" rel="noopener noreferrer">'+escape(entry['source_name'])+'</a> · 출처 확인 '+escape(CONTENT['checked_time'](entry))+'</p>'
        body += '<p>가격·재고·규격·호환성과 안전인증은 개별 제품의 원문·증빙에서 다시 확인하세요.</p>'
        body += '<p><a class="cta" href="/offers/'+quote(entry['id'], safe='')+'">앱·웹에서 자세히 보기</a></p><a href="/advisor">내 조건으로 육아템 찾기</a> · <a href="/calculator">단가 계산하기</a>'
        target = output/path.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(title, entry['summary'], path, body, detail['structured_data']), 'utf-8')
    content = '<h1>육아템 선택 가이드</h1><p class="answer">가격·구성·사용 조건을 같은 기준으로 비교할 수 있도록 정리했어요. 공식 출처와 데이터의 한계를 함께 확인하세요.</p>'
    content += ''.join('<article class="guide"><h2><a href="/guides/'+g['slug']+'.html">'+escape(g['title'])+'</a></h2><p>'+escape(g['answer'])+'</p></article>' for g in GUIDES)
    content += '<h2>품목별 비교 안내</h2><ul>'+''.join('<li><a href="'+CONTENT['guide_path'](entry)+'">'+escape(entry['title'])+'</a></li>' for entry in CATALOG if CONTENT['active'](entry))+'</ul>'
    (output/'guides.html').write_text(page('육아템 선택 가이드', '기저귀 단가, 젖병 구성, 데이터 활용 근거를 출처와 함께 확인하세요.', '/guides.html', content), 'utf-8')
    (output/'robots.txt').write_text('User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /auth/\nDisallow: /admin\nDisallow: /settings\nDisallow: /my\nDisallow: /login\nDisallow: /signup\nDisallow: /reset\nSitemap: '+ORIGIN+'/sitemap.xml\n', 'utf-8')
    (output/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+ORIGIN+p+'</loc><lastmod>'+UPDATED+'</lastmod></url>' for p in paths)+'</urlset>', 'utf-8')
    (output/'llms.txt').write_text('# 모두의 육아\n\n성인 보호자를 위한 육아용품 비교·공구 수요 서비스. 주문·결제·배송 미제공.\n\n'+''.join('- ['+g['title']+']('+ORIGIN+'/guides/'+g['slug']+'.html)\n' for g in GUIDES)+''.join('- ['+entry['title']+']('+ORIGIN+CONTENT['guide_path'](entry)+')\n' for entry in CATALOG if CONTENT['active'](entry))+'\n출처 확인일과 자료의 한계를 각 문서에 표시합니다. 이 목록은 AI 인용이나 노출을 보장하지 않습니다.\n', 'utf-8')
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=ROOT/'frontend/dist')
    output = parser.parse_args().output_dir.resolve()
    if not output.is_relative_to(ROOT):
        parser.error('Output must remain inside E workspace')
    output.mkdir(parents=True, exist_ok=True)
    print('PUBLIC_GUIDES_EXPORT_PASS', len(export(output)), 'pages; no DB or private data')
