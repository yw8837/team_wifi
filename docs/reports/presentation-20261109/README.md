# 모두의 육아 중간발표 자료

2026-11-09 기준 총38장이다. 사용자가 요청한 기획안, 요구사항정의서, UI화면설계서, ERD와 제공·외부 데이터 활용, SCQA를 포함한다.

편집 가능한 발표 자료는 `page://page_5e6d554cde5081918992da3863ec942c`에 저장했다. 뷰어에서 PowerPoint 형식으로 내려받을 수 있다.

## 장표 구성

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

기존 심볼을 줄여 위쪽에 배치하고 아래에 모두의 육아를 넣은 이미지를 생성했다. Google Play 규격512×512로 변환해 앱 아이콘 변경1건을 검토 전송했다. AI로 수정한 아이콘임을 해당 애셋에 선언했다. 자동 사전 검사 종료 후 검토 중 상태를 확인했다. 실제 공개·Discord 미리보기 갱신은 추가 확인 대상이다.

파일은 artifacts/presentation-20261109/store-icon-with-name.png와 store-icon-512.png이며, 심사 증거는 icon-review.png다.
