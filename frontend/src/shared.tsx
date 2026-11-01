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
import type { User } from "./types";
type AuthValue = {
  user: User | null;
  loading: boolean;
  setSession: (token: string, user: User) => void;
  refresh: () => Promise<void>;
  clear: () => void;
  requireLogin: () => boolean;
};
const Auth = createContext<AuthValue>(null!);
export const useAuth = () => useContext(Auth);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(!!sessionStorage.getItem(TOKEN_KEY));
  const navigate = useNavigate(),
    loc = useLocation();
  const clear = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);
  const refresh = useCallback(async () => {
    if (!sessionStorage.getItem(TOKEN_KEY)) {
      setUser(null);
      return;
    }
    try {
      setUser(await api<User>("/me"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) clear();
    } finally {
      setLoading(false);
    }
  }, [clear]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const expired = () => {
      clear();
      if (!["/login", "/signup", "/reset"].includes(loc.pathname))
        navigate(
          "/login?returnTo=" +
            encodeURIComponent(safeReturnPath(loc.pathname + loc.search)),
          { replace: true, state: { expired: true } },
        );
    };
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, [clear, loc, navigate]);
  const value = {
    user,
    loading,
    clear,
    refresh,
    setSession: (token: string, u: User) => {
      sessionStorage.setItem(TOKEN_KEY, token);
      setUser(u);
      setLoading(false);
    },
    requireLogin: () => {
      if (user) return true;
      navigate(
        "/login?returnTo=" +
          encodeURIComponent(safeReturnPath(loc.pathname + loc.search)),
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
        <input {...props} type={show ? "text" : "password"} />
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
            encodeURIComponent(safeReturnPath(loc.pathname + loc.search))
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
