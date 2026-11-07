# 자료 확인과 적용

기준일 2026-11-01. 읽기·실험·코드 적용·외부 운영 완료를 구분합니다.

| 자료 | 실제 확인 | 현재 연결 |
|---|---|---|
| 사용자 프로젝트 원문 | 기간·공동구매 커뮤니티 과제·선택된 육아 방향·후속 요청 대조 | CONTRACT/101개 요구 대조/팀 실행 문서 |
| 기업 제공 DOCX | 보존 원문 134문단·39링크를 데이터 담당자가 읽음 | 소비 성향·묶음·판매량·구매의도 실험과 한계 |
| Notion 내보내기 | 229파일 inventory, 요구사항 101개 전체 설명 확인 | 코드/시험/미완료 상태표. 원문은 Git 제외 |
| 재전달 Notion 링크 | 연결 도구 fetch404, wifi 검색 결과없음. 브라우저도 페이지 찾지 못함 표시 | 현재 링크의 최신 내용을 읽었다고 주장하지 않음. 보존된 내보내기와 구분 |
| 기업 아이디어 블로그 | 웹 도구 실패 후 브라우저로 2025-08-14 게시물 본문·기능표·지원범위를 끝까지 읽음 | 관심사/모집/조건/정산/커뮤니티/베타 운영 차이를 후속 개발표에 유지 |
| D1–D4 | 해시 확인·실제 재분석·모델 학습·비교·누수/중복 검증 | 관리자 데이터 실험실 및 로컬 추론 API |

[기업 블로그 원문](https://blog.naver.com/swproject7/223970289742)은 상품·서비스 공동구매와 비용 공유를 다루며, 참여 조건·안전결제/정산·커뮤니티·분석·운영 도구를 제안합니다. 현재 육아용품 앱의 채택과 모든 제안 기능 완료는 서로 다른 판단입니다. 카카오·구글 로그인, 예치·자동 분배, 평판, 거래 히스토리, 실제 베타 운영은 첫 빌드의 로컬 계정·무결제 예약으로 대체 완료 처리하지 않습니다. 블로그의 지원 예시는 우리 팀에 제공된 계약/리소스 보증이 아닙니다.

## 데이터 출처

- [Kaggle 소비자 행동](https://www.kaggle.com/datasets/salahuddinahmedshuvo/ecommerce-consumer-behavior-analysis-data): 정확한 데이터셋을 로컬 다운로드 기록과 해시로 확인. 이번 웹 재조회는 본문 없는 응답이므로 라이선스 최신 재확인으로 세지 않음.
- [UCI Online Retail 352](https://archive.ics.uci.edu/dataset/352/online+retail): 원문을 다시 열어 541,909행·영국 선물용품·통화/변수·CC BY4.0을 확인.
- [UCI Online Retail II 502](https://archive.ics.uci.edu/dataset/502/online+retail+ii): 보존된 원문/메타데이터와 복원본 해시로 분석. D2와 중복 합산하지 않음.
- [UCI 구매의도 468](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset): 원문을 다시 열어 12,330세션·구매정답1,908개·특성 정의·CC BY4.0 확인. 실시간 서비스 성능 주장이 아닌 완료세션 실험으로 표시.

## 벤치마크 적용

| 공식 자료 | 확인 범위와 적용 |
|---|---|
| [쿠팡 FAQ](https://news.coupang.com/archives/63616/) | 상품별 배송·교환·반품·판매자 안내. 상세 UI 일부 접근 실패를 로그인 필요 증거로 해석하지 않음 |
| [11번가 상품상세](https://www.11st.co.kr/products/3394145862) | 공개 판매자 정보/조건. 지표 정의·기간 표기 참고. 실제 구매를 수행하지 않음 |
| [스마트스토어 입점](https://help.sell.smartstore.naver.com/faq/content.help?faqId=3657), [보류](https://help.sell.smartstore.naver.com/faq/content.help?faqId=3675) | 제출·검토·보완·승인 구분. 공개 도움말이며 로그인 센터 직접 검증 아님 |
| [당근 비즈프로필](https://www.daangn.com/wv/faqs/34530) | 개설과 검토 후 노출 구분. 개인 거래 인증을 판매자 적격성으로 대체하지 않음 |
| [알리 한국 셀러 규정](https://terms.alicdn.com/legal-agreement/terms/b_platform_service_agreement/20230926144011648/20230926144011648.html) | 정보 정확성·정정·환불 책임 분리. 타국 UI를 한국 흐름으로 일반화하지 않음 |
| [알구몬](https://play.google.com/store/apps/details?id=com.algumon.app&hl=ko), [공구모아](https://gonggumoa.com/) | 별도 핫딜 탐색/출처/확인일. 공구모아 약관의 수집·복제 제한을 확인해 무단 수집 공급원으로 쓰지 않음 |

위 공식 자료는 읽기 전용 조사자가 확인한 내용이며 메인은 그 원문 메모와 구현 대응을 대조했습니다. 직접 모든 사이트에 가입·주문·입점 심사를 수행했다는 뜻이 아닙니다.

## 지정 스킬 적용

지목 16개 SKILL 전체/필요 참조를 읽은 별도 감사 결과를 메인이 확인했습니다. research의 원천 근거, unlazy의 실행 게이트, ultraqa의 권한·중복·중단·오프라인 시험, 한국어 문구/사실 보존, 원문/개발용 가격 구분을 적용했습니다. 정적 디자인 스캐너도 실제 실행했으며 링크 밑줄·외부이동 화살표·카테고리 pill 등 의도된 표시를 무작정 지우지 않았습니다.

SEO/GEO는 보이는 조건과 공개 HTML/JSON-LD의 사실 일치부터 구현했습니다. 개발 상품은 noindex이고 검색 인용 실적은 미측정입니다. [OpenAI bots](https://developers.openai.com/api/docs/bots)의 검색/학습 봇 분리, [Google AI features](https://developers.google.com/search/docs/appearance/ai-features) 및 [업데이트](https://developers.google.com/search/updates)를 확인한 감사 결과에 따라 오래된 AEO 안내를 그대로 적용하지 않았습니다. LinkedIn hook 형식, 개인 문체 인터뷰, Bing 제출, 발표 템플릿 제작은 해당 작업을 실행했다고 표시하지 않습니다. Supabase 외부 프로젝트·유료 서비스·Elice는 호출/생성하지 않았습니다.
