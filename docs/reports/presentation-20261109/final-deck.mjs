import fs from 'node:fs/promises';

const root = 'E:/Team_Wifi/';
const color = { bg: '#F8F5EF', ink: '#382D29', muted: '#756B65', red: '#B94034', teal: '#365E68', pale: '#EEE5D9' };
const font = 'Malgun Gothic';
const artifactDir = root + 'artifacts/presentation-final-20261109/';

function text(slide, value, x, y, w, h, size = 28, bold = false, fill = color.ink) {
  const shape = slide.shapes.add({ geometry: 'textbox', position: { left: x, top: y, width: w, height: h }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = value;
  shape.text.style = { fontFamily: font, fontSize: size, bold, color: fill };
  return shape;
}

function rect(slide, x, y, w, h, fill = color.pale) {
  return slide.shapes.add({ geometry: 'rect', position: { left: x, top: y, width: w, height: h }, fill, line: { fill: 'none', width: 0 } });
}

function table(slide, rows, widths, y = 190, height = 360) {
  const t = slide.tables.add({ rows: rows.length, columns: rows[0].length, left: 68, top: y, width: 1144, height, columnWidths: widths, values: rows });
  for (let r = 0; r < rows.length; r++) {
    for (let c = 0; c < rows[0].length; c++) {
      const cell = t.getCell(r, c);
      cell.fill = r === 0 ? color.teal : r % 2 ? '#FFFFFF' : color.pale;
      cell.text.style = { fontFamily: font, fontSize: 24, color: r === 0 ? '#FFFFFF' : color.ink, bold: r === 0 };
    }
  }
}

export const main = [
  {
    title: '모두의 육아', type: 'cover', seconds: 15,
    subtitle: '데이터와 근거를 연결하는 육아 커뮤니티',
    notes: '안녕하세요. Team_Wifi의 모두의 육아입니다. 저희는 육아 정보를 함께 나누고, 제품 조건을 비교하며, 출처 있는 답변을 얻는 커뮤니티를 만들었습니다. 제공 데이터 분석이 실제 서비스 설계와 구현으로 이어진 과정을 말씀드리겠습니다.',
    source: 'Team_Wifi · 이승현 · 최유정 · 최용우 · 2026.11.09',
  },
  {
    title: '문제 정의와 SCQA', type: 'four', seconds: 40,
    items: [['S · 상황', '육아템을 고를 때\n제품 조건과 사용 경험이 함께 필요'], ['C · 복잡성', '출처·구성·배송비가 흩어져\n같은 기준의 비교가 어려움'], ['Q · 질문', '비교에 필요한 정보와\n신뢰할 근거를 함께 얻으려면?'], ['A · 서비스', '경험을 나누는 커뮤니티에\n가격 비교와 근거 기반 챗봇 연결']],
    bottom: '주요 이용자 · 육아용품을 준비하는 보호자와 예비 보호자',
    source: '팀 기획 가설 · 주간 멘토링과 커뮤니티 방향 피드백',
    notes: '출발점은 육아템 선택 과정에서 정보와 경험이 흩어져 있다는 문제 가설입니다. 가격만 확인해도 구성과 배송비가 달라 다시 비교해야 하고, 사용 경험이나 안전 정보는 다른 곳에서 찾아야 합니다. 멘토 피드백을 반영해 질문과 경험이 쌓이는 커뮤니티를 중심에 두고, 비교와 챗봇을 연결했습니다. 이 문제의 규모와 불편 정도는 실제 이용자 인터뷰로 추가 확인할 항목입니다. 근거는 docs/plans/2026-11-05-community-feedback.md와 주간일지입니다.',
  },
  {
    title: '질문에서 비교와 경험 공유까지', type: 'flow', seconds: 35,
    steps: ['육아템·질문 탐색', '출처·조건 비교', '챗봇·댓글로 확인', '저장·경험 공유'],
    bottom: '공구 상세와 커뮤니티를 댓글로 연결\n같은 계정으로 앱·웹 활동을 이어서 이용',
    source: '통합 요구사항 48개 · 공구·게시판·댓글·저장 구현',
    notes: '사용자는 관심 있는 육아템이나 질문을 찾고, 조건을 비교한 뒤, 챗봇이나 댓글로 궁금한 점을 확인합니다. 확인한 정보는 저장하고 경험을 남길 수 있습니다. 차별화 가설은 제품 조건과 사용자 경험, 공식 근거를 하나의 동선에서 확인하는 데 있습니다. 서비스는 정보와 공동구매 수요를 연결하고 주문·결제·배송·환불은 판매처에서 처리합니다. 관련 요구사항은 groupbuy_02, demand_01~05, comment_01, save_01입니다.',
  },
  {
    title: '제공 데이터의 발견과 서비스 적용', type: 'table', seconds: 45,
    rows: [['제공 자료', '분석에서 확인한 점', '서비스에 반영한 동작'], ['소비자 1,000명', '할인 반응 차이 · 육아 표본 41명', '관심 분야·비교 기준 직접 선택'], ['소매 거래 541,909행', 'Online Retail II와 전체 중복', '추가 합산 제외 · 중복 집계 방지'], ['Online Retail II 1,067,371행', '같이 담는 품목의 동시 출현', '계정별 공동 저장 조합 분석'], ['쇼핑 세션 12,330개', '종료 시점의 구매 여부 기록', '비교 CTA 설계 · 동의 기반 측정']],
    widths: [360, 394, 390],
    bottom: '분석 단위 · 사람 / 거래 / 세션 / 현재 서비스 계정',
    source: '데이터 분석 보고서 · overlap_audit.json · discovery_evidence.json',
    notes: '제공 자료는 네 종류입니다. 소비자 자료는 비교 기준의 선택권을 설계하는 참고로 썼고, 육아용품 표본 41명이라는 범위를 확인했습니다. 소매 데이터는 파일이 달라도 541,909행이 중복되어 추가 합산에서 제외했습니다. 거래 자료의 동시 출현 분석은 현재 서비스의 함께 저장한 육아템 집계에 적용했습니다. 종료된 쇼핑 세션은 분류 실험에 사용하고 실제 서비스에서는 사용자가 선택한 기준에 따른 CTA와 측정 구조를 구현했습니다. 서로 다른 자료를 같은 회원으로 연결하는 키는 없습니다. 근거 docs/reports/data-use-20261103/REPORT.md, ai-pipeline/artifacts/overlap_audit.json.',
  },
  {
    title: '연관 분석 실험과 공동 저장 집계', type: 'association', seconds: 50,
    source: '과거 거래 품목 복원 실험 · discovery_evidence.json / discovery.py',
    notes: '연관 분석은 시간순으로 나눈 과거 거래에서 평가했습니다. 상위 100개 품목을 두 개 이상 가진 평가 송장 4,338개에서 품목 하나를 숨기고 상위 다섯 개 추천에 복원되는지 봤습니다. 조건부 Recall@5는 인기순 10.56%, 연관 규칙 36.21%였습니다. 이 결과의 적용 범위는 해당 과거 장바구니 복원 실험입니다. 서비스에는 동시 출현 방법을 옮겨서, 회원별 저장 중복을 제거하고 다섯 계정 이상이 함께 저장한 조합을 운영자에게 제공합니다. 운영자는 이 조합을 비교 가이드와 공구 조사에 활용합니다. 실제 육아 이용자의 구매 전환 효과는 후속 검증 대상입니다. 근거 backend/app/discovery_evidence.json, ai-pipeline/pipeline.py, backend/app/discovery.py.',
  },
  {
    title: '구매의도 모델의 평가와 적용 판단', type: 'table', seconds: 40,
    rows: [['평가 모델', 'AUROC', 'Average Precision'], ['구매 비율 기준', '0.5000', '0.1522'], ['로지스틱 회귀', '0.7223', '0.3054'], ['LightGBM', '0.7448', '0.2937']],
    widths: [540, 300, 304],
    bottom: '8개 특징 · 특징 그룹 겹침 0 · 학습 / 검증 / 평가 분리\n현재 적용 · 선택한 비교 기준 안내와 단가 비교 CTA',
    source: 'evaluation.json · 종료 세션 12,330개 / 평가 2,746개',
    notes: '구매의도 자료에서는 로지스틱 회귀와 LightGBM을 비교했습니다. PageValues, BounceRates, ExitRates 등은 제외하고 여덟 특징을 썼으며, 같은 특징 그룹이 분할 사이에 겹치지 않게 했습니다. 검증 AP로 선택된 모델은 LightGBM이지만 최종 평가 AP는 로지스틱 회귀가 더 높았습니다. 종료 시점 집계로 학습했기 때문에 진행 중 사용자의 구매 확률로 해석하려면 시점별 로그와 별도 검증이 필요합니다. 현재 제품에는 사용자가 고른 기준 안내와 단가 비교 CTA를 적용했습니다. 근거 ai-pipeline/artifacts/evaluation.json. 분할 7,219 / 2,365 / 2,746.',
  },
  {
    title: '외부 데이터와 현재 정보의 갱신', type: 'table', seconds: 45,
    rows: [['출처', '확보한 범위', '서비스 활용'], ['캔코 공식몰', '공구 1건 + 일반 판매 비교 1건', '조건·단가 비교와 챗봇 조회'], ['Safety Korea · 질병관리청', '리콜·인증·건강 안내 요약 5건', '공식 근거 검색과 출처 연결'], ['서비스 DB', '공개 공구·글·본인 저장·설정', '인증·권한을 확인한 현재 조회']],
    widths: [350, 400, 394],
    bottom: '판매처 6시간 갱신 · 확인 유효기간 24시간\n공공자료는 11월 8일 검토본 · 오프라인 가격은 직접 입력',
    source: 'external_groupbuys.py · external_knowledge.json · 2026.11.09 확인 기록',
    notes: '제공 자료의 분석을 서비스 도메인으로 연결하기 위해 판매처와 공공자료를 추가했습니다. 확보 범위는 공식몰 공구 한 건과 일반 판매 비교 한 건, 공공 안내 요약 다섯 건입니다. 판매처는 여섯 시간마다 갱신하고 확인한 지 하루가 지난 정보는 만료 기준을 적용합니다. 실제로 공구 가격이 109,000원에서 129,000원으로 바뀌어 일반 판매와의 차이가 15.5%에서 0%로 갱신된 기록이 있습니다. 공공 지식의 검토일과 DB의 요청 시점 조회를 각각 표시합니다. 근거 backend/app/external_knowledge.json, scripts/collect-external-groupbuys.py, artifacts/community-20261109/live-api.json.',
  },
  {
    title: 'RAG와 권한 기반 DB 조회 설계', type: 'rag', seconds: 50,
    source: 'assistant_tools.py · COMMUNITY-ASSISTANT.md · Qwen3-1.7B',
    notes: '챗봇은 질문과 현재 로그인 상태를 확인한 뒤 두 종류의 근거를 가져옵니다. 공식 안내는 공개 문서 검색에서 찾고, 현재 공구나 본인 저장은 허용된 도구로 DB를 조회합니다. Qwen3-1.7B는 이 근거를 선택하고 답변을 구성하는 데 사용합니다. 작은 모델을 선택해 기존 GPU 자원 안에서 운영하고, 정확한 가격과 회원 권한은 서버와 도구가 담당하도록 했습니다. 생성 후에는 출처와 응답 상태를 확인합니다. 근거가 부족하거나 의료 판단이 필요한 질문, 도구 실패에는 보류나 오류 안내를 제공합니다. 원문 갱신이 필요한 정보에는 확인 시각을 함께 제시합니다. 근거 docs/build/release-20261106/COMMUNITY-ASSISTANT.md.',
  },
  {
    title: 'Opik 품질 관측과 고정 평가', type: 'two', seconds: 40,
    items: [['고정 평가 · snapshot08', '회귀 항목 통과 52 / 52\n지원 가능 모델 답변 36 / 36\n검색 Recall@5 0.9444\n정확한 공개 인용 42개'], ['운영 요청 관측', '검색 → 도구 → 생성 → 검증\n단계별 지연·상태·오류 코드\n공개 출처 ID와 revision\n실제 Opik 저장 조회 확인']],
    bottom: '고정 문제 반복 평가 · 독립 질문과 사람 평가는 후속 검증\n예열 모델 35표본 p95 878ms · 웹 전체 지연은 별도 측정',
    source: '2026.11.06 평가 및 Opik 저장 기록 · COMMUNITY-ASSISTANT.md',
    notes: 'Opik은 어느 단계에서 지연이나 실패가 생기는지 확인하기 위해 사용합니다. 고정 평가 snapshot08에서 회귀 항목 52개가 통과했고, 지원 가능한 모델 답변 36개와 공개 인용 42개를 확인했습니다. 검색 Recall@5는 원래 정답 기준 0.9444를 보존했습니다. 같은 문제로 반복 보완한 회귀 평가이므로 새로운 질문에서의 일반화 성능은 독립 평가로 확인해야 합니다. 운영에는 단계별 수치와 공개 출처 식별값을 기록하고 질문·답변 원문 및 회원 식별값의 전송은 제한합니다. 예열 모델 지연과 사용자가 경험하는 전체 응답 지연은 각각 관측합니다.',
  },
  {
    title: '커뮤니티 화면에서 바로 여는 챗봇', type: 'screen', seconds: 35,
    image: 'artifacts/account-switch-20261109/chat-compact-live.png',
    lines: ['우하단 팝업으로 질문', 'Enter 전송 · Shift+Enter 줄바꿈', '필요할 때 펼치는 안내·저장 대화', '댓글·관심·저장으로 활동 연결'],
    source: '11월 9일 실제 배포 화면 · 공구 댓글·신고·차단 구현',
    notes: '현재 배포 화면입니다. 하단 오른쪽에서 챗봇을 열고 엔터로 전송하며 쉬프트 엔터로 줄바꿈합니다. 피드백에 따라 크게 차지하던 안내와 저장 대화 영역을 접히는 행으로 줄였습니다. 커뮤니티에는 질문, 경험, 정보, 공구 수요를 구분하고 공구 상세에도 댓글을 연결했습니다. 본인 수정과 삭제, 신고와 차단, 내 활동 조회를 함께 제공합니다. 화면 캡처에 포함된 계정과 게시 내용은 시연 범위로 설명합니다.',
  },
  {
    title: '실제 휴대폰으로 확인한 앱·웹 연동', type: 'sync', seconds: 40,
    source: 'device-saved-confirmed.png · web-after-device-remove.png · 2026.11.09',
    notes: '같은 카카오 계정으로 로그인한 실제 기기에서 저장의 양방향 동작을 확인했습니다. 먼저 웹에서 맘큐 기저귀·물티슈를 저장하고 휴대폰 앱의 저장 목록에 나타나는 것을 확인했습니다. 이어 앱에서 저장을 해제한 뒤 웹을 다시 조회했을 때 목록에서 사라졌습니다. 이 확인은 실제 설치된 0.6.7 앱으로 수행했고 시험용 저장은 복구했습니다. 계정은 provider와 subject로 연결하고, 앱과 웹은 동일한 API와 DB를 조회합니다. 닉네임도 같은 계정으로 표시됨을 확인했습니다.',
  },
  {
    title: '배포 구조와 DB 책임', type: 'flow', seconds: 40,
    steps: ['React 웹·Android 앱', 'Cloudflare HTTPS', 'FastAPI 인증·권한', 'Neon PostgreSQL'],
    bottom: '물리 테이블 4개 · users / tokens / records / rate_buckets\nrecords.kind로 글·댓글·저장 관리 · 고유 키·revision으로 충돌 검사',
    source: 'db.py · release.py · social_auth.py · 물리 ERD와 논리 관계는 부록',
    notes: '웹은 React와 Vite, 앱은 Android 패키지로 같은 서비스 API를 사용합니다. 공개 HTTPS 요청은 Cloudflare를 거쳐 FastAPI로 전달되고 데이터는 Neon PostgreSQL에 저장됩니다. 현재 API와 모델 운영 환경은 기존 Elice 서버 구성입니다. 물리 테이블은 users, tokens, records, rate_buckets 네 개입니다. 글과 댓글, 저장 같은 논리 엔터티는 records의 kind와 JSON 데이터로 표현합니다. 따라서 부모 대상의 종류와 접근 권한, 삭제 정리는 API가 검사합니다. 고유 키와 revision, 트랜잭션으로 반복 요청과 충돌을 처리합니다. 근거 backend/app/db.py, release.py, social_auth.py.',
  },
  {
    title: '구현 검증과 출시 상태', type: 'two', seconds: 30,
    items: [['최신 제품 코드 검증', '서버 CI 663개 통과\n프런트 367개 통과\nAndroid 서명·설정 51개 통과\n제품 커밋 9cd1837'], ['앱·웹 확인 결과', '공개 앱 0.6.7 · 실기기 확인\n0.6.8 · Play 제출·자동 검사 단계\n웹 UI 개선 배포 완료\n카카오 로그인·저장 왕복 확인']],
    bottom: '기준 · 2026년 11월 9일 확인 기록',
    source: 'CI 42580130871 · ACCOUNT-SWITCH-AND-CHAT.md · 서명 빌드 검증',
    notes: '검증 수치는 최신 제품 커밋 9cd1837 기준입니다. 서버 CI 663개와 프런트 367개, 안드로이드 서명과 설정 51개가 통과했습니다. 실기기에서 확인한 공개 버전은 0.6.7이고, 0.6.8은 Play 제출 후 자동 사전 검사 단계로 기록했습니다. 최신 웹 UI는 배포됐습니다. 일반 카카오 로그인 성공과 저장 왕복은 실제로 확인했습니다. 앞서 한 차례 발생한 간헐적 카카오 인증 실패는 당시 세부 원인을 확보하지 못해 실패 분류와 재시도 안내를 보완했습니다. 근거 docs/build/release-20261109/ACCOUNT-SWITCH-AND-CHAT.md.',
  },
  {
    title: '피드백 반영과 다음 평가 기준', type: 'table', seconds: 35,
    rows: [['받은 피드백', '반영한 결과', '다음 확인'], ['커뮤니티·챗봇에 집중', '게시판·공구 댓글·RAG 연결', '새 질문의 근거·유용성 평가'], ['현재 데이터와 Opik 활용', 'DB 도구 조회·단계별 품질 기록', '독립 평가셋·실패 원인 분석'], ['앱·웹 연동과 쉬운 이용', '계정 전환·팝업 UI·저장 왕복', '댓글·설정의 추가 실기기 확인']],
    widths: [330, 410, 404],
    bottom: '이용 효과 · 질문 해결률·비교 사용률·저장률을 정의하고 측정',
    source: '멘토 피드백 기록 · 통합 요구사항 · 실제 배포·기기 확인',
    notes: '피드백은 기능 변경과 검증 결과로 연결했습니다. 커뮤니티와 챗봇에 집중하라는 의견은 게시판, 공구 댓글, RAG로 반영했습니다. 현재 데이터를 가져오고 Opik으로 분석하라는 의견에는 DB 조회 도구와 단계별 관측을 구현했습니다. 사용성 피드백에는 계정 전환과 팝업 UI를 보완했습니다. 앞으로는 새로운 질문의 근거와 유용성, 댓글과 설정의 기기 왕복, 실제 이용 지표를 확인하겠습니다. 사용자 수나 CTR 개선은 실제 표본을 확보한 뒤 판단합니다. 근거 docs/plans/2026-11-05-community-feedback.md.',
  },
  {
    title: '데이터 활용을 서비스 동작으로 연결했습니다', type: 'closing', seconds: 20,
    lines: ['제공 자료의 품질과 적용 범위를 검토', '비교 기준·공동 저장 분석·CTA에 반영', '공식 근거와 현재 DB를 연결한 RAG 구현', '앱·웹과 평가 기록으로 동작 확인'],
    source: 'Team_Wifi · 이승현 · 최유정 · 최용우',
    notes: '저희는 제공 데이터를 분석하고 그 발견을 비교 기준, 공동 저장 분석, CTA에 연결했습니다. 여기에 공식 출처와 현재 DB를 사용하는 RAG를 구현하고 실제 앱과 웹에서 동작을 확인했습니다. 다음 단계는 새로운 질문과 실제 이용 데이터를 통해 사용자가 정보를 찾고 판단하는 데 얼마나 도움이 되는지 검증하는 것입니다. 감사합니다.',
  },
];

export async function addMain({ presentation, input }) {
  for (let index = input.start; index < input.end; index++) {
    const d = main[index];
    const slide = presentation.slides.add({ width: 1280, height: 720 });
    slide.background.fill = color.bg;
    text(slide, d.title, 64, 43, 1150, 98, d.type === 'cover' ? 60 : 40, true);
    rect(slide, 68, 147, 72, 5, color.red);
    text(slide, d.source, 68, 665, 1115, 38, 15, false, color.muted);
    text(slide, String(index + 1), 1190, 665, 40, 30, 15, false, color.muted);
    slide.speakerNotes.text = `권장 시간 ${d.seconds}초\n\n${d.notes}\n\n출처 ${d.source}`;
    if (d.type === 'cover') {
      text(slide, d.subtitle, 68, 238, 820, 160, 45, true);
      text(slide, '중간평가 발표\nTeam_Wifi  이승현 · 최유정 · 최용우', 68, 490, 850, 100, 27);
      slide.images.add({ path: root + 'artifacts/presentation-20261109/store-icon-512.png', fit: 'contain', position: { left: 960, top: 245, width: 220, height: 220 } });
    } else if (d.type === 'four' || d.type === 'two') {
      d.items.forEach(([heading, body], j) => {
        const x = 72 + j % 2 * 594;
        const y = d.type === 'four' ? 190 + Math.floor(j / 2) * 188 : 190;
        rect(slide, x, y, 3, d.type === 'four' ? 150 : 325, color.red);
        text(slide, heading, x + 22, y, 535, 45, 28, true);
        text(slide, body, x + 22, y + 58, 535, d.type === 'four' ? 100 : 260, 29);
      });
      text(slide, d.bottom, 74, 577, 1120, 74, 23);
    } else if (d.type === 'table') {
      table(slide, d.rows, d.widths, 185, d.rows.length === 5 ? 350 : 320);
      text(slide, d.bottom, 74, 562, 1120, 88, 24);
    } else if (d.type === 'flow') {
      d.steps.forEach((value, j) => {
        const x = 68 + j * 291;
        rect(slide, x, 215, 252, 140);
        text(slide, value, x + 16, 245, 220, 98, 29, true);
        if (j < 3) text(slide, '→', x + 257, 256, 38, 55, 30, false, color.red);
      });
      text(slide, d.bottom, 74, 435, 1120, 150, 29);
    } else if (d.type === 'association') {
      slide.charts.add('bar', { position: { left: 65, top: 195, width: 660, height: 360 }, categories: ['인기순 기준', '연관 규칙'], series: [{ name: '조건부 Recall@5', values: [0.1056, 0.3621], fill: color.red }], hasLegend: false, dataLabels: { showValue: true }, chartFill: 'none', plotAreaFill: 'none' });
      text(slide, '10.56% → 36.21%', 750, 205, 440, 70, 38, true, color.red);
      text(slide, '조건 충족 평가 송장 4,338개\n품목 1개를 숨겨 상위 5개로 복원', 750, 295, 445, 130, 27);
      text(slide, '서비스 적용\n계정별 중복 제거\n공동 저장 5계정 이상 조합 표시', 750, 435, 445, 150, 27);
      text(slide, '과거 거래의 조건부 복원 실험 · 실제 서비스의 이용 효과는 후속 관측', 74, 602, 1120, 50, 22);
    } else if (d.type === 'rag') {
      rect(slide, 68, 200, 220, 150);
      text(slide, '질문\n로그인·권한 확인', 88, 235, 185, 110, 28, true);
      text(slide, '→', 304, 250, 45, 60, 34, false, color.red);
      rect(slide, 370, 188, 375, 130);
      text(slide, '공개 문서 검색\n공식 출처·검토일', 393, 211, 330, 95, 29);
      rect(slide, 370, 350, 375, 130);
      text(slide, '허용된 DB 도구\n공구·본인 저장·설정', 393, 374, 330, 95, 29);
      text(slide, '→', 767, 293, 45, 60, 34, false, color.red);
      rect(slide, 840, 220, 370, 210);
      text(slide, 'Qwen3-1.7B\n근거 선택·답변 구성\n검증 후 출처와 함께 제공', 860, 250, 330, 160, 28, true);
      text(slide, '소형 모델 + 검색·도구로 자원과 최신성 확보\n근거 부족·의료 판단·조회 실패는 보류 또는 오류 안내', 74, 535, 1130, 100, 27);
    } else if (d.type === 'screen') {
      slide.images.add({ path: root + d.image, fit: 'contain', position: { left: 76, top: 175, width: 450, height: 470 } });
      d.lines.forEach((line, j) => text(slide, line, 580, 220 + j * 92, 620, 75, 29, j === 0));
    } else if (d.type === 'sync') {
      slide.images.add({ path: root + 'artifacts/account-switch-20261109/device-saved-confirmed.png', fit: 'contain', position: { left: 85, top: 178, width: 230, height: 430 } });
      slide.images.add({ path: root + 'artifacts/account-switch-20261109/web-after-device-remove.png', fit: 'contain', position: { left: 360, top: 178, width: 360, height: 430 } });
      text(slide, '웹 저장 → 앱 표시\n앱 해제 → 웹 목록 갱신', 770, 220, 435, 150, 33, true);
      text(slide, '같은 카카오 계정\n동일 API·DB 사용\n시험용 저장 원상복구', 770, 420, 435, 155, 28);
      text(slide, '실기기 앱 0.6.7', 95, 615, 260, 32, 20, false, color.muted);
    } else if (d.type === 'closing') {
      d.lines.forEach((line, j) => text(slide, line, 78, 200 + j * 80, 1120, 65, 32, j === 3));
      text(slide, 'moduyuga.yeolmaeapps.kr', 78, 565, 1100, 60, 32, true, color.teal);
    }
  }
  return { count: presentation.slides.items.length };
}

export async function organize({ presentation }) {
  const all = presentation.slides.items;
  if (all.length !== 53) throw new Error('Expected original 38 + new 15 slides');
  const keepIndexes = [5, 6, 12, 13, 16, 17, 18, 20, 24, 25, 26, 30, 31, 32, 33, 34, 35, 36, 37];
  const appendix = keepIndexes.map(i => all[i].id);
  const core = all.slice(38).map(s => s.id);
  presentation.slides.keep([...appendix, ...core]);
  presentation.slides.reorder([...core, ...appendix]);
  for (let i = 15; i < presentation.slides.items.length; i++) {
    const slide = presentation.slides.getItem(i);
    for (const shape of slide.shapes.items) {
      const current = shape.text.toString();
      if (/^\d+$/.test(current)) shape.text = String(i + 1);
      if (current.includes('CI42493377207')) shape.text = current.replaceAll('CI42493377207', 'CI42580130871');
    }
    slide.speakerNotes.text = '질의응답용 부록\n\n' + slide.speakerNotes.text;
  }
  const mappings = [
    [['평가항목', '배점', '본편 근거'], ['산업별 문제 정의', '10', '2장 · 보호자의 비교·근거 확인 문제'], ['산업 구조·데이터 이해', '10', '3~4장 · 중개 역할과 분석 단위'], ['문제 해결 아이디어', '15', '3·7·8장 · 커뮤니티·현재 정보·RAG 연결'], ['실무 적용 가능성', '10', '10~13장 · UI·실기기·DB·출시 검증'], ['AI 선정·적용 적절성', '15', '6·8장 · 모델 비교와 검색·도구 설계']],
    [['평가항목', '배점', '본편 근거'], ['AI 구현·활용 수준', '15', '8~9장 · RAG와 Opik 평가 기록'], ['데이터 활용 기획', '10', '4~8장 · 발견→적용·외부 출처 갱신'], ['데이터 활용 진행', '5', '5·7·11장 · 실험·DB 활용·실기기'], ['발표 구성·전달', '10', '1~15장 · SCQA→분석→구현→검증'], ['합계', '100', '본편 10분 · 상세 자료는 부록']],
  ];
  for (let index = 0; index < mappings.length; index++) {
    const slide = presentation.slides.add({ width: 1280, height: 720 });
    slide.background.fill = color.bg;
    text(slide, `부록 · 평가기준과 발표 근거 ${index + 1}`, 64, 43, 1150, 98, 40, true);
    rect(slide, 68, 147, 72, 5, color.red);
    table(slide, mappings[index], [390, 130, 624], 185, 420);
    text(slide, '2026.11.09 공유 평가표 · 9개 항목 100점', 68, 665, 1100, 38, 16, false, color.muted);
    text(slide, String(presentation.slides.items.length), 1190, 665, 40, 30, 15, false, color.muted);
    slide.speakerNotes.text = '평가표와 장표의 대조. 점수는 심사위원이 판단하며 실제 구현과 검증 조건을 설명한다.';
  }
  await fs.mkdir(artifactDir, { recursive: true });
  const timing = main.map((d, i) => ({ slide: i + 1, title: d.title, seconds: d.seconds }));
  await fs.writeFile(artifactDir + 'timing.json', JSON.stringify({ totalSeconds: timing.reduce((s, d) => s + d.seconds, 0), slides: timing }, null, 2));
  return { total: presentation.slides.items.length, main: 15, appendix: 21, duration: '10 minutes planned' };
}

export async function writeNotes() {
  const body = '# 모두의 육아 10분 발표 대본\n\n본편 15장, 설명 560초와 화면 전환 여유 40초로 총 600초를 계획했다. 실제 리허설 측정 전 기준이며 공식 제한 시간은 미확인이다. 슬라이드 16~36은 질문에 따라 사용하는 부록이다. 각 대본 뒤의 출처·검증 조건은 준비용 참고이며 현장에서 모두 읽을 필요는 없다.\n\n' + main.map((d, i) => `## ${i + 1}. ${d.title} · ${d.seconds}초\n\n${d.notes}\n`).join('\n');
  await fs.writeFile(root + 'docs/reports/presentation-20261109/FINAL-SPEAKER-NOTES.md', body);
}
