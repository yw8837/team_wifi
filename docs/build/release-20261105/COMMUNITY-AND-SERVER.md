# 커뮤니티 피드백과 서버 이전

2026-11-05 사용자 요청. 디자인 유지, 만 14세 가입, 글·댓글 수정, 8시간 로그인 종료 개선, Neon 협업 접근, 기존 Elice 인스턴스로 서버 이전을 함께 진행한다.

2026-11-06 확인: 가입 연령·작성자 수정·새 세션 30일 정책은 운영 웹/API에 배포했고 Android 0.5.2(code 9)의 서명 패키지를 만들었다. Elice는 서버 내부 실행까지 완료했다. 외부 HTTPS 전환과 Neon 협업 권한 부여는 아래 조건이 남아 있다.

## 구현

- 내 글·댓글에 바로 보이는 수정 버튼과 저장·취소 제공. API는 작성자만 수정할 수 있고 운영자도 타인의 내용을 대신 바꾸지 않는다.
- 제목·본문·카테고리 검증과 기존 관심·댓글·글 ID·작성 시각 보존. `revision`으로 오래된 화면의 덮어쓰기를 409로 차단한다. 삭제·숨김·차단 상태도 다시 검사한다.
- 공개 서비스에서 새로 발급한 로그인 세션은 30일 유효하다. 기존의 8시간 세션은 소급 연장하거나 만료 상태에서 되살리지 않는다. 정책 변경 후 다시 로그인하면 새 기간을 적용한다. 로그아웃·계정 삭제·복구 시 폐기, 민감 작업 재인증과 복구코드 만료는 유지한다.
- 이메일·소셜 로그인은 같은 세션 발급기를 사용한다. 브라우저 탭의 sessionStorage 방식은 유지하므로 이 변경을 브라우저 재시작 후 자동 로그인 보장으로 설명하지 않는다.

## 데이터 확인

앱·웹 → 동일 FastAPI → 동일 Neon PostgreSQL이다. 실제 주문 DB가 아니며 `records.kind`로 커뮤니티 자료를 구분한다.

| 행동 | API | DB 기록 |
|---|---|---|
| 글 작성·조회·수정 | `/api/release/demands`, `/api/release/demands/{id}` | `release_demand`: title, body, category, 수정 시 updated_at; revision 증가 |
| 댓글 | `/api/release/demands/{id}/comments`, `/api/release/comments/{id}` | `release_comment`; parent_id는 글 ID |
| 관심 표시 | `/api/release/demands/{id}/interest` | `release_interest`; 계정·글 조합의 unique_key로 중복 방지 |
| 육아템 저장 | `/api/release/offers/{id}/saved` | `release_save`; 계정별 저장 |
| 운영 집계 | `/api/release/admin/insights` | 계정 중복 제거, 소수 집계 숨김; 관리자 인증 필요 |

SQL Editor에서 구조와 반영을 확인하는 읽기 전용 예시:

```sql
SELECT kind, status, count(*) AS row_count
FROM records
WHERE kind IN ('release_demand', 'release_comment', 'release_interest', 'release_save')
GROUP BY kind, status ORDER BY kind, status;

SELECT id, kind, parent_id, status, revision,
       to_timestamp(created) AS created_at, data->>'updated_at' AS updated_at
FROM records
WHERE kind IN ('release_demand', 'release_comment')
ORDER BY created DESC LIMIT 20;
```

이메일, 비밀번호 해시, 세션·복구·소셜 인증 레코드는 발표·공유 화면에 노출하지 않는다. 원본 운영 행을 다운로드해 Git에 올리지 않는다. 커뮤니티 본문은 공개 화면에서, 저장 구조는 위 메타데이터 쿼리로 대조한다.

## 서버와 협업

- 제공된 기존 Elice 인스턴스 SSH 접속 확인. C의 원본 키 보존, E의 비공개 복사본은 현재 사용자만 읽도록 제한했다. 키·DB URL·인증 비밀값은 Git 제외다.
- 원격 `/home/elicer/Team_Wifi`에 Python 3.12.16·격리 환경·동일 제품 소스 `05baede3`를 배치했다. Supervisor가 API를 관리하며 `127.0.0.1:8000`에서 내부 health의 `status=ok`, `mode=public-release`, `payments_enabled=false`를 확인했다. 기존 8080 프로세스는 변경하지 않았다.
- 실행 환경 JSON은 원격 비공개 디렉터리에 권한 600으로 보관한다. 문서·저장소에는 실제 비밀값을 포함하지 않는다. 프로세스 자동 재시작 설정은 인스턴스 자체의 상시 가용성 보장과 다르다.
- 공개 HTTPS 주소·포트·리전·인스턴스 가용성, CORS·호스트·카카오 콜백을 확인한 뒤 운영 트래픽을 전환한다. Elice Cloud가 로그인 화면에 있어 이 확인은 남아 있다. SSH 접속·내부 health 성공을 외부 전환 완료로 간주하지 않는다.
- 기존 Neon DB를 유지해 회원·게시글을 재생성하거나 이중 복사하지 않는다. DB 연결은 기존 제한된 런타임 계정을 사용한다.
- Render 무료 Hobby 플랜은 팀원 초대를 지원하지 않는 것을 콘솔에서 확인했다. 유료 업그레이드는 하지 않았다.
- Neon은 조직 Collaborator + 해당 프로젝트 Editor 초대를 준비했다. Editor는 DB 연결·수정도 가능하므로 명시적 승인 요청 상태다. 초대 발송·프로젝트 권한 부여는 아직 하지 않았다.

현재 공개 웹은 `https://moduyuga.onrender.com`, API와 설치 앱의 호환 주소는 `https://moduyuga-beta.onrender.com/api`다. 서버 내부 실행만 확인하고 기존 Render를 중단하지 않았다. 새 외부 주소가 검증되기 전에는 기존 OAuth 콜백과 설치 앱 연결을 유지한다.

## 검증 상태

검증한 제품 소스는 `05baede3b2ce8bf7a9d33bf2bc577d42a2627303`이다.

| 범위 | 확인 결과 | 로컬 근거 또는 공개 CI |
|---|---|---|
| Windows API 전체 | 182개 통과; 신규 수정·세션 13개 포함 | `artifacts/feedback-20261105/backend-community-final.log` |
| 프런트 | 164개 통과, TypeScript/Vite 빌드 성공 | `artifacts/feedback-20261105/frontend-community.log`, `frontend-community-build.log` |
| Elice Python 3.12 API 전체 | 182개 통과 | `artifacts/feedback-20261105/elice-tests-final.log` |
| GitHub Actions | UI·API·실제 PostgreSQL·Android 성공 | [실행 42049217881](https://github.com/yw8837/team_wifi/actions/runs/42049217881) |
| 실제 PostgreSQL | 동시 수정 200/409, 비작성자 차단, 기존 집계 보존, 댓글 revision·쓰기 제한 검증 | 위 API CI 잡 |
| 공개 배포 | API·웹 Live, health·14세 가입 화면·약관·세션 정책 확인 | `artifacts/feedback-20261105/live-and-artifact-checks.json`, `live-signup-age14.jpg` |
| Android | 0.5.2(code 9) APK/AAB 서명·정적 검증 49개 통과, 수정 UI·신규 연령 payload 포함 | `artifacts/feedback-20261105/android9/android-release-verification.json` |

API 배포 ID는 `dep-dbm9i5942hec73e2595g`, 웹 배포 ID는 `dep-dbm9kd56e07s73bilbog`다. 두 배포 모두 제품 커밋 `05baede3`를 사용한다. 완성 Android 산출물과 해시·CI 출처는 `artifacts/android/releases/9-0.5.2/`의 `moduyuga.apk`, `moduyuga.aab`, `build.json`에 있다.

전체 검사 중 예전 8시간 약관 기대값을 새 정책으로 갱신했다. 최초 Elice 검사에서는 배포 압축에 export 스크립트와 AI 서빙 파일이 빠진 것을 확인해 해당 커밋의 파일을 보충한 뒤 182개 전체 통과를 확인했다. 최종 API에는 PUT의 일반 쓰기 한도와 맞는 `write` 제한을 적용했고 실제 PostgreSQL 경로에서도 검증했다.

로컬 화면 검증용 서버 시작 명령은 자동 승인 검토가 차단해 실행하지 않았다. 작성자/비작성자 수정 버튼은 프런트 검사로, 저장·충돌·권한은 API와 PostgreSQL 검사로 확인했다. 실제 회원 세션으로 브라우저에서 수정 저장을 클릭하는 검증, Android 실기기 실행, Play 업로드는 이번에 수행하지 않았다. 이전 설치본에 새 UI가 자동 반영된 것으로 설명하지 않는다.

## 브랜치·리뷰·GitHub 배지

- 가입 연령은 `ee5d7d8`, 수정·세션·서버 실행 구성은 `05baede3`으로 `codex/modu-yuga`에 커밋·푸시했다. [PR #1](https://github.com/yw8837/team_wifi/pull/1)의 설명을 실제 구현·검증 상태로 갱신했고 Draft·미병합 상태를 유지한다.
- 최신 main `4db679d`의 팀원 역할표를 작업 브랜치로 받아 README 충돌을 해결했다(`1199fac`). 검증한 제품 커밋 이후 이 병합의 차이는 README 9줄뿐이다. main 자체는 변경하지 않았고 강제 푸시·보호 규칙 우회는 하지 않았다.
- README에 실제 Actions 상태 배지를 연결했다. 이는 프로필 Achievement와 다르다.
- Pull Shark는 실제 PR 병합 활동, Pair Extraordinaire는 실제 공동 작성 커밋과 병합, Galaxy Brain은 실제 도움이 된 Discussion 답변, Starstruck은 다른 이용자의 평가와 관련된다. 자동 수여·조건·표시 지연은 GitHub가 결정하므로 획득을 보장하지 않는다.
- 유효한 변경을 PR로 남기고 공동 작성자 표기는 실제 기여가 있을 때만 한다. 배지용 무의미한 PR·상호 추천·가짜 공동 작성·검토 생략은 수행하지 않는다. 유료 후원 배지는 무료 운영 범위에서 제외한다.
- 공식 참고: https://docs.github.com/en/account-and-profile/reference/profile-reference
