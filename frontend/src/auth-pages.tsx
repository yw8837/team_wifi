import { PUBLIC_RELEASE, DEPLOYED_MODE, publicBrowsePath, publicReturnPath } from "./release-policy";
import { useState } from "react";
import { BrandLockup } from "./brand";
import { IconArrowRight, IconBuildingStore } from "@tabler/icons-react";
import {
  Link,
  matchRoutes,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { api, safeReturnPath } from "./api";
import { BETA_MODE, BETA_NOTICE, BetaRecover, LegalLinks, RecoveryCodeNotice } from "./beta";
import { signupDestination } from "./beta-policy";
import type { User } from "./types";
import {
  Field,
  PasswordField,
  Feedback,
  PageTitle,
  useAction,
  useAuth,
} from "./shared";
type AuthResponse = { access_token: string; user: User; recovery_code?: string };
// Guest navigation must lead to an existing page outside Protected/auth routes.
const guestBrowseRoutes = [
  "/", "/welcome", "/hotdeals", "/brands", "/brands/:id", "/campaigns/:id", "/benefits", "/my",
].map((path) => ({ path }));
export function Welcome() {
  function seen() { localStorage.setItem("moduyuga.intro", "seen"); }
  return (
    <section className="welcome">
      <div className="welcome-emblem" aria-hidden="true">
        <img src="/brand/symbol.svg" alt="" width="860" height="714" />
      </div>
      <p className="eyebrow">함께 고르는 육아생활</p>
      <h1>필요한 육아템,<br />함께 준비해요.</h1>
      <p className="lead">공동구매의 조건은 꼼꼼하게,<br />육아 핫딜과 혜택은 한곳에서.</p>
      <div className="stack">
        <Link onClick={seen} className="button" to="/">육아템 둘러보기 <IconArrowRight size={20} aria-hidden="true" /></Link>
        <Link onClick={seen} className="button secondary" to="/signup?track=buyer">구매자로 시작</Link>
        <Link onClick={seen} className="seller-entry" to="/signup?track=seller"><IconBuildingStore size={18} aria-hidden="true" /> 판매자로 입점</Link>
        <Link onClick={seen} to="/login">기존 회원 로그인</Link>
      </div>
      <div className="welcome-note">
        <strong>먼저 살펴보고 결정하세요</strong>
        <p>가입 없이 가격·배송·환불 조건을 볼 수 있어요. 공동구매 참여는 결제가 아닌 모집 의사 표시입니다.</p>
      </div>
      <p className="muted">{BETA_MODE ? BETA_NOTICE : "개발용 서비스 · 실제 거래와 결제는 발생하지 않습니다."}</p>
      <LegalLinks />
    </section>
  );
}
export function Login() {
  const [params] = useSearchParams(),
    nav = useNavigate(),
    location = useLocation(),
    { setSession } = useAuth(),
    action = useAction();
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const to = PUBLIC_RELEASE ? publicReturnPath(safeReturnPath(params.get("returnTo"))) : safeReturnPath(params.get("returnTo"));
  return (
    <div className="narrow">
      <div className="auth-brand"><BrandLockup stacked /></div>
      <PageTitle title="다시 만나 반가워요">
        <p>로그인 후 보던 화면으로 돌아갑니다.</p>
      </PageTitle>
      <Link className="button secondary" to={PUBLIC_RELEASE ? publicBrowsePath(to) : matchRoutes(guestBrowseRoutes, to) ? to : "/"}>로그인 없이 둘러보기</Link>
      {location.state?.expired && (
        <p role="status" className="notice">
          로그인 세션이 만료되었습니다. 다시 로그인하면 보던 화면으로
          돌아갑니다.
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(async () => {
            const result = await api<AuthResponse>("/auth/login", "POST", {
              email,
              password,
            });
            setSession(result.access_token, result.user);
            nav(to, { replace: true });
          });
        }}
      >
        <Field
          label="이메일"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <PasswordField
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Feedback {...action} />
        <button disabled={action.busy}>
          {action.busy ? "로그인 중…" : "로그인"}
        </button>
      </form>
      <div className="link-row">
        <Link to={"/signup?returnTo=" + encodeURIComponent(to)}>회원가입</Link>
        <Link to="/reset">비밀번호 재설정</Link>
      </div>
      <p className="muted">
        {DEPLOYED_MODE ? "이메일 인증·소셜 로그인을 제공하지 않습니다. 비밀번호 분실 시 보관한 복구코드가 필요합니다." : "이 개발 빌드는 이메일 인증·소셜 로그인을 제공하지 않습니다."} 세션은 현재 탭 또는 앱 실행 동안 유지됩니다.
      </p>
    </div>
  );
}
export function Signup() {
  const [params, setParams] = useSearchParams(),
    nav = useNavigate(),
    { setSession } = useAuth(),
    action = useAction();
  const track = !PUBLIC_RELEASE && params.get("track") === "seller" ? "seller" : "buyer";
  const [form, setForm] = useState({
    email: "",
    password: "",
    nickname: "",
    terms_accepted: false,
    privacy_accepted: false,
    marketing_opt_in: false,
    invite_code: "",
    adult_confirmed: false,
  });
  const [pending, setPending] = useState<AuthResponse | null>(null);
  const to = PUBLIC_RELEASE ? publicReturnPath(safeReturnPath(params.get("returnTo"))) : safeReturnPath(params.get("returnTo"));
  if (pending?.recovery_code) return <div className="narrow"><RecoveryCodeNotice code={pending.recovery_code} onContinue={() => {
    setSession(pending.access_token, pending.user);
    setPending(null);
    nav(signupDestination(track, to), { replace: true });
  }} /></div>;
  return (
    <div className="narrow">
      <PageTitle
        title={track === "seller" ? "판매자로 시작하기" : "구매자로 시작하기"}
      >
        <p>{PUBLIC_RELEASE ? "정보 저장과 공구 수요·질문에 참여할 수 있어요. 로그인 후 직접 원하는 행동을 선택해 주세요." : "판매자도 같은 계정으로 구매 기능을 이용할 수 있어요."}</p>
      </PageTitle>
      {!PUBLIC_RELEASE && <div className="segmented">
        <button
          type="button"
          className={track === "buyer" ? "selected" : "secondary"}
          onClick={() =>
            setParams({ ...Object.fromEntries(params), track: "buyer" })
          }
        >
          구매자
        </button>
        <button
          type="button"
          className={track === "seller" ? "selected" : "secondary"}
          onClick={() =>
            setParams({ ...Object.fromEntries(params), track: "seller" })
          }
        >
          판매자
        </button>
      </div>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(async () => {
            const result = await api<AuthResponse>("/auth/register", "POST", {
              ...form,
              track,
            });
            setForm({ ...form, password: "", invite_code: "" });
            if (DEPLOYED_MODE) {
              if (!result.recovery_code) throw new Error("복구코드를 받지 못했습니다. 지원·문의에서 안내를 확인해 주세요.");
              setPending(result);
            } else {
              setSession(result.access_token, result.user);
              nav(signupDestination(track, to), { replace: true });
            }
          });
        }}
      >
        <Field
          label="이메일"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <PasswordField
          name="password"
          autoComplete="new-password"
          required
          minLength={10}
          maxLength={128}
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <p className="hint">비밀번호 10~128자. 붙여넣기를 사용할 수 있어요.</p>
        <Field
          label="닉네임"
          name="nickname"
          autoComplete="nickname"
          required
          minLength={2}
          maxLength={30}
          value={form.nickname}
          onChange={(e) => setForm({ ...form, nickname: e.target.value })}
        />
        {DEPLOYED_MODE ? <>
          {BETA_MODE && <Field label="초대코드" name="invite_code" autoComplete="off" autoCapitalize="none" spellCheck={false} required
            value={form.invite_code} onChange={(e) => setForm({ ...form, invite_code: e.target.value })} />}
          <label className="check"><input type="checkbox" required checked={form.adult_confirmed}
            onChange={(e) => setForm({ ...form, adult_confirmed: e.target.checked })} /><span>[필수] 만 18세 이상입니다.</span></label>
          <p className="notice">{PUBLIC_RELEASE ? "실제 주문·결제·배송은 제공하지 않습니다. 아이와 가족의 개인정보는 입력하지 마세요." : BETA_NOTICE + ". 실제 사업자 정보와 민감정보는 입력하지 마세요."}</p>
          <LegalLinks />
        </> : <details>
          <summary>개발용 이용약관 및 개인정보 안내</summary>
          <p>
            이 앱은 공동구매 모집·저장·질문과 개발용 혜택 흐름을 시험하는 로컬
            서비스입니다. 실제 결제·배송은 제공하지 않습니다. 이메일과 닉네임은
            계정 관리에, 입점 정보는 내부 심사에 사용됩니다. 탈퇴 시 프로필은
            익명화되며 운영 기록은 남을 수 있습니다. 실제 개인정보와 사업자
            서류는 입력하지 마세요.
          </p>
        </details>}
        {(
          (DEPLOYED_MODE ? ["terms_accepted", "privacy_accepted"] : ["terms_accepted", "privacy_accepted", "marketing_opt_in"]) as ("terms_accepted" | "privacy_accepted" | "marketing_opt_in")[]
        ).map((key, i) => (
          <label className="check" key={key}>
            <input
              type="checkbox"
              checked={form[key]}
              required={i < 2}
              onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
            />
            <span>
              {
                [
                  "[필수] 이용약관에 동의합니다",
                  "[필수] 개인정보 처리에 동의합니다",
                  "[선택] 마케팅 정보 수신에 동의합니다",
                ][i]
              }
            </span>
          </label>
        ))}
        <Feedback {...action} />
        <button disabled={action.busy}>
          {action.busy
            ? "계정 생성 중…"
            : track === "seller"
              ? "계정 만들고 입점 신청"
              : "계정 만들기"}
        </button>
      </form>
      <p>
        이미 계정이 있나요?{" "}
        <Link to={"/login?returnTo=" + encodeURIComponent(to)}>로그인</Link>
      </p>
    </div>
  );
}
export function Reset() {
  const action = useAction();
  const [email, setEmail] = useState(""),
    [token, setToken] = useState(""),
    [password, setPassword] = useState("");
  if (DEPLOYED_MODE) return <BetaRecover />;
  return (
    <div className="narrow">
      <PageTitle title="비밀번호 재설정">
        <p>로컬 개발용 복구 흐름입니다. 메일은 발송되지 않습니다.</p>
      </PageTitle>
      <section className="panel">
        <h2>1. 복구 요청</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              const result = await api<{ message: string }>(
                "/auth/reset-request",
                "POST",
                { email },
              );
              action.setMessage(result.message);
            });
          }}
        >
          <Field
            label="계정 이메일"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button disabled={action.busy}>복구 요청</button>
        </form>
      </section>
      <section className="panel">
        <h2>2. 새 비밀번호 설정</h2>
        <p className="muted">
          토큰은 개발 담당자가 로컬 서버 outbox 파일에서 확인합니다. 응답
          화면에는 노출하지 않습니다.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              const result = await api<{ message: string }>(
                "/auth/reset",
                "POST",
                { token, password },
              );
              action.setMessage(result.message);
              setToken("");
              setPassword("");
            });
          }}
        >
          <Field
            label="복구 토큰"
            name="token"
            autoComplete="off"
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <PasswordField
            label="새 비밀번호"
            name="new-password"
            autoComplete="new-password"
            required
            minLength={10}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button disabled={action.busy}>새 비밀번호 저장</button>
        </form>
      </section>
      <Feedback {...action} />
      <Link to="/login">로그인으로 돌아가기</Link>
    </div>
  );
}
