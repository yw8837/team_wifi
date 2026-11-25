# 무료 비공개 베타 배포 절차

**비용 조건: 0원.** 카드 등록, 유료 인스턴스, 유료 디스크, 과금형 GCP, 유료 cron, 자동 업그레이드를 사용하지 않습니다. 2026-11-01 Render/Neon 무료 배포와 Play 내부 테스트 활성화를 완료했습니다. 현재 서버는 43be76c이며 [현황](STATUS.md)과 [검증](QA.md)을 함께 확인합니다.

## 선택한 구성과 확인한 조건

| 구성 | 용도 | 무료 제약 |
|---|---|---|
| Render Free Web Service | FastAPI와 빌드된 웹을 한 origin에서 제공 | 유휴 약 15분 후 절전, 파일시스템 휘발, workspace의 무료 시간 공유 |
| Neon Free PostgreSQL | 계정·시험 참여·초대·요청 제한 영속 저장 | 무료 용량/컴퓨트/전송 한도와 자동 절전. 초과 시 유료 전환하지 않음 |
| 기존 Google Play 조직 계정 | 내부 테스트 배포 | 새 개발자 계정 등록비 결제 없음. 실제 콘솔 요건은 별도 확인 |

Render의 30일 만료 무료 PostgreSQL은 사용하지 않습니다. Render의 기존 다른 서비스도 변경하지 않습니다. 공식 근거: [Render Free](https://render.com/docs/free), [Neon Plans](https://neon.com/docs/introduction/plans). 화면에서 실제 Free 플랜과 카드/과금 상태를 다시 확인한 후 생성합니다.

## 배포 순서

1. Neon Console 신규 GitHub 로그인에 요청된 이메일 읽기 권한은 사용자 확인 후 연결했습니다. 이후 별도 약관 동의가 나오면 해당 내용을 확인합니다.
2. 모두의 육아 전용 **Free 프로젝트**와 PostgreSQL DB 생성 완료. PostgreSQL17, AWS 싱가포르, 고정 0.25 CU, 5분 절전, 복구 이력 6시간을 확인했습니다. 기존 앱 DB를 재사용하지 않습니다.
3. `DATABASE_URL`은 psycopg 형식으로 설정하고 외부 연결에 TLS를 요구합니다. 비밀번호를 채팅·로그·Git·빌드 출력에 남기지 않습니다. 전용 비밀 저장소/서비스 환경변수로만 주입합니다.
4. `render.yaml`에 따라 `codex/modu-yuga`의 검토된 커밋을 사용하는 Free 웹 서비스를 구성합니다. 자동 배포는 끄고 검증된 커밋을 수동 배포합니다. 실제 URL이 생기기 전에는 예상 URL을 전달하지 않습니다.
5. `PUBLIC_ORIGIN`을 지정하지 않으면 실제 Render의 `RENDER_EXTERNAL_URL`을 빌드/실행에 사용합니다. `SUPPORT_EMAIL`, `HOSTING_LOCATION`, `DATABASE_LOCATION`, `DATABASE_URL`, 강한 `RATE_LIMIT_SECRET`을 주입합니다. `STATIC_DIR`은 빌드 산출물 경로입니다. 지원 메일은 공개 안내에 표시됨을 확인합니다. 사용자가 Neon 유지와 전용 runtime DB 접속정보의 Render 비밀 환경변수 저장을 승인했고 연결했습니다. owner 접속정보는 전송하지 않았습니다. [DB 선택 근거](DATABASE-CHOICE.md)를 보존합니다.
6. HTTPS `/api/health`가 `closed-beta`, `payments_enabled:false`로 응답하는지 확인합니다. `/api/config`, 4개 `/legal/*` 페이지, 정적 자산을 확인합니다. 잘못된 Host와 API 문서 경로는 거절되어야 합니다.
7. `python -m app.bootstrap_beta --output <접근을 제한한 비밀파일> --admin-email <운영계정> --invites 30`을 **완전히 빈 전용 DB에만** 실행합니다. 파일의 OS 접근권한은 현재 운영자와 SYSTEM만 읽도록 먼저 제한합니다. **실제 Neon 빈 DB에 초기화 완료**했으므로 다시 실행하지 않습니다. 가상 공구6·쿠폰1·핫딜1·초대30을 만들었습니다. 원문 코드·관리자 비밀번호는 비공개 파일에만 보관하며 30개 중 1개를 본인 첫 설치 시험용으로 배정했고 나머지는 공개하지 않았습니다. 스키마 소유자 계정과 앱의 테이블 읽기/쓰기 전용 계정을 분리했습니다.
8. 전용 시험 계정으로 가입·복구/재발급·참여/철회·쿠폰·판매자 신청·신고/차단·탈퇴를 실제 웹과 앱에서 검증합니다. 실데이터 없이 가상 콘텐츠만 사용합니다.
9. 서버 재배포 후 시험 계정·저장 목록 유지와 앱 `https://localhost` CORS를 실제 HTTPS에서 검증했습니다. 요청 제한은 확인되지 않은 peer/XFF에 의존하지 않습니다. DB 이전 전역 한도와 검증된 계정/정규화 이메일의 영속 한도를 분리하며, 위조 헤더·동일 peer·세션 경합은 전용 로컬 PostgreSQL에서 검사합니다. 공개 서버의 전역 한도를 고의 소진하지 않습니다.
10. `scripts/build-android-release.ps1 -ApiBaseUrl <실제 HTTPS /api 주소> -SdkRoot <SDK> -JavaHome <JDK21>`을 실행합니다. 스크립트는 실제 beta health 통과 전에는 서명키나 release를 생성하지 않습니다. 업로드 키와 DPAPI 암호 파일은 비공개 백업하고 Git에 넣지 않습니다.
11. 생성 APK/AAB의 서명·API·앱명·권한·debug/cleartext 설정을 검사하고 실제 기기 설치/기동·핵심 흐름·네트워크 실패·계정 삭제를 확인합니다. debug 성공을 release 성공으로 대신하지 않습니다.
12. Play 내부 테스트에 검증한 AAB를 업로드하고 실제 앱과 맞는 개인정보·앱 액세스·대상 연령·콘텐츠/데이터 선언을 작성합니다. 필요한 서명 약관은 action-time 확인 후 처리합니다. 테스트 릴리스 활성 상태와 실제 테스터 참여/설치 링크를 확인한 뒤 초대합니다. 메일은 발송하지 않습니다.

## 운영과 개인정보

- 초대 대상은 만 18세 이상입니다. 아이 이름·생년월일·건강정보·배송지·실제 사업자정보를 받지 않습니다.
- 이메일은 계정 식별용이며 소유권 확인 완료로 표시하지 않습니다. 비밀번호를 잃으면 복구코드를 사용합니다. 로그인 중에는 현재 비밀번호로 코드를 교체할 수 있습니다.
- 관리자 비밀번호와 모든 테스트 코드/토큰은 로컬 비밀 영역에 보관합니다. 운영자 계정을 공유하지 않습니다. 첫 내부 테스터는 사용자 확인 후 전용 목록에 등록했습니다. 추가 초대·관리자 권한은 필요한 인원만 별도 관리합니다.
- 신고를 매일 확인하고 숨김·정지·이의 접수 결과를 기록합니다. 즉시 응답/자동 심사를 제공한다고 표시하지 않습니다.
- 현재 장기 백업 복원·삭제 이력 자동 대조는 구현하지 않았습니다. 복원이 필요하면 재공개 전에 삭제 처리 영향과 재삭제 절차를 검토하고 기록합니다. 구현되지 않은 복원 보장을 안내하지 않습니다. 계정 가입 후 90일, 베타 종료 후 30일 이내 파기 약속을 지키도록 종료일·담당 확인·실제 파기 결과를 운영 기록에 남겨야 합니다. 공개 초대 전에 이 운영 절차를 확정합니다.
- 개인정보 처리방침의 국외 처리 위치, 수탁업체와 연락처를 실제 설정과 일치시킵니다. 현재 문서는 기술 구현 설명이며 모든 법률 준수를 인증한 문서가 아닙니다.
- 주 1회 무료 한도·서비스 중단 여부를 점검합니다. 유료 전환 대신 초대/새 가입을 멈추고 사용자에게 상태를 알립니다. 기존 다른 서비스의 무료 시간 사용에 영향을 주는지도 확인합니다.

## 회귀 검증 명령

```powershell
cd backend
./.venv/Scripts/python.exe -m pytest tests -q
cd ..
./backend/.venv/Scripts/python.exe scripts/verify-beta-postgres.py --pg-bin <PostgreSQL-bin> --runtime <ASCII-시험폴더>
cd frontend
npm test
npm run build
```

PostgreSQL 검증은 전용 localhost 임시 클러스터를 생성하고 종료 후 제거합니다. 기존 DB에 연결하지 않습니다. Windows의 시스템 포트 예약은 `netsh interface ipv4 show excludedportrange protocol=tcp`로 읽기 전용 확인합니다. 현재 검증은 Play 내부 테스트와 실제 휴대폰을 사용합니다. 에뮬레이터를 재생성·실행하지 않고 시스템 예약/방화벽을 변경하지 않습니다.

## 현재 배포본과 첫 설치

- HTTPS: https://moduyuga-beta.onrender.com
- 개인정보: https://moduyuga-beta.onrender.com/legal/privacy
- 삭제 안내: https://moduyuga-beta.onrender.com/legal/deletion
- Play 참여: https://play.google.com/apps/internaltest/4700489771428159755
- release: `artifacts/android/release/moduyuga-beta.aab`, `moduyuga-beta.apk` — versionCode2, 0.2.0.
- 본인용 초대코드·안내: `artifacts/beta/private/SELF-TEST.txt` (비공개). Google 초대 수락의 공유 안내를 본인이 확인한 뒤 휴대폰에서 설치합니다.
- 첫 실행은 사용자 보고로 확인했고, 인증 이후 Android 전체 동선은 추가 QA 범위로 남깁니다. 심사 전 테스트 페이지의 임시 이름은 `kr.moduyuga.app (unreviewed)`입니다.

이 PC의 명령 실행은 `E:/Team_Wifi`에서 시작하고 `. ./scripts/use-workspace.ps1`로 프로세스별 캐시·임시 경로를 적용합니다. 별도 유료 클라우드나 Android Studio 설치는 필요하지 않습니다.
