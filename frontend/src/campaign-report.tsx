import { useState } from 'react';
import { useContentRequest } from './content-session';
import { Feedback, ResourceState, useAction } from './shared';
import { usePublicResource } from './release-data';
import './campaign-report.css';

type Count = number | null;
type Day = { date: string; accounts: Count; web_opens: Count; link_estimate?: number };
type Dashboard = {
  start: string; end: string; minimum_date: string; checked_at: number;
  shared_opens: Count; web_opens: Count; web_opens_from: string | null;
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

function PrivateLinkEstimate({ day, reload }: { day: Day; reload: () => void }) {
  const request = useContentRequest(), action = useAction();
  const [value, setValue] = useState(day.link_estimate?.toString() ?? '');
  return <div className="link-estimate">
    <details><summary>{day.link_estimate !== undefined ? '추정치 수정' : '공유 링크 방문자 추정치 추가'}</summary>
      <form onSubmit={event => {
        event.preventDefault();
        void action.run(async () => {
          await request('/release/measurement/link-estimates/' + day.date, 'PUT', {count: value === '' ? null : Number(value)});
          reload();
        });
      }}>
        <label>추정 인원 <input type="number" min="0" max="1000000" step="1" value={value} onChange={e => setValue(e.target.value)}/></label>
        <button type="submit" className="secondary" disabled={action.busy}>저장</button>
        <small>값을 비워 저장하면 추정치를 삭제합니다.</small>
      </form><Feedback {...action}/>
    </details>
  </div>;
}

function VisitorMetrics({ data, reload }: { data: Dashboard; reload: () => void }) {
  const { visitors, detail_readers, outbound, days } = data;
  const singleDay = days.length === 1 ? days[0] : undefined;
  const showEstimates = days.some(day => day.link_estimate !== undefined);
  const steps: [string, Count][] = [['동의 회원 방문', visitors], ['공구 상세 열람', detail_readers], ['판매처 이동', outbound]];
  const rate = visitors && outbound !== null ? (100 * outbound / visitors).toFixed(1) + '%' : '—';
  const openCount = (count: Count) => count == null ? '집계 전' : count.toLocaleString('ko-KR') + '회';
  return <>
    <section className="visit-panel" aria-label="기간별 방문 지표">
      <p className="visit-range">{shortDate(data.start)} ~ {shortDate(data.end)} <small>한국 시간</small></p>
      <dl className={'visit-metrics visit-summary' + (singleDay?.link_estimate !== undefined ? ' with-estimate' : '')}>
        {singleDay?.link_estimate !== undefined && <div><dt>공유 링크 방문자 (추정)</dt><dd>약 {singleDay.link_estimate.toLocaleString('ko-KR')}명</dd></div>}
        <div><dt>공개 웹 열람</dt><dd>{openCount(data.web_opens)}</dd><small>비회원·새로고침 포함{data.shared_opens != null && <> · 이 중 공유 링크 {openCount(data.shared_opens)}</>}</small></div>
        <div><dt>로그인 방문 회원</dt><dd>{countText(visitors)}</dd><small>통계 동의 회원 · 계정당 한 번</small></div>
      </dl>
      <p className="visit-note">{data.web_opens_from ? '웹 열람은 ' + data.web_opens_from + ' 첫 집계부터 표시합니다.' : '첫 공개 웹 열람을 기다리고 있습니다.'} 공유 링크 횟수는 서비스 공유 버튼으로 만든 주소를 열 때 집계합니다. 운영 화면과 링크 미리보기 요청은 제외합니다.</p>
      {days.length === 1 && data.start >= kstDate(data.checked_at * 1000 - 29 * 86400000) &&
        <PrivateLinkEstimate key={data.start} day={days[0]} reload={reload}/>}
    </section>
    <section className="visit-panel"><h3>방문에서 판매처 이동까지</h3>
      <p>활동 분석에 동의한 회원 중 공구 상세를 본 인원과 판매처로 이동한 인원입니다. 판매처 이동률 {rate}</p>
      <ul className="visit-funnel">{steps.map(([label, count]) => <li key={label}>
        <span>{label}</span><span className="visit-track" aria-hidden="true"><i style={{ width: visitors && count !== null ? (100 * count / visitors) + '%' : '0%' }}/></span>
        <strong>{countText(count)}</strong>
      </li>)}</ul>
    </section>
    <section className="visit-panel"><h3>날짜별 접속 기록</h3>
      <div className="visit-history"><table><thead><tr><th scope="col">날짜</th>{showEstimates && <th scope="col">공유 링크 방문자 (추정)</th>}<th scope="col">공개 웹 열람</th><th scope="col">로그인 방문 회원</th></tr></thead>
        <tbody>{[...days].reverse().map(day => <tr key={day.date}><th scope="row"><time dateTime={day.date}>{shortDate(day.date)}</time></th>{showEstimates && <td>{day.link_estimate === undefined ? '—' : '약 ' + day.link_estimate.toLocaleString('ko-KR') + '명'}</td>}
          <td>{openCount(day.web_opens)}</td><td>{countText(day.accounts)}</td></tr>)}</tbody></table></div>
      <p className="visit-note">회원 1~4명은 ‘5명 미만’으로 표시합니다. 같은 회원이 다른 날 다시 오면 각 날짜에 한 번씩 셉니다.</p>
    </section>
  </>;
}

export function CampaignReport({ sessionKey }: { sessionKey?: string }) {
  const [range, setRange] = useState<{ period: Period; start?: string; end?: string }>({ period: 'today' });
  const [start, setStart] = useState(() => kstDate(Date.now()));
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
    <p>공개 웹 열람에는 비회원도 포함됩니다. 로그인 방문 회원은 활동 통계에 동의한 계정을 기간 중 한 번씩 셉니다.</p>
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
    {data && <VisitorMetrics data={data} reload={result.reload}/>}
    {result.data && !data && <p role="status">방문 지표를 불러오지 못했습니다. 잠시 후 새로고침해 주세요.</p>}
    {result.data && <section className="visit-panel"><h3>회원이 방문한 공유·홍보 경로</h3>
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
