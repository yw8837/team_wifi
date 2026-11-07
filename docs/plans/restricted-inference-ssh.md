# 제한 SSH 추론 전송 — 승인 검토안

작성일: 2026-11-06. 아래 본문은 최초 승인 검토안과 당시 검증 범위를 보존한다. **현재는 사용자가 추론·상태 조회 전용 연결을 명시 승인하여 전용 공개키 등록, 실제 제한 검증, Render 비밀 파일·환경변수 저장까지 완료했다. 새 제품 소스의 운영 배포와 Render에서 실제 추론하는 최종 확인은 진행 중이다.**

## 현재 적용 상태

- 사용자의 명시 응답: “전용 연결 추가 승인 — 공개 웹·앱에서도 기존 GPU 모델 사용”. 기존 관리자 개인키는 Render에 제공하지 않았다.
- 새 키 지문: `SHA256:3BwQiYDzH0g6+fM5CZcFFsqAmDWdU8vJZszATm9dqTk`. 기존 `authorized_keys` 내용을 보존하고 제한된 한 줄만 추가했다. 서버 파일 권한은 0600/디렉터리 0700, 로컬 개인키는 사용자·SYSTEM ACL이다.
- 실제 OpenSSH 검증 12개 통과: 고정 호스트 키 확인, 상태·최소 합성 추론, 셸·임의 명령·scp·sftp·PTY·포트 전달 거부. 안전 영수증은 `artifacts/community-completion-20261106/restricted-ssh-authorization.json`이다.
- Render 기존 API 서비스의 Secret Files와 환경변수 9개는 **Save only**로 저장했다. 저장 자체를 배포 성공으로 간주하지 않는다. 기록은 `render-inference-configuration.json`이다.
- 플랫폼의 읽기 전용 비밀 파일은 서비스 소유 0700 디렉터리/0400 파일로 복사한 뒤 사용한다. 키 준비 실패 시 서버를 시작하지 않도록 실행 스크립트를 수정했고 실제 Linux에서 재현·검증했다. 원본 비밀 파일은 변경하지 않는다.
- `observe` 품질 메타데이터 전송은 위 두 동작과 별도 범위다. 후보 코드의 기본값은 비활성이며 추가 승인 전 실제 서버·키 권한·Render 설정에 적용하지 않는다.

## 최초 승인 검토안 (이하 역사적 시점)

## 추천 구성과 승인 범위

**새 전용 Ed25519 키 + 강제 명령 + 호스트 공개키 고정 (추천)**. 기존 관리자 키를 Render에 복사하지 않는다. Render는 이 전용 키로 기존 GPU 서버의 제한된 건강 확인 및 추론만 호출한다. 새 인스턴스·유료 자원·공용 크레딧 LLM API를 만들거나 사용하지 않는다.

이 문서는 승인 자체가 아니다. 실제로 적용하기 전 사용자가 **새 공개키 등록과 Render의 전용 비밀키 저장을 명시적으로 승인**해야 한다. 승인 시에도 범위는 아래 두 동작으로 한정한다.

- `health`: 지정된 로컬 모델 서버의 `/health`, `/v1/models` 조회.
- `infer`: 지정된 로컬 모델 서버의 `/v1/chat/completions`에 검증된 JSON 요청 한 건 전달.

셸, 터미널, 파일 전송·열람, 포트·에이전트·X11 전달, DB, 관리자 명령, 임의 URL·모델·도구 실행 권한을 이 키에 부여하지 않는다. 기존 관리자 키와 기존 서비스 설정은 별도 관리한다.

## 검토할 정확한 키 권한 형식

원격 운영자가 신뢰된 관리자 경로로 확인한 절대 경로에 다음 **한 줄**을 등록하는 안이다. 아래 경로와 공개키는 자리표시자다. 승인 전에 실제 경로·운영 계정·새 공개키 지문·선택 포트를 검토 기록에 확정해야 한다. 개인키는 문서나 Git에 적지 않는다.

```text
restrict,command="/approved/venv/bin/python /approved/root/scripts/serve-restricted-inference.py --port 8091" ssh-ed25519 NEW_DEDICATED_PUBLIC_KEY
```

- `restrict`는 OpenSSH의 PTY, 포트 전달, 에이전트 전달, X11 전달, 사용자 rc 실행을 제한한다. 강제 명령에는 호출자가 바꿀 수 없는 절대 Python/스크립트 경로와 고정 포트를 넣는다.
- 호출자는 항상 `moduyuga-inference-v1` 명령만 요청한다. 게이트웨이는 `SSH_ORIGINAL_COMMAND`가 이 문자열과 정확히 같은 경우만 처리한다. 다른 명령, scp, sftp, 인수가 붙은 명령은 거부한다.
- 포트는 운영자가 설치 시 **8091 또는 8092 하나만** 고른다. 기본은 8091이며 요청 JSON은 포트를 포함할 수 없다. 8092 응답을 이유로 4B 모델을 자동 채택하지 않는다.
- 대상 모델 별칭은 `moduyuga-qwen3-1.7b`로 고정한다. `/v1/models` 및 추론 응답에 해당 별칭이 없으면 실패한다. 별칭 검사는 GGUF 가중치의 암호학적 신원 증명이 아니다. 실제 프로세스 인수·가중치 경로·체크섬은 배포 검증에서 별도로 확인한다.
- 이 키를 수용할 계정, 스크립트와 Python의 소유자·쓰기 권한, `authorized_keys` 파일 권한은 승인 후 관리자 검증 대상이다. 가능하면 별도 최소권한 OS 계정을 사용한다. 기존 계정을 쓸 경우 강제 명령의 구현 결함이 그 계정의 권한으로 이어질 위험을 검토한다.

## Render 쪽 설정 계약

기본값은 비활성이다. 다음 값이 모두 명시되어야 연결을 시도한다. 이 파일을 준비하는 과정에서 실제 비밀값은 만들거나 저장하지 않았다.

```text
ASSISTANT_SSH_ENABLED=true
ASSISTANT_SSH_HOST=APPROVED_HOST
ASSISTANT_SSH_PORT=22
ASSISTANT_SSH_USER=APPROVED_ACCOUNT
ASSISTANT_SSH_PRIVATE_KEY_PATH=/absolute/path/to/dedicated-secret-file
ASSISTANT_SSH_HOST_KEY=ssh-ed25519 TRUSTED_HOST_PUBLIC_KEY_BASE64
```

- 개인키는 새 전용 Ed25519 키만 허용한다. 명시한 절대 경로의 파일만 읽으며 SSH agent, 기본 키 탐색, SSH config, ProxyCommand를 사용하지 않는다. POSIX에서는 그룹/다른 사용자 권한이 있는 키 파일을 거부한다. 권장 모드는 소유자만 읽기 가능한 0400 또는 0600이다.
- 서버 호스트 공개키는 이미 신뢰된 관리자 채널에서 확인한다. 첫 접속 자동 신뢰나 `ssh-keyscan` 결과만으로 승인을 대신하지 않는다. 키 알고리즘을 Ed25519로 제한하고, 실제 호스트 키와 고정값을 비교한 뒤에만 클라이언트 인증을 수행한다.
- 클라이언트 의존성은 `paramiko==4.0.0`이다. 지연 import하며 기능 비활성 시 연결하거나 키를 읽지 않는다. 현재 프로젝트 전용 `.runtime/remote-inference-deps`에서 실제 4.0.0 import/API만 검증했다. 운영 requirements 반영·이미지 설치와 Render 비밀 파일 설정은 별도 단계다.
- 원격 게이트웨이는 Python 표준 라이브러리와 공유 프로토콜 모듈만 사용한다. 원격에 Paramiko를 설치할 필요는 없다.

## 프로토콜과 자원 제한

요청은 버전 1 JSON 한 건이며 허용 필드만 받는다. 중복 키, NaN/Infinity, 잘못된 타입, 추가 URL·포트·도구 필드는 거부한다. 추론은 시스템 문자열과 사용자 문자열 각 한 개만 허용한다. 각각 UTF-8 6,000/24,000바이트 이하이며 전체 전송은 32KiB 이하이다. 모델은 위 1.7B 별칭, temperature 0, stream false, enable_thinking false, response_format json_object, max_tokens 1~400으로 고정한다.

- 추론/건강 확인은 클라이언트 프로세스당 동시에 한 건만 진행한다. 게이트웨이도 고정 `.runtime/restricted-inference.lock`의 비차단 `flock`으로 프로세스 간 동시 실행을 한 건으로 제한한다. 잠금 파일은 symlink를 따라 열지 않는다.
- 원격 요청 시간은 최대 40초, 전체 클라이언트 호출은 최대 45초다. 입력 읽기는 5초, 작업 뒤 출력 쓰기는 별도 1초 알람으로 제한한다. 클라이언트 마감 타이머는 SSH Transport를 닫으며 종료 시 채널·소켓을 닫는다.
- 원격 HTTP 호스트는 `127.0.0.1`이다. 위 세 경로 외에는 호출할 수 없으며 HTTP 리다이렉트를 따라가지 않는다. HTTP 응답은 60,000바이트, SSH 응답은 64KiB, stderr는 2KiB로 제한한다.
- 오류에는 고정 코드만 포함한다. 코드가 질문·응답·개인키·스택·원격 stderr를 로그로 출력하지 않는다. 실제 모델 서버/SSH/플랫폼의 별도 로깅 설정은 배포 전에 확인해야 한다.
- 직렬 제한은 총 호출 횟수 제한이 아니다. 키 유출 시 반복 요청으로 기존 GPU를 계속 점유할 수 있다. 운영 API의 인증·빈도 제한, 키 보관, 사용 상태 확인을 함께 유지한다.

## 승인 후 수행할 검증과 철회

승인 후에도 먼저 새 키만으로 고정 건강 확인과 최소 추론 한 건을 검증하고, 셸·임의 명령·scp·sftp·포트/에이전트/X11 전달 거부, 동시 요청 busy, 잘못된 호스트 키 인증 전 거부, 입력/출력 마감과 자원 정리를 실제 Linux/OpenSSH에서 확인해야 한다. 모델 별칭과 실제 가중치의 대응도 확인한다. 이 검증을 마치기 전 원격 경계가 실제로 강제된다고 주장하지 않는다.

철회 시 Render에서 기능을 비활성화하고 전용 비밀키 파일/설정을 제거한 뒤 서버 `authorized_keys`에서 **해당 새 공개키 줄만** 제거한다. 이미 인증된 진행 중 요청은 키 삭제만으로 종료되지 않을 수 있으므로 필요 시 해당 제한 세션을 운영자가 종료한다. 새 요청은 키 제거 후 인증될 수 없다. 회전도 새 전용 키 검증 후 이전 줄 제거 순서로 진행하며 기존 관리자 키는 건드리지 않는다.

## 로컬 검증 기록

`backend/tests/test_remote_inference.py`는 외부 소켓·SSH·HTTP를 모의한다. 활성화 기본값, 요청 필드/크기/타입, 호스트 키 비교 후 인증 순서, 고정 명령, 명시 키 설정, 응답/오류/모델 제한, 예외 정리, 포트와 HTTP 경로, 리다이렉트 거부 및 출력 마감 계약을 검증한다. Windows에서 실행한 로컬 테스트이며 실제 Linux의 OpenSSH `restrict`, SIGALRM, `flock` 강제와 Render 연결 가능성은 아직 미검증이다. 합성 테스트 키 문자열만 사용하며 실제 개인키나 생산 키는 생성하지 않는다.

최종 로컬 실행: `python -m pytest backend/tests/test_remote_inference.py -q` — **82 passed**, 기존 Starlette/httpx 사용 중단 경고 1건. 세 Python 파일의 `py_compile` 통과. 합성 정수 오버플로 입력과 고정 오류 코드 처리도 포함한다. 결과/소스 해시는 `artifacts/community-completion-20261106/remote-inference-local-results.json`에 기록했다.

## 2026-11-06 연결 적용 직전 확인

전용 키는 로컬에서 준비했으며 서버 등록과 Render 비밀 파일 저장은 사용자 명시 응답 전까지 실행하지 않았다. 공개키 지문은 `SHA256:3BwQiYDzH0g6+fM5CZcFFsqAmDWdU8vJZszATm9dqTk`다. 개인키는 E 전용 폴더에 현재 사용자와 SYSTEM ACL로 보호했다.

기존 승인된 관리자 SSH를 통해 전용 게이트웨이 코드를 별도 경로에 배치해 상태 조회 성공과 임의 명령 거부를 확인했다. 이 검사는 OpenSSH 전용 키 제한의 실제 검증을 대신하지 않는다. 확정 강제 명령은 `/home/elicer/Team_Wifi/.venv/bin/python /home/elicer/Team_Wifi/.runtime/restricted-inference-v1/scripts/serve-restricted-inference.py --port 8091`이다.

클라이언트 통합을 포함한 89개 모의·로컬 검사가 통과했다. 추가 보안 검토에서 공개 상태 조회가 추론 슬롯을 점유할 수 있음을 확인하여 상태 API의 네트워크 조회를 제거했다. 상태는 실제 질문의 최근 결과만 읽으며, 외부 키 등록은 별도 사용자 질문의 응답을 기다린다.
