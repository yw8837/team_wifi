# UltraQA Report — Android 외부 베타

## 목표와 경계

외부 테스터의 설치→비회원 탐색→계정→시험 참여/철회→신고→탈퇴를 검증한다. 초대형 가상 상품 시험이며 실제 결제·배송은 없다. 최대5회 수정 검증, 동일 실패3회 종료. 다른 서비스·기획·사용자 계정 보존, E 드라이브만 작업, 에뮬레이터 재생성·실행 금지, 무료 서비스만 사용한다.

현재 결과: **배포·첫 설치 확인 완료 / Android 인증 후 동선의 전체 실기기 QA는 미완료.** 서버와 Play 내부 배포는 완료했다. 이전 Render 연결 승인/DB 선택 대기는 해소됐다.

## 시나리오와 증거

| ID | 의도·행위자 | 준비·실행 | 기대 | 실제 결과·수정 | 증거 | 정리 |
|---|---|---|---|---|---|---|
| B01 | 비회원 탐색 | 공개 웹·API 홈/목록/상세 | 로그인 없이 읽기 | 공개 API·브라우저 공구6개 표시, 참여 전 로그인 이동·뒤로가기 수량3 복원 | public-api-results.json, 실제 브라우저 | 임시 탭 종료 |
| B02 | 정상 계정 | 한 번만 쓰는 QA 초대3개 | 가입·복구·회전·탈퇴 | 실제 HTTPS 통과 | public-api-probe.py/result | 계정3개 탈퇴·초대3개 삭제 |
| B03 | 타인 권한 침해 | 다른 계정의 예약/관리자 API | 401/403/404 | 실제 HTTPS 거절 확인 | 75checks | 소유 시험 데이터 삭제 |
| B04 | 중복·동시성 | stale revision/중복 예약, 초대 동시 사용, 7개 인증 쓰기 | 과예약·중복사용·pool 고갈 없음 | 공개 duplicate/stale 통과, 실제 로컬PG46 및 기존26 통과 | rate-subject-results.json, postgres-results.json | 임시 PG 종료·제거 |
| B05 | 비정상 입력 | 손상 JSON·65KiB body·잘못된 이메일 | 4xx, 비밀 입력 반사 없음 | 422/413, 반사 없음 | 75checks, pytest40 | fixture 정리 |
| B06 | 만료·중단 | 폐기 token, mock timeout·중복 클릭 | guest 유지, 자동 재전송·참여 없음 | 실제 폐기 token401/공개GET200. UI 모의 시험 통과 | unit58, beta.browser-check.mjs, 75checks | 모의 컨텍스트 정리 |
| B07 | 재배포 영속성 | 실제 배포 전 계정·저장1개 생성 → 43be76c배포 → 조회 | 계정·저장 유지 | 통과 | redeploy-persistence-results.json | 계정 탈퇴·임시 초대1개 삭제 |
| B08 | Android release | signed APK/AAB 오프라인 검사·Play 처리 | 이름/API/서명/권한 및 기기 실행 | 오프라인30검사·Play 처리 통과. 휴대폰 설치·실행·guest 목록은 사용자 보고 확인 | android-release-verification.json | 에뮬레이터 종료·테스트 AVD 휴지통 정리 |
| B09 | 개인정보 | 실제 legal4페이지 및 탈퇴 이후 기록/재고 | 정책 일치·토큰 폐기·재고 원복 | 실제 HTTPS 통과, 국외 호스팅/limiter 설명 수정 | legal.py, 75checks | QA 계정 정리 |
| B10 | 오해 방지 | config·앱 안내 비교 | closed-beta, payments false | 공개 API 및 UI 확인 | public-api-results.json | 없음 |
| B11 | 파일·공유 안전 | 이전→E SHA256, staged 비밀검사, 실제 exit/CI 확인 | 유실·비밀 push 없음 | 보존 파일5480개 일치, staged16개 검사, CI 성공 | migration verification, share-check, GitHub CI | 옛 primary checkout은 앱 보호로 보존 |
| B12 | Play 배포 | 전용 테스터 목록1명·release2 출시 | active·실제 참여 가능 | 활성·내부 테스터 제공, 지정 계정에 초대 표시. 다운로드/기기 첫 실행은 사용자 보고 확인 | play-internal-active.png, play-tester-invite-visible.png | 타 앱 목록 변경 없음 |
| B13 | quota 우회 | 같은 peer의 두 계정, 위조XFF·대체token·실패auth·logout 경합 | 계정 분리·실패횟수commit·endpoint 재인증 | 실제 로컬PG46검사와 별도 검토 수용 | test_rate_subject.py, verify-rate-subject-postgres.py | 운영 서버 한도 소진 공격 미실행 |

## 실행과 종료 상태

- 새 E 경로 `python -m pytest tests -q`: exit0, **40 passed**, Starlette/httpx 테스트 도구 deprecation warning1.
- `verify-rate-subject-postgres.py`: 이전 실행 증거 **46 local PostgreSQL checks pass**, 검토자가 본문/결과 대조. 이동 이후 무거운 PG 재시험은 반복하지 않음.
- 43be76c 공개 HTTPS probe: exit0, **75 checks pass**, 실패0. 기존 dd36488의75개 결과는 별도 파일로 보존.
- redeploy probe before/after: exit0, 배포 전 계정·저장 목록 조회 유지, 계정/초대 정리 확인.
- Android signed package: **30 offline checks pass**. 파일명과 Unicode aapt 호출 등 시험 도구 문제를 수정한 뒤 통과했다. 런타임 실행 성공으로 확대하지 않음.
- PowerShell smoke/workspace 스크립트 구문검사: pass. emulator를 실행하지 않음.
- GitHub [push CI](https://github.com/yw8837/team_wifi/actions/runs/41313688780)·[PR CI](https://github.com/yw8837/team_wifi/actions/runs/41313693249): success. API/UI·빌드·npm audit 포함.

## 발견한 문제와 수정

기존 중첩 DB connection 고갈, 판매자 탈퇴 후 쿠폰함500, 복구코드 재발급 공백은 수정·회귀검증했다. 이번에는 Render의 확인되지 않은 proxy peer로 다른 사용자가 한도에 묶이는 문제를 서버 검증 계정 기준으로 변경했다. quota를 action 전에 별도 짧은 transaction으로 commit/close하고 endpoint가 다시 인증한다. 실패한 action의 rollback이 실패 횟수를 지우지 않는다.

release 에뮬레이터는 PC의 가용 RAM이 약356MiB까지 감소한 상황에서 설치·기동 검증을 마치지 못했다. OS 재시작 원인은 확정하지 않는다. 실패를 재현하려고 다시 기동하지 않고 실제 기기 경로로 전환했다. 사용자 승인 범위의 AVD/캐시 약14.35GiB를 휴지통으로 이동했고 사용자 본인이 휴지통을 비웠다고 확인했다.

## 잔여 위험과 다음 확인

실제 휴대폰의 Play 설치·첫 실행·guest 공구 표시는 사용자가 확인했다. Android 기기에서 인증 후 참여·복구·탈퇴의 전체 UI 경로는 아직 독립 검증하지 않았으므로 이 전체 QA 목표에 대해서는 `ULTRAQA BLOCKED: Android 인증 후 실기기 동선 미확인`으로 남긴다. 무료 절전 지연과 전역 예산 소진 시 다른 사용자429 가능성, 메모리 한도의 재시작 초기화는 수용한 베타 한계다. 실결제/배송·이메일 소유 확인·운영 자동 파기·스토어 정식 심사는 완료하지 않았다.

원본 증거는 `artifacts/beta`에 보존한다. 이 실행에 한정한 `.omx` QA 상태를 inactive/cleanup 후 CLI clear하고 absent를 확인했다(`qa-release-cleanup.json`). 이후 들어온 사용자 첫 설치 확인은 `android-user-confirmation.json`에 별도 기록했다. CLI 검증 도구의 outcome enum·read 응답 형식 두 오류는 고친 후 정리 결과를 확인했으며 앱 결함으로 계산하지 않았다. 비공개 서명키·초대/복구코드·DB URL과 기존 자료는 보존한다. 전체 목표가 미확인인 동안 `ULTRAQA COMPLETE`를 출력하지 않는다.
