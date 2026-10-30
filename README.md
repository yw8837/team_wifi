# 🛒 team_wifi — AI 기반 공동구매 커뮤니티 플랫폼

> **중소벤처기업부 이어드림스쿨 6기 산업 특화 연계 파이널 프로젝트 (핀테크)**  
> **참여 기업:** 모바일앱개발협동조합  
> **프로젝트 기간:** 2026. 10. 30 ~ 2026. 11. 26 (4주)

---

## 👥 팀원 구성 (Team wifi)

| 이름 | GitHub | 역할 | 주요 담당 |
| :--- | :--- | :--- | :--- |
| **최용우** | [@yw8837](https://github.com/yw8837) | Full-Stack / Architecture | 서비스 아키텍처 설계, 백엔드 API & GEO 엔진 구현 |
| **최유정** | [@cheezcyj](https://github.com/cheezcyj) | Frontend / UI·UX | 모바일 반응형 웹 인터페이스, 동적 인터랙션 및 CTA |
| **이승현** | [@LEES999](https://github.com/LEES999) | AI & Data Engineering | 이커머스 트랜잭션 분석, 군집화 및 수요·이탈 예측 모델 |

---

## 💡 프로젝트 개요 (Overview)

### 📌 주제: 다양한 형태의 서비스와 물품을 공동구매할 수 있는 커뮤니티 앱
기존 나열식 공동구매의 낮은 참여율과 SEO 인덱싱 지연 한계를 극복하기 위해, **생성형 AI 검색(GEO) 인바운드 트리거**와 **실시간 이탈 방지 동적 CTA**를 결합한 차세대 핀테크 이커머스 커뮤니티 플랫폼입니다.

### 🚀 핵심 솔루션 (Key Features)
1. **GEO(Generative Engine Optimization) 노출 유도 트리거**
   - 신규 공구 딜 생성 시 LLM 기반 구조화 데이터(JSON-LD, Schema.org) 자동 생성
   - ChatGPT Search, Perplexity 등 대화형 AI 검색 엔진의 실시간 최저가 답변 1순위 인용(Citation) 유도
2. **소비자 성향 기반 번들(세트) 공구 추천**
   - 트랜잭션 연관 규칙(Apriori/FP-Growth) 분석을 통한 맞춤형 묶음 공구 제안 (CTR 극대화)
3. **이탈 방지 실시간 동적 CTA 엔진**
   - 세션 행동 데이터 기반 실시간 구매 전환 의도 예측 및 맞춤형 혜택 넛지 (CVR 극대화)

---

## 📊 활용 데이터셋 (Datasets)
- **Ecommerce Consumer Behavior Analysis Data (Kaggle)**: 소비자 특성 군집화 및 개인 맞춤형 피드 추천
- **Online Retail Transaction Data (UCI & Kaggle)**: 장바구니 연관 규칙 분석 및 세트 공구 번들링
- **Online Shoppers Purchasing Intention (UCI)**: 실시간 구매 전환 예측 및 동적 CTA 트리거

---

## 🛠️ 기술 스택 (Tech Stack)

- **Frontend:** Next.js / React, TypeScript, Tailwind CSS
- **Backend:** Python (FastAPI), SQLAlchemy, PostgreSQL
- **AI / Data:** Scikit-learn, LightGBM, Pandas, NumPy
- **Infra & DevOps:** Docker, GitHub Actions

---

## 📁 프로젝트 구조 (Repository Structure)

```text
├── backend/          # FastAPI 백엔드 API 서버 & GEO 트리거 모듈
├── frontend/         # Next.js 반응형 웹 애플리케이션
├── ai-pipeline/      # 데이터 전처리, EDA 및 예측 모델 서빙
├── data/             # 데이터 명세 및 샘플 데이터셋 (.gitignore 처리)
└── docs/             # 요구사항 정의서, 와이어프레임, 회의록
```

---

## 📅 프로젝트 마일스톤 (Milestones)

- **1주차 (10/30 ~ 11/05):** 기획 구체화, 데이터셋 EDA 및 파이프라인 구축, DB 스키마 설계
- **2주차 (11/06 ~ 11/11):** 핵심 공구 API 구현, AI 추천 모델 1차 서빙, **중간평가(11/11)**
- **3주차 (11/12 ~ 11/19):** GEO 시맨틱 마크업 자동 생성기 연동, 동적 CTA 인터랙션 구현
- **4주차 (11/20 ~ 11/26):** E2E 통합 테스트, 서비스 배포 및 데모 시연 준비, **최종평가(11/26)**
