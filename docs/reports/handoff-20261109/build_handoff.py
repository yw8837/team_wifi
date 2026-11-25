"""Build the evidence-based team review packet from preserved sources."""
from pathlib import Path
import html
import json
import shutil
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, Flowable

ROOT = Path('E:/Team_Wifi')
OUT = ROOT / 'output/handoff-20261109'
ASSETS = ROOT / 'artifacts/handoff-20261109'
SOURCE = ROOT / 'artifacts/drive-reference-20261103'
REQ = json.loads((ROOT/'docs/plans/integrated-requirements-20261107.json').read_text(encoding='utf-8'))
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('Korean', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KoreanBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Korean', normal='Korean', bold='KoreanBold')
INK = colors.HexColor('#243B45')
styles = {name: ParagraphStyle(name,fontName='KoreanBold' if name in ('title','h2') else 'Korean',
          fontSize=size,leading=leading,wordWrap='CJK',textColor=INK,spaceAfter=8)
          for name,size,leading in [('title',24,33),('h2',15,22),('body',10,16),('small',8,12)]}

def p(text, style='body'):
    return Paragraph(html.escape(text).replace('\n','<br/>'),styles[style])

def table(rows, widths):
    result=Table([[p(str(cell),'small') for cell in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EEF0')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#CAD6DA')),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    return result

def picture(path, width=190, height=410):
    result=Image(str(path)); ratio=min(width/result.imageWidth,height/result.imageHeight)
    result.drawWidth=result.imageWidth*ratio;result.drawHeight=result.imageHeight*ratio
    return result

class PhysicalERD(Flowable):
    def __init__(self):
        super().__init__()
        self.width=510
        self.height=340
    def draw(self):
        c=self.canv
        def box(x,y,w,h,title,lines):
            c.setStrokeColor(INK);c.setFillColor(colors.HexColor('#F4F7F8'));c.roundRect(x,y,w,h,7,fill=1)
            c.setFillColor(INK);c.setFont('KoreanBold',11);c.drawString(x+10,y+h-20,title)
            c.setFont('Korean',8)
            for index,line in enumerate(lines):c.drawString(x+10,y+h-39-index*14,line)
        box(5,150,220,180,'users',['PK id VARCHAR(36)','UQ email VARCHAR(254)','password_hash / nickname','is_admin / deleted / created','seller_status / points / marketing'])
        box(285,220,220,110,'tokens',['PK digest VARCHAR(64)','FK user_id → users.id','kind / expires'])
        box(285,5,220,195,'records',['PK id VARCHAR(36)','FK owner_id → users.id (nullable)','kind / parent_id / unique_key','status / data JSON / revision','counter / capacity / ends / created','UQ (kind, unique_key)','INDEX (kind, parent_id)','INDEX (kind, owner_id)'])
        box(5,5,220,105,'rate_buckets',['PK key VARCHAR(64)','count / expires','expires 인덱스 · 요청 제한'])
        c.setFont('Korean',8)
        for y,target in [(275,275),(180,130)]:
            c.line(225,y,255,y);c.line(255,y,255,target);c.line(255,target,285,target)
            c.drawString(228,y+5,'1');c.drawString(268,target+5,'N')

story=[]
story += [p('모두의 육아\n목업 대조 · ERD · 화면설계','title'),p('Team_Wifi | 이승현 · 최유정 · 최용우 | 2026년 11월 9일'),
 p('검토 기준은 11월 7일 중개방향 통합 요구사항 48개와 구성 한눈에보기다. 11월 3일 보존한 쇼핑몰 방향 목업 3개를 현재 배포 화면과 대조했다. 기존 346개 화면보드 전체를 재검수한 결과로 확대하지 않는다.'),
 p('회의에서 먼저 확인할 내용','h2'),table([
 ['항목','현재 근거와 팀 확인 사항'],
 ['서비스 방향','육아 커뮤니티와 정보 비교, 외부 판매처 공구 연결. 최신 통합본을 공동 기준으로 사용한다.'],
 ['메인','공구 정보와 인기 수요가 우선이다. 기존 목업의 배너·장바구니·결제·마일리지는 현재 화면과 다르다.'],
 ['DB','실제 SQLAlchemy 물리 테이블은 users, tokens, records, rate_buckets 4개다. 글·공구·댓글은 records.kind로 구분한다.'],
 ['화면설계','이 문서의 현행 화면은 배포 사이트 직접 캡처다. 원본 목업은 비교 자료로 표기한다.'],
 ['앱','연결된 SM-S938N에서0.6.6 확인. 카카오 인증 후 앱 복귀, 사용자 가입 완료, 로그인 홈 표시를 관찰했다.'],
 ['검증 범위','서버660·프런트366·Android51개 자동 검사 이력. 휴대폰 전체48개 수용조건 검증은 수행하지 않았다.']],[105,405]),
 p('오늘 공유할 결론','h2'),p('최신 통합본의 주요 기능은 구현·배포 근거가 있다. 목업과 화면이 동일하다는 설명은 수정해야 한다. 메뉴 변경, 실제 마감 미확인, 홈의 시각적 배치 차이를 대조표에 남기고 팀에서 화면 기준을 맞춘다.'),PageBreak()]

comparisons=[
 ('홈','001_PUB-01.png','web-home.png','main_01, groupbuy_01, demand_01',
  '원본은 검색·판매 배너·상품 이미지 카드·장바구니를 중심으로 구성된다. 현행은 판매처 공구와 관심 수요를 우선하고 검색 조건을 아래에 배치한다. 하단5개 메뉴 중 공구 수요는 후속 피드백으로 커뮤니티로 바뀌었다.',
  '팀 확인 사항 — 검색을 첫 화면에 올릴지, 실제 상품 이미지를 어디에 둘지 결정한다. 마감이 미확인인 수집 공구에 임박 문구를 붙이지 않는다. ends에 저장된 수집 유효기간과 실제 마감의 정렬 의미를 추가 점검한다.'),
 ('챗봇','100_CHAT-01.png','web-chat.png','chatbot_01, chatbot_02, a11y_01',
  '원본은 독립 대화 화면과 선물 추천 버튼을 보여준다. 현행은 하단 팝업 및 별도 대화 경로를 제공하며 Enter 전송과 Shift+Enter 줄바꿈을 지원한다. 원본의 추천 질문 버튼은 현재 팝업 첫 화면에 없다.',
  '팀 확인 사항 — 초기 질문 예시와 추천 카드의 표현을 최신 구성에 맞춘다. 검색 출처·확인 시각을 유지하며 응답 품질은 고정 질문 평가 결과로 설명한다.'),
 ('마이페이지','131_BUY-01.png','web-my.png','mypage_01, account_01, account_02, terms_01',
  '원본은 주문·마일리지·장바구니·배송지·판매자 입점을 배치한다. 현행은 공유 공구·커뮤니티 활동·관심 설정·저장·프로필·계정·정책을 제공한다. 캡처는 비회원 상태이며 회원 데이터는 로그인 후 표시된다.',
  '팀 확인 사항 — 제출 화면설계서는 현행 활동 중심 메뉴를 사용한다. 거래·정산 화면은 최신 통합본의 서비스 범위와 대조한 뒤 별도 논의한다.')]
for title,old,new,ids,delta,action in comparisons:
    story += [p(title+' 목업 대조','title'),p('연결 요구사항 '+ids,'small'),
      Table([[p('보존한 원본 목업','h2'),p('현재 배포 화면','h2')],[picture(SOURCE/old),picture(ASSETS/new)]],colWidths=[255,255]),
      p(delta),p(action),PageBreak()]

story += [p('물리 ERD','title'),p('코드 근거 backend/app/db.py · 운영 PostgreSQL / 개발 SQLite'),PhysicalERD(),
 p('관계와 제약','h2'),p('users.id는 tokens.user_id와 records.owner_id에서 외래키로 참조한다. records.parent_id는 다형 참조 문자열이며 DB 외래키 제약이 없다. API의 종류·공개 상태·소유권 검사와 삭제 정리 로직이 참조 무결성을 처리한다.'),
 p('JSON에는 종류별 필드를 저장한다. 문서상의 글·댓글·공구 논리 엔터티를 별도 물리 테이블로 설명하지 않는다. rate_buckets는 요청 제한을 위한 독립 테이블이다. users의 일부 판매·포인트 필드는 기존 모델에 남아 있으나 현재 공개 거래 제공 근거로 사용하지 않는다.'),PageBreak()]

story += [p('논리 데이터 관계와 API','title'),table([
 ['records.kind','주요 관계와 내용'],
 ['release_groupbuy','owner_id → 공유자. 판매처 URL·가격·배송비·출처·실제 마감 또는 수집 유효기간을 관리한다.'],
 ['release_demand','owner_id → 작성자. post_type으로 질문·경험·정보·수요를 구분. data.groupbuy_id로 공구를 연결한다.'],
 ['release_comment','owner_id → 작성자. parent_id → 수요/게시글 또는 공구. body와 수정 시각을 저장한다.'],
 ['release_interest','owner_id → 회원. parent_id → 공구 수요. 계정별 중복 관심을 제한한다.'],
 ['release_save','owner_id → 회원. 공개 육아템의 식별자를 연결한다. 제공 카탈로그의 자료와 함께 조회한다.'],
 ['release_report / release_notice','신고 대상·사유·처리 상태 및 회원 알림. 작성자·운영자 권한을 검사한다.'],
 ['소셜 인증 / 세션','소셜 연결은 provider·subject로 식별한다. 로그인 세션은 tokens의 digest로 조회하며 만료를 검사한다.'],
 ['감사·활동 측정','운영 조치와 동의 기반 활동을 기록한다. 공개 응답은 허용한 필드만 직렬화한다.']],[135,375]),
 p('동기화 동선','h2'),p('Android 앱 / 웹 → 같은 HTTPS API → 인증·소유권 검증 → 같은 PostgreSQL. 서버에 저장되는 글·댓글·관심·설정은 계정 기준으로 공유된다. 화면에서 직접 입력한 단가 비교값은 로컬 계산이다.'),
 p('스토어 공개 상태','h2'),p('0.6.6(code16)은 Google Play 프로덕션에서2026-11-09 오전2:07 공개 완료로 확인했다. 제공 국가는 대한민국이며 정식 상세 페이지에 새 출시 노트와 설치 버튼이 표시된다.'),p('주요 경로','h2'),p('공구 /api/release/groupbuys\n게시판 /api/release/demands\n공구 댓글 /api/release/groupbuys/{id}/comments\n댓글 수정·삭제 /api/release/comments/{id}\n내 활동 /api/release/activity'),PageBreak()]

screens=[('커뮤니티 게시판','web-community.png','/demands','demand_01~05, comment_01','질문·경험·정보·수요 탭, 검색·기간 조건, 글 목록. 공개 읽기와 회원 작성 권한을 구분한다. 화면 예시에는 시연 콘텐츠가 포함된다.'),
 ('공구 상세 댓글','../community-20261109/mobile-comments.png','/groupbuys/{id}','groupbuy_02, comment_01','공구별 질문·경험 댓글. 비회원은 읽고 로그인 후 작성한다. 본인 수정·삭제 및 신고·차단을 제공한다.'),
 ('단가 비교','web-calculator.png','/calculator','price_01','상품 총액·배송비·수량으로 계산한다. 두 상품은 동일 단위로 입력하며 빈 값·0수량·음수 입력을 검사한다.')]
for title,img,route,ids,description in screens:
    story += [p(title+' 화면설계','title'),p(route+' · '+ids,'small'),picture(ASSETS/img,240,480),Spacer(1,12),p(description),
      p('확인 기준 — 현재 공개 웹, 모바일390×844. 저장·삭제·신고 등 실제 회원 행동은 권한·오류·중복 요청 검사 근거와 함께 검토한다.','small'),PageBreak()]

story += [p('실제 휴대폰 확인','title'),p('Samsung SM-S938N · Android 앱0.6.6(code16)'),
 picture(ASSETS/'device-home.png',220,450),p('ADB cold launch TotalTime204ms, WaitTime205ms. 이 값은 네이티브 Activity 기동 시간이다. 서버 자료가 전부 표시되는 시간으로 해석하지 않는다.'),
 p('사용자가 카카오 인증을 수행한 뒤 앱의 가입 화면으로 복귀했다. 사용자 직접 닉네임·동의를 확인한 뒤 로그인된 홈이 표시되는 것을 관찰했다. 개인 식별이 담긴 로그인 후 캡처는 공개 제출 패킷에서 제외했다.'),
 p('휴대폰의 저장·댓글 작성과 웹 재조회 간 왕복 동기화는 이번 관찰에서 아직 실행하지 않았다. 기존 자동 검사 및 동일DB 구조와 실기기 성공 관찰을 각각 기록한다.'),PageBreak()]

story += [p('48개 요구사항 대조 인덱스','title'),p('원문은 2026-11-07 통합본이다. 이 표는 검토 위치를 찾는 인덱스이며, 이번48개 실기기 전수 합격표로 사용하지 않는다. 상세 수용조건은 함께 제공한 원본 Excel을 따른다.')]
mapping={'signup':'로그인·가입','login':'로그인·가입','logout':'계정 관리','recovery':'계정 관리','mypage':'마이페이지','account':'계정 관리','main':'홈','groupbuy':'공구 목록·상세','demand':'커뮤니티','comment':'게시글·공구 댓글','item':'육아템 정보','save':'저장','price':'단가 비교','detail':'육아템 상세','interest':'관심 설정','report':'신고·차단','consent':'분석 동의','rule':'이용 안내','broker':'중개 고지','finder':'육아템 찾기','chatbot':'챗봇·평가','admin':'운영자','admreport':'신고 관리','admgroupbuy':'공구 검토','insight':'분석','analytics':'측정','terms':'약관·정책','guide':'공개 가이드','seo':'공개 페이지','state':'공통 상태','auth':'공통 권한','time':'공통 일시','a11y':'공통 접근성'}
rows=[['요구사항','기능 / 원문 담당','대조 결과와 확인 위치']]
md=['# 목업·요구사항 대조 결과','', '기준 2026-11-07 중개방향 통합본48개 / 확인2026-11-09','', '## 직접 확인한 차이','']
for title,old,new,ids,delta,action in comparisons:md += ['### '+title,'',delta,'',action,'']
md += ['## 요구사항 검토 인덱스','','| ID | 기능 | 확인 위치 | 이번 대조 메모 |','|---|---|---|---|']
for r in REQ['requirements']:
    key=r['id'].split('_')[0];where=mapping.get(key,'관련 화면·API')
    note='기존 구현·회귀 검사 이력. 이번 실기기 전수 확인은 별도.'
    if r['id']=='main_01':note='원문 대비 메뉴명 변경. 실제 마감 미확인 자료와 검색 위치 대조 필요.'
    if r['id']=='groupbuy_01':note='수집 유효기간과 실제 모집 마감의 정렬 의미를 추가 점검.'
    if r['id']=='comment_01':note='공구 상세 댓글까지 확대. 웹 캡처·서버 회귀 검사 확인.'
    if r['id']=='signup_01':note='실기기 카카오 인증 복귀·사용자 가입 완료·로그인 홈 관찰.'
    rows.append([r['id'],r['name']+' / '+(r.get('source_assignee') or '미지정'),where+'\n'+note])
    md.append('|'+r['id']+'|'+r['name']+'|'+where+'|'+note+'|')
story += [table(rows,[83,167,260]),Spacer(1,12),p('근거와 전달 범위','h2'),p('배포 웹 https://moduyuga.yeolmaeapps.kr\n원본 요구사항·구성표는 사용자 제공 Excel을 그대로 동봉한다. 현재 DB 설계는 backend/app/db.py, 커뮤니티는 release.py·groupbuys.py, 화면은 frontend/src의 현행 구현을 기준으로 작성했다. 스토어 공개 상태는 확인 시점의 Google Play Console 기록을 별도로 따른다.')]

def footer(canvas,doc):
    canvas.setFont('Korean',8);canvas.setFillColor(INK)
    canvas.drawString(42,25,'Team_Wifi · 모두의 육아 · 2026-11-09')
    canvas.drawRightString(A4[0]-42,25,str(doc.page))

SimpleDocTemplate(str(OUT/'모두의육아_목업대조_ERD_화면설계.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=44).build(story,onFirstPage=footer,onLaterPages=footer)
(OUT/'목업_요구사항_대조표.md').write_text('\n'.join(md),encoding='utf-8')
shutil.copyfile(OUT/'목업_요구사항_대조표.md',Path(__file__).with_name('COMPARISON.md'))
shutil.copyfile(ROOT/'artifacts/requirements-20261107/requirements.xlsx',OUT/'요구사항정의서_중개방향_통합본.xlsx')
shutil.copyfile(ROOT/'artifacts/requirements-20261107/overview.xlsx',OUT/'모두의육아_구성_한눈에보기.xlsx')
(OUT/'팀_공유문구.txt').write_text('승현님 공유해주신 중개방향 통합 요구사항48개를 기준으로 기존 목업과 현행 웹을 대조했습니다. 첨부에 실제 물리 ERD, 논리 데이터 관계, 사이트 캡처 기반 화면설계, 요구사항별 대조 인덱스를 묶었습니다. 홈 검색 위치·상품 이미지·메뉴명과 챗봇 초기 질문 예시는 원본과 차이가 있어 팀 확인 항목으로 적었습니다. 실기기에서는0.6.6 실행과 카카오 가입 후 홈 복귀를 확인했습니다. 원본 Excel 두 파일도 함께 첨부합니다.',encoding='utf-8')
print('HANDOFF_PDF_CREATED')
