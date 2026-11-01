# 모두의 육아 — 내부 테스트 배포 현황

2026-11-01 23:58 KST 기준, **첫 실행부터 공구 홈이 열리는 수정본을 웹과 Android0.2.1/versionCode3에 반영했고 Play 내부 트랙에서 활성/내부 테스터에게 제공됨을 확인했습니다.** 이전0.2.0 설치 결과는 사용자 보고였으며, 이후 사용자가 지적한 새 설치의 소개·가입 우선 진입을 수정했습니다. 수정0.2.1의 실제 휴대폰 실행은 아직 직접 관찰하지 않았습니다.

- 웹: https://moduyuga-beta.onrender.com
- Play 참여: https://play.google.com/apps/internaltest/4700489771428159755
- 정식 앱명: **모두의 육아 - 육아템 공동구매,핫딜**, 개발자 Team_Wifi, 패키지 `kr.moduyuga.app`.
- 최초 승인 테스터 1명을 전용 목록에 등록했습니다. 가입용 1회 초대코드와 본인 시험 안내는 로컬 `artifacts/beta/private/SELF-TEST.txt`에 보관합니다. 코드·비밀번호는 공유 문서에 넣지 않습니다.

## 최신 첫 화면 수정과 공개 출시 준비

- 코드 `b0e3a8a`: 새 저장소에서도 홈 직행, 로그인에서 게스트 복귀, 보호 경로는 홈으로 탈출. 별도 검토 승인과 최종 CI 프런트95/백엔드40 통과.
- Render 배포 `dep-dbjks5ec6qcc73bqvkmg` Live. 실제 HTTPS의 새 방문 상태에서 공구6개·비밀번호 입력0개·390px 가로 넘침 없음·로그인 탈출 확인.
- Android0.2.1/versionCode3: 서명 APK/AAB 빌드, 오프라인30검사, 웹 번들 전체 파일 일치 확인. 23:58 내부 업데이트 활성화. 이전 버전과 서명키 보존, 에뮬레이터 실행 없음.
- 공개 출시: 개인정보·광고 없음·정부 앱 아님·앱 분류/지원 연락처 **4/11 완료**. 팀원 내부 테스터는 추가하지 않았다. 프로덕션 심사 제출과 실제 공개는 미완료다. 현재 상품·가입은 시험/초대형이므로 실제 정보 콘텐츠와 공개 가입 전환이 남아 있다.
- [첫 진입 수정·화면·패키지 해시](../release-20261101/GUEST-FIRST.md) · [공개 출시 준비](../release-20261101/READINESS.md).

## 이전0.2.0 배포에서 확인된 것

| 항목 | 실제 확인 결과 | 증거/남은 조건 |
|---|---|---|
| 작업 위치 | `E:/Team_Wifi` 독립 저장소·Codex 프로젝트 설정. 앱 보존 파일 4,267개와 과거 자료 1,213개 SHA-256 일치 | [이전 검증 기록](WORKSPACE-MIGRATION.md). 옛 primary checkout은 Codex 보호로 보존 |
| 무료 운영 | Render Free + Neon Free PostgreSQL17, 싱가포르. 기존 카드 없는 Render 계정, 유료 전환 없음 | [운영 절차](RUNBOOK.md) |
| 실제 서버 | 검토 커밋 `43be76c` 수동 배포 성공 | Render deploy `dep-dbjkb7ijnfac7388ntkg`, `render-43be76c-live.png` |
| 공개 HTTPS | 탐색·초대 가입·권한·참여/철회·저장·질문/신고/차단·복구/탈퇴·CORS 등 75개 검사 통과 | `public-api-results.json`. 임시 계정 3개 탈퇴·초대 3개 삭제 |
| 재배포 영속성 | 배포 전 만든 별도 계정과 저장 목록을 새 배포에서도 조회. 이후 계정·임시 초대 정리 | `redeploy-persistence-results.json` |
| 요청 제한 | 확인되지 않은 프록시 IP 대신 서버가 검증한 계정으로 분리. 전역 예산은 DB 접근 전 적용 | E에서 pytest40 통과, 로컬 PostgreSQL46 검사, 별도 spec/quality 검토 수용 |
| 프런트 | 기존58개 단위시험·320px 모의 브라우저 검증. 새 커밋 GitHub CI의 API/UI 검사 성공 | 실제 Android 실행은 별도 |
| 서명 Android | 0.2.0/versionCode2 APK·AAB 생성. 서명·이름·HTTPS API·권한 등 오프라인30검사 통과 | `artifacts/android/release`. release 설치·첫 실행·비회원 목록은 사용자 확인. Android 인증 후 동선은 추가 시험 범위 |
| Play 내부 테스트 | **활성 / 내부 테스터에게 제공됨**, 11/1 23:02 게시. 실제 참여 페이지 접근 확인 | `play-internal-active.png`, `play-tester-invite-visible.png`. 휴대폰 설치·첫 실행은 사용자 확인 완료 |
| 공개 안내 | 개인정보·약관·삭제·지원 URL이 실제 HTTPS로 열림. Render/Neon 위치와 요청 제한 문구 반영 | `/legal/privacy`, `/legal/terms`, `/legal/deletion`, `/legal/support` |
| 팀 공유 | `codex/modu-yuga` push, [Draft PR #1](https://github.com/yw8837/team_wifi/pull/1) 유지 | [push CI](https://github.com/yw8837/team_wifi/actions/runs/41313688780), [PR CI](https://github.com/yw8837/team_wifi/actions/runs/41313693249) 성공 |

Play의 정식 심사 전 내부 테스트 페이지에는 `kr.moduyuga.app (unreviewed)`라는 임시 이름이 표시됩니다. 스토어 한국어 정식명은 초안으로 저장했으며, 콘솔 앱 헤더도 아직 이전 이름을 표시할 수 있습니다. 패키지 내부 정식 명칭 검증과 스토어 공개 심사를 구분합니다. 제출 경고 1건은 난독화 가독화 파일 없음이며 현재 `minifyEnabled false`인 빌드로, 제출 차단 오류는 없습니다.

## 기기 확인 결과와 후속 베타 시험

1. 승인 테스터의 Play 설치·실행·비회원 공구 목록 표시는 사용자 응답으로 확인했습니다. 기기 모델·Android 버전·native 로그는 아직 수집하지 않았습니다.
2. 초대코드 가입·로그인 후 복귀·시험 참여/철회·탈퇴의 실제 Android UI 동선은 후속 베타 시험으로 남깁니다. 서버는 실제 HTTPS75검사, 프런트는 단위·모의 브라우저 검사와 공개 웹 guest 로그인 이동·수량 복원으로 검증했습니다.
3. 본인 설치 확인 기록은 `artifacts/beta/android-user-confirmation.json`입니다. 검증 방법과 범위를 구분하여 기록합니다.

## 베타 범위와 한계

실제 결제·주문·배송·정산·환불, 판매자 사업자 인증, 실제 공급 계약은 제공하지 않습니다. 상품·가격·쿠폰·포인트는 시험용입니다. 독립 커뮤니티 게시판, 이메일 소유 확인, 최신 57개 설계 화면 전체 구현도 완료된 것으로 표시하지 않습니다. [화면 대조표](../../design/screen-spec-20261101-57.md)를 별도로 관리합니다.

무료 서비스가 절전되면 첫 요청이 약 1분 지연될 수 있습니다. 쓰기 요청을 자동 재전송하지 않습니다. 전역 요청 한도는 공격 시 다른 참여자에게도 영향을 줄 수 있고 재시작하면 초기화됩니다. HMAC 계정/이메일 제한은 DB에 남습니다. 한도를 초과하면 초대·가입을 중단하고 유료 전환하지 않습니다.

[QA 보고서](QA.md) · [운영 절차](RUNBOOK.md) · [자원 정리](RESOURCE-AUDIT.md) · [DB 선택 근거](DATABASE-CHOICE.md). 원본 증거는 `artifacts/beta`에 보관하고 비밀·콘솔 원문은 Git에 올리지 않습니다.
