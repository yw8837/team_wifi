import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Capacitor } from '@capacitor/core';
import { api } from './api';
import { Feedback, ResourceState, useAction, useAuth } from './shared';
import { usePublicResource } from './release-data';

const Measurement = createContext({ enabled: false, eligible: true, reload: () => {} });
export function MeasurementProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth(), [version, setVersion] = useState(0);
  const [choice, setChoice] = useState({ enabled: false, eligible: true, userId: '' });
  const reload = useCallback(() => setVersion(n => n + 1), []);
  useEffect(() => {
    let alive = true;
    setChoice({ enabled: false, eligible: !user?.is_admin, userId: '' });
    if (user) void api<{enabled: boolean; eligible: boolean}>('/release/measurement/consent').then(result => {
      if (alive) setChoice({ ...result, userId: user.id });
    }).catch(() => {});
    return () => { alive = false; };
  }, [user?.id, version]);
  return <Measurement.Provider value={{ enabled: !!user && choice.userId === user.id && choice.enabled, eligible: choice.eligible, reload }}>{children}</Measurement.Provider>;
}
type Placement = 'catalog' | 'personal' | 'detail' | 'demand_list' | 'demand_detail';
type Action = 'detail' | 'source' | 'calculator' | 'save' | 'interest';
export function useExposure(offerId: string | undefined, placement: Placement) {
  const { enabled } = useContext(Measurement), ref = useRef<HTMLElement | null>(null);
  const viewed = useRef<Promise<boolean> | null>(null), clicked = useRef(new Set<string>());
  const channel = Capacitor.isNativePlatform() ? 'android' : 'web';
  const send = useCallback(async (action: Action | 'view') => {
    if (!enabled || !offerId) return false;
    try { return (await api<{recorded: boolean}>('/release/measurement/events', 'POST', {
      ...(placement.startsWith('demand_') ? {demand_id: offerId} : {offer_id: offerId}), placement, channel, action, visible_ms: action === 'view' ? 1000 : 0,
    })).recorded; } catch { return false; } // Optional measurement must never break the feature.
  }, [enabled, offerId, placement, channel]);
  useEffect(() => {
    viewed.current = null; clicked.current.clear();
    if (!enabled || !offerId || !ref.current || !('IntersectionObserver' in window)) return;
    let timer: ReturnType<typeof setTimeout> | undefined, visible = false;
    const cancel = () => { if (timer) clearTimeout(timer); timer = undefined; };
    const schedule = () => {
      cancel();
      if (visible && document.visibilityState === 'visible' && !viewed.current) timer = setTimeout(() => { viewed.current = send('view'); }, 1000);
    };
    const observer = new IntersectionObserver(entries => { visible = entries.some(e => e.isIntersecting && e.intersectionRatio >= .5); schedule(); }, { threshold: [.5] });
    observer.observe(ref.current);
    document.addEventListener('visibilitychange', schedule);
    return () => { cancel(); observer.disconnect(); document.removeEventListener('visibilitychange', schedule); };
  }, [enabled, offerId, send]);
  const click = async (action: Action) => {
    if (!enabled || !viewed.current || clicked.current.has(action)) return;
    clicked.current.add(action);
    if (await viewed.current) await send(action);
  };
  return { ref, click };
}
export function MeasurementSettings() {
  const { enabled, eligible, reload } = useContext(Measurement), action = useAction();
  return <section className="panel"><h2>서비스 개선 통계</h2><p>선택하면 보인 육아템·수요 글, 버튼 클릭, 저장·관심 완료를 계정별로 중복 제거해 30일간 분석합니다. 이메일·닉네임·검색어·아이 정보는 분석 항목에 넣지 않습니다.</p>
    <p className="hint">화면의 50% 이상이 1초 연속 보일 때 노출로 기록합니다. 동의한 회원의 활동만 분석하므로 전체 이용자의 성향을 뜻하지 않습니다. 해제하면 내 분석 기록도 삭제합니다.</p>
    <label className="check"><input type="checkbox" checked={enabled} disabled={action.busy || !eligible} onChange={e => { const checked = e.target.checked; void action.run(async () => { await api('/release/measurement/consent', 'PUT', { enabled: checked }); reload(); }, checked ? '통계 참여를 켰습니다.' : '통계 참여를 끄고 분석 기록을 삭제했습니다.'); }}/><span>[선택] 서비스 개선을 위한 활동 분석에 참여</span></label>
    {!eligible && <p>운영자 계정의 활동은 통계에서 제외합니다.</p>}<Feedback {...action}/></section>;
}
type Row = {placement: Placement; channel: string; accounts: number | null; clicked_accounts: number | null; saved_accounts: number | null; interested_accounts: number | null; interest_rate: number | null; ctr: number | null; ctr_95_interval: number[] | null; save_rate: number | null; decision: string};
type Report = {rows: Row[]; definition: string; limitations: string; search: string};
const percent = (n: number | null) => n === null ? '집계 보류' : (n * 100).toFixed(1) + '%';
const places = {catalog: '육아템 목록', personal: '내 관심 육아템', detail: '육아템 상세', demand_list: '공구 수요 목록', demand_detail: '공구 수요 관심 버튼'};
export function MeasurementReport() {
  const data = usePublicResource<Report>('/release/measurement/report');
  return <section className="panel"><h2>노출 → 클릭 → 저장·관심</h2><ResourceState {...data} retry={data.reload}/>{data.data && <><p>{data.data.definition}</p>
    {!data.data.rows.length && <p>아직 동의한 일반 회원의 측정 기록이 없습니다. 성과 수치를 만들지 않고 실제 활동을 기다립니다.</p>}
    {data.data.rows.map(row => <article className="measurement-row" key={row.placement + row.channel}><h3>{places[row.placement]} · {row.channel === 'android' ? '앱' : '웹'}</h3><dl className="account-summary"><div><dt>노출 계정</dt><dd>{row.accounts ?? '5명 미만'}</dd></div><div><dt>클릭 계정</dt><dd>{row.clicked_accounts ?? '소수 집계 숨김'}</dd></div><div><dt>{row.placement.startsWith("demand_")?"관심 완료 계정":"저장 완료 계정"}</dt><dd>{(row.placement.startsWith("demand_")?row.interested_accounts:row.saved_accounts) ?? '소수 집계 숨김'}</dd></div></dl>
      <p>계정 기준 CTR {percent(row.ctr)} · {row.placement.startsWith("demand_")?"관심":"저장"} 전환율 {percent(row.placement.startsWith("demand_")?row.interest_rate:row.save_rate)}</p>{row.ctr_95_interval && <p className="hint">CTR 95% Wilson 구간 {percent(row.ctr_95_interval[0])}~{percent(row.ctr_95_interval[1])}. 동의 회원의 관찰 집단에 대한 구간이며 인과 효과 검정이 아닙니다.</p>}<p>{row.decision}</p></article>)}
    <p className="hint">저장·관심은 측정된 클릭 이후 30분 안에 서버가 신규 행동을 완료했을 때 마지막 클릭에 연결합니다. 단순 버튼 클릭·기존 행동 반복은 전환이 아닙니다. 구매나 매출을 뜻하지 않습니다.</p><p>{data.data.limitations}</p><h3>검색·AI 답변 노출</h3><p>{data.data.search}</p></>}
    <button className="secondary" disabled={data.loading} onClick={data.reload}>측정 결과 새로고침</button></section>;
}
