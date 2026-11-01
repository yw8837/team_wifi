# 브랜드 적용·화면설계 대조 검증

기준일: 2026-11-01. 정식 앱명 **모두의 육아 - 육아템 공동구매,핫딜**. 로고 표기 **모두의육아**. 패키지 `kr.moduyuga.app`, 개발자 `Team_Wifi`.

## 반영한 범위

사용자 원본 쪽쪽이 SVG와 투명 워드마크 PNG를 웹 헤더·로그인·소개·favicon과 Android 아이콘/시작 리소스에 연결했다. 디자인보드의 코랄·크림·코코아를 적용하고 홈의 검색·주제 배너·2열 상품 카드·선형 아이콘을 정리했다. 인증 화면에서는 하단 탐색을 숨겼다. 기존 가입·권한·참여·동의 로직을 유지했다.

[v0.6 대조표](../../design/screen-spec-v0.6.md)에 01–50까지 중복·누락 없이 기록했다. **연결 2 / 부분 34 / 미구현 14**는 화면별 현재 동선 분류이며 완성도 비율이 아니다. 연결된 두 화면도 픽셀 일치·운영 출시를 의미하지 않는다. 전체 하단 메뉴 변경·독립 커뮤니티·실결제·배송·환불을 완료했다고 보고하지 않는다.

## 실행 증거

아래 명령은 저장소 루트 또는 표기한 디렉터리에서 직접 실행했다. 로컬 증거는 `artifacts/brand`, `artifacts/e2e`, `artifacts/android`에 보존하며 공개 Git에서 제외한다.

| 검사 | 실제 결과 | 증거·한계 |
|---|---|---|
| `python scripts/build-brand-assets.py` | `BRAND_ASSETS_PASS`, 원본 SVG 3개 path | `asset-generation.json`. 잘린 워드마크 SVG는 별도 보존하고 PNG 사용 |
| `npm test` (frontend) | **22 passed** | `frontend-tests.log`. API 유틸리티 단위시험 |
| `npm run build` (frontend) | 성공, 최종 웹 CSS 20.20 kB / JS 336.05 kB | `web-build.log`. 배포 자체의 성공이 아님 |
| `.venv/Scripts/python -m pytest tests -q` (backend) | **24 passed, 1 warning**, 5.40s | 현재 소스에 대한 pytest 실행 출력. 경고: Starlette TestClient의 httpx 사용 방식 폐기 예정 |
| `node scripts/e2e.cjs` | **7개 시나리오 통과**, `MODU_YUGA_E2E_PASS` | production preview `4173`, 실제 로컬 API, `REQUIRE_CSP=1`. `e2e-production.log`, `artifacts/e2e/results.json` |
| 브라우저 반응형·확대 검수 | **9개 화면/크기 조합에서 가로 넘침 없음** | `responsive-qa.json`. 홈 320/390/844/1440, 로그인 320/844, 구매자/판매자 가입·상세 320 |
| 키보드·200% 글꼴 | 본문 건너뛰기 링크 포커스 표시. 이메일 16→32px, 제목 26→52px, 가로 넘침 없음 | `keyboard-focus.png`, `login-text-200.png`. 임시 검사 스타일은 제거. 전체 WCAG 인증 또는 실기기 접근성 시험이 아님 |
| 색상 대비 | 버튼 흰색/액션색 **5.38:1**, 보조글자/크림 **5.36:1**, 본문/배경 **13.94:1** | 최종 CSS 값으로 계산한 `contrast.json`. 모든 상태·모든 조합을 검사한 것은 아님 |
| `scripts/build-android.ps1` | `BUILD SUCCESSFUL`, `ANDROID_BUILD_PASS` | `android-build.log`. JDK 21·SDK 36 기반 debug 빌드 |
| `python scripts/verify-android-build.py` | `ANDROID_PACKAGE_CHECK_PASS` | 패키지 ID·전체 앱명·CSP 위치·실제 내장 심볼/워드마크의 원본 일치 확인 |
| `aapt2 dump badging` | 앱과 시작 Activity 라벨 **모두의 육아 - 육아템 공동구매,핫딜** | `apk-label.txt`. minSDK 24, targetSDK 36, 새 v33 launcher 리소스 참조 |

최종 Android debug APK: **4,657,609 bytes**.

SHA-256: `21da576526fec156645066c005d01469bce506b80e22b39aaadbb47ea3665946`.

APK는 에뮬레이터 호스트 `10.0.2.2:8000`의 로컬 API를 사용하는 개발용이다. 실기기 실행·Play 업로드·서명 release AAB·출시 검증은 완료되지 않았다. 이전의 Android 실행 제약은 [android-runtime.md](../android-runtime.md)에 있다. 빌드 경고(실험적 Windows 경로 설정, flatDir 메타데이터, SDK XML 버전 차이)가 남아 있으나 이번 assembleDebug는 성공했다.

## 검수에서 수정한 문제

헤더의 기존 `.wordmark span`이 새 로고의 inline-flex를 덮어써 심볼과 글자가 세로로 쌓였다. 브랜드 컨테이너의 선택자 우선순위를 수정한 뒤 4개 화면 크기에서 가로 배치를 확인했다. 기존 body 색도 브랜드 본문색으로 명시해 상속 충돌을 없앴다. 수정 후 웹 production E2E와 Android 빌드를 다시 실행했다.

## 원본 추적

| 자산 | SHA-256 |
|---|---|
| v0.6 원본 | `2078ac084ea64a5ec21615d77e147dd13262c319bf82ffddf0f4d8563c2ad7cc` |
| 쪽쪽이 SVG | `4e6f6622068fe88f5742586c47c57cfb409b052033677cd72b6f277269676861` |
| 워드마크 PNG | `2ac384fd66a2a689ea3c413f4838088a0ebfb55a1a488404322bcb59848e36e8` |

첨부 워드마크 SVG 텍스트는 끝이 잘려 XML 파싱에 실패했다. 따라서 ‘심볼과 워드마크 모두 정상 SVG’라는 최초 G1은 충족 불가능하다. 원문을 보존하고 원본 PNG로 표시한 대체 G7을 검증했다. 원본 PNG를 다시 그리거나 AI로 변형하지 않았다.

## Play Console 저장 결과

처음 등록정보 메뉴에서 오류 `5652B991`와 Google 로그인 `ERR_TOO_MANY_REDIRECTS`가 발생했다. 사용자 재로그인 이후 Team_Wifi 조직 계정의 해당 앱에 다시 진입해 **한국어 기본 스토어 등록정보의 앱 이름을 ‘모두의 육아 - 육아템 공동구매,핫딜’로 입력하고 임시보관함에 저장했다.** ‘변경사항이 저장되었습니다’ 안내와 페이지 새로고침 후 전체 이름(20/30자) 유지를 확인했다. 증거: `artifacts/brand/play-app-name-draft-saved.png`.

설명·아이콘·그래픽·스크린샷은 아직 미입력이고, 콘솔 메뉴/목록 제목에는 최초 생성명 ‘모두육아’가 남아 있다. **이번 완료 범위는 등록정보 초안 저장이며 전체 등록정보 확정·공개 게시·앱 출시는 아니다.** 계정 보안 설정·쿠키·다른 앱은 변경하지 않았다.

공유 전 비밀/원본 데이터 검사와 Git 결과는 [GATES.md](GATES.md)에 기록한다. 콘솔 캡처·계정 정보·테스트 계정·원본 데이터는 공개 저장소에 포함하지 않는다.
