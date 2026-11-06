# 최신 요구사항 검토 — 2026-11-06

원문 **47개 ID(상세21개 + 한눈에 보기만 있는26개)**를 실제 소스와 범위가 명확한 실행 증거에 연결했다. 전체47개 수용 완료 판정은 하지 않는다. 최신 `002d46c`의 Render API·웹 모두 **Deploy succeeded | Live**, API health200/public-release와 공개 챗봇 3요청의 기대 결과를 확인했다. 기존 서버 API b23d938 배포와 이전 Render 실패도 이력으로 보존했다. 원본 파일과 원문 셀은 수정하지 않았다.

- 원본: [요구사항정의서.xlsx](https://docs.google.com/spreadsheets/d/126Dpyel1_-mQZT5aS5RAwVgq3LlXeA4T/edit)
- 원본 수정: 2026-11-06 16:06:44 KST
- 원본 XLSX SHA-256: `20bb64c8a1538cd11eb6499209b1e8afa1940e4445c247d50baa69846a66acb7`
- 파생 추출 JSON SHA-256: `87d99827c1d97e3638b8da6bdf1acc797882e74dfcaf36543d14353251f12e50`
- [기계 판독 매핑](latest-requirements-20261106.json)에는 각 ID의 원문 설명·시트/행/셀, 공유된 개요 묶음, 소스 파일, 증거 범위와 미완료 조건을 보존했다.

## 원문 해석

하단 메뉴는 **공구 찾기 · 공구 수요 · 단가 비교 · 저장 · 마이**, 챗봇은 별도 버튼이다. 비회원도 챗봇을 이용한다. 거래는 판매처에서 진행하고 플랫폼은 주문·결제·가격·재고를 보장하지 않는다. 운영 기능은 최신 개요28~29행에 따라 앱·웹 모두 제공하는 범위이며 서버 역할 검사는 유지한다.

`demand_03,demand_04`는 “수요 상세·관심 표시”, `account_01,account_02,recovery_01`는 “닉네임·복구코드·탈퇴”라는 한 행을 공유한다. 원문에 없는 ID별 기능 배분을 만들지 않았다. 최신 인증 범위는 이메일·카카오다. 옛128개 정의의 Naver/Google 조건을 다시 필수로 넣지 않는다.

## 실행 증거와 한계

| 증거 | 확인한 결과 | 적용 범위 |
|---|---|---|
| 최신 PR CI `42202013901` / push `42202005369` | **API643 · PostgreSQL174 · UI353/27파일 · public build · audit0 · unsigned Android 성공** | `ci-final-summary.json`의 최신002 connector job states·logs 확인. 직전639는 `ci-c455c9b-summary.json` 보존. ID별 전체수용·실기기와 구분 |
| 공개 HTTP / Opik 후속 | **읽기전용73/73 · 공개합성요청3건의 실제Opik추적3건** | HTML/robots/sitemap/canonical/정책/bundle/CSP/CORS 확인. 입력·출력·thread_id null/allowlist. 공구양수운영표본0, 실제회원·장기성과 증거 아님 |
| 서명 Android 산출물 | **0.6.0/code10 APK·AAB 오프라인49/49** |0eb0614 서명빌드. 별도 최신002 입력동등성 영수증에서158개 변경없음 확인. 실제설치/Play배포·승인 아님 |
| 기존서버 API 배포 | **b23d938 배포·health·새 공구경로·release process 확인** | API만 전환, 기존모델설정/보호프로세스 보존, frontend dist·DB restore/migration 변경 없음. 공개 Render 배포와 구분 |
| 공개 Render 최신배포 | **정확한002d46c API·웹 모두 Live, health200/public-release** | API dep-dbmqmtm1egvs73dbuchg·웹 dep-dbmqomrrjlhs73c8eerg. rewrite·공개HTTP73·공개요청3건 Opik 저장 확인. 이전 실패 보존 |
| 이전 backend 회귀 | Windows/Linux 각각622; hosted b23는623, c455는639 | 각 당시소스 증거. 최신643과 합산하지 않으며 과거실패도 보존 |
| 이전 프런트 로컬 | 334 전체/26파일 →84 scoped →95 scoped/5파일 →69 scoped/2파일 + 최신 public typecheck/build | 서로 다른 manifest. 최신 hosted 전체353과 합산하지 않음 |
| 실제 공식웹 브라우저 | 비회원질문 → 모델이 선택한 근거 안내·답변·출처카드·현재정보시각, 다섯 메뉴 확인 | `public-browser-final.json`·`public-chat-live.jpg`. 앞선3요청 Opik 시간창과 별도. 카카오 로그인창 도달, 사용자 인증·콜백 미수행 |
| 실제 로컬 UI | 320px 가로넘침 없음·챗봇 nowrap·닉네임 접근이름, 종료 확인·키보드·취소초점·저장; 숨김 취소→trigger/성공→main, 숨김본문/판매처링크 제거·연결수요 공구 제외, 신규/중복 신고문구 | root CUA, 일회성 합성 API/PG. 운영 데이터 변경 없음. 실제 Android·스크린리더 확인 아님 |
| 공구 로컬 회귀 | own34 passed, 이전155와 중복 | 합성 데이터/작업자 자기검증. 판매처 실정보 확인 아님 |
| 공구 실제 PostgreSQL | 로컬24 checks, guard 활성, 동시수정·처리 `[200,409]`, PG 종료·소스불변 | 실제 ASGI+일회성PG. portable helper24는 같은 범위 재현이며48로 합산하지 않음 |
| AI snapshot08 | 반복52/52, 모델답변 직접검토36/36, 원래 gold Recall@5 0.944444 | 기존40+검토된12 재평가. 새52문항/최종 제품 snapshot 아님 |
| 고정평가 Opik | 실제 저장52/52, 입력·출력 null | 공개·합성 평가. 실서비스 회원질문 전체 관측 아님 |
| 관측 로컬 통합/후보 | hook15+기존50+HTTP경계5=70; 후보56 포함240 | 전송 비활성/SDK·SSH mock. 중복이며 합산하지 않음 |
| 기존서버 실제 관측 | 실제 지정모델 공개질문1건, remote accepted1, 별도 SDK 읽기조회로 **추적1건 저장**, input/output/thread_id null·metadata allowlist; **실제 제한검사15건** | 승인된 기존서버 gateway/collector. 회원 데이터·질문/답변 로그 없음. 운영 Render 웹요청 저장 증거 아님 |
| CI 이식성 수정 | 이전3fail/620pass 원인 수정 후 로컬12 passed, 실제 crash23/24 복구 | gold 원문·30frozen/10holdout 유지, CRLF/LF 정규화와 자식 cwd/import 수정. 최신 hosted643과 합산하지 않음 |

로컬 프런트334 manifest: `8ceb09e41f3554af868fe910f1d562d5c21c995b7f08f31fc27c85e3241a0b95`; 최신 로컬69/build manifest(78파일): `5ab74e3b9d96f5a40a2fc75c8abf10a647142e5f2dbcd5823bce9ee1c0f8d4d6`. 실제 UI의 성공main초점은 `ui-report-hide-final.json`으로 확인했다. 이전 프런트 영수증의 pending 문구는 당시 상태이며 이 후속 증거로 갱신한다. 경로·SHA와 세부 범위는 JSON evidence registry에 있다.

관측 `validation`은 tools를 포함한 검증 경과시간이므로 단계값을 더하지 않고 `total`을 전체 지연으로 읽는다. 인용 전체가 정적map과 맞지 않으면 공개 출처를 미전송하고 모델답변 품질을 `not_assessed`로 남긴다. 수신된 mismatched source는 계약에서 거부한다. 전송카운터와 실제 저장조회는 서로 구분한다.

## 남은 검증과 확인된 공백

1. **공개 관측 연결 확인:** 정확한002 공개 합성3요청(지원200/local_extractive+공식 인용·의료200/abstained·잘못된 본문422)이 닫힌 시간창의 Opik 실제 추적3건과 일치했다. SDK 읽기조회에서 결과·오류enum·단계와 input/output/thread_id null·정확한 metadata allowlist를 확인했다. 고정평가52와 초기bootstrap1은 서로 다른 증거다.
2. **CI 공구 PostgreSQL 초기 공백 해결:** `checks.yml → verify_public_postgres.py → verify_assistant_postgres.checks → verify_groupbuy_postgres.checks`로 portable helper가 연결됐다. 로컬 실제PG24건 재현 뒤 root가 최종 hosted PostgreSQL174 PASS를 확인했다. 최종 PR/push 성공 영수증의 경로·해시를 JSON에 연결했다. 이 감사자는 CI나 helper를 수정하지 않았다.
3. **소프트웨어 출시와 별도 범위:** 최신002 CI·API/웹 Live·공개HTTP73/73·공개요청3건/Opik저장을 확인했다. Android 실기기/스크린리더·운영자 흐름·오프라인 실행, Play 전달, 실제 카카오 사용자 인증·동의·복귀는 별도다(제공자 로그인창 진입은 관측). 운영 공구표본0으로 양수상세·종료 동적HTML은 운영표본 실관측을 주장하지 않으며 합성UI·PG·CI 증거를 유지한다. CTR/매출/검색인용의 장기효과를 구현수용과 섞지 않는다.
4. 일반 신고 조치의 계정정지와 공구 전용 검토의 숨김/확인필요/종결은 각각 상세9행·10행에 맞춰 구분했다. 운영자 서버 권한·메모·이력·완료 재처리 방지는 유지한다.

## 47개 ID 매핑

아래는 **구현·CI·정확한 소스 배포의 소프트웨어 판정**과 실제 관측/추가 범위를 나눈다. “확인”은 연결된 자동 검사·관측 범위에 한정하며 전체47개 ID의 실기기/외부 서비스 수용 완료율을 만들지 않는다. 공유 개요의 기능을 ID별로 새로 배분하지 않았다.

| ID | 원문 | 원문 기능/공유 묶음 | 구현·배포 / 관측·추가범위 |
|---|---|---|---|
| a11y_01 | 상세22 | 화면 크기·키보드 이용 | 구현·CI·배포 확인 · 로컬CUA / Android·스크린리더 별도 |
| account_01 | 개요24 | 계정 관리(닉네임·복구코드·탈퇴) | 구현·CI·배포 확인 |
| account_02 | 개요24 | 계정 관리(닉네임·복구코드·탈퇴) | 구현·CI·배포 확인 |
| admgroupbuy_01 | 상세10 | 공구 정보 검토·숨김 | 구현·CI·배포 확인 · 로컬CUA / 앱 실기기 별도 |
| admin_01 | 상세7 | 관리자 전용 접근 | 구현·CI·배포 확인 / 앱 실기기 별도 |
| admreport_01 | 상세8 | 신고 목록·원문 확인 | 구현·CI·배포 확인 / 앱 실기기 별도 |
| admreport_02 | 상세9 | 신고 처리와 결과 기록 | 구현·CI·배포 확인 / 앱 실기기 별도 |
| analytics_01 | 상세12 | 노출·클릭·판매처 이동 분석 | 구현·CI·배포 확인 |
| auth_01 | 상세20 | 본인 정보와 기록 보호 | 구현·CI·배포 확인 |
| broker_01 | 상세5 | 통신판매중개 고지 | 구현·CI·배포 확인 |
| chatbot_01 | 상세6 | 육아템·공구 질문 챗봇 | 구현·CI·배포 확인 · 공개API3건·공식웹 대화 |
| chatbot_02 | 상세14 | 챗봇 답변 품질 평가 | 구현·CI·배포 · 공개3건 Opik 저장/개인정보 검사 확인 |
| comment_01 | 개요17 | 댓글 작성·삭제 | 구현·CI·배포 확인 |
| consent_01 | 상세3 | 활동 분석 동의·해제 | 구현·CI·배포 확인 |
| demand_01 | 개요13 | 수요 목록·검색 | 구현·CI·배포 확인 |
| demand_02 | 개요14 | 수요 글 작성·삭제 | 구현·CI·배포 확인 |
| demand_03 | 개요15 | 수요 상세·관심 표시 | 구현·CI·배포 확인 |
| demand_04 | 개요15 | 수요 상세·관심 표시 | 구현·CI·배포 확인 |
| demand_05 | 개요16 | 수요에 진행 중 공구 연결 | 구현·CI·배포 확인 · 로컬CUA |
| detail_01 | 개요20 | 육아템 목록·상세·공식 출처 | 구현·CI·배포 확인 |
| finder_01 | 개요21 | 조건 찾기(목적·분야·예산) | 구현·CI·배포 확인 |
| finder_02 | 개요21 | 조건 찾기(목적·분야·예산) | 구현·CI·배포 확인 |
| groupbuy_01 | 개요9 | 진행 중 공구 목록·검색(마감 임박순, 종료 구분) | 구현·CI·배포 확인 |
| groupbuy_02 | 개요10 | 공구 상세 → 판매처로 이동(거래는 판매처에서) | 구현·CI·배포 확인 · 로컬CUA |
| groupbuy_03 | 개요11 | 공구 정보 공유·수정·종료 | 구현·CI·배포 확인 |
| groupbuy_04 | 개요12 | 잘못된 공구 정보 제보 | 구현·CI·배포 확인 · 로컬CUA |
| guide_01 | 상세16 | 육아템 비교 가이드 조회 | 구현·CI·배포 확인 |
| insight_01 | 상세11 | 관심·공동 저장 집계 | 구현·CI·배포 확인 |
| insight_02 | 상세13 | 분석 근거와 한계 조회 | 구현·CI·배포 확인 |
| interest_01 | 개요25 | 관심 설정·차단 관리·활동 분석 동의 | 구현·CI·배포 확인 |
| interest_02 | 개요22 | 관심 기반 육아템 안내 | 구현·CI·배포 확인 |
| item_01 | 개요20 | 육아템 목록·상세·공식 출처 | 구현·CI·배포 확인 |
| login_01 | 개요23 | 회원가입·로그인(이메일·카카오)·로그아웃 | 구현·CI·배포 확인 / 공유 묶음 카카오 실인증 별도 |
| logout_01 | 개요23 | 회원가입·로그인(이메일·카카오)·로그아웃 | 구현·CI·배포 확인 / 공유 묶음 카카오 실인증 별도 |
| mypage_01 | 개요26 | 내 공구·내 수요·관심 수요 모아보기 | 구현·CI·배포 확인 |
| price_01 | 개요18 | 배송비 포함 단가 계산기(저장 안 함, 오프라인 가능) | 구현·CI·배포 확인 / Android 오프라인 실관측 별도 |
| recovery_01 | 개요24 | 계정 관리(닉네임·복구코드·탈퇴) | 구현·CI·배포 확인 |
| report_01 | 개요31 | 신고·개인정보/직접 거래 주의 안내 | 구현·CI·배포 확인 · 로컬CUA |
| report_02 | 상세2 | 작성자 차단·해제 | 구현·CI·배포 확인 |
| rule_01 | 상세4 | 개인정보·직접 거래 주의 안내 | 구현·CI·배포 확인 |
| save_01 | 개요19 | 육아템 저장·저장 목록 | 구현·CI·배포 확인 |
| seo_01 | 상세17 | 공개·회원 화면 노출 구분 | 구현·CI·배포 · 공개HTTP73 확인 / 공구운영표본0 범위 |
| signup_01 | 개요23 | 회원가입·로그인(이메일·카카오)·로그아웃 | 구현·CI·배포 확인 / 공유 묶음 카카오 실인증 별도 |
| state_01 | 상세18 | 로딩·빈 목록 안내 | 구현·CI·배포 확인 |
| state_02 | 상세19 | 오류 안내와 중복 요청 방지 | 구현·CI·배포 확인 · 로컬CUA |
| terms_01 | 상세15 | 약관·개인정보·도움말 조회 | 구현·CI·배포 확인 |
| time_01 | 상세21 | 일시 기록과 한국 시간 표시 | 구현·CI·배포 확인 |

각 ID 원문은 JSON의 `source_references[].description_verbatim`에 그대로 있다. 개요의 공유된 ID 문자열도 `ids_verbatim`으로 남겼다. 원문 XLSX와 파생 JSON의 해시는 서로 다른 파일의 해시이므로 같은 값으로 표기하지 않는다.
