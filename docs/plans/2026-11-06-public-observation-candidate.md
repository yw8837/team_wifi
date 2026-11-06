# 공개 요청 관측 전송 후보 — 승인 수신, 운영 검증 진행

2026-11-06. 최신 `chatbot_02` 원문은 “챗봇 답변의 검색 근거·도구 호출·응답 품질·지연·오류를 Opik으로 기록하고 고정 평가 질문으로 버전별 결과를 비교한다. 기록 전에 이메일·닉네임 등 개인정보를 제외한다.”이다.

기존 GPU 추론·건강 확인 전용 키의 승인에 관측 전송을 포함시키지 않는다. 아래 후보를 제시한 뒤 사용자가 관측 권한 확대를 별도로 명시 승인했다. 현재 실제 게이트웨이·수집기·Render 연결과 운영 추적 저장 검증을 진행 중이며, 완료 증거는 별도 영수증으로 남긴다. 아래 로컬 후보 테스트 기록을 실제 운영 활성화·저장 증거로 읽지 않는다.

## 제안과 요구 범위

**별도 `observe` 메타데이터 동작과 상주 SDK 수집기 (추천)**. 추론하지 않는 거절·근거 없음과 추론 뒤 최종 검증도 기록하려면 Render의 요청 처리 완료/실패 지점에서 관측을 보내야 한다. GPU의 `infer` 처리만 계측하면 검색·도구·최종 검증, 추론 전 오류를 포함하는 전체 요청 기록을 만들 수 없다.

Render는 기존과 동일한 전용 키와 고정 SSH 명령을 사용하되, 승인 뒤에만 메타데이터 전용 `observe`를 허용한다. 게이트웨이는 허용된 구조만 검증해 고정 로컬 Unix 소켓으로 전달하고, 별도 상주 프로세스의 SDK 작업자 한 개가 기존 자체 호스팅 Opik에 기록한다. 매 요청마다 게이트웨이에 무거운 SDK를 import하지 않는다. 질문·답변을 모델 추론과 별도로 관측 채널에 보내지 않는다.

기존 고정 질문 평가의 자동 통과·내용 검토·실제 추적 저장 영수증은 운영 요청과 구분한다. 새 수집기는 프로젝트 `moduyuga-public-requests`, 추적 이름 `assistant.public_request`, 고정 `record_kind=public_runtime`를 사용한다. 평가 40/12건 등의 기록을 공개 트래픽 기록으로 표시하지 않는다.

## 검토할 계약

프로토콜 버전은 1이며 동작은 새 `observe`다. 봉투 키는 `version`, `operation`, `timeout_seconds`, `observation`만 허용한다. 기존 `infer`/`health`의 필드·모델·포트 제한은 유지한다. 관측 전송은 추론과 별도의 클라이언트 실행 제한을 사용하여 추론 슬롯을 점유하지 않는다. 공개 상태 조회는 최근 결과를 읽는 방식이며 관측 또는 건강 확인 네트워크 요청을 만들지 않는다.

| 관측 필드 | 허용 값 |
|---|---|
| schema_version / prompt_version | 정수 1 / 고정 `extractive-group-v5` |
| public_sources | 최대 5개. 저장소의 정적 공개 ID→SHA-256 맵과 ID·revision 모두 정확히 일치해야 함 |
| stages | retrieval/tools/generation/validation/total. 각 status는 completed/skipped/error/unknown, duration_ms는 0~120,000의 정수 |
| tools | public_catalog/own_saved/own_preferences/public_community/public_groupbuys의 호출 횟수 0~16. 조회한 개인 기록 수가 아님 |
| outcome | generated/local_extractive/retrieval_only/abstained/error |
| validation | exact_public_citation/retrieval_only/abstained/not_assessed |
| error_code | none, disabled, busy, timeout, unavailable, invalid_output, invalid_citation, no_supported_claims, non_extractive_text, unsafe_output, oversized_output, host_key_mismatch, invalid_configuration, invalid_request, quota, auth_changed, evidence_changed만 |

추가 필드, 자유 문자열, 인용문·질문·답변·이메일·닉네임·사용자/대화 ID·요청 UUID·IP·판매처 URL·예외 메시지·토큰·개인키를 받지 않는다. 기존 내부 요청 UUID도 전송 전에 버린다. SDK의 `input`과 `output`은 `None`이고 자동 LLM/프레임워크 추적 데코레이터를 사용하지 않는다. SDK 익명 사용 분석은 끈다. SDK trace ID는 SDK가 독립 생성하며 회원 ID와 연결하지 않는다.

공개 출처 맵은 `scripts/build-observation-sources.py`가 회원 DB에 접속하지 않고 저장소의 승인된 공개 corpus로만 생성한다. 후보 생성 시 19개 출처다. 새 배포의 실제 corpus와 맵을 함께 생성·검토하고 양쪽에 동일한 파일을 배치해야 한다. 수신 계약은 전송된 source ID/revision이 맵과 다르면 관측 이벤트를 거부하며 질문 응답은 계속한다. 상위 요청 훅은 인용 전체가 정적 맵에 정확히 일치할 때만 공개 source ID/revision을 붙인다. 미일치 인용이 있으면 인용 목록을 전송하지 않고 `public_sources=[]`로 남기며, 모델 답변의 검증 품질은 `not_assessed`로 표시한다. 이것은 출처 일치를 확인했다는 뜻이 아니다.

`exact_public_citation`은 공개 인용의 기계적 검증 상태다. 답변의 완전성·의학적 적절성·사람의 의미 판단 점수가 아니다. 의미 품질은 고정 공개/합성 평가와 명시한 검토 기준으로 따로 비교한다. 실행하지 않았거나 확인할 수 없는 단계는 skipped/unknown/not_assessed로 남긴다. `validation` 시간은 초기·최종 권한/근거/저장 검증 구간의 경과 시간이며 그 안의 `tools` 조회 시간과 겹치는 포괄 시간이다. 단계별 시간을 더해 전체 지연으로 표시하지 않는다. 전체 요청 지연은 별도의 `total`로 읽는다.

## 자원·실패 제한

- 관측 본문 최대 4KiB. Render 전송 대기열 32개, SSH 관측 실행 1개다. 비차단 enqueue가 실패하거나 검증에서 거절되어도 회원 응답은 바꾸지 않는다.
- Unix 소켓 경로는 배포 루트의 `.runtime/assistant-observe/collector.sock`으로 고정한다. 디렉터리는 0700, 소켓은 0600이며 프로세스 소유자만 사용한다. 요청이 경로·URL·프로젝트를 선택할 수 없다.
- 수집기는 대기열 32개, 분당 최대 30건, SDK 작업자 1개다. JSON 읽기와 ACK도 길이·시간 제한을 둔다. 게이트웨이에는 SDK를 import하지 않고 고정 소켓 통신만 수행한다.
- SDK 전송/flush 실패 후에는 실패 상태를 유지하고 추가 SDK 전송을 중단한다. 대기/신규 이벤트는 drop으로 계수하며 재시작은 운영자가 판단한다. SDK 내부 재시도 큐가 계속 늘어나는 것을 피한다.
- ACK의 accepted는 수집기 메모리 큐에 들어갔다는 뜻이다. Render의 remote_accepted와 SDK의 sdk_flushed를 분리한다. 항상 persistence_verified=false이며 실제 Opik 조회로 영속 저장을 별도 확인해야 한다.
- 프로세스 재시작 시 대기 이벤트와 누적 카운터는 소실된다. 분당 제한·대기열 포화·소스 맵 불일치·네트워크/SDK 장애로 기록이 빠질 수 있다. failed/dropped/rejected와 마지막 원격 카운터를 운영 화면에 드러내며 전량 보존을 주장하지 않는다.
- 추적 수집기 하나의 메모리/CPU 사용량은 실제 설치 SDK로 활성화 전 계측해야 한다. 이 후보는 추가 유료 서비스나 새 인스턴스를 만들지 않는다. 기존 서버의 추론·Opik과 자원을 공유하므로 부족하면 관측을 끄고 추론을 유지한다.

## 승인 후에만 바뀔 권한과 설정

현재 등록된 공개키의 지문은 `SHA256:3BwQiYDzH0g6+fM5CZcFFsqAmDWdU8vJZszATm9dqTk`이다. 기존 동일 키의 강제 명령 줄에 **`--enable-observe`를 추가하는 권한 변경**을 검토한다. 다른 키와 줄은 보존한다. 새 셸·파일 전송·포트/에이전트/X11 전달·PTY 권한은 추가하지 않는다.

```text
restrict,command="/home/elicer/Team_Wifi/.venv/bin/python /home/elicer/Team_Wifi/.runtime/restricted-inference-v1/scripts/serve-restricted-inference.py --port 8091 --enable-observe" ssh-ed25519 EXISTING_DEDICATED_PUBLIC_KEY
```

승인 뒤에만 후보 파일/공개 출처 맵 배치, `ASSISTANT_OBSERVE_COLLECTOR_ENABLED=true`인 수집기 시작, Render의 `ASSISTANT_OPIK_ENABLED=true` 및 `ASSISTANT_SSH_OBSERVE_ENABLED=true`를 진행한다. Opik의 목적지는 고정 자체 호스팅 loopback이며 클라우드 기본값을 사용하지 않는다. 현재 후보의 기본값과 기존 강제 명령은 관측을 허용하지 않는다.

철회는 Render 관측 플래그를 끄고, 동일 키 줄에서 `--enable-observe`를 제거하고, 관측 수집기만 중단하는 순서다. 추론/건강 확인과 기존 모델·Opik 프로세스를 유지한다. 이후 안전한 공개/합성 요청으로 별도 프로젝트의 실제 SDK 저장과 본문/식별자 부재를 확인하기 전에는 운영 기록 연결이 완료됐다고 말하지 않는다.

## 검증 기록

후보 프로토콜의 원문/ID/자유 필드 거부, 정적 출처·해시 검증, 시간/상태/오류 열거형, 프레임 크기, 별도 실행 슬롯, 분당/큐 제한, SDK 실패 누적, 입력/출력 미수집, ACK와 영속 저장의 구분을 모의 SDK·SSH로 검사한다. 기존 추론·건강 확인 회귀도 함께 실행한다. 실제 운영 Opik이나 현재 게이트웨이에 새 동작을 호출한 결과가 아니다. 최종 테스트와 소스 해시는 `artifacts/community-completion-20261106/observation-candidate-results.json`에 기록한다.

최종 로컬 검증: 후보 56개와 기존 추론·관측·운영 요약·도우미·공구·키 준비 회귀를 합해 **240 passed**. SDK·SSH는 새 후보 검사에서 모의했고 실제 관측 권한이나 운영 기록 연결은 활성화하지 않았다. 회원 공구·커뮤니티 레코드 ID는 전송하지 않고 도구 종류·호출 횟수만 기록한다.
