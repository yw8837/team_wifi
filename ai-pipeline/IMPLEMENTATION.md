# 모두의 육아 데이터 분석과 추론 구현

기준일 2026-11-01. 제공된 네 데이터, 기업 원문 DOCX, 버전이 보존된 Notion 기획·요구사항·출처·기존 분석을 실제로 읽고 재현 가능한 분석과 추론 코드로 연결했다. 이 문서는 현재 데이터 작업의 실행 증거다. 서비스 전체 구현·국내 육아 데이터 성능·실제 PG 계약·출시 완료를 뜻하지 않는다. 기존 기획서는 수정하지 않았다.

## 실행

이 PC의 작업 위치는 `E:/Team_Wifi`다. 원본 자료는 이 프로젝트 안에 보존된 `_archive/legacy-project/data`를 읽기 전용으로 사용한다. `data/`에는 공유용 안내만 있으며 원본은 없다. 분석·검증 스크립트의 기본 입력 경로도 저장소 기준의 이 보존 폴더다. 팀원이 별도 자료를 받은 경우에만 `--data-root`로 위치를 지정한다. 원본은 Git에 올리거나 다시 내려받지 않는다. 과거 실행 당시 D: 경로가 담긴 출처 매니페스트는 역사 기록으로 보존한다.

```powershell
. ./scripts/use-workspace.ps1
.\backend\.venv\Scripts\python.exe -u ai-pipeline/pipeline.py *> ai-pipeline/pipeline-run.log
.\backend\.venv\Scripts\python.exe ai-pipeline/verify_outputs.py *> ai-pipeline/verify-run.log
Get-Content ai-pipeline/verify-run.log
```

성공 검증은 `DATA_PIPELINE_PASS`다. 검증은 원본/복원본과 모든 산출물의 SHA-256, 세션 특성 그룹의 분할 간 중복 0, 금지 입력 제외, 저장한 모델의 테스트 지표 재계산, 동시구매 산식, 수요 기준모델 오차 산식, 동적 import 및 잘못된 추론 입력 7종 거절을 확인한다. 단순 파일 존재만으로 통과하지 않는다.

사용 환경은 Python 3.11, pandas 3.1.0, scikit-learn 1.9.1, LightGBM 4.7.0, joblib 1.6.0, openpyxl 3.1.5다. 버전은 `requirements.txt`와 `artifacts/summary.json`에 기록했다. LightGBM은 CPU 2개 스레드와 고정 난수를 사용한다. 다른 라이브러리 버전/플랫폼에서는 미세한 수치 차이가 날 수 있다.

## 기업 자료와 팀 원문의 사용

`모바일앱개발협동조합_공개데이터.docx`의 실제 OOXML에서 134개 문단과 외부 링크를 추출했다. 원문은 공동구매 주제에 대해 구매성향, 인기품목, 묶음구매, 판매/주문 패턴·수요, 목표인원·할인 기준을 제안하며 컬럼과 라이선스 사전 확인을 요구한다. 원문과 파일 해시는 `artifacts/company_source_extract.json`에 보존했다.

원문이 열거한 MBTI 가계부·금융 교육 플랫폼 및 다른 금융·전자상거래 데이터 후보는 선택한 공동구매 주제의 추가 후보 자료다. 이를 현재 서비스에 모두 도입하거나 학습했다고 보고하지 않는다. 선택되어 제공된 D1–D4를 실제 분석했다. 금융 신용점수, 자동 주최자 승인, 실제 수집되지 않은 육아 수요를 만들어내지 않는다.

Notion 로컬 내보내기 229개 파일을 경로·크기·SHA-256·활용 이유로 조사했다. 텍스트/CSV/JSON/스크립트/노트북 본문은 전체 읽기, DOCX는 실제 문단과 하이퍼링크 읽기, 기존 XLSX는 시트·규모·헤더 확인, ZIP은 구성 조사 및 복원 매니페스트 대조를 했다. 분할 ZIP 자체는 독립 ZIP이 아니므로 이미 복원된 원본으로 분석했다. ZIP 내부의 모든 과거 코드를 새로 실행했다는 뜻이 아니다. 자료별 범위는 `artifacts/materials_inventory.json`에 명시했다. 과거 노트북 출력은 원문 검토 근거로 읽었으며 이번 실행 성과는 `pipeline-run.log`로 구분했다.

팀 원문의 요구사항 101개는 이름·전체 설명·중요도를 실제 CSV에서 읽었다. `artifacts/requirements_traceability.csv`, 같은 이름 JSON·MD는 각 요구를 **현재실험/참조/후속검증**으로 분류한다. 이는 데이터의 근거 범위다. **101개 모두 UI 구현 상태는 미판정**이며 메인이 현재 코드와 실행 시험으로 별도 판정한다. 과거 서비스 예약·비용 정산·물류·실 PG 요구가 존재한다는 이유로 현재 기능이 완성됐다고 표시하지 않는다.

v1/v2는 이전 버전으로 보존하고 v3의 관심사·구매 방식·주최자 권한·조건 우선 추천·공개 검색/GEO 요구를 기능 대조의 참조로 사용했다. 과거 Elice 링크나 지시는 비활성 상태로 분류하며 호출·설치·키 복구·연결 점검을 실행하지 않았다.

이 데이터 작업은 연결된 Notion/블로그의 현재 원문을 새로 열었다고 주장하지 않는다. 여기 사용한 본문은 버전이 보존된 로컬 내보내기다. 블로그·Notion의 현재 읽기 증거는 메인의 조사 기록과 구분한다.

## 입력과 출처

| 자료 | 실제 규모 | 사용 및 결과 | 출처 확인 범위 |
|---|---:|---|---|
| D1 Ecommerce Consumer Behavior Analysis Data | 1,000행 × 28열 | 카테고리·할인 민감도·채널 집계 | 2026-10-30 다운로드 매니페스트와 2026-11-01 로컬 해시 대조 |
| D2 Online Retail Transaction Data | 541,909행 × 9열 | 업무 8열의 정확한 다중집합 중복 감사 | 동일, 상품 분석에 D3와 합치지 않음 |
| D3 Online Retail II | 1,067,371행 × 8개 업무열, 2시트 | 상품·월별 판매·RFM 집계·동시구매·시계열 기준모델 | 복원본/정규화본 매니페스트 해시 및 시트별 원본 행 매핑 대조 |
| D4 Online Shoppers Purchasing Intention | 12,330행 × 18열 | 더미·로지스틱·LightGBM 학습/검증/테스트 | 2026-10-30 다운로드 매니페스트와 2026-11-01 로컬 해시 대조 |

- [D1 원 출처](https://www.kaggle.com/datasets/salahuddinahmedshuvo/ecommerce-consumer-behavior-analysis-data), Salahuddin Ahmed. 보존된 메타데이터는 CC BY 4.0을 표시한다. 수집/표집/합성 여부는 미확인이다.
- [D2 재게시 출처](https://www.kaggle.com/datasets/thedevastator/online-retail-transaction-data), The Devastator. Other 표시의 상세 조건은 불명확하다. CSV는 중복 감사에만 사용하며 규칙은 이용 조건이 명시된 D3에서 산출한다.
- [D3 원 출처](https://archive.ics.uci.edu/dataset/502/online+retail+ii), Chen, D. (2012), DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), 보존된 출처 기록 CC BY 4.0.
- [D4 원 출처](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset), Sakar, C. & Kastro, Y. (2018), DOI [10.24432/C5F88Q](https://doi.org/10.24432/C5F88Q), 보존된 출처 기록 CC BY 4.0.
- [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 이 작업은 형식 정규화·분석 필터·집계·모델 학습을 추가했다. 출처 기관의 서비스 보증을 뜻하지 않는다. 현재 사이트 이용 조건을 다시 확인한 것으로 표시하지 않는다.

중요한 파일 차이가 있다. 현재 `raw/03_uci_retail_ii/online_retail_II.xlsx`는 원래 다운로드의 절대경로 메타데이터 `absPath`를 제거해 Notion에 올렸던 복원 사본이다. 실제 해시는 `b1038e950f7d800a6dbe96104f28bdcbf7c733642964ae4476756d7b13e672d5`, 39,146,386바이트다. 원래 다운로드 기록은 `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`, 45,622,278바이트다. 이를 같은 바이트라고 간주하지 않는다. 복원 매니페스트가 셀 데이터 보존과 메타데이터 변경을 명시한다.

정규화본 `processed/retail_ii_normalized.csv.gz`는 20,856,845바이트, SHA-256 `366d3fa614325357e8b235979f27b5a947cb00048b6b56bc72869a1b7fd15054`다. 현재 파일이 원문 패키지의 해시와 정확히 일치함을 확인해 재사용한다. 시트별 525,461/541,910행과 각 `source_row`가 2부터 끊김 없이 매핑됨을 확인했다. 과거의 분석 플래그는 그대로 신뢰하지 않고 취소·중복·양수 수량·양수 단가·상품코드·설명을 다시 계산했다. 원본 XLSX의 100만 행을 이번에 모두 다시 파싱했다는 주장은 하지 않는다.

## 실제 계산 결과와 제품 연결

### D1 관심사와 할인 탐색

`keep_default_na=False`로 None을 범주로 보존했다. SNS None 247행, 광고 None 256행이다. 할인 민감도는 Very Sensitive 350, Somewhat Sensitive 319, Not Sensitive 331이다. 24개 카테고리와 민감도×채널 집계를 저장했다.

앱의 명시적 관심 카테고리 선택과 혜택/쿠폰 탐색 UI의 설계 근거로 사용할 수 있다. 이 표본의 고객 ID를 앱 회원과 연결하거나 할인 민감도를 자동 부여하지 않는다. 할인율을 올리면 전환이 개선된다는 인과 주장은 없다. `Occupation`은 High/Middle로 직업 설명과 맞지 않아 타기팅에 사용하지 않는다. `Purchase_Intent`는 구매 여부가 아닌 명목 범주다.

### D2와 D3 중복 감사

`index`를 제외한 업무 8열을 식별자·수치·날짜 기준으로 정규화한 뒤 실제 값의 튜플 Counter를 비교했다. 등장 횟수도 보존하는 정확한 다중집합 비교이며 해시 충돌을 전제로 하지 않는다.

- D2 541,909행 전부가 D3 두 번째 시트에 포함된다.
- D3 두 번째 시트는 541,910행이며 단 한 개 POSTAGE 항목만 추가다. 추가 행에서 고객 ID는 내보내지 않았다.
- D2의 동일 업무행 반복분 5,268, D3 반복분 34,335다.
- D2와 D3를 합쳐 데이터가 늘었다고 주장하지 않고 D3만 상품 집계에 사용한다.

상세 실행 결과는 `artifacts/overlap_audit.json`과 로그에 있다. 이전 `source_catalog.json`의 간략한 설명보다 이번 실제 감사의 1행 차이를 우선한다.

### D3 상품과 RFM

같은 업무행의 첫 항목만 유지하고, 취소 송장·0 이하 수량/단가·빈 설명을 제외했다. 실물 후보 코드 규칙 `5자리 숫자 + 영문 0~2개`는 비용코드를 제외하기 위한 분석상 선택이며 완전한 상품 마스터가 아니다. 남은 상품 분석행 1,003,213, 송장 39,516, 상품 4,877개다.

월별 양수 판매량·판매액을 집계했고, 고객 번호가 있는 행으로 RFM 5,852명의 **분위수 집계만** 내보냈다. 최근성 기준일은 마지막 관측 다음 날인 2011-12-10이다. 고객별 원행·고객 번호·구매이력은 산출물에 내보내지 않는다. 양수 판매액은 취소/반품을 차감한 순매출이 아니며 2011년 12월은 9일까지의 부분 월이다.

### D3 동시구매 규칙과 평가

영국 송장 36,184개를 날짜순으로 앞 80%(28,947) 학습, 뒤 20%(7,237) 테스트로 나눴다. 학습 마지막은 2011-08-16 13:05, 테스트 첫 송장은 같은 날 13:12다. 상위 100개 품목을 학습 송장에서만 선정하고 같은 송장 내 같은 품목은 한 번 센다. 함께 나온 송장 100개 이상인 방향성 규칙 7,242개를 산출했다.

한 규칙의 실제 예는 GREEN REGENCY TEACUP AND SAUCER → ROSES REGENCY TEACUP AND SAUCER다. 학습 송장 28,947개 중 718개 동시 등장, 앞 상품 946개 송장, 뒤 상품 961개 송장이다. 지지도 2.4804%, 신뢰도 75.8985%, 향상도 22.86196다. 이는 관측된 영국 찻잔의 동시구매 관계다. 한국 육아용품으로 이름을 바꾸거나 판매 향상이 22배라고 해석하지 않는다.

평가는 학습 상위 100개 중 2개 이상을 포함하는 테스트 송장 4,338개에서 송장 해시로 정한 상품 하나를 숨기고 나머지 품목으로 복원했다. 규칙 후보는 최대 신뢰도로 정렬하고 같은 학습 데이터의 인기 상위 5개를 기준모델로 비교했다.

| 테스트 지표 | 동시구매 규칙 | 인기 기준모델 |
|---|---:|---:|
| Recall@5 | 0.362148 | 0.105579 |
| MRR@5 | 0.227601 | 0.056286 |

이 값은 알려진 장바구니의 일부를 복원하는 제한된 평가다. 다음 주문·신규고객·국내 육아용품 추천 성능이 아니다. 같은 고객이 시간 분할 양쪽에 다시 등장할 수 있다. 앱에서는 판매자/관리자의 오프라인 분석 실험으로 표시하고 현재 육아 상품 카탈로그와 연결하지 않는다. 실제 육아 추천은 앱 상품과 명시 관심사/조건으로 별도 검증해야 한다.

### D3 판매량 기준모델

기업 원문의 수요 예측 제안을 실제로 시험하기 위해 24개 완전한 월을 만들고 2011-01~2011-11의 11개 월을 순서대로 평가했다. 각 달은 이전 달 판매량과 12개월 전 동일 달 판매량만 사용한다. 부분 월인 2011-12는 제외했다.

| 기준모델 | MAE 수량 | WAPE |
|---|---:|---:|
| 직전 달 판매량 | 67,971.27 | 0.152866 |
| 12개월 전 판매량 | 43,571.00 | 0.097990 |

`artifacts/demand_backtest.json`에 11개 실제값·예측값·산식 검증을 보존했다. 품절·노출·재고·가격이 없어 잠재수요가 아닌 과거 양수 판매량의 기준모델이다. 앞으로 한국 육아용품이 얼마나 팔릴지 예측한 결과가 아니다. 목표인원·최소수량·할인율은 공급자가 제공한 조건으로 처리해야 하며 여기서 자동 추정하지 않는다.

### D4 구매 여부 분류

총 12,330세션 중 구매 정답 1,908개(15.4745%)다. 전체행 중복 반복분은 125개이고 선택한 8개 특성의 중복 반복분은 846개다. 같은 입력 특성 벡터가 학습과 테스트에 흩어지지 않게 **정답을 제외한 모든 선택 특성 값**으로 그룹을 만들었다. 그룹 단위 고정 난수 60/20/20 분할의 실제 행 수는 학습 7,219, 검증 2,365, 테스트 2,746이다. 그룹의 크기가 달라 정확히 행 기준 60/20/20은 아니다. 분할 간 동일 입력 그룹과 동일 행 인덱스의 교집합은 0이다.

8개 입력은 `Administrative`, `Administrative_Duration`, `Informational`, `Informational_Duration`, `ProductRelated`, `ProductRelated_Duration`, `SpecialDay`, `Weekend`다. `PageValues`, `BounceRates`, `ExitRates`, Revenue 및 나머지 필드는 입력에서 제외한다. PageValues를 포함해 얻은 높은 수치를 제품 성능으로 제시하지 않는다. 페이지 수·체류시간은 세션 종료 집계이며 진행 중 세션 prefix로 학습한 결과가 아니다.

더미는 학습 구매 비율, 로지스틱은 결측 중앙값/표준화 후 분류, LightGBM은 160개 트리·깊이 6·15 leaves·학습률 0.04·lambda 2를 사용한다. 학습은 학습 세트만, 선택은 검증 Average Precision만 사용했다. 테스트를 보고 모델을 바꾸지 않았다. 최종 선택은 LightGBM이다.

| 모델 | 검증 AP | 테스트 AUROC | 테스트 AP | 테스트 Brier | 테스트 ECE 10 bins |
|---|---:|---:|---:|---:|---:|
| 구매비율 더미 | 0.175053 | 0.500000 | 0.152221 | 0.129060 | 0.003170 |
| 로지스틱 | 0.275760 | 0.722321 | 0.305419 | 0.122587 | 0.013878 |
| LightGBM | 0.281094 | 0.744809 | 0.293728 | 0.117844 | 0.022278 |

LightGBM이 모든 지표에서 이기지는 않는다. 테스트 AP와 ECE는 로지스틱이 더 낫다. 더미 ECE가 작은 것은 전체 비율만 출력하는 모델도 주변부 보정이 좋을 수 있음을 보여준다. 예측의 구분 능력과 확률 보정은 함께 비교해야 한다. Brier/ECE·reliability bins를 측정했지만 별도 확률 보정기를 학습하지 않았다. 국내 데이터 보정·신뢰구간·독립 서비스 검증은 미실행이다. ID·일자가 없어서 동일한 실제 사람/세션의 재등장을 완전히 배제하거나 진정한 시간순 평가를 할 수 없다.

## 서버 연결 계약

`serving.py`는 파일 경로 기반 `importlib`로 안전하게 불러올 수 있다. 패키지명이나 작업 디렉터리에 의존하지 않는다.

```python
get_summary()  # dict: sources/source_hashes/materials/d1/retail/intent/limitations
get_bundle_examples()  # list[dict]: 상위 12개 원명/원코드 규칙 및 출처
predict_intent({
    "Administrative": 1,
    "Administrative_Duration": 12,
    "Informational": 0,
    "Informational_Duration": 0,
    "ProductRelated": 8,
    "ProductRelated_Duration": 120,
    "SpecialDay": 0,
    "Weekend": 0,
})
# {probability: float, model: "lightgbm", experimental: True,
#  target: ..., feature_timing: ..., limitations: [...], source_url: ...}
```

추론 입력은 정확히 8개 키가 필요하다. 누락·추가 키·문자열·음수·NaN·무한대·소수 방문 수·범위 밖 Weekend/SpecialDay는 ValueError다. Weekend는 0/1, SpecialDay는 0~1, 방문 수는 0 이상 정수다. 외부 업로드 모델을 받지 않으며 신뢰하는 로컬 joblib만 메타데이터 SHA-256과 대조 후 로드한다. 입력이 학습 분포 밖인 경우의 타당성은 아직 검증하지 않았다.

모델 점수는 관리자 실험용이다. 자동 결제·쿠폰 발급·가격 차별·주최자 승인 또는 개별 구매자에 대한 검증된 사실로 사용하지 않는다. D4에는 앱 회원·상품 ID 연결 키가 없으며 D1/D3의 고객 ID와 조인하지 않는다.

## 산출물과 남은 일

| 파일 | 확인 가능한 내용 |
|---|---|
| `pipeline.py`, `serving.py`, `verify_outputs.py` | 분석·학습·추론·실제 검증 코드 |
| `pipeline-run.log`, `verify-run.log` | 새 실행 결과와 통과/실패 증거 |
| `artifacts/summary.json` | 화면에 연결할 집계/한계/지표/출처 |
| `artifacts/evaluation.json`, `model_metadata.json`, `intent_model.joblib` | 재현 가능한 세션 모델·분할·평가·무결성 |
| `artifacts/bundle_rules.json`, `overlap_audit.json`, `demand_backtest.json` | 묶음 규칙·중복 감사·판매량 기준모델 |
| `artifacts/materials_inventory.json`, `company_source_extract.json` | 제공 자료 조사·원문 DOCX 읽기 증거 |
| `artifacts/requirements_source.json`, `requirements_traceability.*` | 101개 요구 원문과 데이터 활용 범위, UI 상태 미판정 |
| `artifacts/artifact_manifest.json` | 실행 산출물별 SHA-256 |

데이터 부분에서 새 분석·모델 실행·저장·로컬 추론·산식/누수/무결성 검증을 완료했다. **현재 앱 화면/보안/권한/API와 연결한 최종 기능 판정은 메인의 코드·화면 시험으로 별도 확인해야 한다.** 국내 육아 거래의 학습 데이터 수집·실사용 추천 품질·실시간 구매 의도·공급 계약·실제 PG·예약/물류 연동·검색엔진/GEO 노출·테스터 모집·배포 완료는 이 파이프라인에서 검증하지 않았다. GEO는 공개 정보와 구조화 데이터의 제품 구현 과제이며 D4의 Region 코드를 국내 위치로 바꾸지 않는다.
