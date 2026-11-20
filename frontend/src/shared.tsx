import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode, InputHTMLAttributes } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { api, ApiError, TOKEN_KEY, safeReturnPath } from "./api";
import { clearSessionToken, createSessionAttempt, invalidateSessionAttempts, readSessionToken, readTabSessionToken, writeSessionToken } from "./session-storage";
import type { User } from "./types";
type AuthValue = {
  user: User | null;
  loading: boolean;
  setSession: (token: string, user: User, expectedToken?: string | null) => void;
  updateProfile: (user: User) => void;
  refresh: () => Promise<void>;
  clear: (expectedToken?: string | null) => boolean;
  requireLogin: () => boolean;
};
const Auth = createContext<AuthValue>(null!);
export const useAuth = () => useContext(Auth);
export function useSessionAttempt() {
  const attempt = useRef(createSessionAttempt());
  useEffect(() => {
    attempt.current.setActive(true);
    return () => attempt.current.setActive(false);
  }, []);
  return attempt.current;
}
export function AuthProvider({ children }: { children: ReactNode }) {
  const refreshAttempts = useSessionAttempt();
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(!!readSessionToken());
  const navigate = useNavigate(),
    loc = useLocation();
  const refreshCurrent = useRef<(() => Promise<void>) | null>(null);
  const clear = useCallback((expectedToken?: string | null) => {
    if (!clearSessionToken(expectedToken)) return false;
    setUser(null);
    setLoading(!!readSessionToken());
    if (readSessionToken()) void refreshCurrent.current?.();
    return true;
  }, []);
  const refresh = useCallback(async () => {
    const attempt = refreshAttempts.begin(), requestedToken = attempt.expectedToken;
    if (!attempt.isCurrent()) return;
    if (!requestedToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const result = await api<User>("/me");
      if (attempt.isCurrent()) {
        setUser(result);
      }
    } catch (e) {
      if (e instanceof ApiError && [401, 403].includes(e.status) && attempt.isCurrent()) clear();
    } finally {
      if (attempt.isCurrent()) setLoading(false);
    }
  }, [clear, refreshAttempts]);
  refreshCurrent.current = refresh;
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key !== TOKEN_KEY && event.key !== null) return;
      // A tab-only login is independent; remembered sessions follow device logout.
      if (readTabSessionToken()) return;
      invalidateSessionAttempts();
      setUser(null);
      setLoading(!!readSessionToken());
      void refresh();
    };
    window.addEventListener("storage", changed);
    return () => window.removeEventListener("storage", changed);
  }, [refresh]);
  useEffect(() => {
    const expired = (event: Event) => {
      // api() already removed the failed token. A separate remembered session
      // may now be visible, so never clear storage for a second time here.
      setUser(null);
      void refresh();
      const shouldRedirect = (event as CustomEvent<{ redirect?: boolean }>).detail?.redirect === true;
      if (shouldRedirect && !readSessionToken() && !["/login", "/signup", "/reset"].includes(loc.pathname))
        navigate(
          "/login?returnTo=" +
            encodeURIComponent(safeReturnPath(loc.pathname + loc.search + loc.hash)),
          { replace: true, state: { expired: true } },
        );
    };
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, [refresh, loc, navigate]);
  const value = {
    user,
    loading,
    clear,
    refresh,
    updateProfile: (updated: User) => {
      // A late save must never recreate a logged-out or switched account.
      setUser(current => current?.id === updated.id ? { ...current, nickname: updated.nickname } : current);
    },
    setSession: (token: string, u: User, expectedToken?: string | null) => {
      if (expectedToken !== undefined && readSessionToken() !== expectedToken) {
        throw new Error('다른 로그인으로 계정 상태가 변경됐어요. 현재 계정을 확인하고 다시 진행해 주세요.');
      }
      writeSessionToken(token);
      setUser(u);
      setLoading(false);
    },
    requireLogin: () => {
      if (user && readSessionToken()) return true;
      navigate(
        "/login?returnTo=" +
          encodeURIComponent(safeReturnPath(loc.pathname + loc.search + loc.hash)),
      );
      return false;
    },
  };
  return <Auth.Provider value={value}>{children}</Auth.Provider>;
}
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(!!path),
    [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    let alive = true;
    if (!path) {
      setLoading(false);
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    api<T>(path)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, version]);
  return { data, error, loading, reload };
}
export function useAction() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const lock = useRef(false);
  async function run(work: () => Promise<unknown>, success?: string) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      if (success) setMessage(success);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "요청에 실패했습니다.");
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return { busy, error, message, setError, setMessage, run };
}
export function Feedback({
  error,
  message,
  busy,
}: {
  error?: string;
  message?: string;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) ref.current?.focus();
  }, [error]);
  return (
    <>
      {busy && (
        <p role="status" className="muted">
          요청을 처리하고 있습니다. 잠시 기다려 주세요…
        </p>
      )}
      {error && (
        <div ref={ref} tabIndex={-1} role="alert" className="feedback error">
          {error}
        </div>
      )}
      {message && (
        <div role="status" className="feedback success">
          {message}
        </div>
      )}
    </>
  );
}
export function ResourceState({
  loading,
  error,
  empty,
  retry,
}: {
  loading: boolean;
  error: string;
  empty?: boolean;
  retry: () => void;
}) {
  if (loading)
    return (
      <p role="status" className="state">
        불러오는 중…
      </p>
    );
  if (error)
    return (
      <div className="state">
        <Feedback error={error} />
        <button className="secondary" onClick={retry}>
          다시 불러오기
        </button>
      </div>
    );
  if (empty)
    return (
      <p className="state">
        아직 표시할 내용이 없어요. 다른 조건도 살펴보세요.
      </p>
    );
  return null;
}
export function Field({
  label,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return (
    <label className="field">
      <span>
        {label}
        {props.required && <small> 필수</small>}
      </span>
      <input {...props} />
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}
export function PasswordField({
  label = "비밀번호",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  const [show, setShow] = useState(false);
  return (
    <label className="field">
      <span>{label}</span>
      <span className="password">
        <input {...props} aria-label={props['aria-label'] || label} type={show ? "text" : "password"} />
        <button
          type="button"
          className="text-button"
          aria-label={show ? "비밀번호 숨기기" : "비밀번호 표시"}
          onClick={() => setShow(!show)}
        >
          {show ? "숨기기" : "표시"}
        </button>
      </span>
    </label>
  );
}
export function Protected({
  children,
  admin = false,
}: {
  children: ReactNode;
  admin?: boolean;
}) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <p role="status">로그인 상태 확인 중…</p>;
  if (!user)
    return (
      <section className="panel">
        <h1>로그인이 필요해요</h1>
        <p>로그인 후 이 화면으로 돌아옵니다.</p>
        <Link
          className="button"
          to={
            "/login?returnTo=" +
            encodeURIComponent(safeReturnPath(loc.pathname + loc.search + loc.hash))
          }
        >
          로그인
        </Link>
      </section>
    );
  if (admin && !user.is_admin)
    return (
      <section className="panel">
        <h1>관리자 전용 화면</h1>
        <p>접근 권한이 없습니다.</p>
        <Link to="/">홈으로</Link>
      </section>
    );
  return children;
}
export function PageTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-title">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      {children}
    </header>
  );
}
