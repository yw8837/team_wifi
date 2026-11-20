# 네이버 로그인 소프트웨어 구현 — 2026-11-06

`signup_01`, `signup_03`, `login_01`의 네이버 경로를 서버 OAuth2 어댑터와 합성 테스트로 구현한다. 실제 네이버 애플리케이션 등록, 제공 항목 동의 변경, 자격정보 입력, 사전 검수와 실제 계정 왕복은 수행하지 않았다. 기존 Kakao OIDC 설정과 외부 콘솔은 변경하지 않는다.

## 공식 계약과 최소 정보

- [네이버 로그인 API 명세](https://developers.naver.com/docs/login/api/api.md): `https://nid.naver.com/oauth2.0/authorize`의 인증 코드와 `state`를 검증한 뒤, 고정된 `https://nid.naver.com/oauth2.0/token`으로 서버가 POST한다. `scope`는 이 OAuth2 경로에서 전송할 필요가 없는 내부 구분값이므로 생략한다.
- [회원 프로필 조회 명세](https://developers.naver.com/docs/login/profile/profile.md): 서버가 토큰을 Bearer 헤더로 `https://openapi.naver.com/v1/nid/me`에 전달한다. HTTP 성공, `resultcode=00`, 비어 있지 않은 문자열 `response.id`를 확인한다. 이 ID는 애플리케이션마다 다른 회원 식별자다. 네이버 로그인 아이디나 이메일을 계정 식별 근거로 사용하지 않는다.
- [공식 개발 가이드의 재인증](https://developers.naver.com/docs/login/devguide/devguide.md): 재인증에는 `auth_type=reauthenticate`를 전송한다. 이 구현은 OAuth2.0이며, 별도 OIDC 경로의 ID 토큰 서명·nonce·auth_time 검증을 수행했다고 주장하지 않는다. Google·Kakao의 기존 OIDC nonce 검증은 유지한다.

네이버 콘솔에서 회원 식별자 외 이메일·이름·연령대·생일·전화번호·프로필 사진을 요청하지 않는 최소 제공 항목 설정이 필요하다. 이 설정 자체는 코드 실행이나 추천으로 승인되지 않는다. API가 추가 프로필 필드를 보내더라도 어댑터는 `id`만 반환하며 다른 필드와 접근·갱신 토큰을 저장하거나 리다이렉트하지 않는다.

## 서버 흐름

1. `POST /api/auth/social/naver/start`: `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`, 기존 공개 API/웹 원점 설정이 모두 있을 때만 시작한다. 키 하나라도 없으면 provider 목록에서 숨기고 시작 요청은 503으로 거절한다.
2. 기존 한 번 쓰는 state와 10분 flow TTL을 사용한다. Naver 재인증 flow는 5분으로 제한한다. OIDC nonce와 제공자 PKCE 필드는 Naver OAuth2 요청에 넣지 않는다. 로그인 시작 기기의 별도 challenge/verifier 증명은 계속 필수다.
3. 콜백은 state 해시·제공자·만료·대기 상태를 확인하고, 네트워크 교환 전에 state를 소비한다. Naver 토큰 요청에도 원래 state를 전송하며 저장된 해시와 다시 대조한다. 인증 코드를 재시도하지 않는다.
4. 토큰·회원 정보 API 오류, 리다이렉트, 비정상 JSON/토큰 유형·유효기간·식별자는 실패 처리한다. HTTP 환경 프록시와 자동 리다이렉트는 사용하지 않는다. 브라우저/앱에는 flow ID만 전달한다.
5. 기존 claim 절차가 기기 verifier, 소유 계정, 제공자별 identity, 필수 동의와 만 14세 확인을 검사한다. 같은 이메일은 자동 가입·계정 합치기 근거가 아니다. 다른 회원에게 이미 연결된 identity는 409, 다른 계정의 연결 claim은 403이다.
6. 재인증은 연결된 동일 subject와 시작 계정만 허용한다. 네이버의 강제 로그인 요청과 로컬 flow 생성 시각 5분 제한을 결합하며, 제공자가 서명한 인증 시각을 별도로 검증하는 것으로 설명하지 않는다.
7. Android 반환 주소와 flow의 모바일 신호를 유지한다. 기존 운영자 모바일 로그인 차단은 Naver claim에도 적용된다. 이 신호를 변조 불가능한 기기 증명으로 설명하지 않는다.

## 설정 예시와 남은 외부 확인

[서버 환경 변수 예시](../../backend/.env.example)의 `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`은 서버에서만 설정한다. 프런트엔드 `VITE_` 변수나 Android 번들에 넣지 않는다. 등록할 callback은 `PUBLIC_ORIGIN/api/auth/social/naver/callback`이다. 임의 클라이언트 callback이나 return URL을 서버에 받지 않는다.

실제 운영 가능 판정에는 네이버 앱·정확한 callback·최소 제공 항목·서비스 URL·사전 검수·실제 계정의 신규 가입/기존 로그인/연결/재인증 왕복을 별도로 확인해야 한다. 이번 작업은 해당 외부 설정을 활성화하거나 실제 로그인을 시도하지 않는다.

## 검증 범위

`backend/tests/test_naver_auth.py`는 고정된 합성 HTTP 응답만 사용한다. 실제 네이버 서버에는 접근하지 않는다. 설정 부재, state/제공자/TTL, 코드 재사용, 취소, 토큰·회원 정보 실패, 추가 프로필 폐기, 중복 연결/제공자 격리, onboarding, 기기 proof, Android 운영자 차단과 재인증을 검사한다. 기존 `test_social_auth.py`와 `test_social_events.py`를 함께 실행해 Google/Kakao 검증과 Kakao 계정 상태 변경 처리의 회귀를 확인한다.

실행 결과와 전체 릴리스 게이트는 메인 작업의 검증 기록에서 구분한다. 합성 테스트 통과를 제공자 콘솔 활성화 또는 실제 네이버 로그인 관찰로 표시하지 않는다.

확인한 실행: `python -m pytest backend/tests/test_naver_auth.py backend/tests/test_social_auth.py backend/tests/test_social_events.py -q -p no:cacheprovider` → **54 passed** (2026-11-06, 합성 DB·HTTP transport). 실제 제공자 호출과 운영 계정은 사용하지 않았다.
