# 커뮤니티 피드백과 서버 이전

2026-11-05 사용자 요청. 디자인 유지, 만 14세 가입, 글·댓글 수정, 8시간 로그인 종료 개선, Neon 협업 접근, 기존 Elice 인스턴스로 서버 이전을 함께 진행한다.

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
- 원격 프로젝트 디렉터리에 Python 3.12와 격리 환경을 구성한다. 기존 8080 프로세스는 변경하지 않는다.
- 공개 HTTPS 주소·포트·인스턴스 가용성, CORS·호스트·카카오 콜백을 확인한 뒤 운영 트래픽을 전환한다. SSH 접속 성공을 운영 전환 완료로 간주하지 않는다.
- 기존 Neon DB를 유지해 회원·게시글을 재생성하거나 이중 복사하지 않는다. DB 연결은 기존 제한된 런타임 계정을 사용한다.
- Render 무료 Hobby 플랜은 팀원 초대를 지원하지 않는 것을 콘솔에서 확인했다. 유료 업그레이드는 하지 않았다.
- Neon은 Collaborator + 해당 프로젝트 Editor 초대를 준비했다. Editor는 DB 연결·수정도 가능하므로 명시적 승인과 실제 초대 결과를 별도 기록한다.

## 검증 상태

신규 수정·세션 검사 13개와 프런트 전체 164개 통과. 전체 서버 검사에서 8시간 문구를 기대하던 기존 약관 검사 1개가 발견되어 새 정책에 맞게 갱신했다. 최종 API/실제 PostgreSQL/화면/배포/Android 검증 결과는 완료 후 아래에 추가한다.

## 브랜치·리뷰·GitHub 배지

- `codex/modu-yuga`에 기능 단위 커밋·푸시하고 기존 PR #1의 설명을 실제 구현·검증 상태로 갱신한다. main 병합·강제 푸시·보호 규칙 우회는 하지 않는다.
- README에 실제 Actions 상태 배지를 연결했다. 이는 프로필 Achievement와 다르다.
- Pull Shark는 실제 PR 병합 활동, Pair Extraordinaire는 실제 공동 작성 커밋과 병합, Galaxy Brain은 실제 도움이 된 Discussion 답변, Starstruck은 다른 이용자의 평가와 관련된다. 자동 수여·조건·표시 지연은 GitHub가 결정하므로 획득을 보장하지 않는다.
- 유효한 변경을 PR로 남기고 공동 작성자 표기는 실제 기여가 있을 때만 한다. 배지용 무의미한 PR·상호 추천·가짜 공동 작성·검토 생략은 수행하지 않는다. 유료 후원 배지는 무료 운영 범위에서 제외한다.
- 공식 참고: https://docs.github.com/en/account-and-profile/reference/profile-reference
