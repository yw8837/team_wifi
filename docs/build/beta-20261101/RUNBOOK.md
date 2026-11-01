# 무료 비공개 베타 배포 절차

**비용 조건: 0원.** 카드 등록, 유료 인스턴스, 유료 디스크, 과금형 GCP, 유료 cron, 자동 업그레이드를 사용하지 않습니다. 이 문서는 재현 절차이며 실제 배포 완료 기록이 아닙니다.

## 선택한 구성과 확인한 조건

| 구성 | 용도 | 무료 제약 |
|---|---|---|
| Render Free Web Service | FastAPI와 빌드된 웹을 한 origin에서 제공 | 유휴 약 15분 후 절전, 파일시스템 휘발, workspace의 무료 시간 공유 |
| Neon Free PostgreSQL | 계정·시험 참여·초대·요청 제한 영속 저장 | 무료 용량/컴퓨트/전송 한도와 자동 절전. 초과 시 유료 전환하지 않음 |
| 기존 Google Play 조직 계정 | 내부 테스트 배포 | 새 개발자 계정 등록비 결제 없음. 실제 콘솔 요건은 별도 확인 |

Render의 30일 만료 무료 PostgreSQL은 사용하지 않습니다. Render의 기존 다른 서비스도 변경하지 않습니다. 공식 근거: [Render Free](https://render.com/docs/free), [Neon Plans](https://neon.com/docs/introduction/plans). 화면에서 실제 Free 플랜과 카드/과금 상태를 다시 확인한 후 생성합니다.

## 배포 순서

1. Neon Console 신규 GitHub 로그인에 요청된 이메일 읽기 권한을 사용자 확인 후 연결합니다. 현재 이 단계가 대기 중입니다. 이후 별도 약관 동의가 나오면 해당 내용을 확인합니다.
2. 모두의 육아 전용 **Free 프로젝트**와 PostgreSQL DB를 만듭니다. 기존 앱 DB를 재사용하지 않습니다. 리전과 실제 무료 한도를 기록합니다.
3. `DATABASE_URL`은 psycopg 형식으로 설정하고 외부 연결에 TLS를 요구합니다. 비밀번호를 채팅·로그·Git·빌드 출력에 남기지 않습니다. 전용 비밀 저장소/서비스 환경변수로만 주입합니다.
4. `render.yaml`에 따라 `codex/modu-yuga`의 검토된 커밋을 사용하는 Free 웹 서비스를 구성합니다. 자동 배포는 끄고 검증된 커밋을 수동 배포합니다. 실제 URL이 생기기 전에는 예상 URL을 전달하지 않습니다.
5. 실제 `PUBLIC_ORIGIN`, `SUPPORT_EMAIL`, `HOSTING_LOCATION`, `DATABASE_LOCATION`, `DATABASE_URL`, 강한 `RATE_LIMIT_SECRET`을 주입합니다. `STATIC_DIR`은 빌드 산출물 경로입니다. 지원 메일은 공개 안내에 표시됨을 확인합니다.
6. HTTPS `/api/health`가 `closed-beta`, `payments_enabled:false`로 응답하는지 확인합니다. `/api/config`, 4개 `/legal/*` 페이지, 정적 자산을 확인합니다. 잘못된 Host와 API 문서 경로는 거절되어야 합니다.
7. `python -m app.bootstrap_beta --output <접근을 제한한 비밀파일> --admin-email <운영계정> --invites 30`을 **완전히 빈 전용 DB에만** 실행합니다. 파일의 OS 접근권한은 현재 운영자만 읽도록 먼저 제한합니다. 생성된 원문 초대코드는 한 명에게 하나씩 배정하고 공개 이슈/저장소에 넣지 않습니다. 이 작업은 아직 실행하지 않았습니다.
8. 전용 시험 계정으로 가입·복구/재발급·참여/철회·쿠폰·판매자 신청·신고/차단·탈퇴를 실제 웹과 앱에서 검증합니다. 실데이터 없이 가상 콘텐츠만 사용합니다.
9. 서버 재배포 후 데이터 유지, 절전 후 재접속, 앱 `https://localhost` CORS, 요청 제한의 프록시 경계를 검증합니다. 전달 헤더를 무조건 신뢰하지 않습니다. Render의 실제 프록시 규약에 맞춰 설정한 뒤 위조 헤더/서로 다른 테스트 접속을 검사합니다.
10. `scripts/build-android-release.ps1 -ApiBaseUrl <실제 HTTPS /api 주소> -SdkRoot <SDK> -JavaHome <JDK21>`을 실행합니다. 스크립트는 실제 beta health 통과 전에는 서명키나 release를 생성하지 않습니다. 업로드 키와 DPAPI 암호 파일은 비공개 백업하고 Git에 넣지 않습니다.
11. 생성 APK/AAB의 서명·API·앱명·권한·debug/cleartext 설정을 검사하고 실제 기기 설치/기동·핵심 흐름·네트워크 실패·계정 삭제를 확인합니다. debug 성공을 release 성공으로 대신하지 않습니다.
12. Play 내부 테스트에 검증한 AAB를 업로드하고 실제 앱과 맞는 개인정보·앱 액세스·대상 연령·콘텐츠/데이터 선언을 작성합니다. 필요한 서명 약관은 action-time 확인 후 처리합니다. 테스트 릴리스 활성 상태와 실제 테스터 참여/설치 링크를 확인한 뒤 초대합니다. 메일은 발송하지 않습니다.

## 운영과 개인정보

- 초대 대상은 만 18세 이상입니다. 아이 이름·생년월일·건강정보·배송지·실제 사업자정보를 받지 않습니다.
- 이메일은 계정 식별용이며 소유권 확인 완료로 표시하지 않습니다. 비밀번호를 잃으면 복구코드를 사용합니다. 로그인 중에는 현재 비밀번호로 코드를 교체할 수 있습니다.
- 관리자 비밀번호와 모든 테스트 코드/토큰은 로컬 비밀 영역에 보관합니다. 운영자 계정을 공유하지 않습니다. 초대와 관리자 접근 인원은 배포 전 확정해야 합니다.
- 신고를 매일 확인하고 숨김·정지·이의 접수 결과를 기록합니다. 즉시 응답/자동 심사를 제공한다고 표시하지 않습니다.
- 탈퇴 데이터가 백업 복원으로 되살아나지 않게 삭제 이력을 대조합니다. 현재 장기 복구 자동화는 없습니다. 계정 가입 후 90일, 베타 종료 후 30일 이내 파기 약속을 지키도록 종료일·담당 확인·실제 파기 결과를 운영 기록에 남겨야 합니다. 공개 초대 전에 이 운영 절차를 확정합니다.
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

PostgreSQL 검증은 전용 localhost 임시 클러스터를 생성하고 종료 후 제거합니다. 기존 DB에 연결하지 않습니다. Windows의 시스템 포트 예약은 `netsh interface ipv4 show excludedportrange protocol=tcp`로 읽기 전용 확인합니다. 시험 에뮬레이터는 예약되지 않은 포트로 실행하고 시스템 예약/방화벽을 변경하지 않습니다.
