# Gates: 사용자 브랜드 디자인 적용

Scope: 제공 SVG와 디자인보드를 보존하여 앱 UI 및 Android 브랜드 리소스에 적용하고 기능·접근성·빌드 증거를 저장한다.

- [ ] G1: 사용자 원본과 배포 자산이 유효한 SVG이며 심볼·워드마크가 실제 화면에 렌더링된다
  EVIDENCE: 워드마크 SVG 첨부가 잘려 XML 파싱 실패. 원본 PNG를 사용하는 G7로 대체하며 원문은 보존한다.
- [x] G2: 프런트 단위시험과 production build가 통과한다
  CHECK: npm test && npm run build
  EXPECT: built in
  CWD: frontend
  EVIDENCE: PowerShell, cwd frontend, exit 0. 22 passed; built in 6.88s. artifacts/brand/frontend-tests.log 및 web-build.log. 실행은 저장소 루트 --cwd 기준.
- [x] G3: 실제 API와 기존 구매자·판매자·관리자 핵심 흐름이 통과한다
  CHECK: node scripts/e2e.cjs
  EXPECT: MODU_YUGA_E2E_PASS
  EVIDENCE: PowerShell, cwd 저장소 루트, exit 0. WEB_URL=127.0.0.1:4173, REQUIRE_CSP=1. MODU_YUGA_E2E_PASS, 7개 통과·pageErrors 0·inline script 차단. artifacts/brand/e2e-production.log.
- [x] G4: 작은 화면·가로 화면·데스크톱·확대 글꼴·키보드·색상 대비를 검사하고 화면 증거를 저장한다
  EVIDENCE: CUA 실제 브라우저 9조합 가로 넘침 0. 로그인 글꼴 200%·Tab 포커스·대비 5.38/5.36/13.94 확인. artifacts/brand/responsive-qa.json, contrast.json 및 화면 PNG. 전체 화면/실기기 접근성 시험은 아님.
- [x] G5: 신규 아이콘과 웹 디자인을 포함한 Android debug APK를 빌드한다
  EVIDENCE: PowerShell, cwd 저장소 루트, exit 0. ANDROID_BUILD_PASS 및 ANDROID_PACKAGE_CHECK_PASS. 4657609 bytes, sha256 21da576526fec156645066c005d01469bce506b80e22b39aaadbb47ea3665946. aapt2 앱 라벨 일치. Android 실행은 미검증.
- [x] G6: 비밀·원본 개인정보 제외를 검토한 변경을 커밋·푸시하고 원격 해시를 확인한다
  EVIDENCE: SHARE_CHECK_PASS 33 staged text files 및 git diff --cached --check 통과. 코드·자산 커밋 a67f7b285ccf08ddcc23bc3f84194e026a65d0a0을 origin/codex/modu-yuga로 push 성공; git ls-remote의 동일 SHA 확인. 후속 증거 문서 갱신 커밋도 동일 검사 후 공유한다.
- [x] G7: 정상 원본 심볼 SVG와 원본 워드마크 PNG가 웹·APK에 포함되고 화면에서 렌더링된다
  EVIDENCE: BRAND_ASSETS_PASS, CUA logoLoaded=true·brokenImages=0, APK 두 자산 byte 일치 assertion 통과. 원본 SHA-256은 VERIFICATION.md에 보존.
- [x] G8: v0.6 50화면을 누락·중복 없이 구현과 대조하고 전체 앱명을 기록한다
  EVIDENCE: 대조표 ID가 정확히 01–50이며 연결 2/부분 34/미구현 14. artifacts/brand/source-inventory.json. README·웹·Capacitor·Android 라벨에 정식 전체 이름 반영.

ABANDON: G1 사용자 첨부 워드마크 SVG가 잘려 정상 벡터 검증 불가. 원문 보존·정상 PNG 적용 G7로 대체했으며 최종 보고에서 한계를 알린다.

외부 변경 결과: 사용자 재로그인 후 Play Console 한국어 기본 스토어 등록정보에 정식 명칭을 임시보관함 저장했고 새로고침 후 20/30자 전체 값 유지를 확인했다. 설명·시각 애셋 미입력으로 전체 등록정보 확정/공개 게시 전이며 콘솔 목록 제목은 최초 이름이 남아 있다. 세부 증거와 미구현 기능은 VERIFICATION.md 및 화면 대조표 참조.
