# 문맥 오탐 수정과 검토된 52건 회귀 — 2026-11-06

최초 홀드아웃 12건의 실패를 확인한 뒤, 같은 12건을 검토된 회귀 집합으로 전환하고 기존 40건과 합쳐 평가했다. source-06의 최초 결과, snapshot07의 부분 누락과 모든 원본 fixture를 보존한다. 아래 개선 후 성적은 새 질문에 대한 독립 검증이 아니다.

## 최초 결과와 후속 회귀를 구분한다

| 실행 | 자동 검사 | 지원 답변의 전체 기대 조건 충족 · 에이전트 검토 | 실제 모델 선택 | Opik 실제 저장 |
| --- | --- | --- | --- | --- |
| source-06 · 최초 새 질문 12건 | 10/12 | 7/10 | 8/8 | 12/12 |
| AI snapshot07 · 검토된 40+12건 | 52/52 | 34/36 | 36/36 | 52/52 |
| AI snapshot08 · 검토된 40+12건 | 52/52 | 36/36 | 36/36 | 52/52 |

지원 답변 외 16건은 기대된 의료·가격·안전/인증 거절 또는 근거 없음 처리에 부합했다. 전체 답변을 snapshot07과 대조했고, 같은 모드·답변이 유지된 45건은 기존 검토와 동일함을 확인했다. 바뀐 7건은 내용을 직접 읽었다. 이는 에이전트의 조건 충족 검토이며 독립된 사람의 groundedness 점수나 실제 사용자 만족도 조사가 아니다.

snapshot07에서는 F01의 비회원 임시 이용 조건과 F07의 증정품/할인 조건 구분이 빠졌다. 자동 52/52 결과와 해당 누락 기록을 함께 보존했다. snapshot08에서는 두 조건을 포함한 승인 안내가 실제 모델 선택으로 반환됐다. 모델이 선택하지 않은 사실 문장을 결과 뒤에 붙이지 않았다.

## 수정 범위와 근거

- `knowledge.unsupported`: 기간·수량·측정 문맥의 ‘얼마’를 가격 확인 요청과 구분했다. 로그인·계정의 인증 토큰 문구를 제품 인증과 분리하되 실제 KC/제품 인증·안전성·의료·금액/재고 거절은 유지했다. 전체 질문 문자열이나 사례 ID를 하드코딩하지 않는다.
- `knowledge.restricted_data_request`와 `assistant.py`: 비밀번호·토큰·다른 회원 비공개 정보의 출력/조회 요청을 별도 판단한다. 혼합 요청의 공개 안내는 허용하되 민감 부분은 고정 문구로 거절하고, 추론 전 사전 점검과 최종 응답 양쪽에서 모든 live 도구 호출을 건너뛴다. 인증·비회원 각각의 API 테스트로 도구 호출이 0회임을 확인했다. 인증을 위한 세션 검사는 계속 수행한다.
- 카탈로그 관련성: 승인 카탈로그의 분야를 비공개 메타데이터로 보관해 명시된 분야와 다른 카탈로그를 제외한다. 이 필드는 모델 입력이나 공개 Citation DTO에 추가하지 않는다. 유모차 질문에 도서/배터리 안내가 붙었던 F06을 해결했다.
- 완결 보관 안내: 실제 비회원 질문 API와 기존 공개 privacy-chat 안내에 맞춰 chat-history 자체에 비회원 임시 이용·직접 선택 저장·30일·삭제·새 로그인 이어보기 제한을 함께 담았다.
- 작업별 비교 안내: 브랜드를 지정하지 않은 할인·쿠폰·증정품/사은품 비교는 완결 작업 가이드를 우선한다. 일반 포장·총수량 확인만 필요한 경우 불필요한 브랜드 카탈로그를 제외하고, 소재·모델·규격·팩당 매수 등 추가 제품 조건이나 특정 브랜드를 물으면 해당 자료를 유지한다.
- `guide:discount-gift`: 기존 공개 카탈로그의 개별 포장·본품 수량·증정품 지급 조건 확인과 실제 계산기의 범위를 묶은 일반 안내다. 계산은 `frontend/src/release-policy.ts`의 `compareUnit`에 있는 `(price + shipping) / quantity`와 일치한다. `frontend/src/public-app.tsx`의 Calculator가 명시하는 쿠폰·묶음 조건·반품비 제외와 판매처 확인도 그대로 설명한다. 개별 상품의 가격·할인액·지급 여부를 만들어 넣지 않았다.

`extractive-group-v5`, 기존 Qwen3-1.7B Q8_0 모델과 원본 질문 파일은 바꾸지 않았다. 승인 그룹의 정확한 공급·원문·그룹 멤버십 검증과 최대 두 그룹 계약도 유지했다. `assistant_tools.py`는 이 작업에서 편집하지 않았다.

## 원래 출처 목록 점수를 보존한다

snapshot08의 **원래 gold 출처 기준 Recall@5는 0.944444(적용 36건)**이다. 질문 내용 충족 36/36과 같은 수치로 표시하지 않는다.

- F09는 동결 gold가 `analysis:d2`인데, 기대한 영국 상품 치환 금지·수요예측 제한은 `analysis:d3`에 있다. 실제 답변은 d3을 선택했다. 최초 결과부터 확인한 표기 불일치이며 원본과 원점수를 바꾸지 않았다.
- F07은 원래 gold인 `catalog:motherk-hygiene` 대신, 이후 승인한 완결 `guide:discount-gift`를 선택했다. 개별 포장·본품 총수량과 증정품/할인 조건 구분을 모두 답하지만 기존 출처 ID는 검색하지 않았으므로 원래 Recall=0을 유지한다. 이를 F09의 원래 표기 오류와 같은 종류의 오류로 설명하지 않는다.

기존 40건의 원본 SHA-256은 `73d03184ced03cc8ab8e83c5356aa6d8787c4439ddec72979652d9f7dcd50f97`, 검토된 12건은 `6522a6a7d5843290d6230d9ef63a3eedf6dc8edc6162a5e725822e9f00e84b84`다. 두 파일을 수정하지 않았다.

## 실행 증거와 범위

- AI snapshot08 source archive SHA-256: `118f2c87103f9e0a8b040dce3c9dba207aed50e4f3a8abeeb08de3a453ae932e`
- snapshot08 원본 결과 SHA-256: `7d452e6e7a60ce209ca8e0863c430ec782f6f62ea06907b72b1f571df14e7989`
- 결과·출처·직접 검토·실제 추적 조회: `.runtime/assistant-evaluation/regression52-snapshot08/regression52-v5-snapshot08{.json,.provenance.json,.agent-review.json,.traces.json}`
- 최초 실패와 중간 결과: `.runtime/assistant-evaluation/final-holdout/`, `.runtime/assistant-evaluation/regression52-snapshot07/`
- 원격 snapshot08: `/home/elicer/Team_Wifi/.runtime/community-candidate/ai-regression-08`. source-06과 snapshot07 디렉터리도 별도로 보존했다.

기존 8091 모델을 재사용하고 `ASSISTANT_SSH_ENABLED=false`를 명시했다. 모델 파일·기존 프로세스 명령·source manifest와 양쪽 fixture 해시를 검증했다. 서비스를 재시작하거나 새 자원을 만들지 않았다. 모델 선택 지연은 warm 35개 표본의 p50 610.38ms, p95 877.925ms다. 첫 호출은 604.035ms이고 콜드 스타트로 확인한 값은 아니다. 이 값은 운영 SSH 경유·API DB 작업·웹 전체 왕복 시간을 측정한 결과가 아니다.

Opik SDK 누적 전송은 enqueued 52, flushed 52, failed/dropped/rejected/pending 각 0이었다. 이 카운터와 별개로 실제 52개 request ID를 읽어 52개 추적 저장, 중복 없음, 입력·출력 null, 허용 메타데이터와 v5 버전 일치를 확인했다. 실제 회원 질문·대화나 운영 회원 DB는 평가 입력에 사용하지 않았다.

## 코드 확인과 평가 카드

- 관련 도우미·검색·문맥 회귀: **91 passed**.
- 평가 요약 admin API: **2 passed**.
- `backend/app/assistant_evaluation.json`에 최신 snapshot08과 snapshot07 카드를 추가했다. 최초 새 질문 실패와 이전 모델 결과는 유지했다. 결과 수집 후 갱신한 요약 데이터는 snapshot08 추론 동작을 바꾼 코드가 아니다.

AI 코드와 요약 카드는 이 상태로 동결한다. snapshot08은 AI 회귀 증거이며 최종 제품 전체의 출시 snapshot이나 전체 테스트 완료 선언이 아니다. 전체 backend/frontend·운영 배포 게이트는 메인 작업에서 별도로 실행한다. 관련 추가 그룹이나 반복 안내가 붙는 간결성 한계도 남아 있다.
