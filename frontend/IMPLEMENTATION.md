# 모두육아 프런트엔드 구현 기록

기준일: 2026-11-01. 작업 위치: 분리 worktree의 `frontend/`.

## 구현 범위와 원문 대조

`docs/build/CONTRACT.md` 원문을 먼저 읽고 아래 경로를 실제 API에 연결했다. UI 내부의 예시 목록·성공 응답·가짜 인증은 없다. `/api` 또는 `VITE_API_BASE_URL`로 호출한다.

| 요청 | 구현 위치/경로 | 상태 |
|---|---|---|
| 최초 소개, 비회원 우선 진입, 소개 다시 보기 | `/welcome`, `/`, `/my` | 구현 |
| 로그인, 구매자·판매자 가입, 별도 필수 동의와 선택 동의 미선택 | `/login`, `/signup?track=buyer|seller` | 구현 |
| 로그인 후 안전한 내부 경로 복귀, 수량 보존, 자동 참여 금지 | `api.ts`, `shared.tsx`, `catalog.tsx` | 구현, 유틸리티 검증 |
| 비밀번호 표시·자동완성·붙여넣기, 실패 입력 보존 | `auth-pages.tsx`, `shared.tsx` | 구현 |
| 로컬 복구 요청→토큰 입력→비밀번호 재설정 | `/reset` | 구현, 메일 미발송 설명 |
| 검색·URL 카테고리·상세·참여·철회·저장 | `/`, `/campaigns/:id`, `/my/reservations`, `/my/saved` | 구현 |
| 육아 외부 핫딜 별도 피드, https 링크, 링크 없음 사유 | `/hotdeals` | 구현, URL 경계 검증 |
| 브랜드 목록·브랜드 공구 | `/brands`, `/brands/:id` | 구현 |
| 쿠폰 수령·포인트·보유쿠폰·장부 | `/benefits` | 구현 |
| 질문·신고·작성자 차단 | 공구 상세, `/settings` 안내 | 구현; 계약에 차단 조회/해제 API가 없어 해제 기능 없음 명시 |
| 판매자 2단계 정보·임시저장·신청·상태·심사 의견·수정 제한 | `/seller` | 구현 |
| 승인 판매자 공구 임시저장→게시 심사, 종료, 쿠폰, 자기 참여자 | `/seller/campaigns`, `/seller/coupons`, `/seller/reservations` | 구현 |
| 관리자 입점·공구 심사, 신고 처리, 외부 개발 주문/환불 | `/admin` | 구현 |
| 추가 요청 데이터 실험실 | `/admin`, `GET /research/summary`, `POST /research/purchase-intent` | 구현, 실험 한계 표시 |
| 로그아웃·비밀번호 재확인 회원탈퇴 | `/settings` | 구현 |
| 로딩·오프라인·빈 목록·오류 focus/role alert·처리 중 중복차단 | `shared.tsx`, `main.tsx` | 구현 |
| React+TS+Vite+Router, Capacitor8 설정 | package/config 및 src | 실제 웹 빌드 통과 |
| Android 플랫폼 생성·APK·실행·화면 검수 | 메인 담당 | 이 작업에서 실행하지 않음 |

## 보안 경계

- 세션 토큰은 `sessionStorage`만 사용하며 비밀번호는 React 메모리 폼 값에만 둔다. 영구 저장하지 않는다. 소개 확인 여부만 `localStorage`, 공구 수량만 `sessionStorage`에 저장한다.
- 401이면 토큰을 지우고 재로그인 경로를 보존한다. 외부 URL·프로토콜 상대 URL·백슬래시·개행·인증 반복 경로는 복귀 대상으로 거부한다.
- 공개 URL은 https이며 사용자정보 부분이 없는 외부 링크만 허용한다. 새 창은 `noopener noreferrer`를 사용한다.
- 역할·소유자·수량·기한·revision·쿠폰 중복·포인트는 서버 검증을 요청한다. UI 메뉴 제한은 보안 권한으로 주장하지 않는다.
- 회원탈퇴·철회·공구 종료·차단·주문 환불은 결과를 설명하고 명시적 확인 뒤 해당 API를 호출한다.
- 가입에 외부 본인·사업자·메일 인증 완료 문구가 없으며, 전 화면에 실제 거래 없는 개발용 앱임을 표시한다.
- 데이터 실험실의 8개 숫자 입력은 부모 에이전트가 확정한 flat dict이다: Administrative, Administrative_Duration, Informational, Informational_Duration, ProductRelated, ProductRelated_Duration, SpecialDay, Weekend. PageValues는 입력하지 않는다. 육아 이탈 성능·실제 추천으로 표시하지 않는다.

## 디자인 원문과 적용

Refero 스킬 `개인 환경의 refero-design/SKILL.md` 및 `references/craft-details.md`를 읽었다. 실시간 Refero 도구는 제공되지 않아 번들 craft 기준과 계약의 직접 구현 UX를 기준으로 삼았다. 시각 옵션 탐색·이미지 생성은 사용자가 디자인보다 UX를 우선한 요청에 맞춰 생략했다.

| 결정 | 근거 | 적용 |
|---|---|---|
| 흰 배경·얇은 테두리·초록색 주요 행동 | 계약의 기본 CSS/UX 우선 직접 구현 방향 | `styles.css`의 전역 토큰; 과장된 장식 없음 |
| 44px 이상 터치, 단열 양식, 라벨/자동완성 | craft-details Forms/Touch | 기본 버튼 46px, 명시적 라벨과 모바일 양식 |
| URL에 탐색 조건, 링크 기반 이동 | craft-details Navigation | q/category URLSearchParams, React Router Link |
| 오류 focus와 aria-live, 중복전송 방지 | craft-details Error/Async | Feedback role alert/status, action lock |
| 이미지 없는 실제 상품 정보 중심 | 계약에 이미지 API 없음 | 가짜 상품사진·사진처럼 보이는 CSS를 만들지 않음 |

Serena 최초 지침을 읽었으나 활성 프로젝트의 지원언어가 Python뿐이어서 이 worktree TSX 개요 조회가 `Active languages: ['python']` 오류로 실패했다. 신규 파일 작성과 TSX 보완은 apply_patch 및 formatter를 사용했다.

## 실제 실행한 검증과 증거

- `npm install`: 성공, package-lock 생성.
- `npm run build`: TypeScript 검사 및 Vite production bundle 성공. 실제 출력은 `frontend/evidence/build.txt`.
- `npm test`: Vitest 1개 파일, 22개 테스트 통과. 실제 출력은 `frontend/evidence/unit-tests.txt`.
- 테스트 범위: 내부 복귀경로·외부 링크 거부, 세션 Bearer 첨부, 401 세션 폐기/이벤트, 422 메시지, 연결 실패 시 성공으로 위장하지 않음. 이 테스트의 fetch stub은 API 유틸리티 경계 시험 전용이며 제품에는 포함되지 않는다. 실제 서버 E2E 성공을 대신하지 않는다.
- `npm audit --omit=dev`: 취약점 0개. `frontend/evidence/audit-production.txt`.
- 전체 개발 의존성 audit에는 4개 moderate가 존재한다: Capacitor CLI→rimraf→glob/minimatch. npm 자동 수정 제안은 Capacitor 4로의 하향 변경으로, Capacitor 8 계약과 충돌하여 실행하지 않았다. 프로덕션 의존성에는 해당 항목이 없다.

## 남은 통합 확인과 제한

실제 backend API와 화면을 함께 띄운 흐름, 모바일 스크린샷·모든 접근성 상호작용·Android APK는 메인 통합 검증 대상이다. 이 작업에서 Vite 서버·외부 서비스·메일·배포·APK 빌드·Play 제출은 실행하지 않았다. 계약의 endpoint·body를 그대로 구현했으며 서버 구현의 런타임 응답과 아직 대조하지 않은 상태다. 관리자 연구 응답은 아래 후속 개정에서 실제 요약 구조에 맞춘 카드·표와 원본 JSON 확인 영역으로 보완했다.

고객/판매자 가입과 판매자 신청의 입력 실패는 값을 유지한다. 임시저장을 하지 않고 앱을 완전히 닫으면 판매자 변경이 유실될 수 있으므로 미저장 안내와 beforeunload 확인을 제공한다. 비밀번호는 화면 재진입 시 복구하지 않는다. 실제 법률 약관·본인인증·외부 결제·프로덕션 보안저장은 이 로컬 개발 빌드의 완료 항목이 아니다.

## 2026-11-01 후속 개정 · 모두육아 첫 개발 빌드

사용자가 확정한 서비스명을 **모두육아**로 적용했다. 상단 워드마크·HTML 제목·경로별 페이지 제목·Capacitor `appName`을 변경했다. 앱 ID는 기존 `kr.moduyuga.app`을 유지하며 native Android 파일은 이번 작업에서 수정하지 않았다. 이 결과는 첫 개발 빌드이며, 후속 개발을 종료한다는 뜻이 아니다.

실제로 읽은 자료는 `ai-pipeline/artifacts/summary.json`의 D1·retail audit·bundle_evaluation·intent 지표/분할/제한, `evaluation.json`, `bundle_rules.json`의 예시 구조 및 `ai-pipeline/serving.py`의 `get_summary`, `get_bundle_examples`, `predict_intent` 원문이다. 큰 JSON 출력에서 잘린 지표 구간은 필요한 분기를 다시 추출해 읽었다. 제품에 정적 지표를 복사하지 않고 `GET /research/summary`, `GET /research/bundles`의 응답을 표시한다.

- `src/research-summary.tsx`: D1 1,000행/28열·원자료 카테고리, D2–D3 중복 대조, 번들 규칙 대 인기 Recall@5/MRR@5, D4 분할·모델별 검증/테스트 AP·AUROC·Brier·ECE를 카드/표로 표시한다. 값이 없으면 0으로 가장하지 않고 ‘미제공’으로 표시한다.
- 동일 입력 특성 그룹 분할·0개 그룹 겹침, 모델 선택에 검증 AP를 사용한 점, 사후 확률 보정 미실시를 설명한다. 현재 데이터의 실험 결과를 국내 육아 구매/이탈/할인 효과로 일반화하지 않는다.
- 번들 API의 원 StockCode·원 영문 상품명·동시 구매 송장 수·support/confidence/lift를 표시하며 실제 육아 상품으로 바꾸거나 구매 링크로 연결하지 않는다. 출처와 실험 한계를 함께 둔다.
- 원본 요약 JSON은 접어 둔 검증 영역에 보존했다. 8개 숫자 입력을 받는 실제 모델 추론 호출은 유지했다.
- `src/recruitment.ts`, `types.ts`, `catalog.tsx`: 서버의 `recruitment_status` 및 `remaining_quantity`를 반영했다. 상태는 모집 중/최소 수량 충족/종료 충족/종료 미달/취소로 구분한다. 현재 예약 수량·최소 모집수량·부족 수량·추가 예약 가능 수량을 보여주며 독립 참여 인원이나 실물 주문·결제·배송·할인 확정을 의미하지 않음을 표시한다. 최소 기준까지 부족량은 `max(0, minimum_quantity-reserved_quantity)`이다.

후속 개정 검증: 2026-11-01 16:06 KST `npm run build` 통과(49 modules), `npm test` 22/22 통과. 초기 `frontend/evidence` 로그는 초기 인계 시점의 기록이며 이번 후속 실행 출력은 작업 도구 기록에 있다. 이번 후속 작업의 브라우저 E2E와 Android 동기화/빌드는 메인이 수행한다.
