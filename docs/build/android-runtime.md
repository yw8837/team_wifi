# 모두육아 Android 실행 검증 · 2026-11-01

상태: **APK 파일은 존재하지만 Android 실행 검증은 미완료다. 전용 에뮬레이터가 두 번의 90초 프로브 내 ADB 기기로 연결되지 않아 설치·앱 실행·통신·스크린샷 단계에 도달하지 못했다.**

## 시험 대상과 경계

- 입력 APK: `artifacts/android/modu-yuga-debug.apk`. 최초 시험 입력 SHA-256: `930C41DD902BC8FA8F59685DCAF305B0C94F116282A0AFA95D9DE6657BC3DC47`. 이 입력은 CSP 추가 전 생성된 APK이며 메인의 후속 재빌드와 구분한다.
- 앱 ID: `kr.moduyuga.app`. 전용 테스트 AVD: `ModuYugaLocal`, Android 35 Google APIs x86_64, 포트 5554/5555.
- SDK는 설치 원본을 가리키는 junction을 사용한다. 원본 SDK·AVD 설정은 이번 보조 검증에서 수정하지 않았다.
- 사용자가 쓰던 다른 프로세스나 ADB 서버를 종료하지 않았다. 메인이 생성하고 종료를 허용한 해당 AVD의 QEMU 프로세스만 재시작했다.
- raw emulator stdout에는 ADB 공개키 등이 포함될 수 있어 Git 작업폴더 밖의 private runtime 폴더에만 저장했다. 공개 문서에는 필요한 진단 사실만 기록한다.

## 확인한 문제와 실행 시도

| 실행 | 실제 확인 | 판정 |
|---|---|---|
| 인계받은 WHPX 실행 | QEMU 프로세스는 생존하고 약 2.25GB를 사용했지만 `adb devices -l`은 빈 목록, 5554/5555 연결 없음 | 앱 설치 전 단계 |
| WHPX verbose·kernel 로그 재시작, 약 90초 | WHPX operational 출력 이후 커널 초기화 출력과 ADB 기기 없음 | 해당 전용 QEMU만 중지 |
| `-accel off`, `-gpu swiftshader`, 1536MB 요청 | 시작 로그 후 프로세스 종료, stderr에 원인 없음 | 대안 실행 실패; 원인은 미확정 |
| WHPX 유지, 2코어, 1536MB 요청, `-feature -Vulkan,-QuickbootFileBacked`, 기존 `swiftshader_indirect` | `Decompressing Linux...`와 Android init·SELinux·드라이버 초기화로 진행 | 부팅 진행을 실제 확인했으나 첫 90초 프로브는 timeout |

마지막 설정에서 SDK가 생성한 `hardware-qemu.ini`는 요청값과 다르게 `hw.ramSize = 2560`이었다. 시작 로그도 `Increasing RAM size to 2560MB`라고 표시했다. 이 이미지가 최소 RAM을 상향하므로 “1.5GB 에뮬레이터로 실행 성공”으로 보고할 수 없다. 관찰 당시 호스트 여유 RAM은 약 1.2GB였다. 부팅 지연의 단일 원인이 메모리라고 확정하지는 않는다. 같은 실행에서 추가 90초 프로브를 수행했으나 역시 ADB 연결은 되지 않았다.

## 재현 스크립트

`scripts/android-smoke.ps1`은 PowerShell 7용이다. 기존 테스트 에뮬레이터에 연결하여 최대 90초 안에 `sys.boot_completed=1`을 확인한 뒤 다음을 순서대로 실행한다.

1. APK SHA-256과 기기 상태 기록.
2. `adb -s emulator-5554 install -r` 및 `am start -W`.
3. 앱 PID·활동 상태 확인.
4. 디버그 WebView에 ADB port forward 후 DevTools Protocol로 실제 화면의 둘러보기 링크를 누르고 요청/화면 상태 관찰.
5. 같은 WebView 실행 문맥에서 개발 API `/health`, `/campaigns`를 호출해 HTTP 상태 확인. 네트워크 관찰과 별도로 실행한 probe임을 JSON에서 구분.
6. 테스트 기기 화면을 PNG로 저장.

```powershell
pwsh -NoProfile -File scripts/android-smoke.ps1 -BootTimeoutSeconds 90
```

에뮬레이터가 실행 중이지 않을 때만 `-StartEmulator`를 추가하면 위의 마지막 부팅 설정을 재현한다. 실행 중인 동일 AVD를 발견하면 자동 종료하지 않고 중단한다. 생성되는 raw 부팅 로그는 Git 밖의 private runtime 경로에 둔다.

```powershell
pwsh -NoProfile -File scripts/android-smoke.ps1 -StartEmulator -BootTimeoutSeconds 90
```

스크립트는 부팅·설치·통신 중 어느 단계라도 실패하면 성공을 출력하지 않는다. 기본 결과는 Git에서 제외된 `artifacts/android/runtime/`에 저장된다. `webview-api.json`의 실제 HTTP 상태·화면 텍스트 및 `app-screen.png`가 생성돼야 앱 통신/화면의 증거로 사용할 수 있다. 이번 실행의 도달 여부는 아래 최종 상태에 기록한다.

## 최종 실행 상태

| 항목 | 실행 결과 | 증거 |
|---|---|---|
| 스크립트 파싱 | PowerShell parser 오류 0개 | 실제 `Parser.ParseFile` 실행 결과 `PowerShell parser PASS` |
| 첫 90초 프로브 | exit 1, 부팅 확인 timeout | `artifacts/android/runtime/android-smoke.log`, 마지막 기록 16:25:34 KST |
| 같은 실행의 두 번째 90초 프로브 | exit 1, 부팅 확인 timeout | `artifacts/android/runtime-lowmem-second/android-smoke.log`, 마지막 기록 16:27:47 KST |
| Android 내부 초기화 | 커널·init·adbd 서비스·surfaceflinger 시작까지 진행 | private kernel 로그의 아래 발췌 |
| 호스트 ADB 연결 | 기기 목록 비어 있음, 127.0.0.1:5555 연결 거부(10061) | 실제 `adb devices -l`, `adb connect` 결과 |
| APK 설치 | 미실행 | 부팅 gate를 통과하지 않아 install 호출 전 중단 |
| 앱 시작·실제 API 통신 | 미실행 | 앱 WebView가 없어 CDP 통신 검증 미도달 |
| Android 앱 스크린샷 | 미생성 | `app-screen.png` 없음 |
| 시험 QEMU 종료 | 16:29:05 KST 전용 PID 41588만 종료 | 종료 전 실행 경로와 `-avd ModuYugaLocal` 일치 검사 후 `Stop-Process` |

개인정보·공개키를 포함하지 않는 진단 로그 발췌:

```text
WHPX(10.0.26300) is installed and usable.
Feature 'QuickbootFileBacked' (17) is overridden to 'disabled'
Increasing RAM size to 2560MB
Decompressing Linux...
[  185.736232] init: starting service 'surfaceflinger'...
[  189.360346] init: starting service 'adbd'...
[  189.456712] init: ... started service 'adbd' has pid 457
```

확인한 장애는 “Android 내부 서비스는 진행하지만 호스트 ADB transport가 생성되지 않음”이다. WHPX 사용 가능 검사는 통과했으므로 하드웨어 가속이 설치되지 않았다고 보고하지 않는다. 메모리 압력·Quick Boot backing·해당 Windows/에뮬레이터 조합 중 단일 원인을 분리 확정하지 못했다. 개발 PC의 사용자 프로세스 종료나 시스템 보안/가상화 설정 변경은 수행하지 않았다.

후속 실행에서는 메인이 최신 APK를 다시 생성한 뒤 이 스크립트로 기기 부팅을 먼저 통과시키거나, 이미 정상 부팅된 별도 테스트 장치에서 설치·실행을 검증해야 한다. 이 문서는 APK 생성 성공을 Android 앱 실행 성공으로 대신하지 않는다. 설치 이후의 스크립트 분기는 작성·파싱만 확인했으며 실제 기기로 실행 검증하지 못했다.
