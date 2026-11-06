import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { PersonalDiscovery, PreferenceForm, InsightsView } from "./discovery";
import type { Insights } from "./discovery";
import evidence from "../../backend/app/discovery_evidence.json";
import { publicBrowsePath, publicReturnPath } from "./release-policy";
vi.mock("./shared", async () => ({ ...await vi.importActual<typeof import("./shared")>("./shared"), useAuth: () => ({ user: null }), useAction: () => ({ busy: false, run: vi.fn() }), Feedback: () => null, ResourceState: () => null, PageTitle: () => null }));
vi.mock("./release-data", () => ({ usePublicResource: () => ({ data: null, loading: false, error: "" }) }));
const render = (node: React.ReactNode) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
describe("discovery user choices and honest evidence", () => {
  it("keeps guest browsing without assuming a profile or fake recommendations", () => {
    const html = render(<PersonalDiscovery/>);
    expect(html).toContain('href="/my/preferences"');
    expect(html).toContain("관심 육아템 고르기");
    expect(html).not.toContain("구매 확률");
  });
  it("offers explicit labeled choices with reset and cross-device feedback", () => {
    const html = render(<PreferenceForm initial={{ categories: ["기저귀·물티슈", "수유·이유식", "목욕·위생"], priority: "unit_price" }}/>);
    expect(html.match(/type="checkbox"/g)).toHaveLength(6);
    expect(html.match(/type="radio"/g)).toHaveLength(4);
    expect(html.match(/disabled=""/g)).toHaveLength(3);
    expect(html).toContain("설정 지우기");
    expect(html).toContain("배송비를 포함한 단가");
    expect(html).not.toContain('name="child');
  });
  it("protects new owned pages while retaining their post-login destinations", () => {
    for (const path of ["/my/preferences", "/admin/insights"]) {
      expect(publicBrowsePath(path)).toBe("/");
      expect(publicReturnPath(path)).toBe(path);
    }
  });
  it("shows suppressed small cohorts and empty pairs without claiming demand forecasts", () => {
    const data: Insights = { minimum_cohort: 5, saved_accounts: null, note: "실제 관심 기록", categories: [{ category: "기저귀·물티슈", saved_accounts: null, demand_authors: 0, interested_accounts: null }], pairs: [], evidence };
    const html = render(<InsightsView data={data}/>);
    expect(html).toContain("5명 미만 · 비공개");
    expect(html).toContain("최소 5계정");
    expect(html).toContain("결제·동시구매 기록은 아닙니다");
    expect(html).toContain("541,909");
    expect(html).toContain("12,330");
  });
  it("escapes offer titles and shows both directions of association", () => {
    const data: Insights = { minimum_cohort: 5, saved_accounts: 10, note: "", categories: [], pairs: [{ first: "<script>bad</script>", second: "B", accounts: 5, support: .5, first_to_second: .5, second_to_first: 1 }], evidence };
    const html = render(<InsightsView data={data}/>);
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).toContain("반대 방향 100.0%");
  });
});
