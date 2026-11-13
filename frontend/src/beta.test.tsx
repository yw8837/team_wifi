import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { betaApiOrigin, buildCsp, isPublicRead, signupDestination } from "./beta-policy";
import { RecoveryCodeNotice } from "./beta";

describe("beta API build boundary", () => {
  it.each([undefined, "", "/api", "http://api.example.test/api", "https://localhost/api",
    "https://a.localhost/api", "https://localhost./api", "https://a.localhost./api", "https://127.0.0.1/api", "https://127.4.2.1/api", "https://[::1]/api",
    "https://0.0.0.0/api", "https://user:secret@example.test/api", "https://example.test/api?token=x",
    "https://example.test/api#fragment"])("fails closed for %s", (base) => {
    expect(() => betaApiOrigin(true, base)).toThrow();
  });
  it("allows a configured HTTPS origin and adds no local debug origins", () => {
    expect(betaApiOrigin(true, "https://api.example.test:8443/api")).toBe("https://api.example.test:8443");
    const csp = buildCsp(true, "https://api.example.test:8443/api");
    expect(csp).toContain("connect-src 'self' https://api.example.test:8443;");
    expect(csp).not.toMatch(/10\.0\.2\.2|127\.0\.0\.1|localhost/);
  });
  it("preserves local Android debug connectivity outside beta", () => {
    expect(buildCsp(false, undefined)).toContain("http://10.0.2.2:8000 http://127.0.0.1:8000");
  });
});

describe("guest reads and original-page return", () => {
  it.each(["/campaigns", "/campaigns/c1?quantity=3", "/campaigns/c1/questions", "/brands/b1", "/coupons", "/config"])(
    "recognizes public read %s", (path) => expect(isPublicRead(path)).toBe(true));
  it.each(["/me", "/wallet", "/seller/application", "/admin/reports", "/campaigns/c1/reservations"])(
    "keeps account read protected %s", (path) => expect(isPublicRead(path)).toBe(false));
  it("never classifies a mutation as a public read", () => {
    expect(isPublicRead("/campaigns/c1/questions", "POST")).toBe(false);
  });
  it("returns seller signup to a supplied original page before seller onboarding", () => {
    expect(signupDestination("seller", "/campaigns/c1?quantity=3#conditions")).toBe("/campaigns/c1?quantity=3#conditions");
    expect(signupDestination("seller", "/")).toBe("/seller");
    expect(signupDestination("buyer", "/")).toBe("/");
  });
});

describe("one-time recovery code acknowledgment", () => {
  it("starts unchecked with a required acknowledgment and disabled navigation", () => {
    let continued = false;
    const html = renderToStaticMarkup(<RecoveryCodeNotice code="TEST-ONLY-RECOVERY" onContinue={() => { continued = true; }} />);
    expect(html).toContain("TEST-ONLY-RECOVERY");
    expect(html).toMatch(/type="checkbox"[^>]*required=""/);
    expect(html).not.toMatch(/checked=""/);
    expect(html).toContain('<button disabled="">확인하고 계속</button>');
    expect(html).toContain("지금 한 번만 표시");
    expect(continued).toBe(false);
  });
});
