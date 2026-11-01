"""Public, readable policy pages tied to the running beta configuration."""
from html import escape
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from . import config

router = APIRouter()
NAME = '모두의 육아 - 육아템 공동구매,핫딜'


def page(title, content):
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{escape(title)} | {NAME}</title>
<style>body{{margin:0;background:#fffaf3;color:#4f382e;font:17px/1.8 system-ui,sans-serif}}main{{max-width:760px;margin:auto;padding:28px 20px 80px}}h1{{font-size:30px;line-height:1.3}}h2{{margin-top:32px;font-size:22px}}a{{color:#a4362d}}li{{margin:10px 0}}nav{{display:flex;gap:18px;flex-wrap:wrap}}.notice{{padding:16px;background:#f5e4df;border-radius:14px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border:1px solid #dbc8bc;text-align:left;vertical-align:top;overflow-wrap:anywhere}}</style></head>
<body><main><p>{NAME} · Team_Wifi</p><h1>{escape(title)}</h1>
<p class="notice">비공개 베타 · 실제 결제·배송 없음 · 만 18세 이상 시험 참여</p>
{content}<hr><nav><a href="/">앱 둘러보기</a><a href="/legal/privacy">개인정보</a><a href="/legal/terms">이용약관</a><a href="/legal/deletion">계정 삭제</a><a href="/legal/support">문의</a></nav>
<p>적용일: 2026년 11월 1일</p></main></body></html>'''


@router.get('/legal/{kind}', response_class=HTMLResponse)
def legal(kind: str):
    email = escape(config.SUPPORT_EMAIL) if config.SUPPORT_EMAIL else ''
    contact = f'<a href="mailto:{email}">{email}</a>' if email else '운영 연락처 설정 전 · 외부 배포 불가'
    pages = {
        'privacy': ('개인정보 처리방침', f'''
<p>Team_Wifi는 이 비공개 베타의 계정과 시험 활동을 아래 범위에서 처리합니다. 운영·개인정보 문의: {contact}.</p>
<h2>수집하는 정보와 목적</h2>
<table><tr><th>정보</th><th>목적·보관</th></tr>
<tr><td>이메일, 닉네임, 비밀번호 해시, 약관·18세 이상 확인 기록</td><td>가입·로그인·계정 관리. 이메일 소유 확인 및 이메일 발송은 제공하지 않습니다. 실명 대신 닉네임을 사용하세요.</td></tr>
<tr><td>참여·철회·저장·시험 쿠폰·가상 판매자 신청·질문·신고·차단</td><td>공구 기능 시험과 부적절한 콘텐츠 처리. 질문과 브랜드명은 다른 참여자에게 공개될 수 있습니다.</td></tr>
<tr><td>로그인·참여·복구코드의 해시</td><td>권한 확인·중복 사용 방지. 원문 복구코드는 가입/재발급 화면에서 한 번 표시하며 서버에 원문을 저장하지 않습니다. 복구코드는 90일간 유효합니다.</td></tr>
<tr><td>요청 IP를 비밀키로 변환한 값·요청 횟수</td><td>과다 요청 차단. 원본 IP를 앱 DB에 저장하지 않으며 약 20분 이후 다음 요청 때 정리합니다. 호스팅 제공자는 통신·보안 로그를 자체 정책에 따라 처리할 수 있습니다.</td></tr></table>
<h2>수집하지 않는 정보</h2><p>아이의 이름·생년월일·건강정보, 배송지, 결제정보, 실제 사업자번호·대표자 연락처를 요구하지 않습니다. 위치·사진·마이크 권한, 광고 식별자, 제3자 광고·분석 SDK를 사용하지 않습니다. 게시물에도 민감한 정보나 타인의 정보를 입력하지 마세요.</p>
<h2>보관·삭제</h2><p>회원탈퇴 시 세션·복구코드와 계정 소유 시험 기록을 삭제하고 이메일·닉네임·비밀번호를 사용할 수 없게 바꿉니다. 실제 결제 내역이 없어 거래보관 기간을 적용하지 않습니다. 연관 데이터 무결성을 위한 식별 불가능한 계정 ID가 남을 수 있습니다. 계정은 가입 후 최장 90일, 베타 종료 후 30일 이내 운영자가 파기하며, 탈퇴 시에는 즉시 처리됩니다.</p>
<p>호스팅·DB의 복구 이력에 일시적으로 이전 데이터가 남을 수 있습니다. 복원할 경우 삭제 이력을 대조하여 탈퇴 계정을 다시 활성화하지 않습니다. 사용 중인 무료 서비스의 복구 보관기간은 아래 제공자 정책에 따릅니다.</p>
<h2>처리 위탁·저장 위치</h2><p>서버: {escape(config.HOSTING_LOCATION or '배포 전 미확정')}. DB: {escape(config.DATABASE_LOCATION or '배포 전 미확정')}. 계정·시험 기록은 네트워크를 통해 해당 서버/DB에 저장되므로 해외 리전을 사용하면 국외에서 처리됩니다. 서비스 운영에 필요한 범위로만 사용하며 광고 목적으로 판매하지 않습니다.</p>
<p>무료 배포 예정 제공자: <a href="https://render.com/privacy">Render</a>, <a href="https://neon.com/privacy-policy">Neon</a>. 실제 배포 설정과 지역이 확정되기 전에는 외부 이용자 가입을 시작하지 않습니다.</p>
<h2>권리 행사</h2><p>앱 및 웹의 계정·설정에서 계정 삭제가 가능합니다. 열람·정정·처리정지·개별 게시물 삭제 요청은 {contact}로 접수합니다. 비밀번호나 복구코드를 메일로 보내지 마세요. 인증 수단을 잃은 경우 운영자가 추가 확인 후 처리합니다.</p>
<h2>단말 저장과 보호</h2><p>로그인 토큰은 브라우저/WebView의 세션 저장소에 보관되며 8시간 뒤 만료됩니다. 로그아웃·탈퇴·비밀번호 복구 시 서버 토큰을 폐기합니다. 소개 화면 확인 여부만 단말에 남습니다. 통신은 HTTPS, 비밀번호는 Argon2, 서버 데이터 접근은 권한으로 제한합니다.</p>'''),
        'terms': ('베타 이용약관', '''
<h2>1. 제공 범위</h2><p>본 앱은 육아템 공동구매 모집·핫딜 탐색·질문·브랜드·혜택 기능을 시험하는 서비스입니다. 베타에 표시된 상품·가격·배송비·쿠폰·포인트는 시험 데이터입니다. 참여는 결제나 구매계약이 아니며 실제 배송·현금 환급·정산은 없습니다.</p>
<h2>2. 참여 조건과 계정</h2><p>만 18세 이상으로 초대받은 참여자가 가입할 수 있습니다. 참여코드는 한 번만 사용합니다. 본인의 이메일을 입력하고 비밀번호와 복구코드를 안전하게 보관하세요. 계정·초대·복구코드를 타인에게 공개하거나 다른 사람의 정보로 가입하지 마세요.</p>
<h2>3. 판매자 시험</h2><p>판매자 가입은 가상 브랜드 신청과 공구 등록 절차를 시험하기 위한 것입니다. 실제 입점 승인·사업자 인증·판매 계약을 의미하지 않습니다. 시험용 브랜드명과 설명만 입력하며 실제 사업자서류·전화·주소를 입력하지 않습니다.</p>
<h2>4. 커뮤니티 이용</h2><p>욕설·괴롭힘·차별·성적/불법 콘텐츠·사기·스팸·권리침해·개인정보 노출을 금지합니다. 게시자에게 콘텐츠 권리가 있어야 합니다. 공구/질문/사용자 신고와 차단을 이용할 수 있으며 운영자는 신고 검토 후 콘텐츠 숨김·이용정지 등 조치를 취할 수 있습니다. 이의 제기는 문의 창구로 접수합니다.</p>
<h2>5. 참여 철회·탈퇴</h2><p>참여 내역에서 시험 예약을 철회할 수 있습니다. 계정·설정에서 탈퇴하면 진행 중인 시험 예약도 철회됩니다. 실제 금전 거래가 없어 환불·배송 정산은 발생하지 않습니다.</p>
<h2>6. 외부 링크·중단</h2><p>외부 핫딜 원문을 열면 해당 사이트의 조건·정책이 적용됩니다. 베타는 무료 서버 절전·용량 제한으로 접속 지연이나 중단이 생길 수 있으며 상태를 안내합니다. 시험 기록은 개선·초기화 과정에서 변경될 수 있습니다. 법률상 인정되는 이용자 권리를 이 안내로 제한하지 않습니다.</p>'''),
        'deletion': ('계정과 데이터 삭제', f'''
<p>앱을 삭제한 뒤에도 이 웹페이지에서 계정 삭제 경로를 확인할 수 있습니다.</p>
<h2>직접 삭제</h2><ol><li><a href="/login?returnTo=%2Fsettings">웹에서 로그인하고 계정·설정 열기</a></li><li>회원탈퇴 영역에서 현재 비밀번호 입력</li><li>삭제 내용을 확인하고 회원탈퇴 실행</li></ol>
<p>이메일·닉네임·비밀번호를 사용할 수 없게 바꾸고, 세션·복구코드·소유 시험 기록을 삭제합니다. 시험 예약도 함께 철회됩니다. 백업/복구 이력 및 식별 불가능한 ID 처리 범위는 <a href="/legal/privacy">개인정보 처리방침</a>을 확인하세요.</p>
<h2>로그인할 수 없을 때</h2><p><a href="/reset">보관한 복구코드로 비밀번호 재설정</a> 후 직접 삭제할 수 있습니다. 코드를 잃었거나 삭제 중 오류가 발생하면 {contact}로 계정 이메일과 요청 내용을 보내 주세요. 비밀번호·복구코드·주민등록번호는 보내지 마세요. 운영자가 계정 주체를 확인한 뒤 처리합니다.</p>'''),
        'support': ('베타 이용·문의', f'''
<h2>시험할 수 있는 기능</h2><p>로그인 없는 탐색, 구매자/판매자 가입, 공구 참여·철회·저장, 질문·신고·차단, 시험용 쿠폰, 가상 브랜드 신청을 이용할 수 있습니다. 실제 물품 구매·결제·배송은 지원하지 않습니다.</p>
<h2>접속이 늦을 때</h2><p>무료 서버는 일정 시간 요청이 없으면 절전 상태로 들어갑니다. 첫 접속은 약 1분 걸릴 수 있습니다. 요청 실패 안내가 뜨면 잠시 뒤 다시 불러오기를 누르세요. 참여·신청 버튼을 여러 번 누르기 전에 내역에서 처리 여부를 확인하세요.</p>
<h2>오류·신고·개인정보 문의</h2><p>{contact}</p><p>발생 화면, 시간, 기기와 오류 메시지를 알려 주세요. 화면을 첨부할 때 이메일·참여코드·복구코드는 가려 주세요. 운영 주체는 Team_Wifi이며 무료 시험 서비스로 실시간 응답을 보장하지 않습니다.</p>'''),
    }
    if kind not in pages:
        raise HTTPException(404, '페이지를 찾을 수 없습니다.')
    title, body = pages[kind]
    return HTMLResponse(page(title, body), headers={'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"})
