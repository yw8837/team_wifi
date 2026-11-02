# 마이페이지·정책 안내와 정식 웹 주소

2026-11-02. 사용자 요청: 안내 내용뿐 아니라 배치도 정리하고, 출시할 이름에 beta/test/MVP 꼬리표를 붙이지 않는다. 무료 서비스만 사용한다.

## 화면과 내용

- 마이페이지: 프로필, 내 활동·계정, 도움말, 하단 정책 메뉴 순서. 약관 전문을 주 활동 메뉴와 같은 비중으로 나열하지 않는다.
- `/my/policies`: 비회원도 접근하는 약관·개인정보·삭제 안내 모음. 새 탭 이동을 명시한다.
- 정책 문서: 핵심 안내, 접는 모바일 목차, 번호가 있는 본문, 문의, 다른 정책 순서. 원래 공개 URL 네 개를 유지한다.
- 계정 삭제: 실제 UI의 ‘계정 삭제 진행 → 현재 비밀번호·확인 → 계정 영구 삭제’와 기존 앱의 메뉴명을 함께 안내한다. 앱 제거와 계정 삭제, 개별 기록 삭제, 연관 댓글 삭제, 남는 임의 ID/제공자 복구 이력을 구분한다.
- 아직 없는 실제 주문·결제·배송·판매자 입점을 약속하지 않는다. 국외 처리 위치는 설정값을 HTML escape해 표시한다. 정책 내용은 실행 코드에 맞춘 안내이며 법률 적합성 인증을 의미하지 않는다.
- `ui-ux-pro-max`: 메뉴 위계·터치 영역·반응형 문서. `game-ui-ux`: 화면 이동 포커스, 안전 영역, 상태별 터치 피드백을 적용했다. 엔진·게임패드 기능은 이 웹 앱의 범위가 아니다.
- `humanize-korean`은 기존 약관의 문장만 별도 점검했다. light, 변경률 0%, 게이트 통과. 원문의 번역투보다 누락된 이용 절차와 정보 구조가 문제였으므로 구조·기능 설명은 별도 편집했다. 원문과 결과는 `_workspace/2026-11-02-001-7150/`에 로컬 보존한다.

## 웹·앱 연결과 주소 원칙

- 기존 API 서비스 ID `srv-dbjj7hc9v7es73a8uvk0`와 Neon DB를 유지한다. Play 심사에 제출한 code 4가 사용하는 기존 API 주소를 끊지 않는다.
- Render 서비스 이름 변경만으로 기존 `onrender.com` 주소는 바뀌지 않았다. API 서비스 표시 이름은 `moduyuga-api`로 정리했다.
- 무료 정적 웹을 별도 배포하는 설정을 추가했다. 계정 DB를 새로 만들거나 복제하지 않는다. 정적 웹에는 DB 비밀번호·서명키·API 비밀키를 넣지 않는다.
- `PUBLIC_WEB_ORIGIN`은 명시적인 HTTPS 웹 원점 한 개를 API CORS에 추가한다. 와일드카드·자격증명 포함 URL·경로·쿼리를 허용하지 않는다. 웹에서 토큰이 생겼다고 Android에 자동 로그인되는 것은 아니며, 각 클라이언트에서 같은 계정으로 로그인한다.
- 정적 웹의 정책 네 개는 서버와 같은 Python 템플릿에서 생성한다. `scripts/export-public-policies.py`는 DB를 사용하지 않는다. 정식 웹 주소는 **https://moduyuga.onrender.com**이며 실제 배포·접속을 확인했다.
- `VITE_PUBLIC_WEB_ORIGIN`을 지정한 웹/앱은 정책을 정식 웹에서 연다. HTTPS API 검사는 유지한다.
- Android App Links(공유 링크 → 설치 앱의 해당 화면)는 현재 구현되지 않았다. 계정·데이터 공유와 링크 기반 앱 실행을 혼동하지 않는다.

## 검증 기록

- 서버 전체 81개 통과. Starlette/httpx 사용 중단 예정 경고 1건은 기존 의존성 경고다.
- 프런트 142개 통과 후 화면 이동/웹 원점 변경을 추가했다. 후속 전체 실행에서 1개가 외장 드라이브 지연으로 5초 제한을 초과했고, 별도 단일 worker·15초 제한에서 전체 142개가 통과했다(11.2초). 논리 실패 없이 동일 테스트를 완료했다.
- 공개 웹 빌드 성공. 로컬 실제 브라우저에서 비회원 My 진입, 계정 접근 보호, 시험 계정 로그인 후 계정 관리 복귀, 정책 목차 펼침과 앵커 이동을 확인했다.
- 390×844px에서 My 메뉴 높이 83px 이상, 가로 넘침 없음. 정책 화면은 핵심 안내를 목차보다 먼저 배치했다. 브라우저 결과이며 Android 실기기 결과가 아니다.
- 초기 0.3.1(code 5) 서명 APK/AAB 및 오프라인 검사 43개 통과: `artifacts/android/releases/5-0.3.1/`. 이후 정식 명칭/웹 원점 변경 전의 중간 산출물이며 최종 제출물로 쓰지 않는다. 기존 code 4 산출물은 보존했다.
- 원본 화면과 수정 화면 증거: `artifacts/mypage-20261102/` (로컬). 로컬 UI 확인에는 별도 SQLite 시험 DB만 사용했다.

Google Play에는 현재 code 4가 심사 중이다. 이 수정의 신규 APK/AAB 빌드, 웹 운영 반영, Play 제출은 각각 구분해서 기록한다. C: 원본 보존, 이번 삭제량 0 bytes. 당시 설정한 이전 coordinator hold는 아래 후속 검증 완료 후 해제했다.

## 운영 반영 완료 — 2026-11-02 13:52 KST

- 무료 정적 웹 `moduyuga`, 서비스 ID `srv-dbk1ajnb9u1s73fb09qg`: `01f7ea9a658ba826623b1a842387f05c021aa618`, 배포 `dep-dbk1bd5g1s2s738gh660` Live. 도메인 구매·카드 등록·새 DB 생성 없이 Render 기본 주소를 사용했다.
- 기존 API `moduyuga-api`: `eb21fce7188670625661fa4ecedd9adcaf48ed69`, 배포 `dep-dbk1b0vlk1mc73aiae20` Live. 이후 `01f7ea9`는 CI/검증 스크립트 변경뿐이다. 기존 주소와 DB는 code 4 호환성을 위해 유지한다.
- API의 `PUBLIC_WEB_ORIGIN`, 기존 웹 빌드의 `VITE_PUBLIC_WEB_ORIGIN`을 정식 웹 주소로 지정했다. 정적 사이트에는 공개 설정만 저장했다. 서비스 자동 배포는 Off이며 검증한 커밋을 수동 배포한다.
- Render는 SPA 포괄 rewrite가 정책의 디렉터리 URL도 처리하므로 `/legal/:kind → /legal/:kind/index.html`을 `/* → /index.html`보다 앞에 두었다. 보안 헤더 nosniff, DENY, strict-origin-when-cross-origin을 설정했다. 이 실제 설정을 `render.yaml`에도 기록했다.
- 운영 브라우저에서 비회원 육아 정보 목록 → 마이페이지 → 약관 및 정책 → 개인정보 처리방침을 확인했다. 네 문서 모두 HTTP 200과 각 문서 제목/본문을 확인했다. 정책 모음과 마이페이지 직접 접근도 정상이다.
- CORS preflight: 정식 웹 원점은 200 및 정확한 Allow-Origin, 허용하지 않은 원점은 400이고 Allow-Origin 없음. 운영 로그인을 새로 수행하거나 사용자 데이터를 수정하지 않았다. 동일 계정/데이터를 사용하도록 같은 API를 연결했고, 로그인 후 계정 화면은 앞서 분리된 로컬 DB로 확인했다.
- 375×812, 가로 약 844×390, 1280×800에서 가로 넘침을 확인하지 못했다. 화면 이동 후 main 포커스, Tab으로 돌아가기 링크 선택, Enter 복귀를 확인했다. Android 실기기 검증은 별도다.
- 최종 화면 증거: `artifacts/mypage-20261102/after-my-mobile-final.png`, `after-privacy-mobile-final.png`, `policy-hub-desktop-final.png`. 운영 응답 기록: `live-web-verification.json`. 이전 after-my-mobile.jpg는 중간 화면이므로 최종 결과로 사용하지 않는다.
- GitHub Actions [41390331304](https://github.com/yw8837/team_wifi/actions/runs/41390331304): `01f7ea9`의 api, ui, unsigned-android 모두 성공. 서버 81개·프런트 142개 검사와 PostgreSQL 검증, npm audit 및 Android 빌드 포함.

## 정식 주소 반영 시점의 서명 Android 산출물

- 버전 **0.3.1 / code 5**, 소스 `01f7ea9`의 앱 코드, 기존 업로드 인증서 유지. E의 Node/JDK/SDK와 E Gradle 캐시에서 명령행 빌드 성공. 최종 디렉터리 `artifacts/android/releases/5-0.3.1-final/`.
- `moduyuga.aab`: 3,258,096 bytes, SHA256 `e6f60be6c8a3c26eff595da50946f27ba4cb836009615f95f2fa01dece0305da`.
- `moduyuga.apk`: 3,414,821 bytes, SHA256 `dafde7267c6ce1f28a96caca20e66a328c4c1b2e6d6f1d00282a1f40e2c8e602`.
- 오프라인 검증 **45개 통과**: APK/AAB 서명, 기존 인증서, 패키지/앱 이름/버전, API 36, 위험 권한 없음, HTTPS API, 정식 정책 원점, 실제 번들 HTML/JS/CSS 일치. 증거 `artifacts/mypage-20261102/android-final/android-release-verification.json`.
- 이 code 5는 이번 작업에서 Play에 올리지 않았다. 현재 code 4 심사와 신규 빌드 완료를 구분한다. 설치된 앱의 화면 변경에는 앱 업데이트가 필요하며, 서버에서 제공하는 기존 정책 URL에는 새 내용이 반영됐다.
- 무료 API는 유휴 후 첫 연결 지연이 있을 수 있다. Android App Links, 실기기 0.3.1 실행, Play의 계정 유지형 데이터 삭제 선택 답변 갱신은 이 완료 범위에 포함하지 않는다.

## 초기 연결 개선·육아템 표기와 데이터 공유 검증 — 2026-11-02 14:43 KST

- 사용자가 운영 웹에서 연결 오류를 확인했다. 프런트의 기존 모든 요청 제한은 15초였고, Render Free UI는 유휴 후 기동에 50초 이상 걸릴 수 있다고 안내한다. 조사 시 API 응답은 200(0.617초)이었고 브라우저 재시도로 목록이 복구됐다. 원래 실패 요청의 서버 기동 추적은 확보하지 못했으므로 그 한 번의 실패 원인을 절전으로 확정하지 않는다.
- 초기 `GET /config`만 전체 90초 한도 안에서 최대 3회 시도한다. 네트워크 오류와 502/503/504에만 1.5초·3초 간격으로 재시도한다. 쓰기 요청은 자동 재전송하지 않으며 기존 15초 제한을 유지한다.
- 10초 이상 대기하면 연결 지연과 자동 진행 안내, 도움말을 제공한다. 55초 지연 응답 성공, 일시 503/네트워크 오류 복구, 전체 90초 제한, 쓰기 요청 재시도 금지를 자동 검사했다. 실제 유휴 15분 후 재기동 시험은 수행하지 않았다. Render 절전 정책을 없앤 변경이 아니므로 상시 즉시 응답이나 무중단을 보장하지 않는다.
- 홈·검색·탐색·저장 메뉴의 사용자 노출 명칭을 ‘육아템’으로 정리했다. 정책의 기능 설명도 같은 표현을 사용하며 기존 앱의 계정 삭제 안내 호환성은 유지한다.
- 웹과 앱은 기존 API/DB를 공유한다. 별개 로그인 토큰의 동일 계정이 저장/저장 해제와 게시글 소유권을 공유하고 다른 계정은 소유자로 취급되지 않는 서버 검사를 추가했다. 로그인 상태는 클라이언트별이며 다른 화면의 변경은 데이터를 다시 읽을 때 반영된다. 푸시 동기화나 Android App Links 구현을 뜻하지 않는다.
- 소스 `49cfbcbf463b003cd130e3c42c5c350cf1d8f0b3` 커밋·푸시 완료. [CI 41395192059](https://github.com/yw8837/team_wifi/actions/runs/41395192059)의 api/ui/unsigned-android 모두 성공: 서버 82개, 프런트 146개 통과. E 로컬 데이터 파이프라인 검증도 통과했다.
- 정적 웹 배포 `dep-dbk23s3bc2fs73e6kukg`와 API 배포 `dep-dbk23q0u01pc738r4v70` 모두 같은 소스 `49cfbcb`로 Live. 운영 브라우저에서 초기 연결 안내가 목록으로 전환되고 육아템 검색·하단 메뉴가 표시되는 것을 확인했다. 화면 증거: `artifacts/mypage-20261102/connection-fixed-home.png`.

### 현재 최신 서명 Android 산출물

- 0.3.1(code 5), `artifacts/android/releases/5-0.3.1-connection/`. 앞의 `5-0.3.1-final`은 당시 검증 산출물로 보존하며 새 제출에는 이 최신 연결 개선본을 사용한다.
- `moduyuga.aab`: 3,258,411 bytes, SHA256 `cacff993eeccd5bb45e51bb94f5d294e8d4bb28a48ad029109ad062728e4caab`.
- `moduyuga.apk`: 3,415,149 bytes, SHA256 `73fe514a0ebadf520ffe3f897a34b01939949f5e0915036488e2d58db383f6ff`.
- E Node/JDK/SDK·Gradle 캐시로 서명 빌드 성공. 오프라인 검증 45개 통과: `artifacts/mypage-20261102/android-connection/android-release-verification.json`. 기존 서명키와 제출된 code 4 산출물은 해시 불변 확인.
- 이 code 5는 Play 미업로드이며 실기기 실행은 미확인이다. code 4 심사 상태와 혼동하지 않는다. 현재 설치된 code 4에는 프런트 연결·표현 개선이 자동 반영되지 않는다.
- E 실행·시험·빌드 증거를 이전 검증에 연결해 G1/G2/G3를 통과시켰고 hold를 보존 후 해제했다. 기존 C 자료의 전체 보존 복사는 백그라운드에서 재개했다. C 삭제량은 0이며 전체 이전 완료가 아니다.
