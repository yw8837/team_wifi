import { useContentRequest } from "./content-session";
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { categories, safeExternalUrl } from './api';
import { PageTitle, ResourceState, useAuth } from './shared';
import { usePublicResource } from './release-data';
import type { Offer } from './release-data';
import { comparisonChoices } from './discovery';
import type { Preferences } from './discovery';
import { useExposure } from './measurement';
import './advisor.css';

export type Choices = Preferences & { purpose: 'own' | 'gift'; budget_max: number | null };
export type SuggestedItem = Offer & { reason: string; accounts?: number | null };
export type Selection = { choices: Choices; items: SuggestedItem[]; unknown_price_count: number; over_budget_count?: number; focus: string; note: string; has_saved_choices?: boolean };
const initial: Choices = { categories: [], priority: 'none', purpose: 'own', budget_max: null };

export function SuggestedCard({ item, placement }: { item: SuggestedItem; placement: 'advisor' | 'companion' }) {
  const exposure = useExposure(item.id, placement);
  return <article className="suggestion-card" ref={exposure.ref}>
    <p className="eyebrow">{item.category}</p>
    <h3><Link to={'/offers/' + encodeURIComponent(item.id)} onClick={() => void exposure.click('detail')}>{item.title}<span aria-hidden="true"> ↗</span></Link></h3>
    <p>{item.reason}</p><small>{item.source_name} · 공식 참고 목록</small>
  </article>;
}

export function CompanionList({ offerId }: { offerId: string }) {
  const result = usePublicResource<{ items: SuggestedItem[]; basis: 'co_save' | 'category' | 'expired'; minimum_cohort: number }>('/release/offers/' + encodeURIComponent(offerId) + '/companions');
  return <section className="companion-section" aria-label="함께 살펴볼 육아템">
    <h2>함께 살펴볼 육아템</h2>
    <ResourceState {...result} retry={result.reload}/>
    {result.data && !result.loading && !result.error && <>
      <p className="hint">{result.data.basis === 'co_save' ? '같은 계정들이 함께 저장한 목록이에요. 구매 이력이나 세트 할인은 아니에요.' : '공동 저장 근거가 충분하지 않아 같은 분야의 목록을 보여드려요.'}</p>
      {result.data.items?.length ? <div className="suggestion-grid">{result.data.items.map(item => <SuggestedCard key={item.id} item={item} placement="companion"/>)}</div> : <p>아직 함께 안내할 목록이 없어요. <Link to="/advisor">내 조건으로 찾기</Link></p>}
    </>}
  </section>;
}

export function ComparisonCta({ offer }: { offer: Offer }) {
  const { user } = useAuth();
  const preference = usePublicResource<Preferences>(user ? '/release/preferences' : null, user?.id);
  return <ComparisonChoice key={offer.id + (preference.data?.priority || 'none')} offer={offer} priority={preference.data?.priority || 'none'}/>;
}

function ComparisonChoice({ offer, priority }: { offer: Offer; priority: Preferences['priority'] }) {
  const [choice, setChoice] = useState(priority);
  const exposure = useExposure(offer.id, 'compare_cta');
  const source = safeExternalUrl(offer.source_url);
  return <section className="comparison-assist" ref={exposure.ref} aria-labelledby="comparison-assist-title">
    <p className="eyebrow">한 가지씩 비교해요</p><h2 id="comparison-assist-title">지금 가장 궁금한 건 무엇인가요?</h2>
    <fieldset><legend className="sr-only">비교 기준</legend><div className="advisor-options">
      {(['unit_price', 'composition', 'care'] as const).map(value => <label key={value} className={choice === value ? 'selected' : ''}>
        <input type="radio" name="detail-focus" value={value} checked={choice === value} onChange={() => setChoice(value)}/>{comparisonChoices[value].label}
      </label>)}
    </div></fieldset>
    <p aria-live="polite">{comparisonChoices[choice].detail}</p>
    {choice !== 'unit_price' && source && <p className="hint">공식 출처의 외부 사이트를 새 탭으로 엽니다. 제품 사양과 사용·관리 기준은 원문에서 확인하세요.</p>}
    {choice === 'unit_price' ? <Link className="button" to="/calculator" onClick={() => void exposure.click('calculator')}>배송비까지 단가 비교하기</Link> : source && <a className="button" href={source} target="_blank" rel="noopener noreferrer" onClick={() => void exposure.click('source')}>{choice === 'care' ? '공식 사용·관리 안내 확인' : '공식 구성·규격 확인'} ↗</a>}
    <p className="hint">직접 선택한 기준에 맞춰 안내해요. 현재 화면의 선택은 관심 설정을 바꾸지 않아요.</p>
  </section>;
}

export function AdvisorPage() {
  const { user } = useAuth();
  return <AdvisorSession key={user?.id || 'guest'} signedIn={!!user} sessionKey={user?.id || ''}/>;
}

function AdvisorSession({ signedIn, sessionKey }: { signedIn: boolean; sessionKey: string }) {
  const stored = usePublicResource<Selection>(signedIn ? '/release/advisor' : null, sessionKey);
  return <div className="advisor-page"><Link to="/offers">← 육아템 정보</Link>
    <PageTitle eyebrow="우리에게 맞는 선택" title="어떤 육아템을 찾고 있나요?"><p>필요한 분야와 비교 기준을 고르면 공식 정보를 좁혀드려요.</p></PageTitle>
    {signedIn && <ResourceState {...stored} retry={stored.reload}/>}
    {(!signedIn || (!stored.loading && !stored.error && stored.data)) && <AdvisorForm signedIn={signedIn} saved={stored.data}/>}
  </div>;
}

export function AdvisorForm({ signedIn, saved }: { signedIn: boolean; saved: Selection | null }) {
  const request = useContentRequest(), lock = useRef(false);
  const [choices, setChoices] = useState<Choices>(saved?.choices || initial);
  const [budget, setBudget] = useState(saved?.choices.budget_max?.toString() || '');
  const [result, setResult] = useState<Selection | null>(saved?.has_saved_choices ? saved : null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const live = useRef(true), output = useRef<HTMLElement>(null);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  const change = (patch: Partial<Choices>) => { setChoices(c => ({ ...c, ...patch })); setResult(null); setError(''); setMessage(''); };
  const submit = async () => {
    if (lock.current) return;
    const amount = budget.trim() ? Number(budget) : null;
    if (amount !== null && (!Number.isSafeInteger(amount) || amount < 0 || amount > 10000000)) { setError('예산은 0~10,000,000원의 정수로 적어주세요.'); return; }
    lock.current = true; setBusy(true); setError(''); setMessage('');
    try {
      const response = await request<Selection>(signedIn ? '/release/advisor' : '/release/advisor/preview', signedIn ? 'PUT' : 'POST', { ...choices, budget_max: amount });
      if (live.current) { setResult(response); setMessage(signedIn ? '같은 계정의 앱·웹에서 이 조건을 이어서 볼 수 있어요.' : '이 조건은 계정에 저장하지 않았어요.'); requestAnimationFrame(() => { if (live.current) output.current?.focus(); }); }
    } catch (e) { if (live.current) setError(e instanceof Error ? e.message : '조건을 확인하지 못했어요. 다시 시도해주세요.'); }
    finally { lock.current = false; if (live.current) setBusy(false); }
  };
  const clear = async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      if (signedIn) await request('/release/advisor', 'DELETE');
      if (live.current) { setChoices(initial); setBudget(''); setResult(null); setMessage('조건 찾기를 끝냈어요. 저장한 조건도 지웠어요.'); }
    } catch (e) { if (live.current) setError(e instanceof Error ? e.message : '지우지 못했어요. 다시 시도해주세요.'); }
    finally { lock.current = false; if (live.current) setBusy(false); }
  };
  return <>
    <form onSubmit={e => { e.preventDefault(); void submit(); }} className="advisor-form">
      <fieldset disabled={busy}><legend><span className="step-number">1</span> 누구를 위한 선택인가요?</legend>
        <div className="advisor-options">{([['own', '우리 집에서 쓸 거예요'], ['gift', '선물할 거예요']] as const).map(([value, label]) => <label key={value} className={choices.purpose === value ? 'selected' : ''}><input type="radio" name="purpose" checked={choices.purpose === value} onChange={() => change({ purpose: value })}/>{label}</label>)}</div>
      </fieldset>
      <fieldset disabled={busy}><legend><span className="step-number">2</span> 어떤 분야가 필요한가요?</legend><p className="hint">최대 3개 · 고르지 않으면 전체 분야를 살펴봐요.</p>
        <div className="advisor-options">{categories.map(category => <label key={category} className={choices.categories.includes(category) ? 'selected' : ''}><input type="checkbox" checked={choices.categories.includes(category)} disabled={!choices.categories.includes(category) && choices.categories.length >= 3} onChange={e => change({ categories: e.target.checked ? [...choices.categories, category] : choices.categories.filter(c => c !== category) })}/>{category}</label>)}</div>
      </fieldset>
      <fieldset disabled={busy}><legend><span className="step-number">3</span> 무엇부터 비교할까요?</legend>
        <div className="advisor-options">{Object.entries(comparisonChoices).map(([value, description]) => <label key={value} className={choices.priority === value ? 'selected' : ''}><input type="radio" name="priority" checked={choices.priority === value} onChange={() => change({ priority: value as Choices['priority'] })}/>{description.label}</label>)}</div>
        <label className="field budget-field"><span>배송비 포함 예산 상한 (선택)</span><input type="number" inputMode="numeric" min="0" max="10000000" step="1" value={budget} placeholder="제한 없음" onChange={e => { setBudget(e.target.value); setResult(null); setError(''); setMessage(''); }}/></label>
        <p className="hint">가격이나 배송비가 확인되지 않은 목록은 예산 결과에서 제외해요.</p>
      </fieldset>
      <div className="actions"><button disabled={busy} type="submit">{busy ? '확인 중…' : signedIn ? '조건 저장하고 찾기' : '이 조건으로 찾기'}</button><button type="button" className="secondary" disabled={busy} onClick={() => void clear()}>끝내고 조건 지우기</button></div>
      {!signedIn && <p className="hint">로그인 없이 찾을 수 있어요. <Link to="/login?returnTo=%2Fadvisor">로그인하면 앱·웹에서 조건을 이어서 사용해요.</Link></p>}
      {error && <p role="alert" className="error">{error}</p>}{message && <p role="status">{message}</p>}
    </form>
    {result && <SelectionResults result={result} outputRef={output}/>}
  </>;
}

export function SelectionResults({ result, outputRef }: { result: Selection; outputRef?: React.RefObject<HTMLElement | null> }) {
  return <section className="advisor-results" ref={outputRef} tabIndex={-1} aria-labelledby="advisor-result-title">
    <p className="eyebrow">선택한 조건의 결과</p><h2 id="advisor-result-title">{result.items.length ? '이 목록부터 살펴보세요' : '지금 확인할 수 있는 목록이 없어요'}</h2><p className="comparison-focus">{result.focus}</p>
    {(result.over_budget_count ?? 0) > 0 && <p>배송비 포함 예산 상한을 넘는 육아템 {result.over_budget_count}개는 제외했어요. 예산을 높이거나 비우면 다시 살펴볼 수 있어요.</p>}
    {result.unknown_price_count > 0 && <p>가격·배송비 미확인 목록 {result.unknown_price_count}개는 예산에 맞는지 판단할 수 없어 제외했어요. 예산을 비우면 공식 정보를 살펴볼 수 있어요.</p>}
    <div className="suggestion-grid">{result.items.map(item => <SuggestedCard key={item.id} item={item} placement="advisor"/>)}</div>
    <p className="hint">{result.note}</p><Link to="/calculator">가격을 확인했다면 단가 비교하기 →</Link>
  </section>;
}
