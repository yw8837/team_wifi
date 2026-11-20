# 모두의 육아 중간발표 자료

2026-11-09 최신본은 본편 15장과 부록 23장, 총 38장이다. 사용자 의견에 따라 2장 Answer, 3장 목차를 먼저 제시하고 데이터 활용·RAG·서비스 검증의 세 가지 근거로 전개한다. 설명 560초와 화면 전환 여유 40초로 사용자가 예상한 10분을 계획했다. 실제 리허설 전 기준이다.

사용자 전달 폴더는 `output/presentation-20261109`다. 발표자료 PPTX·PDF, 대본 PDF, 평가항목 대조표 PDF를 각 하나씩 보관한다. 발표자료 파일명은 `모두의육아_발표자료.pptx`와 `모두의육아_발표자료.pdf`다. 38장에 발표 메모를 포함하며 표와 차트를 편집할 수 있다. 표준 PPTX 재작성 후 전체 장표를 다시 가져와 렌더링했다.

`pyramid-revision.py`는 기존 검토한 36장 PPTX를 수정한 이번 개편 기록이다. 앞선 작성·출력 스크립트는 이전 구성 이력이다. 사용자에게 확인용 MD와 중복 Word 파일을 전달하지 않는다.

최신 대본은 `FINAL-SPEAKER-NOTES.md`다. `final-deck.mjs`는 본편 구성과 대본, `export-final.mjs`는 기존 라이브 장표 스냅샷의 PPTX 출력과 검사를 담당한다. 기존 `deck.mjs`와 `SPEAKER-NOTES.md`는 이전 38장 작성 이력이다.

본편은 SCQA → 서비스 흐름 → 제공 자료 → 분석·모델 비교 → 외부 자료 → RAG·Opik → UI·실기기 → DB·검증 → 피드백 순서다. 부록에는 데이터 세부, CTR·AEO/GEO, 요구사항, 화면설계, ERD, 권한, 출처와 평가표 대조를 담았다.

앱·웹 저장 왕복, 최신 팝업 UI, 제품 커밋 9cd1837의 서버 CI 663개·프런트 367개·서명 검증 51개와 확인 당시의 앱 공개·제출 상태를 본편에 갱신했다. 파일 구조·레이아웃 검사와 재가져오기 검사가 통과했으며 6개 이미지의 실제 바이트와 36개 발표자 메모를 별도 확인했다. 증거는 `artifacts/presentation-final-20261109/final-validation.json`과 `media-verification.json`이다.

편집 가능한 발표 자료는 `page://page_5e6d554cde5081918992da3863ec942c`에 저장했다. 뷰어에서 PowerPoint 형식으로 내려받을 수 있다.

## 이전 38장 구성 이력

- 1~4장 표지·SCQA·사용자 흐름·서비스 범위
- 5~11장 제공 데이터4종·품질 감사·분석 결과·서비스 적용
- 12~17장 외부 데이터·갱신·가격 변화·RAG·Opik·CTR·AEO/GEO
- 18장 최신 통합 요구사항 개요
- 19~23장 실제 사이트 캡처 기반 UI화면설계
- 24~27장 배포 구조·물리 ERD·논리 엔터티·권한과 데이터 수명
- 28~30장 검증·공개 배포·후속 개선·시연 흐름
- 31~32장 근거 자료
- 33~38장 요구사항48개 요약. 상세 원문은 각 슬라이드 발표자 노트에 보존했다.

## 근거 매핑

| 코드 | 원천 |
| --- | --- |
| S1 | docs/reports/data-use-20261103/REPORT.md |
| S2 | backend/app/discovery_evidence.json |
| S3 | ai-pipeline/artifacts/overlap_audit.json |
| S4 | ai-pipeline/pipeline.py 및 artifacts/summary.json |
| S5 | backend/app/discovery.py, release.py |
| S6 | ai-pipeline/artifacts/evaluation.json |
| S7 | backend/app/external_groupbuys.py, scripts/collect-external-groupbuys.py |
| S8 | backend/app/external_knowledge.json |
| S9 | artifacts/community-20261109/live-api.json |
| S10 | docs/build/release-20261106/COMMUNITY-ASSISTANT.md |
| S11 | backend/app/growth.py, frontend/src/measurement.tsx, scripts/export-public-guides.py |
| S12 | docs/plans/integrated-requirements-20261107.json |
| S13 | artifacts/handoff-20261109 및 community-20261109 실제 웹 캡처 |
| S14 | CI42493377207, docs/build/release-20261109/PLAY-SUBMISSION.md, docs/reports/handoff-20261109/DEVICE-CHECK.md |
| S15 | backend/app/db.py, release.py, groupbuys.py, social_auth.py |

연구 실험 수치와 실제 서비스 효과를 구분했다. LightGBM 구매 확률의 실시간 적용이나 실서비스 CTR 상승을 성과로 주장하지 않는다. 공공자료5건은11월8일 검토 스냅샷이며 판매처 수집은공구1건과비교1건 범위다. 기존 분석·평가 산출물을 대조했고 이번 장표 작성에서 전체 모델 재학습은 수행하지 않았다.

## 썸네일 후속 요청

기존 심볼을 줄여 위쪽에 배치하고 아래에 모두의 육아를 넣은 이미지를 생성했다. Google Play 규격512×512로 변환해 앱 아이콘 변경1건을 검토 전송했다. AI로 수정한 아이콘임을 해당 애셋에 선언했다. 자동 사전 검사 종료 후 검토 중 상태를 확인했다. 이후 공개 Google Play 페이지에서 수정 아이콘 반영을 확인했다. 공개 증거는 artifacts/presentation-20261109/icon-published.png다. 기존 Discord 메시지의 미리보기 캐시 갱신 여부는 확인하지 않았다.

파일은 artifacts/presentation-20261109/store-icon-with-name.png와 store-icon-512.png이며, 심사 증거는 icon-review.png다.
