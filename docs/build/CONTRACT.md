# 모두육아 첫 개발 빌드 계약 · 2026-11-01

사용자 승인: 앱을 지금 구현. 쿠팡/11번가/네이버스토어/당근/알리/중개서비스 벤치마크, 디자인보다 UX. 구매자·판매자 가입 투트랙과 상세 권한. 브랜드관·마일리지/쿠폰·육아 핫딜 모음·BM 계획 추가.

## 범위와 분담

- 메인: `backend/**`, `scripts/**`, 통합 E2E, Android 빌드/설치, 문서와 증거. frontend 워커 작업 종료 전 해당 파일 수정 금지.
- 프런트 워커: `frontend/**`만. React+TypeScript+Vite+React Router+Capacitor Android 준비. 디자인 토큰/기본 CSS, 44px 터치, 한 열 양식. 서버 모킹으로 구현 완료를 주장하지 말 것.
- 읽기 전용 조사: 지정한 benchmark 메모만. 팀원 R&R 배정 아님.
- 기존 기획서 및 원래 D:/파이널프로젝트 작업폴더 보존. 소스는 이 분리 worktree. 새 사용자 계정·계약·메일·Elice·외부 게시/Play 제출 없음.

## 개발 환경

FastAPI + SQLAlchemy. 로컬 SQLite, `DATABASE_URL`로 PostgreSQL 설정 가능. 별도 외부 DB를 생성하지 않는다. 인증은 서버에서 Argon2 해시와 폐기 가능한 opaque 세션으로 실제 구현. Supabase/OAuth/SMTP 계정 미설정이므로 이번 빌드에서 외부 소셜 인증·메일 인증을 구현했다고 표시하지 않는다. 존재하지 않는 소셜 로그인 버튼은 넣지 않는다. 최초 빌드는 개발용 데이터/거래 화면임을 상단에 명시. 실제 결제·외부 쿠폰 적용·본인/사업자 인증 완료 아님.

웹: 127.0.0.1:5173 (Vite /api proxy → 127.0.0.1:8000). Android 패키지의 API는 `VITE_API_BASE_URL=http://10.0.2.2:8000/api`로 debug emulator에 연결. 배포 서버 URL이 없는 로컬 개발 APK이며 유료/실거래 배포 아님. webDir=dist, appId=kr.moduyuga.app. 네이티브 플랫폼 생성/빌드/설치는 메인이 수행한다. frontend는 capacitor.config.ts와 package deps만 준비한다.

## UX

첫 진입: 짧은 서비스 설명, '육아템 둘러보기' 우선, '구매자로 시작', '판매자로 입점', 기존회원 로그인. 소개는 한번만, 다시 설정에서 접근. 비회원도 탐색/검색/카테고리/브랜드/상세/핫딜 이용 가능. 저장/참여/쿠폰받기는 로그인 후 원래 안전한 내부 경로로 돌아가고 자동 구매/참여하지 않는다. 상세의 기존 선택은 보존. 로그인실패/오프라인 때 입력 유지, 전송중 중복 클릭 차단, 오류 focus/aria-live. 가입창의 role 선택을 보안 권한으로 신뢰하지 않는다.

탭: 홈(공동구매), 핫딜 모음(육아만), 브랜드관, 내 혜택, 마이. 저장/참여 목록 마이에서. 글/질문·신고·차단은 상세와 내설정. 회원탈퇴/로그아웃 명확. 판매자센터 별도 경로. 판매자는 구매자 기능도 이용하지만 자기 공구 참여는 거절. 판매자 draft/pending/needs_changes/approved/suspended 표시와 보완사유. 승인전 공구게시/쿠폰발행 불가. 관리자 메뉴는 is_admin일 때만 보이나 서버도 검사.

구매자가입: 이메일, 비밀번호(10~128자), 닉네임(2~30), 필수 이용약관/개인정보 동의 분리, 선택 마케팅 미체크. seller track도 같은 계정 만든 후 단계별 사업정보→운영조건 입력/저장→신청. 구매자 계정에서 나중에 입점신청 가능. 비밀번호 토글/자동완성/붙여넣기 허용. 비밀번호분실은 실제 로컬개발용 복구 요청/토큰 입력 흐름 제공, 메일발송을 거짓표시하지 않음.

## API 인터페이스 (모든 경로 /api 아래)

JSON 에러: {detail:"한국어 메시지"}, Pydantic422 detail배열도 폼에 표시. Bearer access_token 사용. client token은 sessionStorage(탭/앱 세션)만, 장기기억/보안저장 완료 주장 금지. 401 시 제거하고 안전한 복귀경로 보존. 로그인/가입 응답 {access_token,token_type:"bearer",user}; /me는 user. user={id,email,nickname,is_admin,seller_status:null|draft|pending|needs_changes|approved|suspended,points_balance,email_verified:false}. 날짜는 UTC ISO, UI Asia/Seoul 표시. ID는 string. money 정수원. GET 리스트={items:[...]}.

Auth:
- POST /auth/register {email,password,nickname,track,terms_accepted,privacy_accepted,marketing_opt_in}
- POST /auth/login {email,password}; GET /me; POST /auth/logout; DELETE /me {password} (프로필 익명화/세션폐기, 미완료 모집철회; seller live campaign 있으면 먼저종료 안내)
- POST /auth/reset-request {email} → {message}; POST /auth/reset {token,password} → {message}. 개발용 토큰은 서버의 로컬 outbox 파일에서만 조회, 응답에 노출하지 않음.

Catalog:
- GET /campaigns?q=&category=&brand_id= → items. GET /campaigns/{id} → campaign
- campaign={id,brand_id,title,description,category,kind:"group_buy"|"hotdeal",price,shipping_fee,unit,minimum_quantity,stock,reserved_quantity,ends_at,status:"draft"|"pending"|"active"|"ended"|"rejected",revision,is_demo,brand_name,seller_name,refund_policy,shipping_policy,source_url:null|string,verified_at,saved:boolean?}. pricing is item+shipping, no fake savings.
- GET /brands → items {id,name,description,logo_text}; GET /brands/{id} → {brand,campaigns:[]}
- GET /hotdeals?category=&q= → items {id,title,category,price,shipping_fee,seller_name,source_url,source_name,verified_at,ends_at,status:"active"|"ended"|"stale",is_demo}. No scraping arbitrary URLs. Safe https source link clearly external; testdata source_url=null disables purchase link with explanation.
- PUT /saved/{campaign_id}; DELETE /saved/{campaign_id}; GET /saved → campaign items
- POST /campaigns/{id}/reservations {quantity,revision} → reservation {id,campaign_id,title,quantity,status:"active"|"withdrawn",created_at}; GET /reservations → items; POST /reservations/{id}/withdraw. Participation is NOT paid order; show this before confirm. Server capacity/deadline/revision/owner checks.

Seller:
- GET /seller/application → {status,review_note,fields:{...}} (no record means status:draft fields:{})
- PUT /seller/application {business_name,business_number,representative,contact_phone,contact_email,business_address,return_address,commerce_number,commerce_exempt_reason,shipping_policy,refund_policy,brand_name,brand_description,seller_terms_accepted}. All fields strings except bool; save allows partial, submit validates required/checksum/terms. Either commerce_number or exemption reason.
- POST /seller/application/submit → application. pending locks edit; needs_changes enables edit/resubmit. approved business identity not editable through this path.
- GET /seller/campaigns → items; POST /seller/campaigns {title,description,category,price,shipping_fee,unit,minimum_quantity,stock,ends_at} → campaign draft; POST /seller/campaigns/{id}/submit → pending; POST /seller/campaigns/{id}/end → ended. Owner and approved status required, draft/pending not public.
- GET /seller/reservations → only own campaign items {id,campaign_id,title,quantity,status,buyer_alias}; no buyer email/address disclosure.
- POST /seller/coupons {title,amount,min_spend,stock,ends_at,points_cost:0} → coupon. Only approved seller, own brand. No client-defined user/brand owner bypass.

Benefits:
- GET /coupons → items {id,brand_id,brand_name,title,amount,min_spend,stock,issued_count,ends_at,points_cost,claimed:boolean,is_demo:true}
- POST /coupons/{id}/claim → owned coupon; unique claim & atomic stock/points debit. GET /wallet → {balance,ledger: [{id,delta,reason,created_at}],coupons:[{id,coupon_id,code,title,brand_name,amount,min_spend,ends_at,status:"available"|"used"|"expired",is_demo:true}]}. Redemption code is local demo only; no real store applicability promised.
- Points earned only via admin-verified demo external orders, not client events. No user arbitrary earn endpoint. Refund reverses original grant once; may leave negative points if spent, no additional redemption then. No cash withdrawal/transfer.

Community:
- GET /campaigns/{id}/questions → items {id,author_id,author_name,body,created_at}; POST ... {body}; POST /reports {target_type:"question"|"campaign",target_id,reason}; POST /blocks/{user_id}. Blocked authors excluded from authenticated question lists. Posts require user. User cannot set author_id.

Admin:
- GET /admin/applications → items {user_id,nickname,status,fields,review_note}; POST /admin/applications/{user_id}/review {decision:"approved"|"needs_changes"|"suspended",note}
- GET /admin/campaigns → items; POST /admin/campaigns/{id}/review {decision:"active"|"rejected",note}
- GET /admin/reports → items; POST /admin/reports/{id}/resolve {action:"hide"|"dismiss"}
- POST /admin/orders {user_id,campaign_id,external_reference,eligible_amount,status:"confirmed"} → order; POST /admin/orders/{id}/refund → order. 1% points eligible_amount//100; unique reference; no live selleraccount proof implied.

## Acceptance

Meaningful pytest: role escalation, pending seller forbidden, seller A/B isolation, sensitive data not public, coupon doubleclaim/cap/points, no arbitrary points, order/refund replay, withdrawal/capacity/revision/deadline, logout/deletion revocation, login failure and reset token one-use. E2E real API: guest→detail→buyer signup→return→participate→withdraw; seller signup→draft/save→submit→admin approve→create/submit→admin publish→visible brand; coupon claim→wallet persistence; curated feed distinct; error/loading/back behavior. Production React build and Android debug APK must actually build. Emulator install/launch and screenshot if system image boots. No passing claims for unexecuted steps.
