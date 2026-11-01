# Android 외부 베타 구현 계획

## Global Constraints

- 정식 명칭: 모두의 육아 - 육아템 공동구매,핫딜. 심볼/워드마크는 전달받은 원본 유지.
- 로그인 없이 공개 탐색. 소유 행동만 로그인. 로그인 후 원래 화면/수량 복귀, 자동 참여 없음.
- 실결제/실배송 없는 비공개 베타. 포인트·쿠폰도 시험용. 출시 완성으로 주장하지 않는다.
- 기존 기획·데이터 분석·다른 서비스 보존. 메일 발송·Elice·main merge·비밀 커밋 금지.
- 기존 codex/modu-yuga worktree 사용. 공유 파일 되돌림 금지. 전용 클라우드 자원만.
- 사용자 확정: 유료 사용 불가. 결제수단 추가·유료 전환·과금형 인프라 배포 금지. Render Free(기존 카드 없는 계정)와 Neon Free 전용 DB를 준비하며 신규 OAuth 권한은 사용자 확인 후 연결.

## Task 1: 베타 프런트 인증과 이용안내

소유 파일: frontend/src/**, frontend/vite.config.ts. Android/config/package/서버/공용문서는 변경하지 않는다.

공개 환경 API 계약:
- VITE_BETA_MODE=1 빌드에서 베타 UX. VITE_API_BASE_URL은 확정 HTTPS API 주소. 개발 기본 동작 보존.
- POST /auth/register: 기존 payload + invite_code(string), adult_confirmed(boolean). beta는 둘 다 필수. 성공 시 기존 access_token,user + recovery_code (한 번만 표시). 복구코드를 기록하고 확인한 뒤 원래 화면으로 이동한다. 코드·비밀번호는 로그/localStorage에 보존하지 않는다.
- POST /auth/recover: {email,recovery_code,password}; 결과 {message,recovery_code}. 기존 세션 전체 폐기, 복구코드 회전. 새 코드를 확인하고 로그인으로 이동한다. 베타에서는 outbox/메일 발송 UI를 대체한다.
- GET /api/config: {mode, invite_required, payments_enabled:false,seller_real_data_enabled:false, legal:{privacy:'/legal/privacy',terms:'/legal/terms',deletion:'/legal/deletion',support:'/legal/support'}}. 법률 페이지는 API_BASE에서 /api를 뺀 서버 origin에 제공된다. 앱에서 링크 열기 가능.
- 베타 판매자 신청은 가상 정보만: POST /seller/application/beta {brand_name,brand_description,seller_terms_accepted}; 서버가 가상 사업자 fixture 채우고 draft 반환. 기존 submit endpoint로 심사 요청. 실제 전화·사업자번호·주소 입력 UI는 beta에서 제공하지 않는다. 비beta 기존 기능 보존.
- POST /reports target_type에 user 추가, target_id는 작성자 ID. 기존 공구/질문 신고 보존.

해야 할 일:
1. 베타 초대코드·18세 이상 확인·복구코드 UX·복구 플로. 약관/개인정보/삭제/지원 링크를 가입·마이에서 찾기 쉽게 제공.
2. 베타 전역 안내/실결제 없음 정확한 문구. 실제 사업자 민감정보 입력을 막는 별도 beta seller form. 게스트 탐색 회귀 보존.
3. API 오류에서 개발 서버 문구 제거. fetch 시간 제한 및 중복 재시도 자동실행 금지. 세션 만료 후 guest 공개 GET은 탐색 유지하도록 개선하되 계정 액션은 로그인 요청.
4. CSP connect-src는 설정된 API origin만 추가. beta 빌드는 HTTPS API가 없거나 localhost면 fail closed. 로컬 debug는 기존 10.0.2.2 허용 유지.
5. 의미 있는 단위 테스트·TypeScript build. 320px에서도 복구코드 줄바꿈·확인 UI 가독성. 최종 보고에 수정 파일/검증/남은 조건.

## Task 2: 서버·운영

메인이 소유: backend/**, Dockerfile/인프라 설정, scripts/**, docs/build/**, .gitignore.
초대코드 단회/만료/동시성, 복구코드 회전, 서버 입력 제한·검증/데이터 삭제·설정 fail closed, 전용 PostgreSQL/HTTPS 배포, 공개 정책 페이지, 검증.

## Task 3: Android·배포·통합 검증

Task1/2 검토 후 release 서명·AAB/APK·기기 실행·Play 내부 테스트·테스터 링크·Git/CI. 운영 비용/약관은 필요한 시점에 구체적으로 확인한다.

## 사전 인터페이스 검토

| 대상 | 일치 여부 및 결정 |
|---|---|
| Task1 자체 | 개발모드 보존과 beta 별도 분기. 실제 이메일 발송 미구성 상태를 복구코드로 명시적 해결. |
| Task2 자체 | PostgreSQL 전용 beta, 초기 공개 데이터는 가상 fixture이며 실제 공급 주장 없음. |
| Task3 자체 | 서명 APK 생성과 설치 검증/Play 배포를 별도 조건으로 유지. |
| Task1↔2 | 위 API 계약 사용. 코드 공유 없음. config와 /legal 정적 서버 페이지로 문구 연결. |
| Task1↔3 | VITE_BETA_MODE=1 + HTTPS API로 웹 빌드 후 Android 패키징. |
| Task2↔3 | 실제 배포 URL 확정 이후 release 생성. 미승인 유료 자원 생성 금지. |
