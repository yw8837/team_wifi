import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearSessionToken, createSessionAttempt, invalidateSessionAttempts, OAUTH_PROOF_PREFIX, readSessionToken, rememberLogin, sessionFingerprint, SESSION_TOKEN_KEY, setRememberLogin, writeSessionToken } from "./session-storage";

function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); },
    removeItem: key => { values.delete(key); }, clear: () => values.clear(), key: index => [...values.keys()][index] ?? null,
    get length() { return values.size; } };
}

describe("explicit session persistence", () => {
  beforeEach(() => { vi.stubGlobal("sessionStorage", memoryStorage()); vi.stubGlobal("localStorage", memoryStorage()); });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the default login only in the current tab", () => {
    expect(rememberLogin()).toBe(false);
    writeSessionToken("tab-token");
    expect(localStorage.getItem(SESSION_TOKEN_KEY)).toBeNull();
    sessionStorage.clear();
    expect(readSessionToken()).toBeNull();
  });

  it("resumes an opted-in session after tab storage is recreated and clears on logout", () => {
    setRememberLogin(true);
    writeSessionToken("remembered-token");
    vi.stubGlobal("sessionStorage", memoryStorage());
    expect(readSessionToken()).toBe("remembered-token");
    clearSessionToken();
    expect(readSessionToken()).toBeNull();
    expect(localStorage.getItem(SESSION_TOKEN_KEY)).toBeNull();
  });

  it("does not resurrect a prior remembered account when selecting tab-only login", () => {
    setRememberLogin(true); writeSessionToken("old-account");
    setRememberLogin(false); writeSessionToken("new-account");
    sessionStorage.clear();
    expect(readSessionToken()).toBeNull();
  });

  it("ignores late expiration for a replaced session", () => {
    writeSessionToken("new-session");
    clearSessionToken("old-session");
    expect(readSessionToken()).toBe("new-session");
  });

  it("reports denied persistence without claiming a saved login", () => {
    setRememberLogin(true);
    vi.spyOn(localStorage, "setItem").mockImplementation(() => { throw new Error("denied"); });
    expect(() => writeSessionToken("not-saved")).toThrow("로그인 유지를 끄고");
    expect(readSessionToken()).toBeNull();
  });

  it('rejects a denied tab store and never reports an unpersisted token', () => {
    vi.stubGlobal('sessionStorage', undefined);
    Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, get: () => { throw new Error('blocked'); } });
    expect(() => writeSessionToken('unpersisted')).toThrow('저장소');
    localStorage.setItem(SESSION_TOKEN_KEY, 'valid-other-store');
    expect(readSessionToken()).toBeNull();
    expect(localStorage.getItem(SESSION_TOKEN_KEY)).toBe('valid-other-store');
  });

  it('rejects silent writes while preserving the previous session', () => {
    writeSessionToken('old-valid');
    vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => {});
    expect(() => writeSessionToken('not-written')).toThrow('저장소');
    expect(readSessionToken()).toBe('old-valid');
  });

  it('does not switch to remembered A or remove tab B when the tab getter is denied', () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY,'tab-B');localStorage.setItem(SESSION_TOKEN_KEY,'remembered-A');
    const rawGet=sessionStorage.getItem.bind(sessionStorage),remove=vi.spyOn(sessionStorage,'removeItem'),write=vi.spyOn(sessionStorage,'setItem');
    vi.spyOn(sessionStorage,'getItem').mockImplementation(()=>{throw new Error('read denied');});
    expect(readSessionToken()).toBeNull();expect(()=>writeSessionToken('new-C')).toThrow('저장소');
    expect(rawGet(SESSION_TOKEN_KEY)).toBe('tab-B');expect(localStorage.getItem(SESSION_TOKEN_KEY)).toBe('remembered-A');expect(remove).not.toHaveBeenCalled();expect(write).not.toHaveBeenCalled();
  });

  it('restores a known prior target after read-back denial without claiming success', () => {
    writeSessionToken('old-B');const get=sessionStorage.getItem.bind(sessionStorage),put=sessionStorage.setItem.bind(sessionStorage);let denied=false;
    vi.spyOn(sessionStorage,'getItem').mockImplementation(key=>{if(denied)throw new Error('readback denied');return get(key);});
    vi.spyOn(sessionStorage,'setItem').mockImplementation((key,value)=>{put(key,value);if(value==='new-C')denied=true;});
    expect(()=>writeSessionToken('new-C')).toThrow('저장소');expect(get(SESSION_TOKEN_KEY)).toBe('old-B');
  });

  it('does not overwrite a newer observed target while rolling back a failed login', () => {
    writeSessionToken('old-A');const put=sessionStorage.setItem.bind(sessionStorage);
    vi.spyOn(sessionStorage,'setItem').mockImplementation((key,value)=>{put(key,value);if(value==='attempt-C')put(key,'newer-B');});
    expect(()=>writeSessionToken('attempt-C')).toThrow('저장소');expect(readSessionToken()).toBe('newer-B');
  });

  it('does not revive an anonymous attempt after another account logs in and out', () => {
    const old=createSessionAttempt().begin();writeSessionToken('account-B');expect(old.isCurrent()).toBe(false);clearSessionToken('account-B');expect(readSessionToken()).toBeNull();expect(old.isCurrent()).toBe(false);
  });

  it('invalidates unchanged-token attempts on a cross-tab auth event', () => {
    writeSessionToken('tab-A');const old=createSessionAttempt().begin();invalidateSessionAttempts();expect(readSessionToken()).toBe('tab-A');expect(old.isCurrent()).toBe(false);
  });

  it('discards OAuth proofs on successful login/logout while preserving unrelated drafts', () => {
    sessionStorage.setItem(OAUTH_PROOF_PREFIX+'old-flow','synthetic-proof');sessionStorage.setItem('unrelated-draft','keep');writeSessionToken('account-B');expect(sessionStorage.getItem(OAUTH_PROOF_PREFIX+'old-flow')).toBeNull();
    sessionStorage.setItem(OAUTH_PROOF_PREFIX+'next-flow','synthetic-proof');expect(clearSessionToken('account-B')).toBe(true);expect(sessionStorage.getItem(OAUTH_PROOF_PREFIX+'next-flow')).toBeNull();expect(sessionStorage.getItem('unrelated-draft')).toBe('keep');
  });

  it('retains a previous remembered session when a tab write is denied', () => {
    localStorage.setItem(SESSION_TOKEN_KEY, 'previous');
    vi.spyOn(sessionStorage, 'setItem').mockImplementation(() => { throw new Error('denied'); });
    expect(() => writeSessionToken('new')).toThrow('저장소');
    expect(readSessionToken()).toBe('previous');
  });

  it('does not delete an independent remembered B session when tab A logs out', () => {
    sessionStorage.setItem(SESSION_TOKEN_KEY, 'A');
    localStorage.setItem(SESSION_TOKEN_KEY, 'B');
    expect(clearSessionToken('A')).toBe(true);
    expect(readSessionToken()).toBe('B');
    expect(clearSessionToken('A')).toBe(false);
    expect(readSessionToken()).toBe('B');
  });

  it('discards responses after a replacement, newer request or unmount', async () => {
    writeSessionToken('A');
    const attempts = createSessionAttempt(), old = attempts.begin();
    const pending = Promise.resolve('late-login').then(() => {
      if (old.isCurrent()) writeSessionToken('late-A');
    });
    writeSessionToken('B');
    await pending;
    expect(readSessionToken()).toBe('B');
    const previous = attempts.begin(), latest = attempts.begin();
    expect(previous.isCurrent()).toBe(false);
    expect(latest.isCurrent()).toBe(true);
    attempts.setActive(false);
    expect(latest.isCurrent()).toBe(false);
    attempts.setActive(true); // React development effect replay retains the same attempt.
    expect(latest.isCurrent()).toBe(true);
    attempts.cancel();
    expect(latest.isCurrent()).toBe(false);
  });

  it('binds an OAuth return to a digest that changes with the session', async () => {
    const loggedOut = await sessionFingerprint();
    writeSessionToken('private-bearer-token');
    const loggedIn = await sessionFingerprint();
    expect(loggedIn).toMatch(/^[a-f0-9]{64}$/);
    expect(loggedIn).not.toContain('private-bearer');
    expect(loggedIn).not.toBe(loggedOut);
    clearSessionToken();
    expect(await sessionFingerprint()).toBe(loggedOut);
  });
});
