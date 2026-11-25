import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ResourceState } from './shared';
import { usePublicResource } from './release-data';
import './campaign-report.css';

type Count = number | null;
type Day = { date: string; accounts: Count; web_opens: Count; link_estimate?: number; campaign_estimate?: { visitors: number; detail: number; outbound: number } };
type Dashboard = {
  start: string; end: string; minimum_date: string; checked_at: number;
  source_opens?: Record<string, number>; shared_opens: Count; web_opens: Count; web_opens_from: string | null;
  visitors: Count; detail_readers: Count; outbound: Count; days: Day[];
};
type CampaignRow = { source: string; medium: string; campaign: string; channel: string; accounts: number };
type Report = { dashboard?: Dashboard; rows: CampaignRow[] };
const presets = { today: '오늘', week: '7일', month: '30일', all: '전체' };
type Period = keyof typeof presets | 'custom';
const sourceNames: Record<string, string> = {
  web: '웹에서 복사한 링크', android: '앱에서 복사한 링크', kakao: '카카오톡', instagram: '인스타그램',
  naver: '네이버', google: '구글', youtube: '유튜브', discord: '디스코드', presentation: '발표 자료', qr: 'QR 코드',
};
const campaignNames: Record<string, string> = { groupbuy: '공구', community_launch: '커뮤니티 출시', midterm: '중간 발표' };
const mediumNames: Record<string, string> = { share: '공유', social: '소셜', search: '검색', referral: '외부 링크', qr: 'QR', presentation: '발표' };
const shortDate = (iso: string) => iso.slice(5).replace('-', '/');
const countText = (count: Count) => count === null ? '5명 미만' : count.toLocaleString('ko-KR') + '명';
const kstDate = (stamp: number) => new Date(stamp + 9 * 3600 * 1000).toISOString().slice(0, 10);

function VisitorMetrics({ data }: { data: Dashboard }) {
  const { days } = data;
  const single = days.length === 1 ? days[0] : undefined;
  const campaign = single?.campaign_estimate;
  const visitors = campaign?.visitors ?? data.visitors;
  const detail = campaign?.detail ?? data.detail_readers;
  const outbound = campaign?.outbound ?? data.outbound;
  const steps: [string, Count][] = [[campaign ? '방문자' : '방문 회원', visitors], ['공구 상세 열람', detail], ['판매처 이동', outbound]];
  const rate = visitors && outbound != null ? (100 * outbound / visitors).toLocaleString('ko-KR', {maximumFractionDigits:1}) + '%' : '—';
  const openCount = (count: Count) => count == null ? '집계 전' : count.toLocaleString('ko-KR') + '회';
  return <>
    <section className="visit-panel" aria-label="기간별 방문 지표">
      <p className="visit-range">{data.start === data.end ? shortDate(data.end) : shortDate(data.start) + ' ~ ' + shortDate(data.end)} <small>한국 시간{campaign && ' · 팀 보고서 기준'}</small></p>
      <dl className="visit-metrics">
        <div><dt>{campaign ? '일방문' : '로그인 방문 회원'}</dt><dd>{countText(visitors)}</dd></div>
        <div><dt>{campaign ? '공유 링크 유입' : '공개 웹 열람'}</dt><dd>{campaign ? countText(single?.link_estimate ?? null) : openCount(data.web_opens)}</dd></div>
        <div><dt>공구 상세 열람</dt><dd>{countText(detail)}</dd></div>
        <div><dt>판매처 이동</dt><dd>{countText(outbound)}</dd></div>
      </dl>
      {!campaign && <p className="visit-note">공개 웹 열람은 {data.web_opens_from ? data.web_opens_from + ' 첫 집계부터' : '첫 접속부터'} 새로고침도 한 번씩 셉니다.{data.shared_opens != null && ' 이 중 공유 링크 열람은 ' + openCount(data.shared_opens) + '입니다.'} 방문 회원 수는 통계에 동의한 계정 기준입니다.</p>}
    </section>
    <section className="visit-panel"><h3>방문에서 판매처 이동까지</h3>
      <p>판매처 이동률 <strong>{rate}</strong>{visitors != null && outbound != null && visitors > 0 && ' · 방문 ' + countText(visitors) + ' 중 ' + countText(outbound)}</p>
      <ul className="visit-funnel">{steps.map(([label, count]) => <li key={label}>
        <span>{label}</span><span className="visit-track" aria-hidden="true"><i style={{width: visitors && count != null ? (100 * count / visitors) + '%' : '0%'}}/></span>
        <strong>{countText(count)}</strong></li>)}</ul>
    </section>
  </>;
}

function DailyVisits({ data, sessionKey }: { data: Dashboard; sessionKey?: string }) {
  const weekStart = new Date(Date.parse(data.end + 'T00:00:00Z') - 6 * 86400000).toISOString().slice(0, 10);
  const start = weekStart < data.minimum_date ? data.minimum_date : weekStart;
  const extend = start < data.start;
  const history = usePublicResource<Report>(extend
    ? '/release/measurement/campaign-report?' + new URLSearchParams({ period: 'custom', start, end: data.end })
    : null, sessionKey);
  const days = extend ? history.data?.dashboard?.days ?? [] : data.days;
  const counts = days.map(day => day.campaign_estimate?.visitors ?? day.accounts);
  const maximum = Math.max(1, ...counts.map(count => count ?? 0));
  const estimates = days.filter(day => day.campaign_estimate).map(day => shortDate(day.date));
  return <section className="visit-panel"><h3>일별 방문자</h3>
    {extend && <ResourceState {...history} retry={history.reload}/>}
    {days.length > 0 && <>
      <div className="visit-history"><ol className="visit-chart" aria-label="일별 방문 그래프" style={{ minWidth: days.length > 7 ? days.length * 43 : undefined }}>
        {days.map((day, index) => <li key={day.date}><strong>{counts[index] === null ? '＊' : countText(counts[index])}</strong>
          <div className="visit-column" aria-hidden="true"><i style={{ height: (counts[index] ?? 0) / maximum * 100 + '%' }}/></div>
          <time dateTime={day.date}>{shortDate(day.date)}</time></li>)}
      </ol></div>
      {estimates.length > 0 && <p className="visit-note">{estimates.join(', ')} 방문 수치는 팀이 작성한 보고서 기준입니다. 다른 날짜는 통계 수집에 동의한 방문 회원 수입니다.</p>}
      {counts.includes(null) && <p className="visit-note">＊는 1~4명이 방문한 날입니다.</p>}
    </>}
  </section>;
}

export function CampaignReport({ sessionKey }: { sessionKey?: string }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get('period') ?? 'today';
  const period: Period = selected === 'custom' || Object.hasOwn(presets, selected) ? selected as Period : 'today';
  const query = new URLSearchParams({ period });
  if (period === 'custom') {
    query.set('start', params.get('start') ?? '');
    query.set('end', params.get('end') ?? '');
  }
  const result = usePublicResource<Report>('/release/measurement/campaign-report?' + query, sessionKey);
  const data = result.data?.dashboard;
  const today = kstDate((data?.checked_at ?? Date.now() / 1000) * 1000);
  const minimum = data?.minimum_date ?? kstDate(Date.now() - 30 * 86400000);
  const [draft, setDraft] = useState<{ scope: string; start: string; end: string } | null>(null);
  const scope = query.toString();
  const start = draft?.scope === scope ? draft.start : data?.start ?? query.get('start') ?? today;
  const end = draft?.scope === scope ? draft.end : data?.end ?? query.get('end') ?? today;
  const sources = Object.entries(data?.source_opens ?? {}).sort((a,b) => b[1] - a[1]);
  const unknown = (data?.web_opens ?? 0) - sources.reduce((sum, [, count]) => sum + count, 0);
  const rows = [...(result.data?.rows ?? [])].sort((a, b) => b.accounts - a.accounts);
  return <section className="visit-report" aria-labelledby="visit-title">
    <header className="visit-heading"><h2 id="visit-title">방문 현황</h2>
      <button type="button" className="secondary" disabled={result.loading} onClick={result.reload}>새로고침</button></header>
    <div className="visit-controls">
      <div role="group" aria-label="조회 기간">{(Object.keys(presets) as (keyof typeof presets)[]).map(key =>
        <Link className="secondary visit-preset" key={key} aria-current={period === key ? 'page' : undefined} to={'?period=' + key} onClick={() => setDraft(null)}>{presets[key]}</Link>)}</div>
      <form aria-label="직접 기간 선택" onSubmit={event => { event.preventDefault(); setParams({ period: 'custom', start, end }); setDraft(null); }}>
        <input required type="date" aria-label="시작일" min={minimum} max={end || today} value={start} onChange={e => setDraft({ scope, start: e.target.value, end })}/>
        <span aria-hidden="true">~</span>
        <input required type="date" aria-label="종료일" min={start || minimum} max={today} value={end} onChange={e => setDraft({ scope, start, end: e.target.value })}/>
        <button className="secondary" aria-pressed={period === 'custom'}>기간 보기</button>
      </form>
    </div>
    <ResourceState {...result} retry={result.reload}/>
    {data && <><VisitorMetrics data={data}/><DailyVisits data={data} sessionKey={sessionKey}/></>}
    {result.data && !data && <p role="status">방문 지표를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</p>}
    {data && <section className="visit-panel"><header className="visit-heading"><h3>경로별 웹 열람</h3><strong>{data.web_opens == null ? '집계 전' : '총 ' + data.web_opens.toLocaleString('ko-KR') + '회'}</strong></header>
      <ul className="visit-sources">{sources.map(([source, count]) =>
        <li key={source}><span>{sourceNames[source] ?? source}</span><b>{count.toLocaleString()}회</b></li>)}
        {unknown > 0 && <li><span>경로 미확인</span><b>{unknown.toLocaleString()}회</b></li>}
      </ul>
      <p className="visit-note">{data.web_opens == null ? '이 기간은 웹 열람 집계를 시작하기 전입니다.' : '공개 페이지를 열 때마다 1회로 셉니다. 새로고침도 포함합니다. 경로 미확인은 출처 표식이 없거나 출처 수집 전에 열린 횟수입니다.'}</p>
    </section>}
    {rows.length > 0 && <section className="visit-panel"><h3>유입 경로별 방문 회원</h3>
      <ul className="visit-sources">{rows.map(row =>
        <li key={[row.source, row.medium, row.campaign, row.channel].join('/')}>
          <div><strong>{sourceNames[row.source] ?? row.source}</strong>
            <small>{campaignNames[row.campaign] ?? row.campaign} · {mediumNames[row.medium] ?? row.medium} · {row.channel === 'android' ? '앱' : '웹'}에서 열람</small></div>
          <b>{countText(row.accounts)}</b>
        </li>)}</ul>
    </section>}
    <p className="visit-note">전체는 보관 중인 최근 30일입니다.{data && ' 마지막 조회 ' + new Date(data.checked_at * 1000).toLocaleTimeString('ko-KR', {timeZone:'Asia/Seoul', hour:'2-digit', minute:'2-digit'})}</p>
  </section>;
}
