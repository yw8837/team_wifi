import { ResourceState } from './shared';
import { usePublicResource } from './release-data';

type CampaignRow = { source: string; medium: string; campaign: string; channel: string; accounts: number };
export function CampaignReport() {
  const result = usePublicResource<{ rows: CampaignRow[] }>('/release/measurement/campaign-report');
  return <section aria-label="UTM 유입 통계">
    <h3>공유·홍보 링크 유입</h3>
    <p>최근 30일 동안 활동 분석에 동의한 회원을 유입 경로별로 한 번씩 셉니다. 같은 경로의 재방문은 중복 집계하지 않으며 5명 이상인 경로만 표시합니다.</p>
    <p className="hint">여러 경로로 방문한 회원은 각 경로에 포함됩니다. 웹·앱 공유 태그는 링크를 만든 플랫폼을 뜻합니다.</p>
    <ResourceState {...result} retry={result.reload}/>
    {result.data?.rows.length === 0 && <p>아직 5명 이상 모인 유입 경로가 없습니다.</p>}
    {result.data?.rows.map(row => <article key={[row.source, row.medium, row.campaign, row.channel].join(':')}>
      <h4>{row.source} · {row.medium} · {row.campaign}</h4>
      <p>{row.channel === 'android' ? '앱' : '웹'} 방문 회원 {row.accounts}명</p>
    </article>)}
    <button className="secondary" disabled={result.loading} onClick={result.reload}>유입 통계 새로고침</button>
  </section>;
}
