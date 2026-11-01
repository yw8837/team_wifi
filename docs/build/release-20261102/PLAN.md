# 공개 심사 제출 — 실행 계약

사용자 요청: 조직 계정 Team_Wifi의 모두의 육아 - 육아템 공동구매,핫딜(kr.moduyuga.app)을 프로덕션 심사 제출까지 진행한다. 제출·승인·공개를 별도로 기록한다.

## 첫 공개 범위

- 비회원: 확인한 육아용품 외부 정보·출처·비교 유의사항 탐색, 카테고리/검색, 단가·배송비 비교, 공구 수요와 질문 읽기.
- 일반 회원: 정보 저장, 공구 수요 제안·관심 표시·질문, 본인 글 삭제, 신고·차단, 복구코드·계정 삭제.
- 운영자: 신규 공개 콘텐츠 신고 처리·숨김. 기존 관리자 권한을 새 외부인에게 부여하지 않는다.
- 실제 주문·결제·배송·공급 계약·가격/재고 보증을 제공하지 않는다. 관심은 예약·구매 계약이 아니다.
- 시험 공구·쿠폰·포인트·가상 판매자 데이터는 공개 모드의 서버 허용 범위에서 차단한다. 원본 자료와 기존 beta 코드는 보존한다.

## 구현 경계

`MODU_ENV=public_release`, `PUBLIC_RELEASE`, `DEPLOYED=BETA or PUBLIC_RELEASE`를 분리한다. 공개 가입은 초대만 생략하며 HTTPS/PostgreSQL/요청 제한/성인 확인/복구/삭제 보호는 유지한다. 프런트는 `VITE_PUBLIC_RELEASE=1`, 안전장치는 deployed 모드 공통. 현재 코드의 BETA=false를 곧바로 로컬 모드로 전환하지 않는다.

기존 데이터 구조 Record를 재사용하되 공개 정보/수요/댓글/관심/저장은 별도 kind로 저장한다. API prefix는 `/api/release`다. 인증은 기존 `/api/auth/*`, `/api/me`와 `/api/config`를 재사용한다. 데이터 수집은 최소화하며 새 추적 SDK와 광고를 넣지 않는다.

## API 계약

목록 응답은 JSON 배열, 단건은 JSON 객체다. 시간은 ISO 8601 UTC 문자열. 인증 사용자 관련 상태는 비회원에게 false. 오류는 기존 HTTPException detail 형식을 사용한다.

- `GET /offers`, `GET /offers/{id}`: Offer {id,title,category,summary,source_name,source_url,source_checked_at,entry_type,price,shipping_fee,unit,expires_at,comparison_notes,is_affiliate,saved}. entry_type은 shopping_reference 또는 verified_offer. 확인하지 않은 가격/기한은 null, comparison_notes는 문자열 배열. 카테고리 링크를 공구/특가라고 부르지 않는다.
- `PUT /offers/{id}/saved`, `DELETE /offers/{id}/saved`, `GET /saved`.
- `GET /demands`, `POST /demands` {title,body,category}, `GET /demands/{id}`, `DELETE /demands/{id}`.
- Demand {id,title,body,category,author:{id,nickname},created_at,interest_count,interested,comment_count,own}. 관심 숫자는 실제 별개 계정의 현재 관심 수다.
- `PUT /demands/{id}/interest`, `DELETE /demands/{id}/interest`.
- `GET /demands/{id}/comments`, `POST /demands/{id}/comments` {body}, `DELETE /comments/{id}`. Comment {id,body,author:{id,nickname},created_at,own}.
- `POST /reports` {target_type:demand|comment|user,target_id,reason}. 신고 자체는 공개하지 않는다.
- 사용자 차단은 기존 `POST /api/blocks/{id}`를 재사용하되 공개 정보의 글·댓글 목록에 필터 적용.
- `GET /admin/reports`, `POST /admin/reports/{id}/resolve` {action:hide|dismiss|suspend,note}. 운영 권한 검사 및 실제 대상 검증.

목록은 제한된 수량을 반환하고 길이 제한·텍스트 렌더링·중복 관심/저장 방지·신고 제한·권한 검사를 서버에서 수행한다. 새 테이블/외부 라이브러리 없이 구현한다. UI는 기존 로고·색상·기본 컴포넌트를 유지하며, 탐색과 참여 UX를 우선한다.

## 완료 조건

1. 실제 확인한 출처와 작성 정보 확보, 시험 상품·가격·관심 수를 실제 정보처럼 표시하지 않음.
2. 공개 모드 회귀·권한·가입/복구/삭제·신고/차단·비회원 흐름을 검증.
3. HTTPS 운영 서버 배포와 새 release AAB의 모드/API/서명·버전 일치 확인.
4. 실제 화면의 스토어 이미지, 정확한 설명·개인정보·등급·데이터 보안·심사 접근 준비.
5. Play Console 프로덕션 검토 제출 결과를 실제 화면과 증거 파일로 확인. 막힌 항목은 누락 없이 기록.

작업은 E:/Team_Wifi 안에서 수행한다. C: 원본 보존 이전 작업과 충돌하는 동시 빌드를 피한다. 무료 서비스만 사용하며 기존 서명키와 APK/AAB, 기획/데이터를 보존한다. main 병합·force push·메일·Elice·에뮬레이터는 사용하지 않는다.
