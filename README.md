# 모두육아 · team_wifi

육아용품 공동구매와 흩어진 핫딜 정보를 확인하고, 조건을 비교하며 함께 참여하는 커뮤니티 앱입니다. 서비스명은 **모두육아**, 저장소는 `yw8837/team_wifi`입니다. 개발 브랜치는 `codex/modu-yuga`입니다.

현재 코드는 제품의 첫 개발 빌드입니다. 가입·판매자 검토·모집·질문/신고·쿠폰/포인트와 공개 데이터 실험을 실제 API와 연결했습니다. 예시 상품·개발용 주문으로 검증하며 **실결제, 배송, 사업자 인증, Play 출시가 완료된 상태는 아닙니다.** 실제 개인정보나 사업자 서류를 넣지 마세요.

## 먼저 볼 문서

- [실행·검증 결과](docs/build/DELIVERY.md)
- [팀 실행과 공유 방법](docs/build/TEAM.md)
- [Google Play 앱 등록 결과·출시 조건](docs/build/PLAY-CONSOLE.md)
- [기능과 API 계약](docs/build/CONTRACT.md)
- [보안 검토](docs/build/security-review.md) / [개인정보·운영 전 조건](docs/build/SECURITY.md)
- [기존 101개 요구와 구현 대조](docs/build/requirements-status.md)
- [자료 활용·실험 결과](ai-pipeline/IMPLEMENTATION.md)
- [출처·벤치마크 적용](docs/build/SOURCES.md)
- [사업모델과 후속 개발](docs/build/PRODUCT.md)

## 로컬 실행

필요 환경: Python 3.11, Node.js 22 이상(팀 기본 Node.js 24 LTS), Chrome. Android 빌드는 JDK 21과 Android SDK가 추가로 필요합니다.

```powershell
git clone https://github.com/yw8837/team_wifi.git
cd team_wifi
git switch codex/modu-yuga
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
cd backend
.venv/Scripts/python -m app.seed --demo
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

다른 터미널에서:

```powershell
cd frontend
npm ci
npm run dev
```

브라우저에서 `http://127.0.0.1:5173`을 엽니다. API 문서는 `http://127.0.0.1:8000/docs`입니다. Mac/Linux에서는 `.venv/Scripts/python`을 `.venv/bin/python`으로 바꿉니다.

초기 계정의 비밀번호는 매번 임의 생성되어 **자기 PC의** `backend/runtime/demo-accounts.json`에만 저장됩니다. 채팅·이슈·Git에 복사하지 마세요. 관리자 계정을 회원가입 화면에서 만들 수 없습니다. 시드는 데이터가 있는 DB를 덮어쓰지 않습니다.

## 검증

```powershell
cd backend
.venv/Scripts/python -m pytest tests -q
cd ../frontend
npm test
npm run build
npm audit
cd ..
node scripts/e2e.cjs
```

E2E는 위 두 로컬 서버와 시드 파일이 있어야 합니다. 가상 계정/공구/쿠폰을 만드는 실제 브라우저 시험입니다. 스크린샷·결과는 Git에서 제외된 `artifacts/e2e`에 저장됩니다. 데이터 원본은 Git에 올리지 않습니다. 별도로 확보한 제공 자료에 대해서만 `ai-pipeline/pipeline.py --data-root <자료폴더>`와 `verify_outputs.py --data-root <자료폴더>`를 실행합니다.

## Android

```powershell
$env:JAVA_HOME = '<JDK 21 설치 경로>'
$env:ANDROID_HOME = '<Android SDK 경로>'
./scripts/build-android.ps1
```

결과: `artifacts/android/modu-yuga-debug.apk`. 이 파일은 `10.0.2.2:8000`의 로컬 API에 연결하는 **에뮬레이터용 debug APK**입니다. 일반 휴대전화 배포나 Play 제출용 파일이 아닙니다. release에서 HTTP를 허용하지 않으며, debug에서 에뮬레이터 호스트 하나에만 허용합니다.

## 구조

| 폴더 | 내용 |
|---|---|
| `frontend` | React·TypeScript UI, Capacitor Android 프로젝트 |
| `backend` | FastAPI·SQLAlchemy, 인증/권한·모집·혜택·운영 API와 시험 |
| `ai-pipeline` | 제공 데이터 분석·모델·집계·무결성 검증 |
| `docs/build` | 구현·출처·보안·요구사항·후속 개발 기록 |
| `scripts` | 공유 전 검사·실제 E2E·Android 재현 명령 |
| `artifacts` | 로컬 실행 증거·APK, Git 제외 |

초기 계획의 Next.js는 이 Android 클라이언트에서 React/Vite/Capacitor로 구체화했습니다. 공개 상세 HTML은 FastAPI가 생성하며 개발 데이터는 noindex입니다. PostgreSQL 연결 설정은 지원하지만 현재 테스트 증거는 SQLite 기준입니다. 운영 웹의 SSR·PostgreSQL 마이그레이션/부하·백업·배포는 별도 검증이 필요합니다. 기존 기획서와 회의 원문은 수정하지 않습니다.
