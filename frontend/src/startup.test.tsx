import { beforeAll, beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactElement, ReactNode } from "react";

const startup = vi.hoisted(() => ({ entry: "/", tree: null as unknown }));
vi.mock("react-dom/client", () => ({
  default: { createRoot: () => ({ render: (tree: unknown) => { startup.tree = tree; } }) },
}));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    BrowserRouter: ({ children }: { children: ReactNode }) => (
      <actual.MemoryRouter initialEntries={[startup.entry]}>{children}</actual.MemoryRouter>
    ),
  };
});

function storage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
}
function renderEntry(path = "/") {
  startup.entry = path;
  return renderToStaticMarkup(startup.tree as ReactElement);
}
function guestBrowseHref(html: string) {
  return html.match(/<a\b[^>]*href="([^"]*)"[^>]*>로그인 없이 둘러보기<\/a>/)?.[1];
}

beforeAll(async () => {
  vi.stubGlobal("document", { getElementById: () => ({}) });
  // Capture the real app boot tree; only the browser mounting/routing boundary is replaced.
  await import("./main");
});
beforeEach(() => {
  vi.stubGlobal("localStorage", storage());
  vi.stubGlobal("sessionStorage", storage());
  vi.stubGlobal("navigator", { onLine: true });
  vi.stubGlobal("window", { location: { origin: "https://app.example.test" } });
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected startup request"); }));
});
afterEach(() => vi.unstubAllGlobals());

describe("guest-first app startup", () => {
  it.each([null, "seen", "unexpected"])("shows the real home without an intro gate for storage value %s", (intro) => {
    if (intro !== null) localStorage.setItem("moduyuga.intro", intro);
    const html = renderEntry();
    expect(html).toContain("우리에게 필요한 공동구매");
    expect(html).toContain('type="search"');
    expect(html).toContain('aria-label="카테고리"');
    expect(html).toContain("기저귀·물티슈");
    expect(html).toContain('href="/hotdeals"');
    expect(html).not.toContain('name="password"');
    expect(html).not.toContain('class="welcome"');
    expect(fetch).not.toHaveBeenCalled();
  });
  it("keeps the introduction available as a voluntary page", () => {
    const html = renderEntry("/welcome");
    expect(html).toContain('class="welcome"');
    expect(html).toContain('href="/"');
    expect(html).toContain("육아템 둘러보기");
  });
  it("lets a login visitor resume the original detail and selected quantity as a guest", () => {
    sessionStorage.setItem("moduyuga.quantity.fixture", "3");
    const html = renderEntry("/login?returnTo=" + encodeURIComponent("/campaigns/fixture?view=conditions#shipping"));
    expect(guestBrowseHref(html)).toBe("/campaigns/fixture?view=conditions#shipping");
    expect(sessionStorage.getItem("moduyuga.quantity.fixture")).toBe("3");
    expect(html).toContain('name="password"');
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([undefined, "https://outside.example", "//outside.example", "/login", "/signup?track=seller", "/reset"])(
    "offers a safe home escape for login returnTo %s", (returnTo) => {
      const path = returnTo === undefined ? "/login" : "/login?returnTo=" + encodeURIComponent(returnTo);
      expect(guestBrowseHref(renderEntry(path))).toBe("/");
    });
  it.each([
    "/my/saved", "/MY/SAVED/", "/my/reservations///", "/settings/", "/SELLER/campaigns/", "/admin///",
    "/unknown", "/unknown/", "/campaigns/fixture/questions", "/brands/fixture/extra", "/%6dy/saved", "/Login/",
  ])("returns a guest home for protected or unknown destination %s without changing authenticated returnTo", (returnTo) => {
    const html = renderEntry("/login?returnTo=" + encodeURIComponent(returnTo));
    expect(guestBrowseHref(html)).toBe("/");
    expect(html).toContain("/signup?returnTo=" + encodeURIComponent(returnTo));
  });
  it.each([
    "/?q=diaper#items", "/hotdeals/?q=diaper#items", "/BRANDS/fixture/?view=details#shipping",
    "/campaigns/fixture/?view=conditions#shipping", "/%63ampaigns/fixture?view=conditions#shipping",
    "/benefits/", "/my/", "/welcome/",
  ])("preserves guest-readable destination %s including routing-compatible separators/case", (returnTo) => {
    expect(guestBrowseHref(renderEntry("/login?returnTo=" + encodeURIComponent(returnTo)))).toBe(returnTo);
  });
  it.each(["/my/saved", "/my/reservations", "/settings", "/seller", "/seller/campaigns", "/admin"])(
    "keeps the owned route %s protected for a fresh guest", (path) => {
      const html = renderEntry(path);
      expect(html).toContain("로그인이 필요해요");
      expect(html).toContain("/login?returnTo=" + encodeURIComponent(path));
      expect(fetch).not.toHaveBeenCalled();
    });
});
