# 무료 베타 DB 선택 — PostgreSQL과 MongoDB

확인일: 2026-11-01. MongoDB 대안을 검토한 뒤 사용자가 **Neon 유지·전용 DB 접속정보의 Render 저장·무료 배포**를 명시적으로 승인했습니다. Neon PostgreSQL과 Render Free로 배포했고 공개 HTTPS 검사 75건을 통과했습니다. 아래 비교는 선택 근거이며 전환 대기 상태가 아닙니다. 최신 검증·배포 상태는 [STATUS](STATUS.md)를 기준으로 봅니다.

## 추천과 이유

**현재 베타는 Neon Free PostgreSQL 유지 (추천).** 이미 SQLAlchemy 기반 API와 동시 참여·초대·복구·탈퇴를 검증했다. 새 57개 화면도 상품·공구·주문·결제·쿠폰·포인트·취소/환불의 관계와 일관성이 중심이다. 기존 구현을 유지하면 DB 교체보다 남은 사용자 동선과 외부 배포 검증에 시간을 쓸 수 있다.

MongoDB도 사용할 수 있고 여러 문서에 걸친 ACID 트랜잭션을 지원한다. ‘공동구매에는 MongoDB를 쓸 수 없다’는 판단은 틀리다. 다만 이 프로젝트에서 이득이 있는지는 변경할 모델·쿼리·원자적 처리·운영 비용과 비교해야 한다. DB 종류를 바꾸는 것만으로 성능·보안·확장성이 좋아지지는 않는다.

| 항목 | PostgreSQL 유지 (추천) | MongoDB Atlas Free로 전환 |
|---|---|---|
| 현재 코드 | SQLAlchemy·psycopg·관계/유일성 제약을 유지 | DB 모델·쿼리·트랜잭션·초기화·시험 도구 재작성 |
| 참여·혜택·주문 일관성 | 현재 트랜잭션 기반, 향후 도메인 테이블 확장 | 단일 문서 조건부 갱신 + 필요 시 다중 문서 트랜잭션 설계 |
| 상품 속성·수집 원문 | JSON/JSONB로 유연한 항목 표현 가능. 현재 Record.data는 JSON | BSON 문서와 중첩 속성에 자연스럽게 대응 |
| 운영 관계 | 외래키·유일성·제약과 SQL 집계 | 참조 무결성·삭제 전파를 앱에서 관리하고 인덱스/집계 설계 |
| 기존 검증 | 로컬 PG 26검사, 실제 Neon DB 연결 API 8검사 통과 | 해당 검증을 MongoDB에서 다시 수행해야 함 |
| 무료 조건 | 전용 Neon Free 생성 완료, 0.25 CU·5분 절전·6시간 복구 이력 확인 | Free M0 선택. 약 0.5GB(인덱스 포함), 100 ops/s·500연결 등 한도 |
| 일정 영향 | 배포·HTTPS·Android release·Play 검증이 남음 | 위 작업에 DB 전환·동시성/탈퇴/복구 회귀검증이 추가됨 |

표의 난이도는 현재 코드 기준의 상대 평가다. MongoDB 전환 기간을 실측하지 않았으므로 ‘하루면 완료’와 같은 수치를 약속하지 않는다. PostgreSQL도 현재 범용 Record 구조를 실제 상품·주문·원장 모델로 발전시키고 마이그레이션을 관리해야 한다.

## MongoDB를 선택할 때의 구현 방법

```text
Android / 웹
    │ HTTPS · 인증·권한·입력 검증
    ▼
FastAPI
    │ PyMongo 드라이버 · 서버 비밀 환경변수 · TLS
    ▼
MongoDB Atlas Free — 모두의 육아 전용 DB
```

앱에 DB 접속정보를 넣지 않는다. 현재 동기 FastAPI 핸들러를 유지한다면 동기 PyMongo가 작은 변경이다. 비동기로 전환한다면 공식 PyMongo Async API를 사용하고 핸들러/수명주기/연결 공유 범위를 함께 변경한다. MongoDB용 URI를 SQLAlchemy의 현재 DATABASE_URL에 넣는 것으로 전환되지 않는다.

1. **전용 Atlas Free M0 구성.** 실제 콘솔에 Free가 표시되는지, 비용과 리전을 확인한다. Flex·Dedicated·백업 구독·카드는 사용하지 않는다. 신규 약관이나 접근권한은 필요한 시점에 확인한다.
2. **최소 권한과 네트워크.** 앱 DB만 읽고 쓰는 계정, TLS, 서버 비밀 환경변수를 사용한다. 실제 Render 서비스의 outbound 주소 범위를 확인해 Atlas IP access list에 제한한다. 공유 CIDR은 해당 서버 하나만을 식별하지 않으므로 DB 인증도 반드시 유지한다. `0.0.0.0/0` 전면 허용으로 해결하지 않는다.
3. **저장 계층 분리.** User·Session/Recovery·Invite·Campaign/Participation·Coupon/PointLedger·Report/Block용 repository와 인덱스를 만든다. 이메일·멱등 키·회차별 활성 참여 중복을 DB 제약으로 막는다. 무한히 늘어나는 주문·댓글·참여자 배열은 상품 한 문서에 넣지 않는다.
4. **원자적 처리.** 남은 정원을 조건으로 공구를 갱신하고, 참여·혜택이 함께 변하면 세션 트랜잭션으로 묶는다. 동일 공구 문서 쓰기로 경합을 감지하고 제한된 재시도를 설계한다. 복구코드·초대의 단회 소비와 계정 생성/세션 폐기도 함께 처리한다.
5. **실결제 확장.** 결제사업자 호출을 DB 트랜잭션 안에서 기다리지 않는다. 주문의 결제대기 상태, 검증된 웹훅, 고유 이벤트 키, 취소/환불 보상 처리를 둔다. 금액은 원화 정수 등 정확한 표현을 사용한다.
6. **데이터 이전.** 현재는 가상 초기 데이터뿐이므로 검증된 초기화 스크립트로 다시 만들 수 있다. 사용자 가입 이후라면 ID/관계/해시/상태를 보존한 이관·대조·롤백 계획이 필요하다. 전환 검증 전 기존 Neon DB를 삭제하지 않는다.
7. **검증과 백업.** 초대 경쟁·마지막 재고·복구 회전·탈퇴/종속 데이터·다중 문서 롤백·재시작 유지·실제 API/Android를 확인한다. 무료 운영에서는 별도 암호화 백업과 복원 시험·탈퇴 재반영 절차를 마련한다. 파일을 떠놓는 것만으로 복원 가능을 주장하지 않는다.

## 비용 확인에서 발견한 점

MongoDB 최신 공식 문서에는 Free M0의 **선택형 백업 구독**이 안내돼 있다. 확인 시점의 가격은 하루 $0.10, 월 최대 $3이며 결제수단이 필요하다. 일부 계정에 순차 제공되는 private preview라 화면에 없을 수 있다. 따라서 ‘Free 클러스터니까 백업도 무료’로 판단하면 안 된다. 이 프로젝트의 **무료만 사용** 조건에서는 활성화하지 않는다.

공식 문서 검색 결과와 Context7 일부 색인에는 과거 ‘M0 백업 미지원’ 설명도 남아 있다. 현재 원문 백업 페이지를 확인해 구독형 옵션을 구분했다. 실제 계정의 플랜 화면 확인 없이 요금·지원 기능을 확정하지 않는다.

## 현재 실행 상태

- Neon 전용 Free DB 생성·가상 데이터 초기화 완료. 런타임 계정은 스키마 생성 권한 없이 앱 테이블 읽기/쓰기만 허용한다.
- 클라이언트 TLS와 실제 DB 대상 API 8개 검사 통과. 이 검사는 로컬 프로세스에서 실제 클라우드 DB에 연결했으며 공개 HTTPS 서버 검증은 아니다.
- **Neon 유지와 Render 비밀 저장·무료 배포 승인 완료.** 대안 검토 뒤 명시적 승인을 받았고 실제 배포·공개 HTTPS 검증을 완료했다. 현재 상태는 [STATUS](STATUS.md)에 기록했다.
- MongoDB 계정/DB/과금 자원은 생성하지 않았다. 두 DB 동시 운영은 동기화·탈퇴·백업 부담을 늘리므로 현재 베타에는 추천하지 않는다.

## 공식 자료

- [Atlas Free 제한](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/): 저장량·처리량·연결·전송·네트워크 제약.
- [Free Cluster Backups](https://www.mongodb.com/docs/atlas/backup/cloud-backup/free-cluster-backup/): 선택형 유료 구독·결제수단·private preview.
- [MongoDB Transactions](https://www.mongodb.com/docs/manual/core/transactions/): 단일 문서 원자성·다중 문서 ACID와 설계 주의점.
- [PyMongo Async 전환](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/): 공식 동기/비동기 드라이버 선택 기준.
- [Atlas IP access list](https://www.mongodb.com/docs/atlas/security/ip-access-list/): 허용 주소/CIDR 및 임시 접근.

소스 근거: `backend/app/db.py`, `backend/app/main.py`, `backend/app/beta.py`, `backend/requirements.txt`. 실제 DB 검사 증거는 비밀 없는 `artifacts/beta/neon-predeploy-results.json`에 보존했다. 접속정보는 별도 비공개 디렉터리에만 있다.
