# Cloudflare·엘리스 이전 진행 기록

2026-11-07 사용자가 Cloudflare 웹과 기존 엘리스 API·챗봇 구성으로 이전을 승인했다. 작업 화면은 앱 브라우저에 표시한다.

## 완료한 준비

- 기존 엘리스 SSH 접속 성공. Supervisor의 moduyuga-api와 moduyuga-assistant-model이 RUNNING이고 내부 API health가 정상이다.
- 제품 소스 e4123ae102d440cc1dde835eac2ca5d808564b68을 서버의 별도 준비 디렉터리로 전송했다.
- Linux 소스 압축파일 SHA256은 6b74fd4199813578cacdee88d617affb4d540bc8847d57774486b7199216e0f3이며 원격 일치를 확인했다.
- 엘리스 Python 환경에서 전체 서버 검사 653개 통과, 경고1개. 합성 SQLite 자료를 사용하는 검사이며 운영 DB는 사용하지 않는다.
- 첫 Windows git archive는 셸 파일에 CRLF가 적용돼 651통과·2실패였다. `git -c core.autocrlf=false archive`로 재생성해 LF를 확인하고 재검사했다.
- scripts/build-cloudflare-web.ps1로 웹 빌드, 약관4개, 가이드11개 및 검색용 문서를 생성했다.
- scripts/cloudflare-public-worker.mjs는 공구 공개 HTML·사이트맵만 API로 전달한다. 읽기 메서드 제한, 원래404 전달, 쿠키 제거, 비공개 헤더 미전달, 오류503을 포함한10개 단언을 확인했다.
- 생성된 canonical·sitemap·llms 문서가 입력 웹 주소를 사용하는지 검사했다.

## 현재 계정·주소 상태

- Cloudflare 브라우저는 로그인 화면이며 사용자 로그인이 필요하다.
- 현재 엘리스 콘솔 계정에는 인스턴스0개가 표시된다. SSH는 정상이다. 인스턴스 소유 계정의 HTTP 외부 연결 주소와 운영 기간 확인이 필요하다.
- Cloudflare 시험 빌드는 example.test 주소와 합성 고지 정보를 사용했다. 실제 공개 주소와 운영 고지 정보로 다시 빌드한 결과를 배포해야 한다.
- 공개 웹/API의 운영 트래픽 전환은 아직 실행하지 않았다.

## 배포 명령

E:/Team_Wifi에서 실제 확인된 값을 전달한다.

```powershell
./scripts/build-cloudflare-web.ps1 -WebOrigin $publicWebOrigin -ApiBase $publicApiBase -HostingLocation $hostingDisclosure -DatabaseLocation $databaseDisclosure -SupportEmail $supportEmail
```

출력은 artifacts/hosting-migration-20261107/cloudflare-web 이다. Cloudflare Pages의 PUBLIC_API_BASE 바인딩에는 같은 공개 API 기본 주소를 지정한다. 기존 API 경로 규약에 따라 기본 주소는 /api까지 포함한다. 직접 업로드 시 _worker.js를 포함한 전체 출력 디렉터리를 배포한다.

## 전환 검증

확인된 주소로 엘리스 PUBLIC_ORIGIN·PUBLIC_WEB_ORIGIN과 CORS, 카카오 콜백을 맞춘다. 웹 탐색·가입·로그인·카카오 복귀·글·저장·챗봇·공구 공개 HTML을 확인하고 Android의 API 주소와 서명 빌드를 갱신한다. 기존 설치본의 주소 전환도 함께 확인한다.

검증 자료는 artifacts/hosting-migration-20261107, 서버 준비 경로는 /home/elicer/Team_Wifi/.runtime/hosting-migration-20261107 이다. 원본 로그·키·환경 비밀값은 Git에 포함하지 않는다.


## 2026-11-08 운영 안정성 보완

사용자가 엘리스에 한정하지 않고 안정적인 배포와 앱 연동을 요청했다. 공개 웹은 HTTP200이지만 기존 API health/config는25초 및65초 검사에서 응답하지 않았다. Render 재시작 접수 후에도 health/config/공구 조회가 시간 초과였다. 16:15 KST에 검증된 운영 커밋 e4123ae 재배포로 접속 복구를 진행했다.

별도 상시 API 후보로 Railway 배포 구성을 준비했다. 비용은 월 최소5달러에 사용량이 적용되며 월20달러 이내 예산을 사용자에게 요청했다. 기존 무료 전용 조건에 따라 유료 실행은 명시적 응답 후 진행한다. Serverless(절전) 해제는 서비스 설정에서 적용한다. railway.json은 이미지 빌드·배포 시 healthcheck·프로세스 실패 재시작을 정의한다. 배포 healthcheck는 지속 모니터링과 구분된다.

코드04cba1c에서 컨테이너를 실제 빌드하고 PostgreSQL과 함께 public_release 모드로 실행했다. GitHub Actions42457939135에서 동적PORT, 정상health, 웹 Origin과 Android https://localhost CORS, Railway healthcheck Host 허용, 임의Host400을 확인했다. AI 모델 서버 없이 기본API가 기동했다. 같은 커밋의 API와 UI 작업도 성공했다.

앱과 웹은 기존 PostgreSQL을 공유하도록 이전하며, 실제 API 주소가 연결된 뒤 Android 서명 빌드와 카카오 callback/앱 복귀 검증을 실행한다. 주소가 미연결인 현재 시점에는 새 Android 배포가 완료된 것으로 표시하지 않는다.
