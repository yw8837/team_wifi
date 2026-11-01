# 공개 후보 QA 기록

갱신일: 2026-11-02. **CI, 로컬 서명·정적 검사, HTTPS 운영 배포와 라이브 API 통합 검증은 통과했다. Play 프로덕션 최종 검토 전송을 실행했고 Console의 ‘검토 중인 변경사항’을 확인했다. 자동 사전 검사는 진행 중이며 승인·공개와 새 versionCode 4의 Android 실기기 실행은 아직 확인하지 않았다.** 아래 결과는 자동 테스트·API·브라우저·서명 검증의 범위를 구분한다. 최신 Console 상태는 [SUBMISSION](SUBMISSION.md)을 확인한다.

## 정확한 후보와 증거

| 항목 | 실제 결과 | 근거 |
|---|---|---|
| 소스 | `82ca2b54520bdab72776762faa5394b39371138f` | [커밋](https://github.com/yw8837/team_wifi/commit/82ca2b54520bdab72776762faa5394b39371138f), 서명 JSON `build.commit` |
| CI | push run `41332869514`; `api`, `ui`, `unsigned-android` 모두 success. pytest **68 통과**, 프런트 **141 통과**, 실제 PostgreSQL **52 checks 통과** | [Actions](https://github.com/yw8837/team_wifi/actions/runs/41332869514), [API job](https://github.com/yw8837/team_wifi/actions/runs/41332869514/job/124926455179), [UI job](https://github.com/yw8837/team_wifi/actions/runs/41332869514/job/124926454991). 수치는 메인의 해당 실행 확인 결과. 문서 작업자는 연결된 GitHub 도구로 세 job과 pytest/PG/npm test/공개 빌드/Android step success를 재확인했으며 테스트를 다시 실행하지 않음 |
| Android CI | public_release 환경의 unsigned AAB/APK 빌드 성공 | [Android job](https://github.com/yw8837/team_wifi/actions/runs/41332869514/job/124926628923), [워크플로](../../../.github/workflows/checks.yml). unsigned 성공과 로컬 서명 검사는 별도 결과 |
| 운영 배포 | Render `dep-dbjnmhlg1s2s7389act0`, 같은 SHA live 상태를 메인이 확인. 라이브 API public mode 확인 | [운영 홈](https://moduyuga-beta.onrender.com/), [health](https://moduyuga-beta.onrender.com/api/health), [config](https://moduyuga-beta.onrender.com/api/config), [배포 화면](../../../artifacts/store/release-4/render-public-deployed.jpg). SHA 일치는 메인의 Render 확인 결과이며 health 응답 자체가 SHA를 증명하는 것은 아님 |
| E: 로컬 서명·정적 검사 | **43/43 통과**, 실패 0. `0.3.0`, versionCode **4**, `public_release`, HTTPS 운영 API, 원래 업로드 인증서, API36, 권한·보안 설정, 원본 브랜드, dist HTML/JS/CSS 일치 | [android-release-verification.json](../../../artifacts/release-20261102/android-release-verification.json). JSON의 commit/run_id도 위 소스/CI와 일치 |
| 운영 API 통합 | `scripts/verify-public-live.ps1 -RunMutations -CreateReviewer`: **71/71 통과**, 실패 0. 폐기용 일반 회원 **2/2 삭제** | [live-qa.json](../../../artifacts/release-20261102/live-qa.json), [스크립트](../../../scripts/verify-public-live.ps1). UTC 2026-11-01 17:50:50~17:51:16, KST 2026-11-02 **02:50:50~02:51:16** |
| 심사 계정 | 최소 권한 일반 회원 생성. 메인이 별도 API 로그인과 일반 회원 권한 확인 | 라이브 JSON `reviewer_created:true`, `signup_least_privilege_and_recovery` 및 메인의 추가 확인. 자격 증명은 DPAPI 비공개 자료에만 보관하며 이 문서에 싣지 않음 |
| Play IARC | 메인이 콘텐츠 등급 **overall 3+ 저장** 확인 | [등급 저장 화면](../../../artifacts/store/release-4/iarc-rating-saved.jpg). 등급 저장은 심사 제출·승인·공개가 아니며 성인 가입 조건/대상 이용자 설정을 바꾼 결과도 아님 |

폐기용 2명은 삭제했으나 Play 접근용 일반 회원 한 명은 의도적으로 유지한다. 임시 게시물 부재도 라이브 검사에 포함한다. 모든 검증 계정을 삭제했다거나 운영 DB에 계정이 전혀 없다고 해석하지 않는다.

## 시나리오 결과와 한계

| ID | 상황 | 실제 결과·증거 | 아직 확인하지 않은 범위 |
|---|---|---|---|
| P01 | 비회원 첫 진입·탐색 | **실제 브라우저 홈 → 정보 상세 확인**, catalog/detail API 200. 로그인 강제 없이 공식 출처·미확인 가격/배송비 표시. 수유·이유식 선택 시 젖병 항목만 표시, 없는 검색어의 빈 안내, ‘젖병’ 검색 결과 확인. [홈](../../../artifacts/store/release-4/phone-01-home.jpg), [상세](../../../artifacts/store/release-4/phone-02-detail.jpg), [필터](../../../artifacts/store/release-4/browser-guest-category.jpg), [검색](../../../artifacts/store/release-4/browser-guest-search.jpg) | 모든 카테고리·조합을 수동 반복한 결과는 아님 |
| P02 | 일반 회원 가입·저장·제안·관심·댓글 | **라이브 API 통과.** 초대 없는 가입, 일반 회원 권한·복구 응답, 저장/제안/관심/댓글 생성·해제. **운영 브라우저 로그인 → 정보 저장 → 저장 목록 확인 → 해제 → 빈 목록 → 로그아웃/비회원 홈도 확인.** [빈 저장 목록](../../../artifacts/store/release-4/browser-save-cleared.jpg), [로그아웃 홈](../../../artifacts/store/release-4/browser-logout-guest.jpg) | 브라우저 가입·약관 체크·복구코드 보관 UI와 글쓰기·관심·댓글의 수동 완주는 미검증 |
| P03 | 타인 ID·관리자 권한 우회 | **라이브 API 통과.** 타인 글/댓글 DELETE 404, 일반 회원 관리자 신고 조회 403. `demand_idor_denied`, `comment_idor_denied`, `report_admin_access_denied_to_buyer` | 실제 관리자 계정으로 운영 신고 숨김/정지를 수행한 라이브 UI 시나리오는 미수행. 관리자 처리 자동 회귀와 구분 |
| P04 | 기존 시험 API·판매·혜택 우회 | **CI 회귀·라이브 차단 통과.** 라이브 guest에서 campaigns/hotdeals/brands/coupons/wallet/reservations/seller application/기존 admin reports/research summary 9개 GET 404 | 모든 역할과 변경 메서드를 운영 서버에서 반복한 것은 아님. CI 공개 허용 범위 회귀와 위 라이브 GET 결과를 분리 |
| P05 | 비정상 값·악성 문자열 | **자동 테스트 통과.** 단가의 빈 값·0 수량·음수·NaN/Infinity/비정상 값, UGC 텍스트 이스케이프·길이·권한 제한. CI pytest68/프런트141/PG52 | 실제 브라우저/WebView에 악성 문자열을 넣어 관찰한 라이브 공격 테스트는 미수행 |
| P06 | 신고·차단·해제 | **라이브 API 통과.** 신고 접수, 일반 회원의 관리자 접근 거부, 차단 시 글·댓글 숨김, 비회원 공개 접근, 해제 후 복원. `owned_content_report_accepted`, `block_filters_*`, `unblock_restores_visibility` | 실제 관리자 브라우저에서 신고 사유 확인·처리 흐름은 미검증 |
| P07 | 반복 저장·관심·요청 제한 | **라이브 중복 방지 통과.** 반복 저장은 단일 record, 반복 관심은 한 계정만 집계. `save_idempotent_1/2`, `save_single_record`, `interest_unique_account_1/2`. **쿼터·경합은 실제 PostgreSQL CI 52 checks 통과** | 운영 서버에 의도적 과부하나 쿼터 소진을 가한 결과는 아님 |
| P08 | 복구·탈퇴·연관 기록 | **라이브 API 통과.** 코드 교체, 이전 세션401, 이전 코드 재사용400, 새 비밀번호 로그인, 탈퇴·토큰 거부·연관 글/댓글/관심/차단 제거, 폐기 계정2/2 정리. `recovery_*`, `old_recovery_code_replay_denied`, `*_owned_account_deleted`, `deleted_account_*` | 복구/탈퇴 화면의 브라우저·Android 완주 UX는 미검증. 잘못된 비밀번호 자동 테스트를 라이브 수동 결과로 올리지 않음 |
| P09 | 오프라인·콜드스타트·모드 불일치 | **단위/SSR/정책 테스트 통과.** 읽기만 제한 재시도, 변경 미재전송, 공개 설정 불일치 차단. **운영 브라우저에서 계산기 로드 후 네트워크 차단**, 오프라인 안내와 130원 대 100원 계산/30원 차이 확인. [화면](../../../artifacts/store/release-4/browser-offline-calculator.jpg). 시험 후 온라인 복원과 배너 제거 확인 | 콜드스타트·오프라인 최초 로드·Android 오프라인은 미검증. 이미 열린 계산기의 동작 범위와 구분 |
| P10 | HTTPS·공개 정책·모드 | **라이브 통과.** health/config public_release, 공식 자료/미확인 가격, privacy/terms/deletion/support 각200, 기존 API 차단 | 선택 삭제 안내의 완비는 단순 URL200과 별개. 제공자 로그·백업 범위는 [DATA-SAFETY](DATA-SAFETY.md)의 미확정 항목 유지 |
| P11 | 서명 패키지 | **43 checks 통과.** 기존 인증서·code4·0.3.0·API36·public_release·운영 API·권한/보안·원본 브랜드·번들 일치 | **새 code4의 Android 실기기 설치/실행 미검증.** unsigned CI·서명 검사·브라우저 표시를 기기 실행 증거로 합치지 않음 |
| P12 | Play 프로덕션 심사 | **code 4 AAB 업로드·저장 및 최종 검토 전송 실행.** 대한민국, 등록정보·콘텐츠 등 10개 변경사항이 ‘검토 중인 변경사항’으로 전환. [접수 화면](../../../artifacts/store/release-4/play-review-submission-queued.jpg), [진행 기록](SUBMISSION.md) | 자동 사전 검사 진행 중. 검사 통과 후 심사로 전달된다는 안내가 있으며 승인·공개는 미확인 |

## 실제 브라우저 계산기·빈 목록

메인은 공개 브라우저에서 **홈 → 공식 정보 상세 → 계산기 → 공구 수요 목록**을 확인했다. A는 `(10,000원 + 배송비3,000원) / 수량100 = 단위당130원`, B는 `(12,000원 + 배송비0원) / 수량120 = 단위당100원`으로 입력하여 **B가 단위당30원 낮음**을 확인했다. [계산기 실제 화면](../../../artifacts/store/release-4/phone-03-calculator.jpg)

수요 목록은 실제 빈 상태였고 샘플 글·가짜 관심 수 없이 안내와 제안 버튼을 표시했다. [빈 목록 실제 화면](../../../artifacts/store/release-4/phone-04-demands.jpg). 이 확인은 신규 회원의 브라우저 글쓰기·관심·댓글 성공을 증명하지 않는다.

## 스토어 이미지 읽기 전용 점검

문서 작업자는 JPEG 원본을 수정하지 않고 크기와 01/02/04 내용을 확인했다. 네 장 모두 **435×774px**, 비율 약9:16, 약29~36KB JPEG다.

| 파일 | 확인 내용 | 품질상 남은 사항 |
|---|---|---|
| phone-01-home.jpg | 원본 로고/색상, 탐색·검색·카테고리, 공식 참고 안내, 계산기 진입 | 개별 참고 정보 카드는 캡처 아래여서 첫 장에 거의 보이지 않음. 오른쪽 데스크톱 형태 스크롤바 노출 |
| phone-02-detail.jpg | 공식 출처·확인 시각·특가 아님·가격/배송비 미확인·외부 출처 버튼이 읽힘 | 비교 메모/저장 부분은 화면 밖. 보조 글자는 확대 시 가독성이 낮아질 수 있고 오른쪽 스크롤바 노출 |
| phone-03-calculator.jpg | 크기 헤더 확인. 계산 값/실제 동작은 위 메인 브라우저 확인 결과 | 이 작업자의 별도 03 시각 감사는 미수행 |
| phone-04-demands.jpg | 관심은 예약·주문·결제가 아니라는 안내, 제안 버튼·검색/분류·정직한 빈 상태 | 작성/관심/댓글 성공 예시는 아님. 오른쪽 스크롤바 노출 |

Google 기본 phone screenshot 크기(최소320·최대3840px, 긴 변≤짧은 변2배)에는 맞는다. 다만 **추천/프로모션 노출용 최소1080×1920 세로 네 장 요건에는 미달**한다. 기본 업로드 크기 위반과 구분하며, 이후 실제 모바일 화면을 높은 해상도로 재캡처하는 방식을 추천한다. 현재 이미지가 새 code4 실기기 실행 증거는 아니다. 이미지 리사이즈·합성·원본 수정은 하지 않았다. [Google 미리보기 요구사항](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en)

## Console 데이터 삭제 선택 질문

메인은 수집 예·전송 중 암호화 예·사용자 이름/비밀번호·계정 삭제 URL을 입력했다. **계정 삭제 없이 일부/전체 데이터 삭제 요청 선택 질문은 안내 URL 보완을 기다리며 미응답/생략 상태다. ‘아니요’로 신고한 것이 아니다.** 본인 글/댓글 삭제·저장 해제·관심 취소·차단 해제는 실제 지원한다. 공개 `/legal/deletion`에 해당 경로·계정 유지·지원 요청 범위를 명확히 안내한 뒤 예와 해당 URL을 입력하는 것이 [DATA-SAFETY](DATA-SAFETY.md)의 권고다. 현재 누락을 보완/저장/승인 완료로 기록하지 않는다.

## 보존·기밀·이전 장애

작업과 증거는 E:/Team_Wifi에 두며 기존 기획·데이터·beta·연구 자료를 보존한다. [기존 데이터 활용 감사](../release-20261101/DATA-USAGE-AUDIT.md)를 유지한다. 공개 쇼핑 참고 정보가 D1~D4 연구를 대체하거나 추천 모델 적용·CTR/CVR 개선까지 검증한 것은 아니다.

이전 로컬 E: 읽기 지연으로 Vitest fork worker가 시작되지 않아 테스트0건으로 실패했던 기록은 [장애 증거](frontend-vitest-infra-failure.txt)에 보존한다. 이후 정확한 후보 SHA의 Linux CI에서 프런트141건·빌드가 통과했다. 이전 로컬 실행을 성공으로 바꾸거나 그 장애를 현재 CI 실패로 취급하지 않는다.

공개 증거에 비밀번호·토큰·복구코드·심사 계정 이메일·원본 운영 로그를 싣지 않는다. 비공개 DPAPI 정리 자료와 서명키는 Git·스토어 증거에 포함하지 않는다.

남은 실제 검증은 **새 code4 Android 실기기, 브라우저 가입/복구·탈퇴·글쓰기·관심·댓글·오프라인 최초 실행 UX, 선택 삭제 URL 안내와 Console 선택 질문, Google 사전 검사 종료·심사 결과**다. 브라우저 로그인·저장·해제·로그아웃과 로드된 계산기의 오프라인 동작을 위 P02/P09에 별도로 기록했다. 제출·검토·승인·공개를 각각 구분한다.
