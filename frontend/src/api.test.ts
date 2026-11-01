import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  ApiError,
  formatError,
  safeExternalUrl,
  safeReturnPath,
  TOKEN_KEY,
} from "./api";
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  });
  vi.stubGlobal("window", new EventTarget());
  vi.stubGlobal(
    "CustomEvent",
    class extends Event {
      constructor(name: string) {
        super(name);
      }
    },
  );
});
afterEach(() => vi.unstubAllGlobals());
describe("safe login return path", () => {
  it("keeps original detail and query without executing actions", () =>
    expect(safeReturnPath("/campaigns/abc?quantity=2")).toBe(
      "/campaigns/abc?quantity=2",
    ));
  it.each([
    "https://evil.test",
    "//evil.test",
    "/\\evil.test",
    "/x\n//evil.test",
    "javascript:alert(1)",
    "/login",
    "/signup?x=1",
    "/reset",
    null,
  ])("rejects external or auth-loop path %s", (value) =>
    expect(safeReturnPath(value)).toBe("/"),
  );
});
describe("external source links", () => {
  it("allows only safe https links", () => {
    expect(safeExternalUrl("https://example.com/deal")).toBe(
      "https://example.com/deal",
    );
  });
  it.each([
    "javascript:alert(1)",
    "http://example.com",
    "https://user:pass@example.com",
    "file:///data",
    "//example.com",
    null,
  ])("rejects unsafe source %s", (value) =>
    expect(safeExternalUrl(value)).toBeNull(),
  );
});
describe("API failures and session", () => {
  it("sends session bearer but no password storage", async () => {
    sessionStorage.setItem(TOKEN_KEY, "test-session");
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetch);
    expect(await api("/me")).toEqual({ ok: true });
    expect(fetch.mock.calls[0][1].headers).toEqual({
      Authorization: "Bearer test-session",
    });
  });
  it("clears expired token and notifies authentication boundary", async () => {
    sessionStorage.setItem(TOKEN_KEY, "expired");
    const expired = vi.fn();
    window.addEventListener("auth-expired", expired);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: "세션 만료" }), {
            status: 401,
          }),
        ),
    );
    await expect(api("/me")).rejects.toMatchObject({
      status: 401,
      message: "세션 만료",
    });
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
  });
  it("preserves server validation details instead of success", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              detail: [{ loc: ["body", "business_number"], msg: "번호 오류" }],
            }),
            { status: 422 },
          ),
        ),
    );
    await expect(api("/seller/application/submit", "POST")).rejects.toThrow(
      "business_number: 번호 오류",
    );
  });
  it("does not simulate success when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(api("/campaigns")).rejects.toBeInstanceOf(ApiError);
    await expect(api("/campaigns")).rejects.toMatchObject({ status: 0 });
  });
  it("formats string and unknown errors safely", () => {
    expect(formatError("실패")).toBe("실패");
    expect(formatError({ x: 1 })).toContain("처리하지 못했습니다");
  });
});
