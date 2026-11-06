# 최신 47개 요구사항과 프런트엔드 독립 검토

2026-11-06 KST. 최신 기준은 [최신 요구사항](../plans/latest-requirements-20261106.md)의 상세21개+한눈에보기26개, 고유47 ID다. 원본 SHA-256은 `20bb64c8a1538cd11eb6499209b1e8afa1940e4445c247d50baa69846a66acb7`이며 원본 탭은 수정하지 않았다. 이전128개 표는 역사 자료다.

[47 ID별 안전 매핑 JSON](../../artifacts/community-completion-20261106/frontend-latest-requirements-map.json)은 원문 참조 탭/행과 연결 코드·시험을 보관한다. 아래 묶음의 ID 합집합이 원천47개와 정확히 같은지 검사했다. 요구사항 전체 완료율로 환산하지 않는다.

## 검토 결과와 수정

- 새 공구 찾기·공유/수정/종료·제보·내 공구·수요 연결·운영 검토, 5개 하단 메뉴와 별도 챗봇, 관심 분석·챗봇 평가 운영 메뉴가 실제 라우터에 연결돼 있다. 개인·운영 화면은 역할/로그인 보호를 유지한다. 공구 공개 상세와 보호된 `mine`, 생성/수정 경로를 guest-return/read allowlist에서 구분했다.
- **확인 후 수정:** 기존 글/댓글 수정 callback을 원본 컴포넌트에서 실행하자 토큰 A→B 교체 직후 재렌더 전에 A초안이 B인증으로 전송됐다. 공통 최초세션 request 경계를 넣어 글/댓글/프로필/관심설정/조건찾기/기존 개인 작업에도 같은 전송·늦은완료 경계를 적용했다. 실제 callback 회귀를 추가했다.
- **확인 후 수정:** 조건 찾기는 React busy state가 바뀌기 전 같은 handler를 다시 호출할 수 있었다. 동기 ref lock을 추가하고 실제 handler 연속 호출 검사로 중복 요청 1회를 확인했다.
- **확인 후 수정:** 복구 응답 이후의 무조건 clear/newCode 표시는 교체 계정을 지우거나 이전 계정 코드를 표시할 수 있었다. 최초세션/요청scope와 `clear(expectedToken)` 결과를 확인한다. 복구 후 의도적으로 로그아웃한 상태에서 새 코드를 볼 수 있게 별도의 fresh scope를 만들고, 다른 로그인 뒤에는 코드를 숨긴다.
- 조회 실패와 빈 결과, 표시 금액 null과 0, 진행/종료/숨김, 출처확인과 등록/수정/운영시각을 구분했다. 공구 상세 재조회 실패 후 이전 본문·판매처 링크를 다시 노출하지 않는다. 등록/제보 실패는 초안을 지우지 않고 자동 재전송하지 않으며 내 공구에서 처리 여부를 확인하도록 안내한다.

## 시험이 증명하는 범위

문구 후속수정 전 전체 **26파일334 tests PASS** (17:41:54,21.85초). 지정 공개환경의 `tsc -b && vite build` **PASS**,6,352 modules,주 JS455.76kB.76개 추적 소스는 시험/빌드 전후 동일했고 manifest SHA-256은 `8ceb09e41f3554af868fe910f1d562d5c21c995b7f08f31fc27c85e3241a0b95`다. 아래 영수증에 파일별 소스·dist 해시와 환경을 기록했다.

[최종 실행·소스/산출물 해시 영수증](../../artifacts/community-completion-20261106/frontend-latest-final-receipt.json)과 [전체 시험 로그](../../artifacts/community-completion-20261106/frontend-latest-final-test.log), [공개 production build 로그](../../artifacts/community-completion-20261106/frontend-latest-final-build.log)를 기준으로 수치를 확정한다. 중간325/331 결과와 좁은 suite를 합산하지 않는다.

SSR 시험은 문구·컨트롤·경로/가림 속성만 증명한다. API mock을 주입한 실제 form callback+실제 useAction/storage 검사는 전송payload·중복lock·오류초안·계정경계를 검증하지만 실제 API 필드 통합을 대신하지 않는다. 실제 IntersectionObserver callback과 fake timer 검사는 50%/999→1000ms/hidden/cleanup/동의/계정교체 조건을 검증하지만 실제 모바일 viewport 관찰은 아니다. 메인의 `18185` 브라우저·실제 PG 검증, 공개 HTML rewrite/배포·실제 인증/Android 실행은 해당 별도 결과로 확정한다.

## 기능 묶음별 연결

| 기능 | 최신 ID | 화면·모듈 | 주요 frontend assertion |
|---|---|---|---|
| 공구 정보 | groupbuy_01, groupbuy_02, groupbuy_03, groupbuy_04, admgroupbuy_01 | [groupbuys.tsx](../../frontend/src/groupbuys.tsx), [groupbuys.css](../../frontend/src/groupbuys.css) | 공개검색·상태/정렬/페이지·출처/중개고지·본인공유/수정/종료·제보·정확한 운영검토 대상과 조치 |
| 수요·댓글·신고 | demand_01, demand_02, demand_03, demand_04, demand_05, comment_01, report_01, report_02, rule_01 | [public-app.tsx](../../frontend/src/public-app.tsx), [community.tsx](../../frontend/src/community.tsx), [community-editors.tsx](../../frontend/src/community-editors.tsx), [groupbuys.tsx](../../frontend/src/groupbuys.tsx) | 유형/기존 URL 유지·작성자CRUD·관심·원수요 작성자의 공구연결/해제·신고/차단/해제·개인정보/직접거래 안내 |
| 계정·내활동 | signup_01, login_01, logout_01, account_01, account_02, recovery_01, mypage_01, auth_01 | [auth-pages.tsx](../../frontend/src/auth-pages.tsx), [social-auth.tsx](../../frontend/src/social-auth.tsx), [session-storage.ts](../../frontend/src/session-storage.ts), [profile-settings.tsx](../../frontend/src/profile-settings.tsx), [account-exit.ts](../../frontend/src/account-exit.ts), [beta.tsx](../../frontend/src/beta.tsx), [content-session.ts](../../frontend/src/content-session.ts) | 이메일/활성소셜·재인증/복구·닉네임/탈퇴·계정별 기록·저장소거부/동시세션/늦은응답·이전 초안 전송 차단 |
| 육아템·비교·저장 | item_01, detail_01, guide_01, finder_01, finder_02, interest_01, interest_02, price_01, save_01 | [public-app.tsx](../../frontend/src/public-app.tsx), [advisor.tsx](../../frontend/src/advisor.tsx), [discovery.tsx](../../frontend/src/discovery.tsx), [interest-onboarding.ts](../../frontend/src/interest-onboarding.ts) | 공식출처·미확인가격·조건선택/명시삭제·복수관심/skip·배송포함오프라인단가·계정저장 |
| 동의·실제활동 분석 | consent_01, insight_01, insight_02, analytics_01 | [measurement.tsx](../../frontend/src/measurement.tsx), [discovery.tsx](../../frontend/src/discovery.tsx) | 기본미동의·화면50%/연속1초/visible·웹앱분리·공구판매처이동·집계숨김·과거공개실험과실활동구분·구매오표시금지 |
| 챗봇·평가 | chatbot_01, chatbot_02 | [chat.tsx](../../frontend/src/chat.tsx), [chat-transport.ts](../../frontend/src/chat-transport.ts), [admin-assistant.tsx](../../frontend/src/admin-assistant.tsx) | 질문/계정저장/출처·실제답변mode·중립passive status·public action allowlist·실패/원점수 보존·운영평가 메뉴 |
| 운영·정책·색인 | admin_01, admreport_01, admreport_02, broker_01, terms_01, seo_01 | [public-app.tsx](../../frontend/src/public-app.tsx), [admin-members.tsx](../../frontend/src/admin-members.tsx), [groupbuys.tsx](../../frontend/src/groupbuys.tsx), [release-policy.ts](../../frontend/src/release-policy.ts), [beta-policy.ts](../../frontend/src/beta-policy.ts) | 역할Protected·앱웹운영접근·정확한신고대상/사유/시각·공구허용조치분기·공통중개footer·법적문서·회원화면noindex |
| 전체 화면 상태·접근성 | state_01, state_02, time_01, a11y_01 | [public-app.tsx](../../frontend/src/public-app.tsx), [shared.tsx](../../frontend/src/shared.tsx), [community.tsx](../../frontend/src/community.tsx), [groupbuys.tsx](../../frontend/src/groupbuys.tsx), [content-session.ts](../../frontend/src/content-session.ts) | 로딩/빈결과/실패·stale목록·오류입력보존·중복lock·계정변경전송차단·한국시간·semantic controls/초점/반응형 |

현재 소스·시험에서 새로 확인한 프런트엔드 결함은 위와 같이 수정했다. 실제 화면/기기·배포 검증이 끝났다는 의미로 확대하지 않는다. 운영 계정의 실제 role grant, 원본 시트 수정, 외부 메시지 발송은 수행하지 않았다.

## 실제 화면 검토 후 문구 보완

수요 연결 확인은 “이 수요 글에 ‘공구제목’을 연결할까요?”로 바꿨다. 연결 해제·공구 종료 확인과 일반 제보/신고 화면의 사용자용 UUID도 제거했다. 제목·내용 미리보기·원문 링크로 대상을 확인하고 API의 정확한 대상 ID/revision과 운영자 감사 식별자는 보존했다.

실제 연결/해제/종료 callback과 제보 표시 회귀를 포함한 **관련4파일84 tests PASS** (17:48:40,6.73초). 전체334는 반복하지 않았다. 같은 공개환경의 `tsc -b && vite build` PASS,6,352 modules,주 JS455.71kB. 당시76개 소스 manifest는 `7ad27327cd40d2cc4c2737c878cae84b95796cf88d8e78841d84ee1c97174c75`이며 빌드 전후 동일하다. [갱신 영수증](../../artifacts/community-completion-20261106/frontend-latest-final-receipt.json)은 전체334의 이전 manifest와 최신scope84를 구분하고, [이전 전체 영수증](../../artifacts/community-completion-20261106/frontend-before-ui-copy-receipt.json)도 보존한다.

## 320px 헤더와 공구 화면내 확인 후속

헤더의 챗봇은 줄바꿈 없이 최소44px 폭을 유지하고, 닉네임은 말줄임하면서 전체 이름의 aria-label/title을 유지한다. 359px 이하 로고를 좁혀 충돌을 줄였다. 메인은 실제320px DOM에서 scrollWidth305, 챗봇 약44×48px·닉네임 줄바꿈 없음·전체 접근 이름을 확인했다. 실제 Android 기기 관찰로 확대하지 않는다.

공구 종료·수요 공구 연결/해제·공구 운영 검토에만 native confirm 대신 화면내 `alertdialog` 2단계 확인을 적용했다. 제목·대상·조치·사유 요약과 최종 적용/취소를 제공한다. 최종 클릭 전 쓰기 없음, 초기 제목 초점·Tab 순환·Escape 취소·취소 후 원버튼 복귀, 처리중 중복/취소 차단을 검증했다. 최종 적용 직전 원계정scope와 최신revision/신고상태를 다시 검사하고 서버의 exact ID/revision을 보존한다. 실패하면 사유·초안을 유지하고 자동 재전송하지 않는다. 성공은 재조회로 버튼이 제거될 수 있어 본문 landmark로 명시 복귀한다. 기존 일반 신고·탈퇴·차단의 확인은 변경하지 않았다.

메인은 새 종료dialog의 제목초점/Tab/ShiftTab/Escape/원버튼 복귀와 최종 종료 저장·관리도구 제거를 실제 확인했다. 성공 후 본문 초점은 후속 수정 상태에서 메인이 추가 관찰한다.

최신 관련 **5파일95 tests PASS** (18:15:27,5.04초), 공개 `tsc -b && vite build` PASS,6,353 modules,주 JS460.37kB. 최신78개 소스 manifest `61de17cb0d4d2d29eda39eac85e7dea3095e75ecddd2798ab3292ddc0be8e0d4`는 범위시험/빌드 전후 동일하다. 전체334는 이전 전체snapshot이며 반복·합산하지 않았다. [갱신 영수증](../../artifacts/community-completion-20261106/frontend-latest-final-receipt.json)에 각 버전과 초기 시험 helper 타입 오류 후 수정/최종 빌드 결과를 구분했다.
