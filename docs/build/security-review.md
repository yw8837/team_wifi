# 모두육아 첫 개발 빌드 보안 검토

기준일: 2026-11-01. 대상 브랜치: `codex/modu-yuga`. 상태: 로컬 개발 빌드의 소스 검토와 격리 API 검사 완료. 운영 배포 보안 승인 문서가 아니다.

직접 확인한 범위에서 인증·권한 우회, 구매자 연락처의 공개 응답 유출, 재고 초과 발급 또는 환불 중복 적립 회수는 재현되지 않았다. 감사자가 최종 후속 검사에서 백엔드 시험 **24개를 직접 실행해 모두 통과**했고, 앞선 관리자·연구 API 11개에 대한 비회원·구매자·판매자 요청 33개도 전부 401/403으로 차단됐다. 세션 저장소의 낮은 위험 1개와 운영 전 확인 조건은 남아 있다. CSP는 배치 문제까지 수정된 빌드와 메인의 실제 브라우저 증거를 대조해 해결로 변경했다. 공개 staged 파일 검사는 아래 시점에 수행했으며 메인의 최종 재stage·커밋·push와 구분한다.

## 범위와 방법

| 요청 항목 | 실제 확인 범위 | 근거·실행 상태 |
|---|---|---|
| 인증·권한 | `backend/app/security.py`, `main.py`, `schemas.py`, `db.py`, `seed.py` | 토큰 발급·만료·폐기, 서버 현재 권한, 소유자 검사, 엄격한 입력 스키마를 읽음. 격리 pytest와 추가 API 호출 실행 |
| 개인정보·탈퇴·복구 | 공개/판매자/관리자 DTO, 탈퇴·reset 경로, 가입·설정·복구 화면 | 응답·DB 상태 검사 실행. 운영 보관기간·법적 적합성까지 검증한 것은 아님 |
| XSS·URL·CORS·CSP | `frontend/src/api.ts`, `shared.tsx`, `auth-pages.tsx`, `account.tsx`, `catalog.tsx`, `seller.tsx`, `admin.tsx`, `main.tsx`; 연구 화면 URL/출력 경로; 공개 HTML; Vite 설정·dist HTML | 위험 sink 검색과 실제 출력 코드 추적. 공개 HTML·CORS 검사 및 CSP 빌드 태그 순서 검사 실행. 메인 브라우저 실행 원문 증거 대조. 감사자 별도 브라우저 침투시험은 미실행 |
| 재고·쿠폰·포인트 | 예약/철회/쿠폰/주문/환불 경로와 테스트 | 동시성·중복·롤백·권한 시험 실행. PostgreSQL 실서버·부하 시험은 미실행 |
| AI 파일·Git·로그 | `ai-pipeline/serving.py`, 공유 JSON 구조/식별자 키/표본, AI 로그 2개, `.gitignore`, `.dockerignore`, 공유 후보 텍스트 | 패턴 검사와 `git check-ignore` 실행. 모델 바이너리 내용 전체 역공학·이미지 OCR·과거 Git 전체 이력 검사는 미실행 |
| 의존성 | 프런트 잠금 파일을 대상으로 `npm audit --json`; `backend/evidence-dependencies.json` | npm 감사자 실행: 알려진 취약점 0건. 메인이 실행한 pip-audit 원문은 45개 의존성·취약점 0건으로 대조. pip-audit 자체는 감사자가 재실행하지 않음 |

감사자 변경은 이 문서 한 파일이다. 애플리케이션 코드·기존 기획서·원본 자료를 수정하지 않았다. 다른 작업자의 수정이 진행 중인 작업 트리의 확인 시점 결과다.

적용 지침은 `security-best-practices/SKILL.md`와 FastAPI·React·일반 브라우저 JavaScript 보안 참조다. `code-review` 원문도 읽었으나 이 요청은 고정 diff 기준의 일반 PR 검토가 아닌 실제 구현의 보안 검토여서 해당 인터뷰·분담 절차를 다시 시작하지 않았다. 새 감사 서브에이전트는 생성하지 않았다.

## 남은 보안 보완

### SEC-01 — 세션 토큰의 JavaScript 접근 가능 저장소 사용

- 위험도: **Low, 확인된 개발용 설계 제약**. 관련 규칙: JS-STORAGE-001.
- 위치: `frontend/src/shared.tsx:67`, `frontend/src/api.ts:64`.
- 근거: `sessionStorage.setItem(TOKEN_KEY, token)`으로 저장하고 API 호출 시 읽어 `Authorization`에 넣는다.
- 영향: 같은 origin에서 XSS나 악성 스크립트 실행이 발생하면 토큰을 읽을 수 있다. 현재 검토에서 해당 XSS 실행 경로는 확인하지 못했다. `sessionStorage`는 탭 수명을 줄일 뿐 기밀 저장소가 아니다.
- 권고 **(추천)**: 실제 개인정보를 다루는 웹 배포 전 서버 관리 `HttpOnly` 세션과 CSRF 방어를 함께 설계하고, 네이티브 토큰은 OS 보안 저장소 사용 여부를 검증한다. 현재의 8시간 만료·서버 폐기·XSS 출력 방어는 유지한다.
- 오탐 경계: 계약에 명시된 로컬 Bearer 세션 구현이며, 보안 저장소 구현 완료로 표시하지 않는다. 현재 개발 빌드에서 즉시 인증 우회를 재현했다는 주장이 아니다.

### SEC-02 — SPA CSP 추가와 태그 순서 수정: 현재 빌드에서 해결

- 이전 위험도: Low, JS-CSP-001. 최종 상태: **수정한 작업 파일·생성 번들에서 해결**. 최종 인덱스 반영은 아래 확인 조건을 따른다.
- 위치: `frontend/vite.config.ts:4`, `frontend/dist/index.html:4`, `scripts/e2e.cjs:43`, 로컬 `artifacts/e2e/results.json`.
- 최초 추가된 `injectTo: "head"`는 CSP meta를 모듈 script 뒤에 삽입했다. meta 정책은 앞선 요소에 소급 적용되지 않으므로 감사자가 메인에 전달했고 `head-prepend`로 수정됐다.
- 감사자가 최종 dist HTML을 읽고 HTMLParser로 검사해 `CSP_BUNDLE_ORDER_PASS ['csp', 'script']`를 확인했다. 정책은 `script-src 'self'`이며 script의 `unsafe-inline`·`unsafe-eval`이 없다. `object-src 'none'`, `base-uri 'none'`, `form-action 'self'`도 존재한다. style의 `unsafe-inline`은 현재 React 스타일에 대한 별도 허용이며 스크립트 허용과 다르다.
- 메인이 Chrome에서 `REQUIRE_CSP=1`, `WEB_URL=http://127.0.0.1:4173`으로 실행한 원문 결과(2026-11-01T07:30:29.024Z)를 읽어 `precedesScripts:true`, `inlineScriptBlocked:true`, 실제 API 7개 흐름 PASS, pageErrors 빈 배열을 대조했다. 감사자가 해당 브라우저 실행을 직접 했다고 표시하지 않는다.
- 운영 전 잔여 조건: 현재 `connect-src`의 로컬 개발 주소를 실제 API에 맞게 좁혀야 한다. meta CSP는 `frame-ancestors`·report-only를 제공하지 않으므로 실제 SPA 호스트의 HTTP 정책/프레이밍 방어도 설정·시험해야 한다. Vite 개발 서버는 `apply:"build"` 대상이 아니다. 운영 웹·release WebView 검증까지 해결했다고 확대하지 않는다.

## 확인된 방어와 개인정보 처리

| 경계 | 확인한 구현 | 실행 근거 |
|---|---|---|
| 비밀번호 | `security.py:10`의 `PasswordHash.recommended()`와 Argon2 의존성. 원문 비밀번호를 User에 저장하지 않음 | 로그인 성공/실패 시험 통과. 해시 내구성 벤치마크는 미실행 |
| 세션 | `security.py:18`의 32바이트 난수 토큰, DB SHA-256 digest, 기본 8시간 만료. 요청마다 삭제 여부·현재 역할 확인 | logout 폐기·만료 토큰 거절·원문 토큰 미저장 검사 통과 |
| 권한 상승 | 가입의 `is_admin`/임의 작성자 필드 거절. 관리자 `admin_user`, 판매자 `approved_seller`, 소유자 `record(..., owner=...)` 검사 | pytest + 추가 33개 관리자 경로 요청 통과 |
| 비공개 심사 | draft/pending는 일반 공개 불가, `published` 확인, 숨김 이후 판매자가 종료로 재노출하지 못함 | 심사 우회/숨김 복구 회귀시험 통과 |
| 공개 개인정보 | `main.py:81`의 공개 campaign DTO는 사업자번호·대표자·연락처·주소를 포함하지 않음. `main.py:443` 판매자 예약은 자기 공구와 별칭만 반환 | 공개 응답의 시험용 민감 마커 부재 확인. 다른 사람 예약 철회 거절 시험 통과 |
| 복구 | `main.py:196`의 존재 여부와 같은 응답. 15분 reset 토큰, 단일사용, 변경 시 모든 세션 폐기 | 기존/없는 이메일 동일 응답, 재사용 거절, outbox 삭제 시험 통과 |
| 탈퇴 | `main.py:231`: 현재 비밀번호 확인, 활성/심사 공구 제한, 활성 예약 철회, 토큰 전부 삭제, 입점서/저장/차단 삭제, 질문 원문 치환, 이메일/닉네임 익명화 | pytest 및 추가 질문 원문·모든 토큰 DB 검사 통과 |
| XSS·외부 URL | JSX 텍스트 출력. `main.py:695`는 HTML escape와 JSON-LD의 `<`, `>`, `&` 치환. 외부 이동은 `safeExternalUrl`의 HTTPS·자격정보 금지와 `noopener noreferrer`; 복귀는 내부 경로만 허용 | HTML/JSON-LD 공격 문자열 회귀시험 통과. `dangerouslySetInnerHTML`, DOM HTML sink, eval, postMessage 위험 경로 검색에서 발견 없음 |
| CORS·CSRF 경계 | `main.py:31`의 명시적 localhost origin, 쿠키 credentials 비허용. 현재는 Authorization Bearer 인증 | 악성 origin에 ACAO 없음, 허용 origin 일치, ACAC 없음 검사 통과. 향후 쿠키 전환 시 CSRF 재검토 필요 |
| 재고·포인트 | 조건부 원자적 UPDATE, 고유 claim/order/ledger 키, 실패시 rollback, SQLite 쓰기는 `db.py:78`의 `BEGIN IMMEDIATE` | 예약·쿠폰 동시성, 부족 포인트 롤백, 환불 재시도, 음수 잔액 시험 통과 |

복구 토큰과 초기 데모 계정 비밀번호는 **의도적으로 원문이 있는 로컬 개발 파일**이다. `runtime/outbox/*.json`, `runtime/demo-accounts.json`은 API로 제공하지 않으며 Git에서 제외된다. “평문 비밀이 어디에도 없다”는 표현을 사용해서는 안 된다. 운영 SMTP·본인확인·관리자 다중인증·분산 rate limit은 이번 구현 완료 범위가 아니다.

탈퇴는 전체 물리 삭제와 다르다. 주문·ledger·감사·신고 레코드 등은 UUID와 함께 남는다. 신고의 자유입력 사유나 관리자 의견에 사용자가 개인정보를 넣었다면 잔존할 수 있다. 가입 안내(`auth-pages.tsx:226`)는 운영 기록 잔존과 실정보 입력 금지를 알리지만, 실제 사용자 서비스 전에는 종류별 보관기간·목적·삭제/가명처리·백업 삭제 정책과 시행 절차를 결정하고 검사해야 한다. 현재 로컬 시험을 법적 보관 적합성 검증으로 표시하지 않는다.

Android main manifest는 `allowBackup="false"`, `usesCleartextTraffic="false"`다. debug 전용 네트워크 설정은 `10.0.2.2`에만 HTTP를 허용하고 그 외는 거절한다. `capacitor.config.ts:6`의 mixed-content/cleartext 옵션은 남아 있으므로 실제 운영 URL·release 변형에서 최종 병합 manifest와 WebView 동작을 다시 확인해야 한다. 감사자는 APK의 release 네트워크 정책이나 실기기 패킷을 검사하지 않았다.

## AI 산출물과 공유 경계

- 연구 API 세 경로는 모두 관리자 의존성을 사용한다. 실제 앱 구매자 기록을 학습/추론 입력과 자동 연결하는 경로는 확인하지 못했다.
- `serving.py:12`는 고정 로컬 파일명만 읽고 임의 경로를 받지 않는다. 추론은 정의된 수치 특성의 정확한 집합, 유한성·비음수·일부 값 범위를 검사한다.
- `serving.py:26`은 모델의 SHA-256을 metadata와 비교한 뒤 joblib로 읽는다. 이 비교는 우발적 파일 변경 탐지다. 공격자가 모델과 metadata를 함께 바꿀 수 있는 환경의 신뢰 보증이나 악성 pickle 방어가 아니다. 업로드/원격 모델 교체 기능은 없으며 신뢰한 파이프라인 산출물만 사용해야 한다.
- JSON 구조 검사에서 모델/평가/동시구매 규칙에 CustomerID·이메일·전화·주소 필드는 없었다. 요약과 overlap 감사에는 원본 대조용 **비개인 거래 한 행**의 송장번호·상품·일시·국가가 들어 있다. 이를 모든 산출물이 순수 통계만이라고 표현하지 않는다. 고객 식별번호/앱 계정은 해당 행에 없다.
- JSON 11개와 AI 로그 2개에서 이메일·한국 휴대폰·개인 절대경로·sk/Bearer/개인키 패턴 검사는 모두 0건이었다. 이것은 패턴 기반 검사이며 임의 형식 개인정보를 전부 탐지했다는 뜻이 아니다.
- `company_source_extract`, `materials_inventory`, `requirements_source`, `requirements_traceability.*`는 원문 추출/내부자료와 경로 노출을 줄이기 위해 공유에서 제외한다. manifest의 파일명·크기·해시는 원문 내용과 구분한다.
- 최종 공개 인덱스의 JSON 7개를 직접 읽어 CustomerID/customer_id/user_id/email/phone/address 식별자 키가 없음을 대조했다. staged 모델 278,756바이트의 SHA-256은 `6dc6e4269671949f5a5f4b80a7dc11647604a4be50647d2303534bcb19f3c0ec`로 metadata와 일치하며, 바이너리 내 이메일·사용자 경로 마커도 0건이었다. 학습 코드는 UCI 세션의 수치 특성 8개만 X로 선택한다. 바이너리 패턴 검사를 모델 개인정보 유출 가능성 전반의 증명으로 해석하지 않는다.

### Git 확인 시점

다음 명령을 실제 실행했다.

```powershell
git check-ignore -v ai-pipeline/artifacts/company_source_extract.json ai-pipeline/artifacts/materials_inventory.json ai-pipeline/artifacts/requirements_source.json ai-pipeline/artifacts/requirements_traceability.md backend/runtime/demo-accounts.json backend/runtime/outbox/example.json frontend/android/local.properties
git diff --cached --name-only
.\backend\.venv\Scripts\python.exe scripts/share-check.py
```

원문/추출 파일은 `ai-pipeline/.gitignore:4`–`:7`, runtime은 루트 `.gitignore:65`, Android 개인 설정은 해당 `.gitignore`가 제외함을 다시 확인했다. `.dockerignore`도 같은 원문 추출/설정/runtime을 제외한다.

최종 후속 검사 시점에는 공개 변경 파일 **126개**가 staged였고, `share-check.py`는 **98 staged text files**, 비밀/개인 경로/금지 원본 파일 매칭 없이 `SHARE_CHECK_PASS`(exit 0)를 반환했다. script가 작업 파일 대신 `git show :경로`로 인덱스 내용을 읽는 점도 확인했다. 별도 읽기 전용 `git cat-file --batch` 검사로 인덱스 원문을 대조했다. 이메일은 전부 `example.com`, 휴대폰은 `01000000000` 시험 fixture였다. 경로 매칭 1개는 비개인 공용 런타임 위치 공용 runtime 디렉터리여서 사용자 이름 노출과 구분했다. 종전 세 문서의 개인 PC 경로는 인덱스에서 더 이상 발견되지 않았다. PNG/JAR의 이미지·실행 내용까지 검증한 것은 아니다.

위 인덱스의 `정렬된 경로 + 공백 + blob OID`를 줄바꿈으로 연결한 SHA-256은 `6bb679049076fb779350327dfcaf4ea5a537821efb36f7fcd58acb2ff4a5e2cd`다. 이 값은 **검사 시점 식별자**이며 최종 커밋 해시가 아니다. 이후 CSP 배치·E2E 증거·감사 파일·Android 스크립트 등의 작업 파일이 추가 수정됐다. 이 문서 역시 감사자가 수정만 하고 stage하지 않는다.

확인 시점 인덱스와 작업 파일에는 다음 차이가 있었다. 메인이 최종본을 재stage하고 공유 검사·차이 확인을 마쳐야 한다.

- `frontend/vite.config.ts`: 인덱스는 기존 `head`, 작업 파일·dist는 검증된 `head-prepend`.
- `frontend/evidence/audit-full.json`: 인덱스는 수정 전 moderate 4건, 작업 파일은 수정 후 0건. 최신 0건 원문을 읽어 대조했다.
- `scripts/e2e.cjs`: 작업 파일에 CSP 순서·인라인 차단 검사가 추가됐다.
- `scripts/android-smoke.ps1`: 인덱스의 이전 blob은 JS 문자열 중간에서 끝났고 작업 파일은 완성본이다. 작업 파일을 PowerShell Parser로 검사해 `ANDROID_SMOKE_SCRIPT_PARSE_PASS`를 얻었다. 실제 Android 실행 검증과 문법 검사는 별개다.

감사자는 `git add`, commit, push를 실행하지 않았다. 이후 커밋·push된 전체 파일까지 직접 검사했다고 표시하지 않는다.

## 감사자가 실행한 검사

### 백엔드 회귀시험

프로젝트의 `backend` 디렉터리에서 다음을 실행했다. fixture는 `tempfile.TemporaryDirectory`의 별도 SQLite DB/outbox를 사용하며 로컬 개발 DB를 열지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
24 passed, 1 warning in 5.49s
exit code: 0
warning: Starlette TestClient의 httpx 지원 deprecation
```

첫 감사의 23개 시험에 최소 모집수량 상태 시험이 추가된 뒤 위 24개를 직접 재실행했다. 초기 시스템 Python 시도는 작업 디렉터리/`pwdlib` 미설치로 import 단계에서 중단됐다. 전용 가상환경 실행은 실제 성공했으며 두 실패를 기능시험 통과로 계산하지 않았다.

### 추가 격리 API probe

동일 fixture를 새 Python 프로세스에서 직접 열어 검사했고, `finally`에서 fixture 종료·engine dispose·임시 디렉터리 정리를 수행했다. 핵심 재현 코드는 다음과 같다. `backend`에서 `@' ... '@ | .\.venv\Scripts\python.exe -`로 실행한다. 토큰 원문과 입력 비밀번호는 출력하지 않는다.

```python
import sys, json
sys.path.insert(0, 'tests')
import conftest
from app.db import SessionLocal, User, Token, Record, engine
from app.security import issue_token, token_digest
from sqlalchemy import select

fixture = conftest.setup.__wrapped__()
try:
    c, p, ids = next(fixture)
    checks = [
        ('GET', '/api/admin/applications', None),
        ('POST', '/api/admin/applications/'+p['pending']['id']+'/review', {'decision':'approved','note':''}),
        ('GET', '/api/admin/campaigns', None),
        ('POST', '/api/admin/campaigns/'+ids['campaign']+'/review', {'decision':'active','note':''}),
        ('GET', '/api/admin/reports', None),
        ('POST', '/api/admin/reports/'+ids['campaign']+'/resolve', {'action':'hide'}),
        ('POST', '/api/admin/orders', {'user_id':p['buyer']['id'], 'campaign_id':ids['campaign'],
                                    'external_reference':'SECURITY-PROBE', 'eligible_amount':100, 'status':'confirmed'}),
        ('POST', '/api/admin/orders/'+ids['campaign']+'/refund', None),
        ('GET', '/api/research/summary', None),
        ('GET', '/api/research/bundles', None),
        ('POST', '/api/research/purchase-intent', {}),
    ]
    for headers, expected in [({},401),(p['buyer']['headers'],403),(p['seller']['headers'],403)]:
        assert [c.request(m,path,json=data,headers=headers).status_code for m,path,data in checks] == [expected]*11
    with SessionLocal() as db:
        expired = issue_token(db, db.get(User,p['buyer']['id']), lifetime=-1)
        db.commit()
        assert db.get(Token,token_digest(expired)) is not None and db.get(Token,expired) is None
    assert c.get('/api/me',headers={'Authorization':'Bearer '+expired}).status_code == 401
    for origin, allowed in [('https://attacker.invalid',False),('http://127.0.0.1:5173',True)]:
        r = c.options('/api/me',headers={'Origin':origin,'Access-Control-Request-Method':'GET',
                                       'Access-Control-Request-Headers':'Authorization'})
        assert (r.headers.get('access-control-allow-origin') == origin) == allowed
        assert r.headers.get('access-control-allow-credentials') is None
    q = c.post('/api/campaigns/'+ids['campaign']+'/questions',headers=p['buyer']['headers'],
               json={'body':'SECURITY_PROBE_PRIVATE_QUESTION'}).json()
    assert c.request('DELETE','/api/me',headers=p['buyer']['headers'],json={'password':conftest.PASSWORD}).status_code == 200
    public = c.get('/api/campaigns/'+ids['campaign']+'/questions')
    assert q['id'] not in [r['id'] for r in public.json()['items']]
    with SessionLocal() as db:
        assert not db.scalars(select(Token).where(Token.user_id == p['buyer']['id'])).all()
        assert 'SECURITY_PROBE_PRIVATE_QUESTION' not in json.dumps(db.get(Record,q['id']).data)
    for name,value in [('x-content-type-options','nosniff'),('x-frame-options','DENY'),('cache-control','no-store')]:
        assert public.headers.get(name) == value
    print('SECURITY_PROBE_PASS')
finally:
    try:
        next(fixture)
    except StopIteration:
        pass
    engine.dispose()
    conftest.TEST_RUNTIME.cleanup()
```

실제 실행 출력: `SECURITY_PROBE_PASS`, exit 0. 관리자 경계 guest/buyer/seller 각 11건, expired_and_hashed_session, cors_origin_and_credentials, deleted_question_and_all_tokens, api_security_headers가 전부 PASS였다. 문서의 코드는 같은 검사를 재현하도록 출력 형식만 축약했다.

### 프런트 의존성 감사

`frontend`에서 `npm audit --json`을 실행했다. exit 0, info/low/moderate/high/critical 모두 0, 총 0건이었다. 이 결과는 해당 날짜의 npm advisory와 현재 잠금 파일 기준이다. 정적 분석·인증 로직 검증을 대신하지 않는다.

메인의 `backend/evidence-dependencies.json` 원문을 읽어 pip-audit 결과의 의존성 45개가 모두 `vulns:[]`임을 확인했다. 감사자가 pip-audit를 별도로 재실행했다고 표시하지 않는다. 프런트 증거 파일의 수정 전/후 차이는 위 Git 항목에 기록했다.

## 미실행·미확인

다음은 실제 개인정보·실거래 서비스를 출시하기 전의 남은 조건이다. 현재 개발 빌드의 성공으로 대체하지 않는다.

| 출시 전 조건 | 현재 한계 |
|---|---|
| 개인정보 목적·최소수집·연령·보관·삭제·백업 | 테스트 안내만 존재. 신청정보는 로컬 DB의 평문이고, 자유입력 신고·감사 기록 등이 탈퇴 뒤 남을 수 있음. 운영 접근통제·암호화·위탁/국외이전·삭제/열람 창구·파기 작업·복구 검증 미완료 |
| 인증·계정 공격 방어 | JS 접근 가능한 토큰, 단일 프로세스 제한, 메일 소유 확인 없음. 운영 웹/네이티브 세션, 관리자 MFA·분산 제한·비밀관리 시험 필요 |
| 실제 호스팅·네트워크 | 공개 TLS·운영 CORS/CSP·SPA 프레이밍 방어·release WebView 정책 미검증. 개발 주소 허용을 그대로 출시 정책으로 사용하지 않음 |
| 운영 DB | PostgreSQL 실서버 직렬화 충돌/재시도·migration·부하·복구·권한 분리 미검증 |
| 거래·배포 | 실제 본인/사업자 확인·PG/에스크로·정산/환불·외부 쿠폰·서명키·Play Data safety/삭제 URL·실기기 악용 대응 미검증 |

최종 인덱스 재반영·커밋·push 확인은 메인의 후속 통합 증거가 필요하다. 공개 개발 소스 검토와 서비스 출시 승인을 구분한다.

## 메인의 후속 수정 기록

위 감사 뒤 Capacitor 설정도 기본 `cleartext:false`, `allowMixedContent:false`로 바꿨다. `MODU_LOCAL_ANDROID=1`을 명시한 debug 빌드 스크립트에서만 로컬 HTTP를 허용하고 종료 시 환경변수를 복구한다. 실제 release 병합 manifest·WebView 검증은 여전히 남아 있다. 운영 빌드는 환경변수 없이 HTTPS API와 함께 다시 sync해야 한다. 이 단락은 감사자의 실행 결과가 아니라 메인이 적용한 후속 수정 기록이다.
