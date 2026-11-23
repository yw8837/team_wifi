import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { CampaignReport } from './campaign-report';

const dates = ['2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21', '2026-11-22', '2026-11-23'];
const days = dates.map((date, index) => index === 6
  ? { date, accounts: 0, link_estimate: 7, campaign_estimate: { visitors: 8, detail: 2, outbound: 2 } }
  : { date, accounts: index === 3 ? null : 0 });
vi.mock('./release-data', () => ({
  usePublicResource(path: string) {
    const week = path.includes('period=custom&start=2026-11-17&end=2026-11-23');
    return { data: { dashboard: { start: week ? dates[0] : dates[6], end: dates[6], minimum_date: '2026-10-24',
      days: week ? days : days.slice(-1), checked_at: 1795400000 }, rows: [] }, loading: false, error: '', reload: vi.fn() };
  },
}));

it('shows one daily summary and all seven dates, preserving suppressed counts and the report source', () => {
  const html = renderToStaticMarkup(<MemoryRouter><CampaignReport sessionKey="owner"/></MemoryRouter>);
  for (const date of dates) expect(html).toContain('dateTime="' + date + '"');
  expect(html).toContain('공유 링크 유입</dt><dd>7명');
  expect(html).toContain('8명'); expect(html).toContain('25%');
  expect(html).toContain('＊'); expect(html).toContain('보고서 기준');
  expect(html).not.toMatch(/홍보 기록 보기|자동 집계 보기|팀 추산|유입 경로별 방문 회원/);
});
