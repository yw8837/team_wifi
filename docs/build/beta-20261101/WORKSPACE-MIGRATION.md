# E 드라이브 작업 경로 통합

2026-11-01 사용자 확정: 이 PC의 활성 프로젝트는 `E:/Team_Wifi` 한 곳에서 작업한다.

| 항목 | 확인 결과 |
|---|---|
| 새 저장소 | E 내부의 독립 `.git`. 이전 D 저장소나 C 워크트리의 Git 메타데이터에 의존하지 않음 |
| 원격·브랜치 | `https://github.com/yw8837/team_wifi.git`, `codex/modu-yuga` |
| Codex 프로젝트 설정 | `FINAL_핀테크`의 저장 경로가 `E:\Team_Wifi`로 변경된 것을 앱 도구에서 확인 |
| 앱 파일 복사 | 63,703개 중 63,702개 복사·1개 동일 파일 건너뜀. 실패·불일치 0건 |
| 앱 보존 검증 | 재생성 가능한 의존성·캐시를 제외한 4,267개 파일, 약 559MiB의 크기와 SHA-256 일치 |
| 과거 기획·회의·데이터 | `_archive/legacy-project`로 1,225개 복사. 캐시 등을 제외한 1,213개 파일, 약 241MiB의 크기와 SHA-256 일치 |
| 비밀·서명키 | DB 접속정보, 업로드 키, DPAPI 암호 파일도 동일성 검사에 포함. ACL은 현재 Windows 사용자와 SYSTEM만 허용 |
| 새 경로 실행 | E의 Python으로 백엔드 40개 시험 통과. PowerShell 경로 스크립트 구문 검사 통과 |
| 이전 체크아웃 | Codex 도구가 현재 채팅의 primary checkout 보관 제거를 거부함. C의 이전 체크아웃과 D 원본은 보존하며 활성 개발에는 사용하지 않음 |

동일성 검사에서 `.git`, `.venv`, `node_modules`, `install-temp-node_modules`, `.gradle`, `__pycache__`는 제외했다. 소스·원본 자료·생성물·실행 증거·비밀 파일은 포함했다. 검증 이후 E에서 수정한 파일은 Git 변경 이력으로 관리한다. 이전 폴더가 삭제됐다고 표시하지 않는다.

## 다음 실행부터

```powershell
Set-Location -LiteralPath E:/Team_Wifi
. ./scripts/use-workspace.ps1
```

이 명령은 현재 shell에서만 TEMP/TMP, Gradle, npm, pip, uv 캐시를 `.runtime` 아래로 지정한다. 기존 SDK/JDK/Node/Python은 그대로 사용한다. 외장 드라이브가 없으면 다른 드라이브에 대체 폴더를 만들지 않는다. 팀원이 다른 PC에서 복제할 때는 자신의 경로를 사용하며, E 고정 지침은 이 Windows 작업 환경에 적용한다.

Android Studio나 가상 기기 없이 명령행 빌드·Play 내부 테스트로 진행한다. 로컬 에뮬레이터는 자동 생성·실행하지 않는다. 테스트 가상 기기와 캐시 약 14.35GiB는 휴지통 이동 후 사용자가 휴지통을 비웠다고 확인했다. [자원 사용 기록](RESOURCE-AUDIT.md)에 범위를 기록했다.

로컬 원본 증거는 `artifacts/beta/workspace-migration-verification.json`, `migration-app-copy.log`, `migration-core-copy.log`, `migration-legacy-copy.log`, `pytest-after-migration.txt`다. 원문 로그와 비밀 파일은 Git에 올리지 않는다.
