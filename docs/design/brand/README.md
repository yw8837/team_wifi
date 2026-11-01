# 모두의 육아 - 육아템 공동구매,핫딜 · 디자인 기준

사용자가 2026-11-01 확정한 명칭과 전달한 원본을 기준으로 한다. 이전 기획의 축약 명칭이 최신 앱명보다 우선하지 않는다.

| 용도 | 확정 값 |
|---|---|
| 정식 앱명·문서 제목·Android 앱명 | **모두의 육아 - 육아템 공동구매,핫딜** |
| 원본 로고의 글자 | **모두의육아** — 원본 이미지 보존 |
| 공개 개발자 | **Team_Wifi** |
| Android 패키지 | `kr.moduyuga.app` |
| 화면 구조·동선 | [v0.6 원본](source/screen-spec-v0.6.png), [50화면 대조표](../screen-spec-v0.6.md) |

## 자산과 사용 범위

| 파일 | 출처·판정 | 적용 |
|---|---|---|
| [symbol.svg](../../../frontend/public/brand/symbol.svg) | 사용자가 메시지로 준 완전한 SVG, 3개 path | 웹 로고·favicon, Android 벡터 아이콘·시작 화면 |
| [wordmark.png](../../../frontend/public/brand/wordmark.png) | 원본 투명 PNG, 3066×744 | 웹 헤더·로그인 워드마크 |
| [symbol-original.png](source/symbol-original.png) | 원본 쪽쪽이 PNG | 원본 보존·대조 |
| [wordmark-truncated.svg.txt](source/wordmark-truncated.svg.txt) | 첨부 텍스트 끝이 잘림. XML 파싱 실패 | 참고 보존만 함. 배포 SVG로 사용하지 않음 |
| [design-board.png](source/design-board.png) | 심볼·워드마크·컬러 디자인보드 | 브랜드 색·느낌의 기준 |
| [palette-reference.png](source/palette-reference.png) | 먼저 받은 5색 팔레트 | v0.6의 강조색 참고 |

워드마크의 잘린 벡터를 추정 복원하거나 다른 폰트로 대체하지 않았다. 정확한 벡터 워드마크가 필요한 인쇄물은 완전한 원본이 필요하다. 현재 PNG는 화면에서 원래 비율을 유지해 표시한다.

## 색·접근성

- 심볼 코랄 `#DC8E85`, 중앙 크림 `#FFF5E7`, 코코아 `#4F382E`, 블러시 `#F5E4DF`를 보존한다.
- 작은 흰 글자가 있는 행동 버튼은 대비를 확보한 `#BD3E33`을 사용한다. 로고 원본 색을 바꾸는 조정이 아니다.
- 본문 `#2B2B2B`, 보조 글자 `#746259`, 흰색/크림 표면. 주요 버튼 최소 높이 48px, 키보드 포커스, 동작 줄이기, Android safe area를 적용한다.
- 상품 사진이 없는 개발 데이터는 카테고리 아이콘과 ‘상품 이미지 준비 중’으로 표시한다. 원본 설계서의 샘플 상품·가격·평점은 운영 데이터가 아니다.

## 재현

`python scripts/build-brand-assets.py`로 원본 심볼의 path를 Android VectorDrawable에 옮긴다. 좌표를 수작업으로 다시 그리지 않는다. `scripts/build-android.ps1`로 웹과 리소스를 포함한 debug APK를 만든다. 실제 실행·배포 검증은 [검증 기록](../../build/brand-20261101/VERIFICATION.md)에 따로 적는다.

현재 반영은 브랜드 자산·홈 상품 카드·검색·로그인/소개·공통 테마다. v0.6의 전체 기능과 모든 화면을 완성한 결과가 아니다. 원본 화면설계서를 줄이거나 삭제하지 않고 [대조표](../screen-spec-v0.6.md)에서 남은 조건을 추적한다.
