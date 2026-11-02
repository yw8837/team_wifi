import { MeasurementReport, useExposure } from "./measurement";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, categories, safeExternalUrl } from "./api";
import { CategoryIcon } from "./brand";
import { Feedback, PageTitle, ResourceState, useAction, useAuth } from "./shared";
import { usePublicResource } from "./release-data";
import type { Offer } from "./release-data";

export type Preferences = { categories: string[]; priority: "none" | "unit_price" | "composition" | "care" };
export const comparisonChoices: Record<Preferences["priority"], { label: string; detail: string }> = {
  none: { label: "골고루 살펴보기", detail: "특정 기준을 먼저 두지 않아요" },
  unit_price: { label: "가격과 수량", detail: "배송비를 포함한 단가가 궁금해요" },
  composition: { label: "구성과 규격", detail: "용량·구성품·호환 조건을 비교해요" },
  care: { label: "사용과 관리", detail: "사용 조건·관리법·교환 안내를 살펴봐요" },
};
export type Recommendations = { items: (Offer & { reasons: string[] })[]; focus: string; priority: Preferences["priority"]; basis: string };

export function PersonalDiscovery() {
  const { user } = useAuth();
  const result = usePublicResource<Recommendations>(user ? "/release/recommendations" : null, user?.id);
  if (!user) return <aside className="discovery-intro"><div><strong>우리 집에 필요한 육아템부터</strong><p>관심 분야를 고르면 다음에도 이어서 살펴볼 수 있어요.</p></div><Link to="/my/preferences">관심 육아템 고르기 →</Link></aside>;
  return <section className="personal-discovery" aria-labelledby="personal-discovery-title">
    <div className="discovery-heading"><h2 id="personal-discovery-title">내 관심 육아템</h2><Link to="/my/preferences">관심 설정</Link></div>
    <ResourceState {...result} retry={result.reload}/>
    {result.data && !result.error && !result.loading && <>
      <p>{result.data.basis === "preferences" ? "직접 고른 관심 분야에서 아직 저장하지 않은 육아템을 먼저 보여드려요." : result.data.basis === "saved" ? "내가 저장한 육아템과 같은 분야를 모았어요." : "관심 분야를 최대 3개 골라 보세요. 설정은 같은 계정의 앱과 웹에서 함께 사용해요."}</p>
      {result.data.items.length ? <div className="discovery-grid">{result.data.items.map(item => <MeasuredRecommendation key={item.id} item={item}/>)}</div> : <Link className="button secondary" to="/my/preferences">관심 분야 설정하기</Link>}
      {result.data.priority !== "none" && <p className="comparison-focus"><strong>{comparisonChoices[result.data.priority].label}</strong> · {result.data.focus} {result.data.priority === "unit_price" && <Link to="/calculator">단가 비교하기 →</Link>}</p>}
      <small className="muted">내 관심 설정과 저장 기록을 기준으로 보여드려요. 판매 순위나 최저가 추천은 아니에요.</small>
    </>}
  </section>;
}

export function PreferenceForm({ initial }: { initial: Preferences }) {
  const [value, setValue] = useState(initial);
  const action = useAction();
  const toggle = (category: string) => setValue(v => ({ ...v, categories: v.categories.includes(category) ? v.categories.filter(c => c !== category) : [...v.categories, category].slice(0, 3) }));
  return <form className="preference-form" onSubmit={e => { e.preventDefault(); void action.run(async () => { setValue(await api<Preferences>("/release/preferences", "PUT", value)); }, "관심 설정을 저장했어요. 같은 계정의 앱과 웹에 적용됩니다."); }}>
    <fieldset disabled={action.busy}><legend>어떤 육아템을 살펴볼까요?</legend><p id="category-help">최대 3개 · 선택하지 않아도 전체 목록을 볼 수 있어요.</p>
      <div className="preference-options">{categories.map(category => <label className={value.categories.includes(category) ? "preference-option selected" : "preference-option"} key={category}>
        <input type="checkbox" aria-describedby="category-help" checked={value.categories.includes(category)} disabled={!value.categories.includes(category) && value.categories.length >= 3} onChange={() => toggle(category)}/><CategoryIcon category={category} size={23}/><span>{category}</span>
      </label>)}</div>
    </fieldset>
    <fieldset disabled={action.busy}><legend>비교할 때 무엇을 먼저 볼까요?</legend><div className="preference-options">{Object.entries(comparisonChoices).map(([key, choice]) => <label className={value.priority === key ? "preference-option selected" : "preference-option"} key={key}>
      <input type="radio" name="comparison-priority" value={key} checked={value.priority === key} onChange={() => setValue(v => ({ ...v, priority: key as Preferences["priority"] }))}/><span><strong>{choice.label}</strong><small>{choice.detail}</small></span>
    </label>)}</div></fieldset>
    <p className="hint">선택은 이 계정에만 저장돼요. 언제든 수정하거나 지울 수 있으며 아이의 개인정보는 입력하지 않아요.</p>
    <Feedback {...action}/><div className="actions"><button type="submit" disabled={action.busy}>{action.busy ? "처리 중…" : "관심 설정 저장"}</button><button type="button" className="secondary" disabled={action.busy} onClick={() => void action.run(async () => { setValue(await api<Preferences>("/release/preferences", "DELETE")); }, "관심 설정을 지웠어요. 저장한 육아템은 그대로예요.")}>설정 지우기</button></div>
    <p><Link to="/">육아템 목록에서 확인하기 →</Link></p>
  </form>;
}

export function PreferencePage() {
  const { user } = useAuth();
  const result = usePublicResource<Preferences>("/release/preferences", user?.id);
  return <section className="preference-page"><Link to="/my">← 마이페이지</Link><PageTitle eyebrow="나에게 맞게" title="관심 육아템 설정"><p>필요한 분야와 비교 기준을 직접 골라 주세요.</p></PageTitle><ResourceState {...result} retry={result.reload}/>{result.data && !result.loading && !result.error && <PreferenceForm key={user?.id} initial={result.data}/>}</section>;
}

type Evidence = {
  d1: { rows: number; baby_rows: number; discount_sensitivity: Record<string, number>; application: string; limitation: string };
  d2: { rows: number; matched_rows: number; application: string };
  d3: { rows: number; application: string; limitation: string };
  d4: { rows: number; purchased_sessions: number; selected_model: string; test_auroc: number; test_average_precision: number; application: string; limitation: string };
  sources: { id: string; name: string; url: string; rows: number }[];
};
export type Insights = { minimum_cohort: number; saved_accounts: number | null; note: string;
  categories: { category: string; saved_accounts: number | null; demand_authors: number | null; interested_accounts: number | null }[];
  pairs: { first: string; second: string; accounts: number; support: number; first_to_second: number; second_to_first: number }[];
  evidence: Evidence;
};
const countLabel = (n: number | null) => n === null ? "5명 미만 · 비공개" : n.toLocaleString() + "명";
const percent = (n: number) => (n * 100).toFixed(1) + "%";

export function InsightsView({ data }: { data: Insights }) {
  const e = data.evidence;
  return <>
    <section className="panel"><h2>어떤 분야에 관심이 모였나요?</h2><p>{data.note}</p><p>현재 육아템을 저장한 계정: <strong>{countLabel(data.saved_accounts)}</strong></p>
      <div className="insight-categories">{data.categories.map(c => <article key={c.category}><h3>{c.category}</h3><dl><dt>저장한 계정</dt><dd>{countLabel(c.saved_accounts)}</dd><dt>수요 글 작성자</dt><dd>{countLabel(c.demand_authors)}</dd><dt>수요에 관심 표시</dt><dd>{countLabel(c.interested_accounts)}</dd></dl></article>)}</div>
      <p className="hint">각 항목은 서로 다른 계정 수이며 더해서 전체 이용자 수로 계산하지 않습니다. 삭제·정지 계정과 숨긴 수요 글은 제외합니다.</p>
    </section>
    <section className="panel"><h2>함께 저장한 육아템</h2><p>함께 비교할 구성이나 공구 조사 주제를 정하는 데 참고하세요. 결제·동시구매 기록은 아닙니다.</p>
      {data.pairs.length ? data.pairs.map(pair => <article className="insight-pair" key={pair.first + pair.second}><h3>{pair.first} + {pair.second}</h3><p>함께 저장 {pair.accounts}명 · 저장 계정 중 {percent(pair.support)}</p><p>{pair.first} 저장자 중 {percent(pair.first_to_second)}가 {pair.second}도 저장 · 반대 방향 {percent(pair.second_to_first)}</p></article>) : <p className="state">최소 {data.minimum_cohort}계정이 함께 저장한 조합이 아직 없어요. 자료가 모이면 여기에 표시됩니다.</p>}
    </section>
    <details className="analysis-evidence"><summary>제공 데이터 분석과 적용 근거</summary>
      <article><h3>D1 · 구매 성향에 맞춘 비교 기준</h3><p>{e.d1.rows.toLocaleString()}명 중 할인에 매우 민감 {e.d1.discount_sensitivity["Very Sensitive"]}명, 어느 정도 민감 {e.d1.discount_sensitivity["Somewhat Sensitive"]}명, 민감하지 않음 {e.d1.discount_sensitivity["Not Sensitive"]}명. 육아용품 분류는 {e.d1.baby_rows}명입니다.</p><p>{e.d1.application}</p><p className="hint">{e.d1.limitation}</p></article>
      <article><h3>D2 · 중복을 제외한 집계</h3><p>{e.d2.rows.toLocaleString()}행 중 {e.d2.matched_rows.toLocaleString()}행이 D3와 겹칩니다.</p><p>{e.d2.application}</p></article>
      <article><h3>D3 · 함께 관심받는 품목 분석</h3><p>과거 소매 거래 {e.d3.rows.toLocaleString()}행에서 검토한 동시구매 집계 방식입니다.</p><p>{e.d3.application}</p><p className="hint">{e.d3.limitation}</p></article>
      <article><h3>D4 · 비교 도움을 주는 시점</h3><p>{e.d4.rows.toLocaleString()}개 완료 세션 중 구매 {e.d4.purchased_sessions.toLocaleString()}개. 보존 모델 {e.d4.selected_model}의 테스트 AUROC {e.d4.test_auroc.toFixed(3)}, AP {e.d4.test_average_precision.toFixed(3)}.</p><p>{e.d4.application}</p><p className="hint">{e.d4.limitation}</p></article>
      <ul>{e.sources.map(source => <li key={source.id}>{safeExternalUrl(source.url) && <a href={source.url} target="_blank" rel="noopener noreferrer">{source.id} · {source.name} ↗</a>}</li>)}</ul>
    </details>
  </>;
}

export function ServiceInsights() {
  const { user } = useAuth();
  const result = usePublicResource<Insights>("/release/admin/insights", user?.id);
  return <section><Link to="/my">← 마이페이지</Link><PageTitle eyebrow="운영자 전용" title="육아템 관심 분석"><p>실제 서비스 활동으로 다음 조사·공구 준비의 우선순위를 정하세요.</p></PageTitle><ResourceState {...result} retry={result.reload}/>{result.data && !result.loading && !result.error && <InsightsView data={result.data}/>}<button className="secondary" disabled={result.loading} onClick={result.reload}>최신 활동으로 새로고침</button><MeasurementReport/></section>;
}

function MeasuredRecommendation({item}:{item:Recommendations["items"][number]}) {
 const exposure=useExposure(item.id,"personal");
 return <div ref={exposure.ref as React.RefObject<HTMLDivElement>}><Link className="discovery-card" onClick={()=>void exposure.click("detail")} to={"/offers/"+encodeURIComponent(item.id)}><CategoryIcon category={item.category} size={26}/><small>{item.category}</small><strong>{item.title}</strong><span>{item.reasons.join(" · ")}{item.saved?" · 저장함":""}</span></Link></div>;
}
