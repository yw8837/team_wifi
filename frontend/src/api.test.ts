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
      detail: unknown;
      constructor(name: string, init?: { detail?: unknown }) {
        super(name);
        this.detail = init?.detail;
      }
    },
  );
});
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
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
  it.each(['/auth/login', '/auth/register'])("waits through a 55-second server wake for %s without replaying credentials", async (path) => {
    vi.useFakeTimers();
    const fetch = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((resolve, reject) => {
      const timer = setTimeout(() => resolve(new Response(JSON.stringify({ access_token: 'fixture-session' }))), 55_000);
      init.signal?.addEventListener('abort', () => { clearTimeout(timer); reject(new Error('aborted')); });
    }));
    vi.stubGlobal('fetch', fetch);
    const result = api(path, 'POST', { email: 'fixture@example.com', password: 'local-only-fixture' });
    await vi.advanceTimersByTimeAsync(55_000);
    await expect(result).resolves.toEqual({ access_token: 'fixture-session' });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("allows the first config read to finish after a 55-second server wake", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((resolve, reject) => {
      const timer = setTimeout(() => resolve(new Response(JSON.stringify({ public_release: true }))), 55_000);
      init.signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new Error("aborted")); });
    }));
    vi.stubGlobal("fetch", fetch);
    const result = api("/config");
    await vi.advanceTimersByTimeAsync(55_000);
    await expect(result).resolves.toEqual({ public_release: true });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].signal?.aborted).toBe(false);
  });
  it("recovers config from a transient gateway and network failure without manual reload", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockResolvedValueOnce(new Response("waking", { status: 503 }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ public_release: true })));
    vi.stubGlobal("fetch", fetch);
    const result = api("/config");
    await vi.advanceTimersByTimeAsync(4_500);
    await expect(result).resolves.toEqual({ public_release: true });
    expect(fetch).toHaveBeenCalledTimes(3);
  });
  it("bounds an unavailable config server at 90 seconds with a read-only message", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    }));
    vi.stubGlobal("fetch", fetch);
    const result = api("/config");
    const rejection = expect(result).rejects.toMatchObject({ status: 0, message: expect.not.stringContaining("처리 여부") });
    await vi.advanceTimersByTimeAsync(90_000);
    await rejection;
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("never automatically retries a mutation rejected by a gateway", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 }));
    vi.stubGlobal("fetch", fetch);
    await expect(api("/release/demands", "POST", { title: "example" })).rejects.toMatchObject({ status: 503 });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("aborts a slow mutation after 15 seconds without replaying it", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    }));
    vi.stubGlobal("fetch", fetch);
    const result = api("/campaigns/c1/reservations", "POST", { quantity: 2 });
    const rejection = expect(result).rejects.toMatchObject({ status: 0, message: expect.stringContaining("처리 여부") });
    await vi.advanceTimersByTimeAsync(15_000);
    await rejection;
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].signal?.aborted).toBe(true);
  });
  it.each([["GET", false], ["POST", true]])("signals %s expiry without automatic replay", async (method, redirect) => {
    sessionStorage.setItem(TOKEN_KEY, "expired");
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "세션 만료" }), { status: 401 }));
    vi.stubGlobal("fetch", fetch);
    const expired = vi.fn();
    window.addEventListener("auth-expired", expired);
    await expect(api("/campaigns/c1/questions", method)).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect((expired.mock.calls[0][0] as CustomEvent).detail.redirect).toBe(redirect);
  });
  it("invalid login does not emit a session-expired event", async () => {
    const expired = vi.fn();
    window.addEventListener("auth-expired", expired);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "로그인 정보 확인" }), { status: 401 })));
    await expect(api("/auth/login", "POST", { email: "test@example.test", password: "test-only" })).rejects.toMatchObject({ status: 401 });
    expect(expired).not.toHaveBeenCalled();
  });
  it("uses a user-facing connection error without development server wording", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api("/campaigns")).rejects.toThrow("인터넷 연결");
    await expect(api("/campaigns")).rejects.not.toThrow("개발 서버");
  });
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
      "X-Moduyuga-Client": "web",
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
