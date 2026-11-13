"""Public-release policies and readable, script-free help pages.

Only describe implemented features. Keep legal routes stable for installed apps
and Play listings; these pages must remain usable without authentication.
"""
from html import escape
import re
from . import config
from .signup_policy import PUBLIC_MINIMUM_AGE

NAME = '모두의 육아 - 육아템 공동구매,핫딜'
PAGES = (
    ('terms', '이용약관'), ('privacy', '개인정보 처리방침'),
    ('deletion', '계정과 데이터 삭제'), ('support', '도움말과 문의'),
)
INTRO = {
    '이용약관': '함께 이용하기 위해 알아두어야 할 서비스 범위와 이용 기준입니다.',
    '개인정보 처리방침': '어떤 정보를 왜 보관하는지, 어떻게 확인하고 삭제할 수 있는지 안내합니다.',
    '계정과 데이터 삭제': '계정을 탈퇴하거나, 계정은 유지하면서 개별 기록을 지우는 방법을 안내합니다.',
    '도움말과 문의': '이용 중 궁금한 점을 먼저 확인하고, 해결되지 않으면 운영팀에 알려 주세요.',
}


def public_page(title, content):
    headings = re.findall(r'<h2>(.*?)</h2>', content)
    for index, heading in enumerate(headings, 1):
        content = content.replace(f'<h2>{heading}</h2>', f'<h2 id="section-{index}" tabindex="-1">{heading}</h2>', 1)
    toc = ''.join(f'<li><a href="#section-{i}">{heading}</a></li>' for i, heading in enumerate(headings, 1))
    links = ''.join(f'<a href="/legal/{kind}"' + (' aria-current="page"' if label == title else '') + f'>{label}</a>' for kind, label in PAGES)
    summary, content = content.split('</div>', 1)
    summary += '</div>'
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex"><meta name="theme-color" content="#fffaf3">
<title>{escape(title)} | {NAME}</title>
<style>
:root{{color-scheme:light;--ink:#4f382e;--muted:#73635b;--line:#e6dcd4;--accent:#a4362d;--cream:#fff5e7}}
*{{box-sizing:border-box}}html{{scroll-padding-top:24px}}body{{margin:0;padding-left:env(safe-area-inset-left);padding-right:env(safe-area-inset-right);padding-bottom:env(safe-area-inset-bottom);background:#fffcf8;color:var(--ink);font:16px/1.8 system-ui,-apple-system,sans-serif;word-break:keep-all;overflow-wrap:anywhere}}
a{{color:var(--accent);text-underline-offset:4px}}a:focus-visible,summary:focus-visible{{outline:3px solid var(--accent);outline-offset:4px;border-radius:3px}}
.skip{{position:absolute;top:-100px;left:16px;background:white;padding:12px;z-index:2}}.skip:focus{{top:12px}}
.brand-bar{{border-bottom:1px solid var(--line)}}.brand-inner{{max-width:1040px;margin:auto;padding:16px 24px;display:flex;justify-content:space-between;align-items:center;gap:16px}}
.brand{{font-size:19px;font-weight:800;color:var(--ink);text-decoration:none}}.brand::before{{content:'';display:inline-block;width:12px;height:12px;border-radius:50%;background:#dc8e85;margin-right:10px}}
.back{{display:inline-flex;align-items:center;min-height:44px;font-size:14px}}
.legal-shell{{max-width:1040px;margin:auto;padding:40px 24px 56px}}.eyebrow{{color:var(--muted);font-size:14px;letter-spacing:.06em;margin:0 0 10px}}
h1{{font-size:clamp(28px,4vw,36px);letter-spacing:-.04em;line-height:1.3;margin:0 0 16px}}.intro{{font-size:18px;max-width:680px;margin:0 0 16px}}.meta{{font-size:14px;color:var(--muted);margin:0 0 30px}}
.mobile-toc{{display:none}}.legal-summary{{grid-column:2;grid-row:1}}.legal-summary .summary{{margin:0}}.legal-layout{{display:grid;grid-template-columns:220px minmax(0,1fr);column-gap:44px;row-gap:0;align-items:start}}.toc{{grid-column:1;grid-row:1 / span 2;border-top:2px solid #dc8e85;padding-top:16px}}.toc h2{{font-size:15px;margin:0 0 10px;border:0;padding:0}}.toc ol{{list-style:none;padding:0;margin:0}}.toc li{{margin:0}}.toc a{{display:flex;align-items:center;min-height:44px;padding:6px 0;text-decoration:none;color:var(--muted);font-size:14px}}.toc a:hover{{color:var(--accent);text-decoration:underline}}
article{{min-width:0;grid-column:2;grid-row:2}}article h2{{font-size:22px;line-height:1.5;letter-spacing:-.025em;margin:36px 0 14px;padding-top:24px;border-top:1px solid var(--line);scroll-margin-top:24px}}article h3{{font-size:17px;margin:22px 0 8px}}p{{margin:0 0 16px}}li{{margin:8px 0}}ul,ol{{padding-left:24px}}.summary{{background:var(--cream);border-radius:16px;padding:22px 24px;margin-bottom:24px}}.summary>p:first-child{{font-weight:700}}.summary ul{{margin-bottom:0}}.summary p:last-child{{margin-bottom:0}}
.data-list{{margin:0}}.data-list dt{{font-weight:700;margin-top:20px}}.data-list dd{{margin:6px 0 0}}.steps{{list-style:none;padding:0;counter-reset:step}}.steps li{{position:relative;padding:0 0 22px 44px;margin:0;counter-increment:step}}.steps li::before{{content:counter(step);position:absolute;left:0;top:1px;width:28px;height:28px;border-radius:50%;background:var(--cream);text-align:center;font-size:14px;font-weight:700}}.steps strong{{display:block}}.steps p{{margin:4px 0 0}}
.action{{display:inline-flex;align-items:center;min-height:48px;padding:10px 18px;background:var(--accent);color:white;border-radius:10px;text-decoration:none;font-weight:600;margin:4px 0 12px}}
details{{border-bottom:1px solid var(--line);padding:4px 0}}summary{{cursor:pointer;min-height:48px;padding:12px 0;font-weight:600}}details p{{margin:4px 0 16px}}.contact{{border:1px solid var(--line);border-radius:14px;padding:20px;margin-top:20px}}.contact a{{overflow-wrap:anywhere}}.muted{{color:var(--muted);font-size:14px}}
footer{{border-top:1px solid var(--line);margin-top:48px;padding-top:24px}}footer nav{{display:flex;flex-wrap:wrap;gap:4px 24px}}footer nav a{{display:inline-flex;min-height:44px;align-items:center;font-size:14px}}footer a[aria-current]{{font-weight:700;color:var(--ink)}}footer p{{font-size:14px;color:var(--muted);margin-top:16px}}
@media(max-width:720px){{.brand-inner{{padding:10px 20px}}.legal-shell{{padding:28px 20px 40px}}.legal-layout{{display:flex;flex-direction:column;gap:0}}.legal-summary{{width:100%}}.desktop-toc{{display:none}}.mobile-toc{{display:block;margin:16px 0 0;width:100%}}.mobile-toc summary{{padding:10px 0}}.toc{{padding:16px;background:#fff;border:1px solid var(--line);border-radius:12px}}.toc ol{{display:grid;grid-template-columns:1fr 1fr;gap:0 16px}}.toc a{{font-size:14px}}.summary{{padding:20px}}.intro{{font-size:16px}}article h2{{font-size:21px;margin-top:28px}}}}
@media(max-width:360px){{.toc ol{{grid-template-columns:1fr}}.brand{{font-size:17px}}}}
@media print{{.brand-bar,.toc,footer,.skip,.action{{display:none}}.legal-layout{{display:block}}.legal-shell{{padding:0}}body{{background:white;color:black}}details::details-content{{display:block}}}}
</style></head><body><a class="skip" href="#document">본문으로 이동</a>
<header class="brand-bar"><div class="brand-inner"><a class="brand" href="/">모두의 육아</a><a class="back" href="/my">← 마이페이지</a></div></header>
<main class="legal-shell"><p class="eyebrow">모두의 육아 이용 안내</p><h1>{escape(title)}</h1><p class="intro">{INTRO[title]}</p><p class="meta">운영 Team_Wifi · 적용일 2026년 11월 6일</p>
<div class="legal-layout"><div class="legal-summary">{summary}</div><nav class="toc desktop-toc" aria-label="이 문서의 목차"><h2>이 페이지에서</h2><ol>{toc}</ol></nav><details class="mobile-toc"><summary>목차 펼쳐보기</summary><nav class="toc" aria-label="모바일 문서 목차"><ol>{toc}</ol></nav></details><article id="document" tabindex="-1">{content}</article></div>
<footer><nav aria-label="다른 이용 안내">{links}</nav><p>{NAME}<br>이용 안내는 로그인 없이 확인할 수 있습니다.</p></footer></main></body></html>'''


def public_pages(contact):
    hosting = escape(config.HOSTING_LOCATION or '운영 환경에 저장 위치 미설정')
    database = escape(config.DATABASE_LOCATION or '운영 환경에 저장 위치 미설정')
    return {
        'privacy': ('개인정보 처리방침', f'''
<div class="summary"><p>먼저 확인해 주세요</p><ul><li>육아템과 공구 수요 글은 로그인 없이 볼 수 있습니다.</li><li>회원의 이메일은 공개하지 않습니다. 작성한 글·댓글과 닉네임은 공개됩니다.</li><li>계정을 유지하면서 글이나 저장 기록을 지울 수 있습니다. <a href="/legal/deletion">삭제 방법 보기</a></li></ul></div>
<h2>1. 운영자와 적용 범위</h2><p>Team_Wifi가 운영하는 만 {PUBLIC_MINIMUM_AGE}세 이상 이용자 대상 육아 정보·경험 공유와 육아용품 비교·공구 수요 커뮤니티에 적용됩니다. 실제 주문·결제·배송·정산과 판매자 입점 기능은 제공하지 않습니다. 개인정보 관련 문의는 {contact}로 접수합니다.</p>
<h2>2. 수집 항목과 이용 목적</h2>
<dl class="data-list"><dt>가입과 계정 관리</dt><dd>이메일, 닉네임, 비밀번호의 Argon2 해시, 계정 ID, 가입 시각, 가입 연령 기준 확인 및 필수 약관·개인정보 동의 기록을 처리합니다. 가입·로그인·계정 관리에 사용하며 마케팅 수신은 받지 않습니다. 가입 연령은 만 {PUBLIC_MINIMUM_AGE}세 이상인지 이용자가 직접 확인하는 방식이며, 생년월일·신분증을 수집하거나 본인·성인 인증을 수행하지 않습니다. 이전 가입·앱의 만 18세 이상 확인 기록은 당시의 확인 내용으로 보존하며 새 확인으로 바꾸지 않습니다. 이메일 인증과 이메일 발송은 제공하지 않습니다.</dd>
<dt>소셜 로그인과 계정 연결</dt><dd>화면에 제공되는 Google·카카오 로그인을 선택하면 해당 서비스가 인증하고 고유 식별자(sub)를 전달합니다. 서비스는 제공자 이름·고유 식별자·내 계정의 연결 관계를 보관합니다. 해당 계정의 이메일·이름·사진을 요청하지 않으며 구글·카카오 비밀번호를 받지 않습니다. 인증 코드·ID 토큰은 서버 검증에만 사용하고 장기 저장하지 않습니다. 기존 이메일 계정은 로그인 후 직접 연결해야 합니다. 소셜 전용 계정의 탈퇴는 연결된 소셜 계정 재인증으로 진행합니다. 카카오에서 서비스 연결을 해제하면 서명된 알림을 받아 카카오 연결과 로그인 세션을 폐기합니다. 이메일 비밀번호나 다른 소셜 연결이 있으면 서비스 계정과 기록은 유지합니다. 다른 로그인 수단이 없는 카카오 전용 회원은 계정과 작성·활동 기록을 계정 삭제 절차와 동일하게 삭제합니다.</dd>
<dt>선택 동의한 활동 분석</dt><dd>계정 관리에서 별도 선택한 일반 회원만 공구·육아템·수요 글 ID, 노출 위치, 웹·앱 구분, 날짜, 클릭 종류(판매처 이동 포함)와 저장·관심 완료를 계정 ID에 연결해 수집합니다. 목적은 화면·비교 안내 개선입니다. 이메일·닉네임·검색어·계산기 값·외부 사이트에서의 방문·열람 내역은 분석 항목에 넣지 않습니다. 운영자에게는 계정별 중복을 제거한 집계만 보이며 1~4계정 집계는 숨깁니다. 최근 30일을 분석하고 만료 기록은 다음 측정·분석 조회 때 삭제하므로 요청이 없으면 물리적 삭제가 지연될 수 있습니다. 동의를 끄면 본인 분석 기록을 즉시 삭제합니다. 동의하지 않아도 나머지 기능을 이용할 수 있습니다.</dd><dt>글쓰기와 커뮤니티 활동</dt><dd>공구 수요 글·댓글의 내용, 작성 시각, 작성자 ID와 닉네임을 처리합니다. 저장·관심·신고 사유와 대상·차단 기록은 각 기능 제공과 신고 처리에 사용합니다.</dd>
<dt>관심 설정과 맞춤 탐색</dt><dd>직접 선택한 관심 카테고리·비교 기준을 계정에 저장하고, 본인의 저장 기록과 함께 맞춤 목록 제공에 사용합니다. 서로 다른 5계정 이상이 함께 저장한 목록은 개인 식별정보 없이 함께 살펴볼 목록으로 안내합니다. 운영자는 저장·수요·관심 활동을 계정별 중복 없이 집계해 서비스 개선에 사용하며 1~4계정의 작은 집계는 표시하지 않습니다. 외부 공개 데이터의 개인 식별자를 회원과 연결하거나 방문 행동으로 구매 확률을 추정하지 않습니다. 선택 동의한 노출·클릭 분석은 아래 별도 기준을 따릅니다. 마이페이지 → 관심 육아템 설정에서 수정하거나 설정 지우기를 할 수 있습니다.</dd><dt>조건으로 찾기</dt><dd>선택한 분야·비교 기준·본인용 또는 선물용·예산 상한을 결과 생성에 사용합니다. 비회원 미리보기는 계정 기록으로 저장하지 않습니다. 로그인 후 조건 저장하고 찾기를 누르면 내 계정에 저장하며, 끝내고 조건 지우기 또는 회원탈퇴까지 보관합니다. 조건 찾기는 선택형 입력이며 아이의 이름·생일·건강정보를 요구하지 않습니다.</dd><dt>도우미 질문과 대화</dt><dd>질문에 답하기 위해 입력한 문장을 처리합니다. 모델에는 질문과 승인된 공개 자료만 전달하며, 내 저장 목록·관심 설정과 현재 커뮤니티 글은 서버가 권한을 확인해 별도로 안내합니다. 아이·가족의 개인정보, 의료정보, 비밀번호 등 비밀정보를 입력하지 마세요. 대화 저장은 기본적으로 꺼져 있습니다. 로그인 후 직접 켜면 이후의 질문·답변·공개 출처를 계정에 저장하고 마지막 저장 활동부터 30일 동안 보관합니다. 저장 끄기·대화 종료·삭제·탈퇴 시 저장된 대화 내용을 삭제합니다. 만료된 대화는 즉시 조회에서 제외하며 조회 또는 매시간 정리 작업에서 물리적으로 삭제합니다. 저장하지 않은 대화는 계정 이력으로 보관하지 않습니다. 도우미 운영 측정에는 무작위 요청 ID, 공개 문서의 버전, 처리 시간과 성공·실패 분류만 사용하며 회원 ID·질문·답변 원문은 Opik 기록에 넣지 않습니다.</dd><dt>인증과 계정 보호</dt><dd>세션 토큰과 복구코드는 해시로 저장합니다. 로그인 세션은 발급 후 30일, 이메일 계정 복구코드는 90일 동안 유효합니다. 소셜 인증 요청은 10분, 계정 삭제 재인증 결과는 5분 동안 유효합니다. 만료된 인증 요청은 다음 소셜 로그인 시작 때 삭제하며 요청이 없으면 정리가 지연됩니다. 원문 복구코드는 가입·재발급 화면에서 한 번 표시하며 서버에는 원문을 저장하지 않습니다. 복구·로그아웃·계정 삭제 시 관련 세션을 폐기합니다.</dd></dl>
<details><summary>과다 요청 제한과 운영 기록의 세부 항목</summary><p>계정 ID, 로그인·복구에 입력한 이메일 또는 도우미 요청의 연결 주소를 비밀키(HMAC)로 변환한 값과 요청 횟수를 과다 요청 제한에 사용합니다. 제한 카운터에는 원문 이메일이나 IP를 저장하지 않습니다. 10분 창이 만료된 카운터는 다음 계정 제한 처리 시 삭제하며, 요청이 없으면 정리가 지연됩니다. 전체 요청 제한은 메모리에 있으며 재시작 시 초기화됩니다.</p><p>카카오 연결 해제 알림의 중복 처리와 해제 전 인증 재사용을 막기 위해 이벤트 ID·제공자 회원번호의 해시와 사건 시각을 24시간 기준으로 보관합니다. 원문 알림 토큰은 저장하지 않습니다. 만료 기록은 다음 유효 알림 처리 때 삭제하므로 알림이 없으면 물리적 삭제가 지연될 수 있습니다. 이 보안 해시는 계정 삭제 후에도 해당 정리 기준까지 남을 수 있습니다.</p><p>동의 및 운영자의 신고 처리 감사 기록에는 계정 ID·대상 ID·조치 종류·처리 사유·접수 및 처리 시각을 보관합니다. 대상 회원에게는 조치와 사유를 안내하고 확인 여부를 기록합니다. 정기 자동 삭제 기한은 설정하지 않았으며 해당 기록 소유 계정 또는 연결된 대상 계정을 삭제할 때 관련 기록도 삭제합니다. 호스팅 제공자는 통신·보안 로그를 자체 정책에 따라 처리할 수 있습니다.</p></details>
<h2>3. 다른 이용자에게 보이는 정보</h2><p>공구 정보·커뮤니티 글·댓글의 내용과 작성·수정 시각, 작성자 ID·닉네임은 공개됩니다. 공구 판매처 링크와 공유한 조건·마감도 공개됩니다. 개인별 저장·관심 목록, 신고 사유, 차단 목록과 이메일은 공개하지 않습니다. 글에 표시되는 관심 수는 실제 계정의 관심 기록을 합산한 값이며 구매 실적이 아닙니다.</p>
<h2>4. 보관 기간과 삭제 범위</h2><p>계정과 작성·활동 기록은 <strong>회원탈퇴 또는 본인 삭제까지</strong> 보관합니다. 회원탈퇴 시 세션·복구코드, 본인 공구 정보·커뮤니티 글·댓글·관심·저장·관심 설정·저장 대화·신고·차단 기록을 삭제합니다. 본인 수요 글에 달린 다른 회원의 댓글과 관련 관심·신고도 함께 삭제합니다.</p><p>이메일·닉네임·비밀번호는 사용할 수 없게 바뀝니다. 데이터 연결 관계를 위한 임의 계정 ID와 탈퇴 상태는 남습니다. 실제 금전 거래가 없어 거래 법정 보관기간을 적용하지 않습니다. 소셜 연결과 선택 분석 기록도 탈퇴 시 삭제합니다. 제한 카운터·인증 요청·선택 분석 기록은 2항의 별도 정리 기준을 따릅니다.</p><p>호스팅·DB 제공자의 복구 이력에는 이전 데이터가 일시적으로 남을 수 있습니다. 제공자의 보관·삭제 정책을 따르며, 별도의 자동 복구·삭제 이력 대조 기능은 없습니다. <a href="/legal/deletion">기록별 삭제 방법과 계정 삭제 절차</a>를 확인하세요.</p>
<h2>5. 위탁과 국외 처리</h2><dl class="data-list"><dt>Render · 서버 운영</dt><dd>운영 환경상 저장 위치: {hosting}. <a href="https://render.com/privacy">Render 개인정보 정책</a></dd><dt>Neon · 데이터베이스 운영</dt><dd>운영 환경상 저장 위치: {database}. <a href="https://neon.com/privacy-policy">Neon 개인정보 정책</a></dd></dl><p>계정·작성·활동 데이터는 서비스 제공을 위해 네트워크로 해당 서버와 DB에 전송되어 처리됩니다. 광고 목적으로 판매하지 않습니다. 제공자의 로그와 복구 이력은 각 제공자 정책에 따라 처리됩니다.</p>
<p>소셜 로그인을 선택하면 해당 제공자와 인증 통신을 합니다. <a href="https://policies.google.com/privacy">Google 개인정보처리방침</a>, <a href="https://www.kakao.com/policy/privacy">카카오 개인정보처리방침</a>, <a href="https://policy.naver.com/policy/privacy.html">네이버 개인정보처리방침</a>이 해당 인증 서비스에 적용됩니다. 서비스 자체 활동 분석은 자체 서버·DB에서 처리하며 제3자 광고·분석 SDK로 전송하지 않습니다.</p><h2>6. 수집하지 않는 정보</h2><p>아이의 이름·생년월일·건강정보, 배송지, 결제정보, 사업자 서류를 요구하지 않습니다. 위치·사진·마이크 권한, 광고 식별자, 광고·분석 추적 SDK를 사용하지 않습니다. 글이나 댓글에도 아이와 가족의 개인정보, 민감한 정보, 타인의 정보를 작성하지 마세요.</p><p>외부 출처 링크를 열면 해당 사이트의 정책이 적용됩니다. 단가 비교 계산기에 입력한 값은 서버에 전송하거나 저장하지 않습니다.</p>
<h2>7. 보호 조치와 이용자의 권리</h2><p>기본 로그인 토큰은 브라우저/WebView 세션 저장소에 보관됩니다. ‘로그인 유지’를 직접 선택하면 해당 기기의 로컬 저장소에 보관하여 브라우저를 다시 열어도 사용할 수 있습니다. 발급 후 30일 만료, 로그아웃·탈퇴·계정 복구에 따른 서버 폐기는 동일하게 적용됩니다. 공용 기기에서는 로그인 유지를 선택하지 마세요. 비밀번호와 소셜 제공자 토큰을 단말 저장소에 보관하지 않습니다. 통신은 HTTPS, 비밀번호는 Argon2 해시, 데이터 접근은 권한 검사로 보호합니다.</p><p>본인 글·댓글과 저장·관심 기록은 해당 화면에서 삭제할 수 있으며, 앱과 웹의 계정 관리에서 탈퇴할 수 있습니다. 열람·정정·처리정지·삭제·이의 제기는 아래 창구로 요청하세요.</p><div class="contact"><strong>개인정보 문의 · Team_Wifi</strong><p>{contact}</p><p class="muted">계정 이메일과 요청 내용을 알려 주세요. 비밀번호·복구코드·주민등록번호는 보내지 마세요. 운영자가 계정 주체를 확인한 뒤 처리합니다.</p></div>'''),
        'terms': ('이용약관', f'''
<div class="summary"><p>현재 서비스의 이용 범위</p><ul><li>공식 출처를 살펴보고 육아용품의 조건을 비교합니다.</li><li>회원은 정보를 저장하고 공구 수요와 질문을 나눌 수 있습니다.</li><li>관심 표시는 수요 조사입니다. 예약·주문·구매계약이 성립하지 않습니다.</li></ul></div>
<h2>제1조. 서비스 범위</h2><p>Team_Wifi는 육아 질문·경험·정보와 공구 수요를 나누는 커뮤니티, 공개 출처에 근거한 육아템 비교, 저장과 관심 설정, 출처를 안내하는 도우미를 제공합니다. 도우미는 공개 자료와 권한이 확인된 현재 서비스 기록을 구분하여 안내하며, 의료 진단·처방이나 확인되지 않은 가격·재고·인증을 대신하지 않습니다. 공구 정보의 공유와 판매처 연결을 제공하며, 실제 주문·결제·배송·환불·정산은 각 판매처에서 진행합니다.</p><p><strong>통신판매중개 고지</strong> 모두의 육아는 공구 정보를 연결하는 통신판매중개 서비스로서 거래 당사자가 아닙니다. 상품 정보와 거래 이행 책임은 각 판매처에 있습니다. 이 안내가 관계 법령에 따른 플랫폼의 책임을 배제하는 뜻은 아닙니다.</p>
<h2>제2조. 가입과 계정 관리</h2><p>만 {PUBLIC_MINIMUM_AGE}세 이상 이용자가 필수 약관과 개인정보 처리에 동의하여 일반 회원으로 가입합니다. 이메일과 소셜 가입에 같은 기준을 적용합니다. 만 {PUBLIC_MINIMUM_AGE}세 미만은 가입할 수 없으며 현재 법정대리인의 동의·확인 절차는 제공하지 않습니다. 이메일 가입은 본인의 이메일을 입력하고 비밀번호와 복구코드를 안전하게 보관하세요. 화면에 제공되는 소셜 로그인은 해당 제공자의 계정을 사용합니다. 기존 회원은 계정 관리에서 연결해 같은 기록을 이용할 수 있습니다. 이메일 소유 확인이나 이메일 복구 발송은 제공하지 않습니다.</p><p>계정·복구코드의 양도·공개 또는 타인 정보 사용을 금지합니다. 비밀번호를 잊었다면 <a href="/reset">복구코드로 비밀번호 재설정</a>을 이용할 수 있습니다.</p>
<h2>제3조. 외부 정보 이용</h2><p>외부 정보에는 출처와 확인 시점을 표시합니다. 쇼핑 참고 링크는 구매 가능한 공구나 특가를 뜻하지 않습니다. 확인하지 못한 가격·배송비·종료 시점은 표시하지 않으며 가격·재고·상품 안전·판매처 이행을 보장하지 않습니다.</p><p>외부 판매처에서 현재 조건과 상품·배송·환불 정책을 직접 확인하세요. 단가 비교 결과는 이용자가 입력한 가격·배송비·수량을 계산한 값입니다.</p>
<h2>제4조. 게시물과 커뮤니티 이용</h2><p>권리가 있는 내용만 게시하세요. 욕설·괴롭힘·차별·성적 또는 불법 콘텐츠·사기·스팸·권리침해·개인정보 노출을 금지합니다. 작성자는 본인 글과 댓글을 수정하거나 삭제할 수 있습니다. 수정 시각은 작성 시각과 구분됩니다.</p><p>부적절한 글·댓글은 해당 화면에서 신고할 수 있으며 작성자를 차단할 수 있습니다. 운영자는 신고 검토 후 콘텐츠 숨김·삭제·정보 확인 필요 표시·이용정지·조치 없는 종결을 할 수 있습니다. 처리 사유와 운영자·시각을 기록합니다. 이의 제기는 {contact}로 접수합니다.</p>
<h2>제5조. 탈퇴와 기록 삭제</h2><p>마이페이지의 계정 관리에서 현재 비밀번호 또는 연결된 소셜 계정 재인증으로 탈퇴할 수 있습니다. 작성·활동 기록의 삭제 범위와 남는 기록은 <a href="/legal/privacy">개인정보 처리방침</a>을 따릅니다. <a href="/legal/deletion">계정·데이터 삭제 안내</a>에서 절차를 확인하세요.</p>
<h2>제6조. 접속 지연과 이용자 권리</h2><p>무료 서버의 절전·용량 제한으로 접속이 지연되거나 중단될 수 있습니다. 문제가 지속되면 <a href="/legal/support">도움말과 문의</a>를 이용하세요. 법률상 인정되는 이용자의 권리를 이 안내로 제한하지 않습니다.</p>'''),
        'deletion': ('계정과 데이터 삭제', f'''
<div class="summary"><p>앱 삭제와 계정 삭제는 다릅니다</p><p>휴대폰에서 앱을 지워도 서버의 계정과 작성 기록은 남습니다. 아래 웹 경로는 앱을 삭제한 뒤에도 이용할 수 있습니다.</p></div>
<h2>1. 계정은 유지하고 기록만 삭제</h2><dl class="data-list"><dt>선택 분석 기록</dt><dd>마이페이지 → 계정 관리 → 서비스 개선 통계 참여를 끄면 분석 기록을 삭제합니다. 기존 저장·관심 기록은 해당 기능에서 따로 삭제합니다.</dd><dt>관심 육아템 설정</dt><dd>마이페이지 → 관심 육아템 설정 → <strong>설정 지우기</strong>를 누릅니다. 저장한 육아템은 별도로 유지되며 아래 방법으로 해제할 수 있습니다.</dd><dt>도우미 대화</dt><dd><a href="/chat">도우미</a>의 저장된 대화에서 삭제하거나, 현재 대화의 저장 끄기·대화 종료를 확인하면 저장된 질문과 답변을 지웁니다. 다른 계정의 대화는 볼 수 없습니다.</dd><dt>조건 찾기 기록</dt><dd><a href="/advisor">내 조건으로 찾기</a> → <strong>끝내고 조건 지우기</strong>를 누르면 계정에 저장한 선택 조건을 삭제합니다.</dd><dt>저장한 육아템</dt><dd>마이페이지 → 저장한 육아템(이전 버전에서는 저장한 육아 정보) → 해당 육아템의 상세 화면에서 <strong>저장 해제</strong>를 누릅니다.</dd><dt>수요 글과 댓글</dt><dd>공구 수요 → 본인이 작성한 글의 상세 화면 → <strong>신고·차단·삭제</strong> 메뉴 → <strong>내 글 삭제</strong>를 누릅니다. 댓글은 해당 댓글의 신고·차단·삭제 메뉴에서 <strong>내 댓글 삭제</strong>를 누릅니다. 수요 글을 지우면 그 글에 달린 댓글·관심·신고도 함께 삭제됩니다.</dd><dt>관심 표시</dt><dd>관심을 표시한 수요 글에서 <strong>관심 취소</strong>를 누릅니다.</dd><dt>작성자 차단</dt><dd>마이페이지 → 계정 관리 → 차단한 작성자에서 <strong>차단 해제</strong>를 누릅니다.</dd></dl><p>신고·동의·운영 기록처럼 개별 삭제 버튼이 없는 항목은 {contact}로 문의해 주세요. 본인 확인 후 요청의 대상과 처리 범위를 안내합니다.</p>
<h2>2. 계정 전체 삭제</h2><ol class="steps"><li><strong>계정 관리 열기</strong><p>로그인 후 마이페이지 → 계정 관리로 이동합니다. 기존 앱에서는 ‘계정·복구·차단 설정’ 또는 ‘계정·설정’으로 표시될 수 있습니다.</p></li><li><strong>삭제 범위 확인</strong><p>‘계정과 데이터 삭제’ 영역의 <b>계정 삭제 진행</b>을 누릅니다.</p></li><li><strong>현재 비밀번호와 확인 항목 입력</strong><p>이메일 회원은 현재 비밀번호를 입력합니다. 소셜 전용 회원은 계정 관리의 연결된 소셜 계정으로 다시 인증합니다. 이어서 삭제 결과와 복구 불가 확인 항목을 선택합니다.</p></li><li><strong>계정 영구 삭제 실행</strong><p><b>계정 영구 삭제</b>를 누르면 처리 후 로그아웃되어 첫 화면으로 이동합니다. 취소하려면 제출 전에 ‘취소’를 누르세요.</p></li></ol><a class="action" href="/login?returnTo=%2Fsettings">로그인하고 계정 관리 열기</a>
<h2>3. 삭제되는 정보와 남는 기록</h2><p>본인 공구 정보·커뮤니티 글·댓글·관심·저장·관심 설정·저장 대화·신고·차단 기록과 세션·복구코드를 삭제합니다. 본인 수요 글에 달린 다른 회원의 댓글·관심·신고도 함께 삭제됩니다. 이메일·닉네임·비밀번호는 사용할 수 없게 바뀌며 계정과 삭제한 콘텐츠는 복구할 수 없습니다.</p><p>데이터 연결 관계를 위한 임의 계정 ID와 탈퇴 상태가 남습니다. 요청 제한 카운터와 제공자의 로그·복구 이력에는 별도 처리 기준이 적용됩니다. <a href="/legal/privacy#section-4">개인정보 처리방침의 보관·삭제 기준</a>을 확인하세요.</p>
<h2>4. 로그인할 수 없거나 삭제가 안 될 때</h2><p><a href="/reset">보관한 복구코드로 비밀번호 재설정</a> 후 직접 삭제할 수 있습니다. 복구코드를 잃었거나 삭제 오류가 발생하면 아래 창구로 계정 이메일과 요청 내용을 보내 주세요. 운영자가 계정 주체 확인 후 처리합니다.</p><div class="contact"><strong>계정·개인정보 삭제 요청 · Team_Wifi</strong><p>{contact}</p><p class="muted">제목에 ‘계정 삭제 요청’ 또는 ‘개별 기록 삭제 요청’을 적고, 대상 기록과 발생 화면을 알려 주세요. 비밀번호·복구코드·주민등록번호는 보내지 마세요.</p></div>'''),
        'support': ('도움말과 문의', f'''
<div class="summary"><p>궁금한 기능부터 확인하세요</p><p>로그인 없이 육아템과 공구 수요 글을 둘러볼 수 있어요. 육아템 저장과 글쓰기·댓글·관심 표시는 로그인 후 이용할 수 있습니다.</p></div>
<h2>1. 자주 묻는 질문</h2><details open><summary>여기서 상품을 주문할 수 있나요?</summary><p>현재는 공식 출처의 정보를 살펴보고 조건을 비교하거나 공구 수요를 나누는 서비스입니다. 실제 주문·결제·배송·판매자 입점은 제공하지 않습니다. 관심 표시는 구매 계약이나 예약이 아닙니다.</p></details>
<details><summary>가격이나 배송비가 없는 이유는 무엇인가요?</summary><p>확인하지 못한 가격·배송비·종료 시점은 표시하지 않습니다. ‘공식 참고 정보’는 특가나 공동구매 판매를 뜻하지 않습니다. 상세 화면의 출처 링크에서 현재 가격과 재고를 확인해 주세요.</p></details>
<details><summary>소셜 계정과 기존 기록을 함께 쓰고 싶어요</summary><p>기존 이메일 계정으로 로그인한 뒤 계정 관리에서 Google 또는 카카오를 연결하세요. 이후 같은 소셜 계정으로 앱과 웹에서 로그인하면 같은 회원 ID의 저장·관심·설정을 이용합니다. 이메일이 같다는 이유만으로 계정을 자동 병합하지 않습니다.</p></details><details><summary>비밀번호를 잊었어요</summary><p>가입 또는 재발급 때 보관한 복구코드로 <a href="/reset">비밀번호를 재설정</a>할 수 있습니다. 복구코드는 90일 동안 유효하며 이메일로 발송하지 않습니다. 코드를 잃었다면 아래 운영 문의 창구로 연락해 주세요. 비밀번호와 복구코드를 보내지는 마세요.</p></details>
<details><summary>불편한 글이나 작성자를 신고하고 싶어요</summary><p>수요 글·댓글의 신고 메뉴에서 사유를 입력할 수 있습니다. 작성자를 차단하면 로그인한 내 화면에서 해당 작성자의 글·댓글이 숨겨집니다. 계정 관리의 ‘차단한 작성자’에서 해제할 수 있습니다. 신고 처리에 이의가 있으면 운영팀에 문의해 주세요.</p></details>
<details><summary>탈퇴하지 않고 글이나 저장 기록만 지울 수 있나요?</summary><p>네. 본인 글·댓글, 저장과 관심 기록은 해당 화면에서 삭제할 수 있습니다. <a href="/legal/deletion">기록별 삭제 방법</a>에서 정확한 경로와 삭제 범위를 확인하세요.</p></details>
<h2>2. 접속이 늦거나 오류가 발생할 때</h2><p>무료 서버가 절전에서 깨어날 때 첫 요청이 지연될 수 있습니다. 연결 상태를 확인하고 잠시 뒤 다시 불러오세요. 글쓰기·관심·저장 버튼을 반복해서 누르기 전에 처리 내역을 확인해 주세요.</p><p>화면을 다시 열어도 문제가 계속되면 발생 시각, 화면 이름, 기기·운영체제, 오류 메시지를 함께 알려 주세요. 로그인이나 계정 삭제에 문제가 있다면 그 상황도 적어 주세요.</p>
<h2>3. 운영팀에 문의</h2><div class="contact"><strong>Team_Wifi 운영 문의</strong><p>{contact}</p><p>이용 문의 · 오류 신고 · 개인정보 요청 · 신고 처리 이의 제기</p><p class="muted">실시간 응답은 보장하지 않습니다. 화면을 첨부할 때 이메일·토큰·복구코드 등 개인정보와 인증정보를 가려 주세요. 비밀번호나 복구코드는 요청하지 않습니다.</p></div>'''),
    }
