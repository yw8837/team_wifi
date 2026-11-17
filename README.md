# 모두의 육아 · Team_Wifi

[![모두육아 checks](https://github.com/yw8837/team_wifi/actions/workflows/checks.yml/badge.svg?branch=codex%2Fmodu-yuga)](https://github.com/yw8837/team_wifi/actions/workflows/checks.yml)

육아 정보와 경험을 나누고 질문을 해결하는 커뮤니티입니다. 육아템 비교·저장·공동구매 수요 연결은 정보 탐색과 교류를 돕습니다. React/Vite·Capacitor, FastAPI, Neon PostgreSQL을 사용합니다. 패키지는 `kr.moduyuga.app`, 작업 브랜치는 `codex/modu-yuga`입니다.

[공개 웹](https://moduyuga.yeolmaeapps.kr)은 비회원 탐색과 회원의 저장·수요/질문·댓글을 제공합니다. 실제 결제·배송·정산은 제공하지 않습니다. 공개 가입 기준은 만 14세 이상이며, 코드·배포·앱 설치·Play 심사 상태를 구분해 기록합니다.

## 팀원과 담당

| 이름 | GitHub | 역할 | 주요 담당 |
| :--- | :--- | :--- | :--- |
| **최용우** | [@yw8837](https://github.com/yw8837) | Full-Stack / Architecture | 서비스 아키텍처 설계, 백엔드 API & GEO 엔진 구현 |
| **최유정** | [@cheezcyj](https://github.com/cheezcyj) | Frontend / UI·UX / Design | 요구사항 정의, 화면 설계, UI·UX 디자인, 화면흐름 프로토타입 설계, 동적 인터랙션 구현 및 CTA 담당 |
| **이승현** | [@LEES999](https://github.com/LEES999) | AI & Data Engineering | 이커머스 트랜잭션 분석, 군집화 및 수요·이탈 예측 모델 |

## 먼저 볼 문서

공개 소스의 최신 구현은 [`codex/modu-yuga`](https://github.com/yw8837/team_wifi/tree/codex/modu-yuga)에서 확인합니다. 기본 브랜치 `main`과 작업 브랜치의 구현 시점이 다릅니다.

### 기능별 코드

| 기능 | 화면 | 서버 |
|---|---|---|
| 커뮤니티 글·댓글 | `frontend/src/community.tsx`, `public-app.tsx` | `backend/app/release.py` |
| 공구 탐색·상세 | `frontend/src/groupbuys.tsx` | `backend/app/groupbuys.py` |
| 공구 자동 수집 | 판매처 출처·확인 시각 표시 | `backend/app/groupbuy_discovery.py`, `external_groupbuys.py`, `groupbuy_schema.py` |
| 선택 동의 기반 활동 통계 | `frontend/src/measurement.tsx` | `backend/app/growth.py` |
| 공유 링크 UTM | `frontend/src/share-link.ts`, `groupbuy-share.tsx` | 공유 URL에 웹·앱 출처 표시 |
| 챗봇 검색·도구 | `frontend/src`의 assistant 관련 파일 | `backend/app/assistant_tools.py`, `model_runtime.py` |

### 공유 링크와 유입 구분

공구 상세의 `공구 링크 복사`는 아래 태그를 붙입니다. `utm_source`는 공유 링크를 만든 플랫폼이며 수신자가 링크를 연 메신저를 뜻하지 않습니다.

| 태그 | 값 |
|---|---|
| `utm_source` | `web` 또는 `android` |
| `utm_medium` | `share` |
| `utm_campaign` | `groupbuy` |

홍보 채널에서 직접 사용하는 링크는 `?utm_source=kakao&utm_medium=social&utm_campaign=community_launch`처럼 구분할 수 있습니다. 계정 ID, 이메일, 이름은 UTM에 넣지 않습니다. 현재 활동 통계는 노출 위치와 웹·앱별 집계이며 UTM별 방문 보고서는 아직 연결되어 있지 않습니다.

### 공개 전 점검

`python scripts/audit-public-source.py --history`는 로컬에서 접근 가능한 Git 기록의 텍스트 파일을 검사합니다. 결과에는 일치한 비밀값 대신 파일명과 규칙만 출력합니다. `python scripts/share-check.py`는 커밋할 파일을 검사합니다. 두 검사는 문자열 패턴에 기반하므로 개인정보, 이미지·PDF, 제공 자료의 재배포 권한은 별도로 검토해야 합니다.

원본 제공 데이터, 운영 DB, 인증 키와 서명키는 로컬에서 관리합니다. `.env.example`에서 설정 이름을 확인할 수 있습니다. 저장소에 별도 라이선스 파일은 없으며 코드 재사용·재배포 허용 범위는 팀과 확인해야 합니다.


**현재 운영과 변경 상태:** [피드백 반영 기록](docs/plans/2026-11-05-community-feedback.md), [가입 연령 변경](docs/build/release-20261105/SIGNUP-AGE.md), [커뮤니티 수정·서버 이전](docs/build/release-20261105/COMMUNITY-AND-SERVER.md). 웹은 Cloudflare Pages, 공개 API는 `https://moduyuga-api.yeolmaeapps.kr/api`를 사용합니다.

이 PC의 작업 경로는 **`E:/Team_Wifi`**로 통일했습니다. 이전 기획·회의·데이터는 `_archive/legacy-project`에 보존했습니다. 새 터미널에서는 `. ./scripts/use-workspace.ps1`로 프로젝트 캐시·임시 경로를 설정합니다. 기존 SDK/JDK를 재사용하며 에뮬레이터를 자동 기동하지 않습니다.

- [외부 베타 준비 현황·검증 결과·남은 배포 조건](docs/build/beta-20261101/STATUS.md)
- [최신 디자인 기준·원본 자산](docs/design/brand/README.md)
- [v0.6 화면설계서 50개 화면과 현재 구현 대조](docs/design/screen-spec-v0.6.md)
- [추가 제공한 57개 화면과 현재 구현 대조](docs/design/screen-spec-20261101-57.md)
- [브랜드 적용 검증 기록](docs/build/brand-20261101/VERIFICATION.md)
- [실행·검증 결과](docs/build/DELIVERY.md)
- [팀 실행과 공유 방법](docs/build/TEAM.md)
- [Google Play 앱 등록 결과·출시 조건](docs/build/PLAY-CONSOLE.md)
- [기능과 API 계약](docs/build/CONTRACT.md)
- [보안 검토](docs/build/security-review.md) / [개인정보·운영 전 조건](docs/build/SECURITY.md)
- [기존 101개 요구와 구현 대조](docs/build/requirements-status.md)
- [자료 활용·실험 결과](ai-pipeline/IMPLEMENTATION.md)
- [제공 데이터·기업 자료 활용 감사와 앱 연결의 한계](docs/build/release-20261101/DATA-USAGE-AUDIT.md)
- [공개 출시 필수 항목·실제 심사 제출 상태](docs/build/release-20261101/READINESS.md)
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

초기 계획의 Next.js는 이 Android 클라이언트에서 React/Vite/Capacitor로 구체화했습니다. 공개 상세 HTML은 FastAPI가 생성하며 시험 데이터는 noindex입니다. 운영 DB는 Neon PostgreSQL이며 웹은 Cloudflare Pages에 배포합니다. 서명 APK/AAB는 `artifacts/android/release`에 보관하며 Play 배포·실제 기기 설치 검증과 구분합니다. 기존 기획서와 회의 원문은 수정하지 않습니다.
