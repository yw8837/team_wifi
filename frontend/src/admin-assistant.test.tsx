import { expect,it,vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
vi.mock('./community',()=>({communityTime:(x:string)=>x,useCommunityResource:vi.fn(),ListFeedback:()=>null}));
vi.mock('./admin-members',()=>({AdminNavigation:()=>null}));
import { EvaluationRunCard,type EvaluationRun } from './admin-assistant';
it('shows failed first-run counts and separates model, evidence and persistence',()=>{
 const run:EvaluationRun={id:'first',label:'최초 새 질문',created_at:'2026-11-06',model:'Qwen3',prompt_version:'v5',cases:12,automatic_pass:10,inference_attempts:8,model_selections:8,valid_citations:11,citation_count:11,warm_p50_ms:468,warm_p95_ms:603,trace_persisted:12,trace_expected:12,full_content:7,content_total:10,report_sha256:'a'.repeat(64),notes:['잘못 거절한 2문항을 보존했습니다.'],source_kind:'public_synthetic'};
 const html=renderToStaticMarkup(<EvaluationRunCard run={run}/>);
 expect(html).toContain('10 / 12문항 통과');expect(html).toContain('7 / 10문항');expect(html).toContain('12 / 12건');expect(html).toContain('잘못 거절한 2문항');expect(html).not.toContain('정확도 100');
});
