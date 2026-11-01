# 제공 자료·데이터 실제 활용 감사

기준: 2026-11-02, 활성 루트 `E:/Team_Wifi`. **제공 자료를 확보하고 데이터 분석·모델·관리자 연구 화면에 연결한 것은 확인했다. 현재 육아 상품의 개인화 추천, 실시간 구매 의도 CTA, 실거래 성능을 완성한 상태는 아니다.** 빌드 생성·내부 트랙 배포·프로덕션 심사 제출 여부는 이 데이터 감사의 판정 대상에서 분리한다.

이번 감사는 소스를 변경하지 않고 보존 원본·현재 코드·산출물을 대조했다. E 하위 보존 자료만 읽었으며 학습/전체 파이프라인을 다시 실행하지 않았다. 외부 Notion·블로그를 이번에 직접 다시 열지 않았고 배포 서버의 관리자 자격증명을 사용한 화면 시험도 수행하지 않았다. 따라서 아래 앱 연결은 **현재 저장소의 정적 경로와 실행한 로컬 추론 검증**의 범위다. Docker에 포함된다는 사실만으로 현재 배포 서버에서 관리자 기능까지 성공했다고 주장하지 않는다.

메인의 추가 확인: 2026-11-02 연결된 Notion 도구로 사용자가 제공한 페이지 ID를 다시 조회했으나 `404 / NOT_FOUND`가 반환됐다. 페이지 삭제 여부와 권한/워크스페이스 불일치는 이 응답만으로 구분할 수 없다. 보존된 내보내기는 검증했으며, 최신 온라인 페이지를 읽었다고 표시하지 않는다.

## 확보 → 실험 → 앱 연결 매트릭스

| 자료 | 확보·원문 읽기 확인 | 분석·모델 확인 | 실제 앱 연결 | 남은 한계 |
|---|---|---|---|---|
| D1 소비 행동 | 보존 CSV 1,000행×28열, 4원본 SHA 검증 통과. 실제 헤더·범주도 재확인 | `None` 범주 보존, 카테고리·할인 민감도·채널 집계 코드/저장 결과 확인 | 관리자 연구 요약의 D1 집계. 카탈로그·혜택 UI의 설계 참고로 설명 | 회원 관심사 저장/수정과 할인 민감도 자동 추정은 구현되지 않았다. 국내 육아 구매자 표본으로 볼 수 없음 |
| D2 거래 CSV | 541,909행×9열. 추가 `index`와 업무 8열을 구분 | D3 두 번째 시트와 정확한 정규화 튜플 다중집합 비교 코드·산출물 확인 | 관리자 연구 요약에 중복 감사 결과 | D3와 합산하지 않음. 재게시 라이선스 상세조건 불명확; 별도 추천 학습재료가 아님 |
| D3 Retail II | 1,067,371행, 2시트. 복원 XLSX의 현재 해시와 저장 산출물 해시 검증 | 상품/RFM 집계, 월별 양수 판매량 기준모델, 시간순 묶음 규칙 평가. 이번 verifier는 저장된 규칙/수요 산식 검증; 원본 100만행 전체 재파싱·규칙 재학습은 하지 않음 | 관리자 요약·원 StockCode/영문 상품명 번들 12개 API/화면 | 영국 과거 선물용품/도매 혼합. 현재 육아 카탈로그와 매핑·구매 링크 없음. 잠재수요/최소인원/할인율 자동 추정 아님 |
| D4 세션 구매 여부 | 12,330행×18열, 구매 정답 1,908개. 원본 SHA와 저장 모델 검증 | 선택 8특성 그룹 분할, 입력 누수 제외, 저장 LightGBM의 테스트 AUROC/AP/Brier/ECE 재계산 성공 | 관리자 숫자 입력 → 추론 POST → 모델 확률·실험 한계 표시. 자동으로 방문자 행동을 수집해 호출하는 경로는 확인되지 않음 | 완료 세션 분류. 현재 사용자의 이탈 예측/실시간 prefix 성능/국내 확률 보정/CTA 개선 실험 없음 |
| 기업 DOCX | 원 OOXML 직접 파싱. 134문단·39외부링크·원본 SHA 및 저장 추출 전체 일치 | 공동구매 주제의 구매성향·인기품목·묶음·판매/주문 패턴·수요 제안을 D1–D4 실험에 대응 | 연구 설명과 범위 경계 | 원문 제안 전체 구현을 뜻하지 않음. 목표인원·할인 기준은 실제 공급 조건/앱 검증 필요 |
| Notion 로컬 자료·요구 101개 | inventory 229개 전부 보존 원본과 SHA 일치. CSV 101개의 이름·전체 설명·중요도와 저장 JSON 전체 일치 | 파이프라인 trace 101개는 데이터 활용 분류이며 UI 상태는 모두 미판정 | 별도 `requirements-status.md`에 UI/API/시험·미완료 대조 101개 존재 | live Notion 최신본과 동기화했다는 증거는 없음. 대조표에 행이 있다는 것과 전체 기능 수용시험 통과는 다름 |
| 기업 블로그 | 기존 조사 기록은 현재 `SOURCES.md`에 존재. 이번 감사에서 원문 재조회·독립 원문 스냅샷 대조는 하지 않음 | 기존 조사에서는 공동구매/비용공유·안전결제/정산·커뮤니티·운영 도구로 정리 | 후속 개발 범위 참고로 기록 | 이번 독립 감사의 원문 검증은 미완료. 블로그 지원예시를 팀의 공급/계약 보증으로 볼 수 없음 |
| 최신 디자인 원본 | 3084×11472 PNG 직접 열람, SHA가 대조표와 일치 | 57개 화면 대조표 존재. 관심사·추천 대화·조건 변경·개별/공구 선택·결제·배송·커뮤니티 화면을 원본에서 확인 | 일부 탐색/브랜드/공구/계정 경로는 현재 코드와 연결 | 57개 화면 완성 아님. 숫자 입력 관리자 연구 폼은 원본의 일반 사용자 추천 대화를 충족하지 않음 |

근거: `ai-pipeline/artifacts/summary.json:5`, `ai-pipeline/pipeline.py:158`, `ai-pipeline/pipeline.py:191`, `ai-pipeline/pipeline.py:324`, `artifacts/beta/data-usage-20261102/materials-crosscheck.json:2`, `artifacts/beta/data-usage-20261102/schema-requirement-check.json:2`, `docs/build/SOURCES.md:10`, `docs/design/screen-spec-20261101-57.md:5`.

## 실제 연결 경로와 사용자 기능의 차이

| 경로 | 확인한 현재 동작 | 근거 |
|---|---|---|
| 연구 요약 | 관리자 의존성 → `serving.get_summary()` → 저장 summary JSON. 프런트 연구 화면이 API를 소비 | `backend/app/main.py:818`, `ai-pipeline/serving.py:16`, `frontend/src/admin.tsx:273` |
| 과거 묶음 규칙 | 관리자 전용 API가 상위 12개 원상품 규칙 제공. 화면은 현재 육아 상품과 매칭/구매 연결하지 않는다고 명시 | `backend/app/main.py:823`, `ai-pipeline/serving.py:21`, `frontend/src/research-summary.tsx:466` |
| 구매 의도 추론 | 관리자 수동 8특성 입력 → POST. 로컬 모델 SHA 확인 후 예측. 응답에 `experimental`, UCI target, 종료 집계 시점, 한계 포함 | `frontend/src/admin.tsx:275`, `frontend/src/admin.tsx:318`, `backend/app/main.py:828`, `ai-pipeline/serving.py:27`, `ai-pipeline/serving.py:62` |
| 실행 패키지 | 백엔드 Dockerfile은 serving과 ai artifacts를 복사 | `backend/Dockerfile:6` |
| 접근 경계 시험 | 기존 테스트는 구매자 summary 403과 관리자 금지특성 입력 422를 검증한다. 이 두 assertion만으로 정상 추론·모든 역할·배포 성공을 검증한 것으로 확대하지 않음 | `backend/tests/test_flows.py:275` |
| 현재 상품 목록 | DB의 공개 공구에 검색/카테고리/브랜드 필터를 적용. 생성시각 내림차순. 연구 규칙/확률을 상품 선택에 사용하지 않음 | `backend/app/main.py:99`, `backend/app/main.py:142`, `backend/app/main.py:365` |
| 참여 CTA | 수량·조건확인·로그인·상태를 확인하고 예약 API를 호출하는 고정 사용자 행동. 실시간 구매 의도 점수와 연결하는 호출 없음 | `frontend/src/catalog.tsx:388`, `frontend/src/catalog.tsx:424` |

`frontend/src`의 연구 endpoint 호출은 관리자 연구 모듈과 연구 요약 모듈에 있다. 카탈로그 상세는 공구·질문 API를 읽고 참여 수량을 sessionStorage에 보존한다(`frontend/src/catalog.tsx:276`). 이 수량 보존이나 요청 timeout을 방문 세션 행동 수집으로 계산하지 않는다. 실시간 모델을 붙이려면 노출/방문/체류시간/종료·주문 정답의 시점 정의, 동의, 테스트 데이터 제외, 같은 시점의 prefix 특성, 시간순 검증 및 CTA 대조 실험이 필요하다. 현재 D4는 그 검증을 대신하지 못한다(`ai-pipeline/artifacts/evaluation.json:309`).

## 스키마·분포·샘플의 핵심 위험

1. **D1의 `Purchase_Intent`는 구매 여부 정답이 아니다.** 실제 값은 Need-based 256, Wants-based 249, Impulsive 248, Planned 247이다. `Occupation`도 Middle 483/High 517로 직업 정의와 맞지 않는다. 이를 구매 전환 모델의 이진 정답이나 직업 타기팅에 쓰면 잘못된 결과가 된다. 수집·표집·실측/합성 여부는 확인되지 않았으므로 합성 데이터라고 단정하지도 않는다. 근거: `artifacts/beta/data-usage-20261102/schema-requirement-check.json:3`, `ai-pipeline/pipeline.py:167`.
2. **D1 고객, D2/D3 고객·상품, D4 세션, 앱 계정·상품은 서로 다른 개체다.** D4에는 앱 상품/회원 연결 키가 없다. 앱 상품 DTO는 별도의 Record ID와 명시 입력 가격·카테고리를 반환한다. 공개 자료의 ID를 임의 조인하거나 StockCode만 육아 상품으로 바꾸는 것은 현재 검증 범위를 벗어난다. 근거: `artifacts/beta/data-usage-20261102/materials-crosscheck.json:27`, `backend/app/main.py:127`, `frontend/src/research-summary.tsx:470`.
3. **D2/D3는 독립 표본이 아니다.** 저장 감사 결과는 D2 541,909행 모두 D3 두 번째 시트에 존재하고 D3에 POSTAGE 1행이 더 있음을 기록한다. 정규화가 index를 제외한 8업무열과 중복 횟수를 보존하고, 상품 분석은 D3만 사용한다. 이번에 이 대규모 Counter 비교 자체를 다시 계산하지는 않았고 원본 SHA·산출물 SHA·코드·저장 결과를 대조했다. 근거: `ai-pipeline/pipeline.py:57`, `ai-pipeline/pipeline.py:207`, `ai-pipeline/artifacts/overlap_audit.json:2`, `ai-pipeline/verify_outputs.py:40`.
4. **D3의 판매량은 순매출·잠재수요·사람 수가 아니다.** 취소/중복/0이하 수량·단가/빈 설명 등을 제외한 양수 판매 기준이며, 부분 월을 제외한 11개월 기준모델이다. 앱의 `minimum_quantity`도 수량이다. 원본 디자인의 최소 참여인원으로 이름만 바꿀 수 없다. 근거: `ai-pipeline/pipeline.py:203`, `ai-pipeline/pipeline.py:170`, `backend/app/main.py:123`, `backend/app/schemas.py:57`, `docs/design/screen-spec-20261101-57.md:20`.
5. **시험용 육아 카탈로그는 실거래 데이터가 아니다.** 베타 bootstrap은 가상 판매자·예시 상품·시험 가격/쿠폰/원문 없는 핫딜을 만든다. DTO도 `is_demo=True`, `source_url=None`이다. 이를 실제 수집 상품, 검증된 공급처, 모델이 발견한 인기품목·할인 효과로 표시할 수 없다. 다만 가상 상품이라는 이유만으로 D1–D4 학습 자료까지 합성이라고 추정하지 않는다. 근거: `backend/app/bootstrap_beta.py:27`, `backend/app/bootstrap_beta.py:34`, `backend/app/bootstrap_beta.py:43`, `backend/app/main.py:131`.
6. **D4 지표가 국내 개인 구매 확률을 보증하지 않는다.** 그룹 분할은 같은 8특성 벡터의 분할 간 중복을 막지만 실제 사람·시각 기반 분할은 아니다. LightGBM은 validation AP로 선택했으며 테스트 AP는 로지스틱 0.305419가 LightGBM 0.293728보다 높다. 선택 모델 테스트 AUROC 0.744809/Brier 0.117844/ECE 0.022278은 재현했지만 별도 보정기를 학습하지 않았고 국내 외부검증도 없다. 근거: `ai-pipeline/pipeline.py:299`, `ai-pipeline/pipeline.py:336`, `ai-pipeline/artifacts/evaluation.json:144`, `ai-pipeline/artifacts/evaluation.json:258`, `ai-pipeline/artifacts/evaluation.json:308`.

## 요구 101개와 디자인의 남은 간격

파이프라인 trace는 데이터의 활용 범위를 설명하는 별도 기록이다. 여기서 101개 모두 `미판정`인 것은 **UI 대조표가 없다는 뜻이 아니다**. 현재 `docs/build/requirements-status.md`에 R001–R101이 각각 한 번씩 있으며 작성된 판정은 구현 5/부분구현 46/미구현 50이다. 이번 감사는 이 수와 존재·선택된 데이터 관련 항목을 확인했고 모든 101개를 실제 기기에서 다시 시험하지 않았다. 이 수를 전체 기능 완료율이나 새 실행 결과로 사용하지 않는다. 근거: `ai-pipeline/pipeline.py:148`, `artifacts/beta/data-usage-20261102/materials-crosscheck.json:17`, `artifacts/beta/data-usage-20261102/schema-requirement-check.json:40`.

| 요구/디자인 | 현재 대조 | 데이터가 있어도 남는 구현/수용조건 |
|---|---|---|
| R007/R009 관심사 등록·수정, 관심사 온보딩 | 미구현. Register에 관심사 필드 없음 | 복수선택/건너뛰기/수정/초기화·계정 저장·재로그인 후 유지. D1 집계 표로 대체 불가 (`backend/app/schemas.py:8`, `docs/build/requirements-status.md:119`) |
| R042/R056 기준모델·공개데이터 분리 | 기준모델 비교는 부분구현, 데이터 범위 분리는 구현으로 기록 | 실제 상품 조건위반/가격/재고/링크·유효주문 효과는 별도 시험 (`docs/build/requirements-status.md:154`, `docs/build/requirements-status.md:168`) |
| R057/R061/R066/R070/R074 조건·이유·대화·실상품·무결과 | 미구현으로 기록. 디자인은 추천 대화·조건 변경 화면 요구 | 앱 상품 후보 조회, 조건 보존, 검증된 가격/링크, 조건위반 차단, 빈결과·지연·오류 구분 (`docs/build/requirements-status.md:169`, `docs/build/requirements-status.md:173`, `docs/build/requirements-status.md:178`, `docs/build/requirements-status.md:182`, `docs/build/requirements-status.md:186`) |
| R064 최근 유효구매자 인기 | 미구현 | 최근 7일 고유 구매자·취소/테스트 제외·집계시각. D3 역사상 인기와 구분 (`docs/build/requirements-status.md:176`) |
| R075/R082/R090 추천 권한·개인화·초기화 | 연구 권한 일부만 있고 사용자 개인화/기억은 없음 | 이력의 동의·접근·보관·삭제·비동의 이용경로 (`docs/build/requirements-status.md:187`, `docs/build/requirements-status.md:194`, `docs/build/requirements-status.md:202`) |
| R013/R014 모집 인원·마감 결과 | 수량 기반 표시 일부 구현 | 고유인원, 영속 성사/미달 판정·후처리·실납부 환불. D3 수량/송장 수로 추정 불가 (`backend/app/main.py:122`, `docs/build/requirements-status.md:125`) |

## 이번 실행 결과와 수정 상태

| 검증 | 결과 | 증거 |
|---|---|---|
| 처음 `--data-root E:/Team_Wifi/data` | 실패: 이 폴더는 공유 안내만 있고 raw가 없음 | `artifacts/beta/data-usage-20261102/verify-e-data.txt:1` |
| E 하위 보존본을 명시한 verifier | exit 0, `DATA_PIPELINE_PASS` | `artifacts/beta/data-usage-20261102/verify-preserved-e-data.txt:1` |
| 메인 담당자의 기본경로/안내 수정 후 무인자 verifier | exit 0, `DATA_PIPELINE_PASS`. D 기본경로 문제 해결 확인 | `ai-pipeline/pipeline.py:392`, `ai-pipeline/verify_outputs.py:85`, `ai-pipeline/IMPLEMENTATION.md:7`, `artifacts/beta/data-usage-20261102/verify-default-e-data.txt:1` |
| 원본·자료 대조 | 4원본/전체 산출물 SHA, 229자료 해시 전부 일치, DOCX 추출 전체 일치, 요구101 전체 일치 | `ai-pipeline/verify_outputs.py:19`, `artifacts/beta/data-usage-20261102/materials-crosscheck.json:2` |
| 추론·평가 | 저장 모델 테스트 지표 재현, 분할 그룹 교집합0, 금지/오류 입력7종 거절, 규칙/수요 산식 확인 | `ai-pipeline/verify_outputs.py:23`, `ai-pipeline/verify_outputs.py:35`, `ai-pipeline/verify_outputs.py:54`, `artifacts/beta/data-usage-20261102/verify-default-e-data.txt:2` |

검증은 기존 코드의 독립 재학습/라이선스 최신 재확인/원본 XLSX 전체 셀 재파싱/실기기·배포 E2E/국내 추천효과까지 포함하지 않는다. 특히 verifier의 D2/D3 항목은 저장 감사의 정합성을 확인하고, 수요/규칙 항목은 저장된 값의 산식을 확인한다. 원본 거래 전체로 해당 실험을 재생성한 것으로 확대하지 않는다(`ai-pipeline/verify_outputs.py:40`).

## 우선 조치

1. **현재 자료를 정직하게 보여주는 상태를 유지(추천).** 관리자 실험과 일반 상품 탐색을 구분하고, 스토어/발표/대외 설명에는 현재 육아 추천·실시간 구매 예측이 완성됐다고 쓰지 않는다. 이미 동작하는 연구·집계·추론을 구체적으로 설명한다. 근거와 위험: 연구 기능은 실제 연결됐지만 한국 육아 전환·CTA 성과는 미검증이다.
2. **일반 사용자 추천은 실상품 조건 검증부터 구현.** 실제 출처/확인일/가격/재고/판매제안과 관심사 저장을 먼저 갖추고, 예산·방식·일정·제외조건을 위반하지 않는 조회/추천 기준모델을 검증한다. 과거 영국 번들 이름 치환이나 가상 육아 상품 학습으로 완료 처리하지 않는다.
3. **실시간 CTA는 별도 데이터 과제로 유지.** 앱 이벤트 정의·동의·시점/정답·테스트 분리 후 prefix만으로 기준모델/시간분할/보정과 행동 효과를 검증한다. 수동 입력 UCI 예측 API를 붙였다는 사실만으로 온라인 효과를 보고하지 않는다.
4. **추적표와 원문 증거를 이어서 갱신.** source_row↔R번호↔화면↔API↔수용시험↔미완료를 유지한다. live Notion의 현재 내용과 블로그 원문 재확인은 아직 별도 확인이 필요하다. 기존 101·57 대조표의 존재를 전체 구현 완료로 축약하지 않는다.
