# 로컬 Android 검증의 자원 사용 확인

확인일: 2026-11-01. Android Studio는 빌드·Play 업로드의 필수 요소가 아니다. 기존 SDK와 JDK를 사용한 명령행 빌드로 서명 APK/AAB를 이미 만들었다. 로컬 에뮬레이터를 외부 베타 배포의 필수 경로로 계속 실행한 판단을 수정한다.

## 확인한 사실

| 항목 | 확인 결과 |
|---|---|
| 기존 Android Studio | `C:/Program Files/Android/Android Studio`, 폴더 생성일 2026-08-17. 이번 작업에서 새로 설치한 것으로 볼 근거 없음 |
| 기존 Android SDK | `%LOCALAPPDATA%/Android/Sdk`, 폴더 생성일 2026-08-24 |
| 이번 SDK 연결 | `C:/Users/Public/CodexRuntime/android-sdk`는 위 기존 SDK를 가리키는 junction. SDK 전체의 복사본이 아님 |
| 이번 가상 기기 | `D:/CodexRuntime/avd/ModuYugaLocal.avd`, 오늘 생성. 관련 AVD 디렉터리 총 14.298GiB. 10GiB userdata 이미지 포함 |
| 이번 별도 Gradle 캐시 | `D:/CodexRuntime/gradle-cache`, 오늘 생성. 0.050GiB |
| 정리 전 남은 공간 | C: 35.23GiB / D: 24.63GiB |
| 실행 자원 | 첫 release 에뮬레이터 실행 중 가용 RAM 약 356MiB까지 감소. ADB/창 응답 실패, 이후 release 설치 미검증 |
| 재확인 | OS 재시작 후 emulator/qemu/Android Studio/테스트 PostgreSQL 프로세스 없음. 재시작 원인을 확정하지 않음 |

전체 디스크 사용량의 과거 기준값이 없으므로 C/D의 사용량 전체를 이번 작업에 귀속하지 않는다. SDK와 Android Studio의 기존 파일도 삭제 대상에 포함하지 않는다.

## 정리 범위와 현재 상태

삭제 대상은 이번 테스트용 `ModuYugaLocal.avd`, 같은 폴더의 `ModuYugaLocal.ini`, 별도 `gradle-cache` 세 곳만이다. 경로가 D:/CodexRuntime 내부인지와 하위 reparse point가 없는지 확인했다. 원본 소스·디자인·데이터·서명키·APK/AAB는 보존한다.

사용자가 세 경로 삭제를 승인했습니다. 영구 삭제 명령은 자동 승인 검토에서 `blocked by policy`로 거부되어 실행되지 않았습니다. 이후 복구 가능한 휴지통 이동을 완료했고, 사용자가 휴지통 비우기를 완료했다고 알려왔습니다. 세 원래 경로는 없습니다. 기존 SDK·Android Studio·서명키·APK/AAB는 보존했습니다. 현재 작업은 `E:/Team_Wifi`에서만 진행합니다.

## 앞으로의 검증 경로

1. 기존 SDK/JDK의 명령행 빌드 또는 기존 GitHub Actions를 사용한다. Android Studio 설치·실행을 요구하지 않는다.
2. 서명·Manifest·정식 명칭·HTTPS API·권한 검사는 완성된 APK/AAB에서 수행한다. 현재 30개 검사 통과.
3. 설치 검증은 Play 내부 테스트와 실제 Android 기기를 우선한다. 로컬 에뮬레이터를 재생성·기동하지 않는다.
4. 에뮬레이터가 특별히 필요한 후속 작업이라도 가용 메모리·디스크 확인 없이 실행하지 않는다. 낮은 여유 자원에서 실패한 부팅을 반복하지 않는다.

## 배포와 증거

- 무료 공개 웹: https://moduyuga-beta.onrender.com
- 실제 HTTPS API 75개 검사 통과. 검토된 limiter 보완43be76c를 배포한 뒤75개 검사를 다시 통과했다.
- 서명 APK/AAB 생성, APK v2와 AAB JAR 서명 검증 완료. Google Play가 AAB 2(0.2.0), minSDK24/targetSDK36을 처리한 화면 확인. 11/1 23:02 내부 테스트 활성화와 승인 계정의 초대 페이지 접근까지 확인했다.
- **release Android의 실제 휴대폰 설치·실행·비회원 목록 표시는 사용자 보고로 확인했다. Play 참여 링크는 발급·접근 확인했다.** APK 생성·AAB 처리와 설치 검증을 구분한다.
- 비공개 로컬 증거: `artifacts/beta/resource-audit-before.json`, `android-release-verification.json`, `public-api-results.json`. 서명키 파일은 비공개 경로에 그대로 있으며 공유하지 않는다.
