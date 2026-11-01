# Gates: Android 외부 베타 배포

확인일: 2026-11-01. 웹/API 배포와 Play 내부 테스트 활성화는 완료. 실제 휴대폰 설치·실행·비회원 목록은 사용자 보고로 확인했다. Android 인증 후 전체 동선은 후속 시험 범위다. 실결제·배송은 범위 밖이다.

- [x] G1: 운영 설정·인증·개인정보·동시성 회귀 검사가 통과한다.
  EVIDENCE: E에서 pytest40; 기존 PG26 + 계정별 제한 실제 로컬 PG46; 별도 spec/quality 검토 수용. 프록시 IP 의존 제거, endpoint 재인증 유지.
- [x] G2: 프런트 단위시험과 배포 빌드가 통과한다.
  EVIDENCE: 기존58개 단위시험·320px 모의 API 브라우저. 43be76c의 GitHub API/UI CI 두 run 성공. Render 실제 HTTPS 설정의 Vite build 성공.
- [x] G3: 전용 HTTPS 서버와 영속 DB가 배포되고 재배포 후 데이터가 유지된다.
  EVIDENCE: https://moduyuga-beta.onrender.com, Neon Free. 배포 전 계정·저장 목록이 43be76c 배포 후 동일하게 조회됨; 시험 계정·초대 정리 확인.
- [x] G4: 비회원 탐색·가입·로그인·참여/철회·신고·탈퇴와 실패 복구가 실제 배포 API에서 검증된다.
  EVIDENCE: 43be76c public HTTPS75checks pass; 타인 자원, 손상 JSON, 입력 반사, 중복·stale 예약, 세션 폐기, CORS 포함. Android UI 연결은 G5.
- [x] G5: release AAB/APK의 서명·API 주소·명칭·권한을 검증하고 Android 설치/실행을 확인한다.
  EVIDENCE: 서명 release30 offlinechecks pass, Play AAB 처리 성공. release 실제 Android 설치/실행·비회원 목록은 사용자 응답으로 확인. 독립 관찰·native 로그가 아니며 이전 debug를 대체 증거로 쓰지 않음.
- [x] G6: 개인정보·약관·삭제·지원 안내가 실제 동작 및 운영 조건과 일치하고 공개 URL로 열린다.
  EVIDENCE: 4개 실제 HTTPS legal200, 운영 연락처·Render/Neon 싱가포르·HMAC 제한 문구. 법률 적합성 인증이나 수동 보관 기한 집행의 미래 완료를 뜻하지 않음.
- [x] G7: Play 내부 테스트 트랙 배포 및 테스터 참여/설치를 확인한다.
  EVIDENCE: 11/1 23:02 활성·내부 테스터에게 제공됨. 승인 테스터 계정의 참여 페이지 열림. Play 다운로드·설치·실행은 사용자 응답으로 확인.
- [x] G8: 변경·재현법·잔여 범위·증거를 저장하고 커밋/푸시 및 CI 결과를 확인한다.
  EVIDENCE: 코드43be76c push, push/PR CI success, Draft PR #1. 로컬 비밀과 원본 로그 제외. 후속 문서 커밋은 Git 이력 참고.

내부 테스트 배포와 첫 설치 확인 조건을 충족했다. 모든 Android 인증 후 동선을 독립 실기기 검증했다고 확대하지 않는다. 해당 동선은 후속 베타 시험 기록에 추가한다.
