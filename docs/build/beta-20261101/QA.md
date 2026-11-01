# UltraQA Report — Android 외부 베타

## 목표와 경계

외부 테스터의 설치→비회원 탐색→계정 사용→예약/철회→신고→탈퇴를 검증한다. 실결제·배송·실제 공급 확보를 시험 성공으로 주장하지 않는다. 전용 시험 계정/환경만 변경한다. 최대 5회 수정 검증, 동일 실패 3회 시 원인과 외부 조건을 명시한다. 기존 기획·다른 서비스·개인 계정은 변경하지 않는다.

## 사전 시나리오

| ID | 의도/행위자 | 준비·실행 | 기대 신호 | 실제 결과/수정 | 증거 | 정리 |
|---|---|---|---|---|---|---|
| B01 | 비회원 탐색 | 새 브라우저/앱 저장소에서 홈·검색·상세·브랜드·핫딜 | 로그인 없이 읽기, 소유 행동에만 로그인 | 로컬/모의 API 통과, 외부 대기 | beta.browser-check.mjs, Android WebView 목록200 | 시험 브라우저 종료 |
| B02 | 정상 계정 | 시험 가입·로그인·로그아웃·복구·재발급·탈퇴 | 인증 및 폐기 실제 동작 | SQLite/PG 통과, 외부 대기 | pytest35, PG26 | 임시 DB 종료·제거 |
| B03 | 권한 우회 | 타인 자원·관리자 API·판매자 공개 시도 | 401/403/404, 상태 불변 | 서버 회귀시험 통과 | backend/tests | 격리 DB 제거 |
| B04 | 동시/반복 요청 | 예약·초대·인증 질문 동시 요청 | 단회 사용·과예약 방지·풀 고갈 없음 | 발견한 풀 교착 수정, PG 통과 | PG26, 별도 검토 재현 | 격리 DB 제거 |
| B05 | 잘못된 입력 | 손상 JSON·초과 요청·부적절한 Host·비밀값 입력 | 4xx, 비밀 입력 반사 없음 | 시험한 서버 입력 통과 | test_beta.py, PG26 | 격리 DB 제거 |
| B06 | 오프라인·만료 | 요청 중단/만료 토큰/중복 제출 | 명확한 오류·자동 참여/재전송 없음 | timeout unit, 만료 guest, 중복 제출 통과. 실제 절전 대기 | unit58, 320px mock browser | 시험 컨텍스트 종료 |
| B07 | 영속성 | DB 재시작 후 조회 | 저장 유지 | 실제 로컬 PG restart 통과. 클라우드 미실행 | postgres-results.json | PG 종료·제거 |
| B08 | Android 배포본 | 설치·기동·HTTPS·핵심 흐름 | 올바른 이름/API/서명 | 로컬 debug 설치/기동/API200. release·외부HTTPS 대기 | android-local-smoke, package-verification | 소유 에뮬레이터만 종료 |
| B09 | 개인정보 | 안내·탈퇴 후 세션/복구/소유 기록·판매자 종속 쿠폰 | 정책과 처리 일치, 타인 기능 유지 | 탈퇴/지갑 오류 수정·회귀 통과. 실제 공개정책/운영값 대기 | test_beta.py, 정책 TestClient200 | 격리 DB 제거 |
| B10 | 오해 방지 | 화면과 서버 거래·혜택 모드 대조 | 시험 표시, 실제 결제 없음 | beta 안내/설정 계약 통과 | config endpoint, 320px beta browser | 없음 |
| B11 | 작업 안전성 | Git diff·비밀 검사·실패 exit·시간 제한 | 기존 작업 보존 | 변경 diff 확인, 커밋 전 share-check 및 CI 확인 예정 | Git/검사 결과를 STATUS에 반영 | 이 QA run만 정리 |
| B12 | 스토어 테스트 | Play 내부테스트·참여 URL | 활성 릴리스·설치 링크 | 미실행. 외부 무료 DB 연결 승인 대기 | Play 초안 기록만 존재 | 없음 |

## 실행·원인·수정·잔여 위험

2026-11-01 실행. 기존 검증을 외부 배포 결과로 대신하지 않는다.

| 실행 | 종료 | 실제 결과 |
|---|---|---|
| backend pytest | 0 | 35 passed, Starlette/httpx 테스트 도구 deprecation 경고1 |
| frontend unit / 일반·베타 build | 0 | 58 tests, TypeScript/Vite 성공 |
| 320px 베타 browser contract | 0 | 명시적 복구 ACK, 수량 복원, 자동 예약0, 잘못된 비밀번호/중복 요청/비밀 저장 검사 통과; mock API |
| verify-beta-postgres.py | 0 | 26 checks. 실제 localhost PostgreSQL17·단회 동시성·재시작 유지·7개 인증 쓰기 |
| 별도 검토의 풀 고갈 재현 | 최초 7개500 → 수정 후 201/409 | 풀 timeout0, 완료 후 health200. 409를 성공 예약/작성으로 계산하지 않음 |
| Android debug build / package check | 0 | 명칭·원본 브랜드·CSP 포함 확인. release 서명 검증 아님 |
| Android local smoke | 0 | install Success, launch ok, health/catalog200, network failures0, 스크린샷 |

처음 Android 포트 5562/5563에서는 부팅됐어도 ADB가 없었다. Windows 예약포트와 충돌했으며 5760/5761로 해결했다. 첫 앱 기동 때 WebView 초기화가 늦어 probe가 실패하여 bounded 대기를 추가했다. 실패 실행을 통과 횟수에 포함하지 않았다. 실제 외부 무료 서버의 냉시작·프록시·TLS·계정삭제 URL, 서명 release와 Play 테스트는 아직 검증하지 못했다.

별도 서버/프런트 검토는 구현 담당자의 자기평가와 구분하여 수행했다. 서버 P1 두 건은 수정 후 재검토 승인, 복구 재발급 UI는 spec·quality 승인이다. 리뷰 원문은 로컬 작업 기록에 보존하며 비밀/로컬 계정 경로가 포함될 수 있는 원본은 공개하지 않는다.

상태: **ULTRAQA BLOCKED — 외부 배포를 위한 Neon 신규 로그인 권한 확인 대기.** 로컬 시험 완료와 외부 베타 완료는 별개다. 무료 DB/서버 구성 이후 B01–B10의 외부 환경 검사 및 B12를 이어간다.
