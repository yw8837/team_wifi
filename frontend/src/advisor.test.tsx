import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { AdvisorForm, SelectionResults, SuggestedCard } from './advisor';
import type { Selection, SuggestedItem } from './advisor';
import { publicBrowsePath, publicReturnPath } from './release-policy';
import { isPublicRead } from './beta-policy';

vi.mock('./shared', async () => ({ ...await vi.importActual<typeof import('./shared')>('./shared'), useAuth: () => ({ user: null }), ResourceState: () => null, PageTitle: () => null }));
vi.mock('./measurement', () => ({ useExposure: () => ({ ref: null, click: vi.fn() }) }));
const render = (node: React.ReactNode) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
const choice = { categories: ['수유·이유식'], priority: 'composition' as const, purpose: 'gift' as const, budget_max: 10000 };

describe('grounded selection and CTA', () => {
  it('offers guest choices without collecting family information or implying a model score', () => {
    const html = render(<AdvisorForm signedIn={false} saved={null}/>);
    expect(html).toContain('이 조건으로 찾기');
    expect(html).toContain('가격이나 배송비가 확인되지 않은 목록은 예산 결과에서 제외');
    expect(html.match(/type="checkbox"/g)).toHaveLength(6);
    expect(html).not.toContain('생년월일');
    expect(html).not.toContain('구매 확률');
  });
  it('makes account persistence and explicit deletion visible', () => {
    const html = render(<AdvisorForm signedIn saved={{ choices: choice, items: [], unknown_price_count: 2, focus: '구성 확인', note: '', has_saved_choices: true }}/>);
    expect(html).toContain('조건 저장하고 찾기');
    expect(html).toContain('끝내고 조건 지우기');
    expect(html).toContain('value="10000"');
  });
  it('does not substitute unknown prices with zero or make up a result', () => {
    const result: Selection = { choices: choice, items: [], unknown_price_count: 2, focus: '구성 확인', note: '선택 기준' };
    const html = render(<SelectionResults result={result}/>);
    expect(html).toContain('가격·배송비 미확인 목록 2개');
    expect(html).toContain('예산을 비우면');
    expect(html).not.toContain('0원');
  });
  it('escapes catalog text and links to real item ids', () => {
    const item = { id: 'a b', title: '<script>bad</script>', category: '수유·이유식', source_name: '공식몰', reason: '같은 분야의 공식 목록이에요.' } as SuggestedItem;
    const html = render(<SuggestedCard item={item} placement="companion"/>);
    expect(html).toContain('href="/offers/a%20b"');
    expect(html).toContain('&lt;script&gt;');
    expect(html).not.toContain('<script>');
  });
  it('allows guest navigation but never classifies saved choices as public', () => {
    expect(publicBrowsePath('/advisor')).toBe('/advisor');
    expect(publicReturnPath('/advisor')).toBe('/advisor');
    expect(isPublicRead('/release/offers/a/companions')).toBe(true);
    expect(isPublicRead('/release/offers/a/guide')).toBe(true);
    expect(isPublicRead('/release/advisor')).toBe(false);
  });
});
