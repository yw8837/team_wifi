import type { ReactNode } from "react";
import { date, safeExternalUrl } from "./api";
import { ResourceState, useResource } from "./shared";

type Metrics = {
  auroc?: number;
  pr_auc_average_precision?: number;
  brier?: number;
  ece_10bins?: number;
};
export type ResearchSummary = {
  generated_at?: string;
  source_check_date?: string;
  sources?: {
    id: string;
    name: string;
    url: string;
    rows: number;
    cols: number;
    period: string;
    grain: string;
    license: string;
    note: string;
  }[];
  materials?: {
    files_inventoried: number;
    requirements_read: number;
    company_documents_read: number;
  };
  d1?: {
    rows: number;
    columns: number;
    categories: { category: string; customers: number }[];
    application: string;
    limitations: string[];
  };
  retail?: {
    audit?: {
      d2_rows: number;
      d3_rows: number;
      matched_rows: number;
      d2_only_rows: number;
      d3_second_sheet_rows: number;
      d3_second_sheet_only_rows: number;
      d2_duplicate_business_rows: number;
      d3_duplicate_business_rows: number;
    };
    eligible_product_rows?: number;
    invoices?: number;
    products?: number;
    bundle_rule_count?: number;
    bundle_evaluation?: {
      train_invoices: number;
      test_invoices: number;
      eligible_test_baskets: number;
      train_last: string;
      test_first: string;
      rules_recall_at_5: number;
      popularity_recall_at_5: number;
      rules_mrr_at_5: number;
      popularity_mrr_at_5: number;
      limitations: string[];
    };
    limitations?: string[];
  };
  intent?: {
    rows: number;
    positive_labels: number;
    label_prevalence: number;
    duplicate_full_rows: number;
    duplicate_selected_feature_rows: number;
    feature_group_overlap: number;
    selected_model: string;
    features: string[];
    excluded_features: string[];
    splits: Record<
      string,
      { rows: number; positive_labels: number; prevalence: number }
    >;
    models: Record<string, { validation?: Metrics; test?: Metrics }>;
    limitations: string[];
    split_method: string;
    calibration: string;
  };
};
type Bundle = {
  antecedent: string;
  consequent: string;
  antecedent_name: string;
  consequent_name: string;
  joint_invoices: number;
  total_invoices: number;
  support: number;
  confidence: number;
  lift: number;
  source: string;
  source_url: string;
  limitation: string;
};
const number = (value: number | undefined) =>
  value === undefined ? "미제공" : new Intl.NumberFormat("ko-KR").format(value);
const decimal = (value: number | undefined) =>
  value === undefined ? "미제공" : value.toFixed(4);
const percent = (value: number | undefined) =>
  value === undefined
    ? "미제공"
    : new Intl.NumberFormat("ko-KR", {
        style: "percent",
        maximumFractionDigits: 2,
      }).format(value);
const modelName = (name: string) =>
  ({
    dummy_prevalence: "구매 비율 기준선",
    logistic_regression: "로지스틱 회귀",
    lightgbm: "LightGBM",
  })[name] || name;
function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note?: string;
}) {
  return (
    <div className="research-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
function Table({
  caption,
  headings,
  rows,
}: {
  caption: string;
  headings: string[];
  rows: ReactNode[][];
}) {
  return (
    <div
      className="research-table-wrap"
      tabIndex={0}
      role="region"
      aria-label={caption}
    >
      <table className="research-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {headings.map((h) => (
              <th scope="col" key={h}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) =>
                j === 0 ? (
                  <th scope="row" key={j}>
                    {cell}
                  </th>
                ) : (
                  <td key={j}>{cell}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Limits({ items }: { items?: string[] }) {
  return items?.length ? (
    <ul className="research-limits">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  ) : null;
}
export function ResearchEvidence({ summary }: { summary: ResearchSummary }) {
  const d1 = summary.d1,
    retail = summary.retail,
    audit = retail?.audit,
    evaluation = retail?.bundle_evaluation,
    intent = summary.intent;
  return (
    <div className="research-evidence">
      <p className="muted">
        자료 확인 기준 {summary.source_check_date || "미제공"}
        {summary.generated_at && <> · 분석 생성 {date(summary.generated_at)}</>}
      </p>
      <div className="notice">
        <strong>과거 공개 데이터의 실험 결과</strong>
        <p>
          실제 모두의육아 고객 데이터·국내 육아 시장 조사·현재 상품 추천 성능과
          구분해서 읽어주세요. 개인별 원자료를 앱 고객과 연결하지 않습니다.
        </p>
      </div>
      {summary.materials && (
        <p className="muted">
          자료 목록 {number(summary.materials.files_inventoried)}개 · 요구사항
          확인 {number(summary.materials.requirements_read)}개 · 회사 자료 확인{" "}
          {number(summary.materials.company_documents_read)}개. 원문별 범위는
          아래 출처와 원본 요약에서 확인할 수 있습니다.
        </p>
      )}
      {d1 && (
        <section className="research-section">
          <h3>D1 · 소비자 성향 데이터</h3>
          <div className="research-stats">
            <Stat
              label="분석 행 수"
              value={number(d1.rows)}
              note="고객 1명당 1행"
            />
            <Stat label="컬럼 수" value={number(d1.columns)} />
            <Stat
              label="Baby Products 범주"
              value={number(
                d1.categories?.find((c) => c.category === "Baby Products")
                  ?.customers,
              )}
              note="원자료의 범주명 그대로 표시"
            />
          </div>
          <p>{d1.application}</p>
          <details>
            <summary>전체 카테고리와 고객 수</summary>
            <Table
              caption="D1 카테고리별 고객 수"
              headings={["원자료 카테고리", "고객 수"]}
              rows={(d1.categories || []).map((c) => [
                c.category,
                number(c.customers),
              ])}
            />
          </details>
          <Limits items={d1.limitations} />
        </section>
      )}
      {audit && (
        <section className="research-section">
          <h3>D2–D3 · 원자료 중복 확인</h3>
          <div className="research-stats">
            <Stat label="D2 전체 행" value={number(audit.d2_rows)} />
            <Stat label="D3 전체 행" value={number(audit.d3_rows)} />
            <Stat
              label="D2 ↔ D3 일치 행"
              value={number(audit.matched_rows)}
              note="8개 공통 컬럼의 실제 행·중복 횟수 대조"
            />
          </div>
          <Table
            caption="D2와 D3 두 번째 시트의 중복 대조"
            headings={["확인 항목", "행 수"]}
            rows={[
              ["D2에만 있는 행", number(audit.d2_only_rows)],
              ["D3 두 번째 시트 전체", number(audit.d3_second_sheet_rows)],
              [
                "D3 두 번째 시트에만 있는 행",
                number(audit.d3_second_sheet_only_rows),
              ],
              [
                "D2 내부 중복 업무 행",
                number(audit.d2_duplicate_business_rows),
              ],
              [
                "D3 내부 중복 업무 행",
                number(audit.d3_duplicate_business_rows),
              ],
            ]}
          />
          <p className="notice">
            D2를 D3에 더하지 않았습니다. 동일 거래를 추가 데이터로 중복 계산하지
            않고 D3를 주 분석 데이터로 사용합니다.
          </p>
          <p className="muted">
            정제 후 상품 행 {number(retail?.eligible_product_rows)} · 송장{" "}
            {number(retail?.invoices)} · 상품 {number(retail?.products)}
          </p>
          <Limits items={retail?.limitations} />
        </section>
      )}
      {evaluation && (
        <section className="research-section">
          <h3>D3 · 묶음 규칙과 인기 기준선 비교</h3>
          <p>
            시간순으로 나눈 과거 영국 송장에서 일부 상품을 가린 뒤, 남은
            장바구니로 가린 상품을 상위 5개 안에 찾는 실험입니다.
          </p>
          <Table
            caption="동일 평가 장바구니에서의 번들 규칙 대 인기상품"
            headings={["방법", "Recall@5 ↑", "MRR@5 ↑"]}
            rows={[
              [
                "동시구매 번들 규칙",
                percent(evaluation.rules_recall_at_5),
                decimal(evaluation.rules_mrr_at_5),
              ],
              [
                "학습기간 인기상품",
                percent(evaluation.popularity_recall_at_5),
                decimal(evaluation.popularity_mrr_at_5),
              ],
            ]}
          />
          <p className="hint">
            Recall@5는 가린 정답을 5개 제안 안에서 찾은 비율, MRR@5는 찾은
            순위의 역수를 평균한 값입니다.
          </p>
          <div className="research-stats">
            <Stat label="학습 송장" value={number(evaluation.train_invoices)} />
            <Stat
              label="테스트 송장"
              value={number(evaluation.test_invoices)}
            />
            <Stat
              label="평가 가능한 장바구니"
              value={number(evaluation.eligible_test_baskets)}
            />
            <Stat
              label="생성된 규칙"
              value={number(retail?.bundle_rule_count)}
            />
          </div>
          <p className="muted">
            학습 마지막 {evaluation.train_last} / 테스트 시작{" "}
            {evaluation.test_first} (원자료 시간 표기)
          </p>
          <p className="notice">
            학습 상위 100개 상품 중 최소 2개를 담은 장바구니에 한정합니다. 다음
            주문·신규 고객·한국 육아상품 추천 성능은 검증하지 않았습니다.
          </p>
          <Limits items={evaluation.limitations} />
          <BundleExamples />
        </section>
      )}
      {intent && (
        <section className="research-section">
          <h3>D4 · 완료 세션 구매 여부 분류</h3>
          <div className="research-stats">
            <Stat label="전체 세션" value={number(intent.rows)} />
            <Stat
              label="구매 발생 세션"
              value={number(intent.positive_labels)}
              note={`전체의 ${percent(intent.label_prevalence)}`}
            />
            <Stat
              label="검증셋으로 선택한 모델"
              value={modelName(intent.selected_model)}
            />
            <Stat
              label="분할 간 동일 특성 그룹"
              value={number(intent.feature_group_overlap)}
              note="같은 입력 그룹이 분할을 넘지 않도록 구성"
            />
          </div>
          <Table
            caption="D4 데이터 분할"
            headings={["분할", "세션 수", "구매 발생", "구매 비율"]}
            rows={Object.entries(intent.splits || {}).map(([key, v]) => [
              (
                { train: "학습", validation: "검증", test: "테스트" } as Record<
                  string,
                  string
                >
              )[key] || key,
              number(v.rows),
              number(v.positive_labels),
              percent(v.prevalence),
            ])}
          />
          <Table
            caption="모델별 검증·테스트 지표"
            headings={[
              "모델",
              "검증 AP ↑",
              "테스트 AUROC ↑",
              "테스트 AP ↑",
              "테스트 Brier ↓",
              "테스트 ECE ↓",
            ]}
            rows={Object.entries(intent.models || {}).map(([key, v]) => [
              <>
                {modelName(key)}
                {key === intent.selected_model && (
                  <span className="badge">선택</span>
                )}
              </>,
              decimal(v.validation?.pr_auc_average_precision),
              decimal(v.test?.auroc),
              decimal(v.test?.pr_auc_average_precision),
              decimal(v.test?.brier),
              decimal(v.test?.ece_10bins),
            ])}
          />
          <p className="hint">
            AP는 불균형 데이터의 구매 세션 탐지 지표입니다. AUROC·AP는 높을수록,
            확률 오차 Brier·ECE는 낮을수록 좋습니다. 모델 선택은 검증 AP로만
            했으며 테스트 AP에서는 로지스틱 회귀가 더 높을 수 있습니다.
          </p>
          <p>
            전체 행 중복 {number(intent.duplicate_full_rows)}개 · 선택 입력 특성
            중복 {number(intent.duplicate_selected_feature_rows)}개. 동일 입력
            특성 그룹으로 분할하여 중복 누출을 줄였습니다. 시계열 외부 검증은
            아닙니다.
          </p>
          <p className="muted">
            입력 {intent.features?.join(", ")}
            <br />
            제외 {intent.excluded_features?.join(", ")}
          </p>
          <p className="notice">
            사후 확률 보정은 적용하지 않았습니다. 완료된 과거 세션의 구매 여부
            분류이며 현재 방문자의 이탈 위험이나 국내 육아 구매 확률로 해석할 수
            없습니다.
          </p>
          <Limits items={intent.limitations} />
        </section>
      )}
      {!!summary.sources?.length && (
        <details>
          <summary>데이터 원문·라이선스·기간 확인</summary>
          {summary.sources.map((source) => {
            const url = safeExternalUrl(source.url);
            return (
              <article className="research-source" key={source.id}>
                <h4>
                  {source.id} · {source.name}
                </h4>
                <p>
                  {number(source.rows)}행 × {number(source.cols)}열 ·{" "}
                  {source.grain}
                  <br />
                  {source.period}
                  <br />
                  라이선스: {source.license}
                </p>
                <p>{source.note}</p>
                {url && (
                  <a href={url} target="_blank" rel="noopener noreferrer">
                    데이터 원문 ↗
                  </a>
                )}
              </article>
            );
          })}
        </details>
      )}
      <details>
        <summary>검증용 원본 요약 JSON</summary>
        <pre className="research-json">{JSON.stringify(summary, null, 2)}</pre>
      </details>
    </div>
  );
}
function BundleExamples() {
  const result = useResource<{ items: Bundle[] }>("/research/bundles");
  return (
    <section>
      <h4>원상품 코드로 보는 번들 예시</h4>
      <p className="muted">
        원 StockCode와 영문 상품명을 유지했습니다. 영국 선물용품의 규칙이며
        모두의육아 상품과 매칭하거나 구매 링크로 연결하지 않습니다.
      </p>
      <ResourceState
        {...result}
        retry={result.reload}
        empty={result.data?.items.length === 0}
      />
      {!result.loading && !result.error && result.data?.items && (
        <div className="research-bundles">
          {result.data.items.map((item, i) => (
            <article
              className="research-bundle"
              key={`${item.antecedent}:${item.consequent}:${i}`}
            >
              <h5>함께 구매된 원상품 {i + 1}</h5>
              <p>
                <code>StockCode {item.antecedent}</code>
                <br />
                {item.antecedent_name}
              </p>
              <span aria-hidden="true">↓</span>
              <p>
                <code>StockCode {item.consequent}</code>
                <br />
                {item.consequent_name}
              </p>
              <dl>
                <div>
                  <dt>동시 구매 송장</dt>
                  <dd>
                    {number(item.joint_invoices)} /{" "}
                    {number(item.total_invoices)}
                  </dd>
                </div>
                <div>
                  <dt>Support</dt>
                  <dd>{percent(item.support)}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{percent(item.confidence)}</dd>
                </div>
                <div>
                  <dt>Lift</dt>
                  <dd>{decimal(item.lift)}</dd>
                </div>
              </dl>
              <p className="hint">{item.limitation}</p>
              {safeExternalUrl(item.source_url) && (
                <a
                  href={safeExternalUrl(item.source_url)!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  원자료 확인 ↗
                </a>
              )}
            </article>
          ))}
        </div>
      )}
      <p className="hint">
        Support: 전체 송장 중 두 상품을 함께 산 비율 · Confidence: 앞 상품이
        있을 때 뒤 상품도 있는 비율 · Lift: 독립 구매를 가정했을 때 대비 동시
        구매의 비율입니다. 인과·할인 효과가 아닙니다.
      </p>
    </section>
  );
}
