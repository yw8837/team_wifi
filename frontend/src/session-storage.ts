/** Explicit device persistence; never store profiles or social-provider tokens. */
export const SESSION_TOKEN_KEY = "moduyuga.session";
export const OAUTH_PROOF_PREFIX = "moduyuga.oauth.";
const REMEMBER_KEY = "moduyuga.remember-login";
let authRevision = 0;

export function invalidateSessionAttempts(): void { authRevision += 1; }

function store(kind: "sessionStorage" | "localStorage"): Storage | undefined {
  try { return globalThis[kind]; } catch { return undefined; }
}

export function rememberLogin(): boolean {
  try { return store("localStorage")?.getItem(REMEMBER_KEY) === "1"; } catch { return false; }
}

export function setRememberLogin(remember: boolean): void {
  try {
    if (remember) {
      const persistent = store('localStorage');
      if (!persistent) throw new Error('unavailable');
      persistent.setItem(REMEMBER_KEY, '1');
      if (persistent.getItem(REMEMBER_KEY) !== '1') throw new Error('not_saved');
    }
    else {
      const persistent = store('localStorage');
      persistent?.removeItem(REMEMBER_KEY);
      if (persistent?.getItem(REMEMBER_KEY) === '1') throw new Error('not_removed');
    }
  } catch { throw new Error('이 브라우저에서는 로그인 유지를 선택할 수 없어요. 현재 탭으로 로그인해 주세요.'); }
}

export function readSessionToken(): string | null {
  // An unreadable tab is not an empty tab. Never switch principals on a storage error.
  try {
    const tab = store('sessionStorage');
    if (!tab) return null;
    const token = tab.getItem(SESSION_TOKEN_KEY);
    if (token !== null) return typeof token === 'string' && token ? token : null;
    const remembered = store('localStorage')?.getItem(SESSION_TOKEN_KEY);
    return typeof remembered === 'string' && remembered ? remembered : null;
  } catch { return null; }
}

export function readTabSessionToken(): string | null {
  try { return store('sessionStorage')?.getItem(SESSION_TOKEN_KEY) || null; } catch { return null; }
}

/** A pending response is valid only for the session and component that started it. */
export function createSessionAttempt() {
  let generation = 0, active = true;
  return {
    cancel: () => { generation += 1; },
    setActive: (value: boolean) => { active = value; },
    begin: () => {
      const expectedToken = readSessionToken(), current = ++generation, revision = authRevision;
      return { expectedToken, isCurrent: () => active && current === generation && revision === authRevision && readSessionToken() === expectedToken };
    },
  };
}

function discardOAuthProofs(): void {
  const tab = store('sessionStorage');
  if (!tab) return;
  const keys = typeof tab.key === 'function'
    ? Array.from({ length: tab.length }, (_, index) => tab.key(index)).filter((key): key is string => !!key && key.startsWith(OAUTH_PROOF_PREFIX))
    : Object.keys(tab).filter(key => key.startsWith(OAUTH_PROOF_PREFIX));
  for (const key of keys) {
    tab.removeItem(key);
    if (tab.getItem(key) !== null) throw new Error('proof_not_removed');
  }
}

export function clearSessionToken(expected?: string | null): boolean {
  // A late failure for an older session must not erase a newly signed-in account.
  const current = readSessionToken();
  if (expected !== undefined && current !== expected) return false;
  invalidateSessionAttempts();
  try {
    discardOAuthProofs();
    for (const kind of ["sessionStorage", "localStorage"] as const) {
      const value = store(kind);
      if (value?.getItem(SESSION_TOKEN_KEY) === current) value?.removeItem(SESSION_TOKEN_KEY);
    }
    return current === null || readSessionToken() !== current;
  } catch { return false; }
}

export function writeSessionToken(token: string): void {
  const remembered = rememberLogin();
  const target = store(remembered ? 'localStorage' : 'sessionStorage');
  const other = store(remembered ? 'sessionStorage' : 'localStorage');
  const previousToken = readSessionToken();
  let previousTarget: string | null = null, previousOther: string | null = null;
  let targetRead = false, targetWriteAttempted = false, otherRead = false, otherRemovalAttempted = false;
  const restore = (storage: Storage | undefined, previous: string | null, ownedValue: string | null) => {
    if (!storage) return;
    try {
      let current: string | null | undefined;
      try { current = storage.getItem(SESSION_TOKEN_KEY); } catch { /* Restore the known pre-write value if read-back is denied. */ }
      if (current !== undefined && current !== ownedValue) return;
      if (previous === null) storage.removeItem(SESSION_TOKEN_KEY);
      else storage.setItem(SESSION_TOKEN_KEY, previous);
    } catch { /* A denied store cannot be repaired by the client. */ }
  };
  try {
    if (!target) throw new Error('unavailable');
    previousTarget = target.getItem(SESSION_TOKEN_KEY);
    if (previousTarget !== null && typeof previousTarget !== 'string') throw new Error('unreadable');
    targetRead = true;
    targetWriteAttempted = true;
    target.setItem(SESSION_TOKEN_KEY, token);
    if (target.getItem(SESSION_TOKEN_KEY) !== token) throw new Error('not_saved');
    if (other) {
      previousOther = other.getItem(SESSION_TOKEN_KEY);
      if (previousOther !== null && typeof previousOther !== 'string') throw new Error('unreadable');
      otherRead = true;
      if (previousToken !== null && previousOther === previousToken) {
        otherRemovalAttempted = true;
        other.removeItem(SESSION_TOKEN_KEY);
      }
    }
    if (readSessionToken() !== token) throw new Error('not_current');
    discardOAuthProofs();
    invalidateSessionAttempts();
  } catch {
    if (targetRead && targetWriteAttempted) restore(target, previousTarget, token);
    if (otherRead && otherRemovalAttempted) restore(other, previousOther, null);
    throw new Error(remembered
      ? '이 브라우저에서는 로그인 상태를 보관할 수 없어요. 로그인 유지를 끄고 다시 로그인해 주세요.'
      : '브라우저 저장소를 사용할 수 없어 로그인을 완료하지 못했어요. 저장소 설정을 확인해 주세요.');
  }
}

export async function sessionFingerprint(): Promise<string> {
  const data = new TextEncoder().encode(readSessionToken() || 'signed-out');
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', data))].map(n => n.toString(16).padStart(2, '0')).join('');
}
