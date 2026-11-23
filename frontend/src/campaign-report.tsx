import { useState } from 'react';
import { ResourceState } from './shared';
import { usePublicResource } from './release-data';
import './campaign-report.css';

type Count = number | null;
type Day = { date: string; accounts: Count };
type Dashboard = {
  start: string; end: string; minimum_date: string; checked_at: number;
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
  const { visitors, detail_readers, outbound, days } = data;
  const steps: [string, Count][] = [['방문 회원', visitors], ['공구 상세 열람', detail_readers], ['판매처 이동', outbound]];
  const rate = visitors && outbound !== null ? (100 * outbound / visitors).toFixed(1) + '%' : '—';
  const maxDay = Math.max(1, ...days.map(day => day.accounts ?? 0));
  return <>
    <section className="visit-panel" aria-label="기간별 방문 지표">
      <p className="visit-range">{shortDate(data.start)} ~ {shortDate(data.end)} <small>한국 시간</small></p>
      <dl className="visit-metrics">
        {steps.map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{countText(count)}</dd></div>)}
        <div><dt>판매처 이동률</dt><dd>{rate}</dd></div>
      </dl>
    </section>
    <section className="visit-panel"><h3>방문에서 판매처 이동까지</h3>
      <p>방문 회원 중 공구 상세를 보고 판매처 링크를 누른 회원의 비율입니다.</p>
      <ul className="visit-funnel">{steps.map(([label, count]) => <li key={label}>
        <span>{label}</span><span className="visit-track" aria-hidden="true"><i style={{ width: visitors && count !== null ? (100 * count / visitors) + '%' : '0%' }}/></span>
        <strong>{countText(count)}</strong>
      </li>)}</ul>
    </section>
    <section className="visit-panel"><h3>일별 방문 회원</h3>
      <div className="visit-chart-scroll" tabIndex={days.length > 7 ? 0 : undefined} role="region" aria-label="날짜별 방문 회원 그래프">
        <ol className="visit-chart" style={{ minWidth: days.length > 7 ? days.length * 46 : undefined }}>
          {days.map(day => <li key={day.date} aria-label={day.date + ' ' + countText(day.accounts)}>
            <span aria-hidden="true">{day.accounts === null ? '＊' : day.accounts.toLocaleString('ko-KR')}</span>
            <div className="visit-column" aria-hidden="true"><i style={{ height: ((day.accounts ?? 0) / maxDay * 100) + '%' }}/></div>
            <time dateTime={day.date}>{shortDate(day.date)}</time>
          </li>)}
        </ol>
      </div>
      <p className="visit-note">하루에 여러 번 방문해도 한 명으로 셉니다. ＊는 1~4명으로 인원수를 숨긴 날입니다.</p>
    </section>
  </>;
}

export function CampaignReport({ sessionKey }: { sessionKey?: string }) {
  const [range, setRange] = useState<{ period: Period; start?: string; end?: string }>({ period: 'week' });
  const [start, setStart] = useState(() => kstDate(Date.now() - 6 * 86400000));
  const [end, setEnd] = useState(() => kstDate(Date.now()));
  const query = new URLSearchParams({ ...range });
  const result = usePublicResource<Report>('/release/measurement/campaign-report?' + query, sessionKey);
  const data = result.data?.dashboard;
  const today = kstDate((data?.checked_at ?? Date.now() / 1000) * 1000);
  const minimum = data?.minimum_date ?? kstDate(Date.now() - 30 * 86400000);
  function selectPeriod(period: keyof typeof presets) {
    const lookback = { today: 0, week: 6, month: 29, all: 30 }[period];
    setStart(period === 'all' ? minimum : kstDate((data?.checked_at ?? Date.now() / 1000) * 1000 - lookback * 86400000));
    setEnd(today);
    setRange({ period });
  }
  const rows = [...(result.data?.rows ?? [])].sort((a, b) => b.accounts - a.accounts);
  return <section className="visit-report" aria-labelledby="visit-title">
    <header className="visit-heading"><h2 id="visit-title">방문 현황</h2>
      <button type="button" className="secondary" disabled={result.loading} onClick={result.reload}>새로고침</button></header>
    <p>활동 분석에 동의한 회원의 화면 열람과 공유 링크 방문을 집계합니다. 비회원과 운영자는 제외합니다.</p>
    <div className="visit-controls">
      <div role="group" aria-label="조회 기간">{(Object.keys(presets) as (keyof typeof presets)[]).map(key =>
        <button type="button" className="secondary" key={key} aria-pressed={range.period === key} onClick={() => selectPeriod(key)}>{presets[key]}</button>)}</div>
      <form aria-label="직접 기간 선택" onSubmit={event => { event.preventDefault(); setRange({ period: 'custom', start, end }); }}>
        <input required type="date" aria-label="시작일" min={minimum} max={end || today} value={start} onChange={e => setStart(e.target.value)}/>
        <span aria-hidden="true">~</span>
        <input required type="date" aria-label="종료일" min={start || minimum} max={today} value={end} onChange={e => setEnd(e.target.value)}/>
        <button className="secondary" aria-pressed={range.period === 'custom'}>기간 보기</button>
      </form>
    </div>
    <ResourceState {...result} retry={result.reload}/>
    {data && <VisitorMetrics data={data}/>}
    {result.data && !data && <p role="status">방문 지표를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</p>}
    {result.data && <section className="visit-panel"><h3>어디에서 들어왔나요?</h3>
      {rows.length ? <ul className="visit-sources">{rows.map(row =>
        <li key={[row.source, row.medium, row.campaign, row.channel].join('/')}>
          <div><strong>{sourceNames[row.source] ?? row.source}</strong>
            <small>{campaignNames[row.campaign] ?? row.campaign} · {mediumNames[row.medium] ?? row.medium} · {row.channel === 'android' ? '앱' : '웹'}에서 열람</small></div>
          <b>{countText(row.accounts)}</b>
        </li>)}</ul> : <p>이 기간에 회원 5명 이상이 방문한 공유·홍보 경로가 없습니다.</p>}
    </section>}
    <p className="visit-note">전체는 보관 중인 최근 30일입니다.{data && ' 마지막 조회 ' + new Date(data.checked_at * 1000).toLocaleTimeString('ko-KR', {timeZone:'Asia/Seoul', hour:'2-digit', minute:'2-digit'})}</p>
  </section>;
}
