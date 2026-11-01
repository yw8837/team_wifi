# Gates: Android 외부 베타 배포

Scope: 모두의 육아 - 육아템 공동구매,핫딜을 외부 테스터가 설치하고 HTTPS 서버에서 시험할 수 있게 한다. 실결제·배송은 베타 범위에 포함되지 않음을 명시한다.

- [x] G1: 운영 설정·인증·개인정보·동시성 회귀 검사가 통과한다.
  CHECK: .venv/Scripts/python.exe -m pytest tests -q
  CWD: backend
  EXPECT: passed
  EVIDENCE: pytest35pass; 전용 로컬 PostgreSQL26checks; 서버 별도 검토의 P1 두 건 수정·재검토 승인. 실제 프록시·클라우드 검증은 G3/G4.
- [x] G2: 프런트 단위시험과 배포 빌드가 통과한다.
  CHECK: npm test
  CWD: frontend
  EXPECT: passed
  EVIDENCE: unit58pass; 일반/베타 TypeScript+Vite build; 320px mocked API browser QA. 실제 서비스 주소 빌드는 G5에서 다시 수행.
- [ ] G3: 전용 HTTPS 서버와 영속 DB가 배포되고 재시작 후 데이터가 유지된다.
  EVIDENCE: pending; 배포 URL·건강 확인·재시작 전후 비식별 시험기록 필요
- [ ] G4: 비회원 탐색·가입·로그인·참여/철회·신고·탈퇴와 실패 복구가 실제 배포 환경에서 검증된다.
  EVIDENCE: pending; QA 시나리오 및 실제 결과 필요
- [ ] G5: release AAB/APK의 서명·API 주소·명칭·권한을 검증하고 Android 설치/실행을 확인한다.
  EVIDENCE: local debug 설치/기동/앱 내부 API200 확인. 서명 beta release와 실제 HTTPS 연결은 아직 미완료이므로 이 게이트는 열려 있음.
- [ ] G6: 개인정보·약관·삭제·지원 안내가 실제 동작 및 운영 조건과 일치하고 공개 URL로 열릴 수 있다.
  EVIDENCE: pending; 운영 연락처 및 호스팅 지역 확정 필요
- [ ] G7: Play 내부 테스트 트랙에 배포가 완료되고 테스터 참여/설치 링크를 확인한다.
  EVIDENCE: pending; 초안·업로드 상태만으로 충족되지 않음
- [ ] G8: 변경·재현법·잔여 범위·증거가 저장되고 커밋/푸시 및 CI 결과가 확인된다.
  EVIDENCE: pending
