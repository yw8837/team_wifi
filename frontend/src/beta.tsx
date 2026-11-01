import { DEPLOYED_MODE } from "./release-policy";
import { useState } from "react";
import { api, API_BASE } from "./api";
import { Field, Feedback, PageTitle, PasswordField, useAction, useAuth, useResource } from "./shared";
import { useNavigate } from "react-router-dom";

export const BETA_MODE = import.meta.env.VITE_BETA_MODE === "1";
export const BETA_NOTICE = "비공개 베타 · 실제 결제·배송 없음 · 포인트·쿠폰은 시험용";
const legalPages = [
  ["terms", "이용약관"], ["privacy", "개인정보 처리방침"],
  ["deletion", "계정·데이터 삭제 안내"], ["support", "지원·문의"],
] as const;
type Config = { legal: Partial<Record<typeof legalPages[number][0], string>> };

export function legalUrl(page: string, configured?: string): string {
  const base = new URL(API_BASE, window.location.origin);
  // Legal documents are served by the configured API origin, never an arbitrary remote URL.
  const path = configured === `/legal/${page}` ? configured : `/legal/${page}`;
  return new URL(path, base.origin).href;
}

export function LegalLinks() {
  const config = useResource<Config>(DEPLOYED_MODE ? "/config" : null);
  if (!DEPLOYED_MODE) return null;
  return <nav className="legal-links" aria-label="이용 안내">
    {legalPages.map(([key, label]) => <a key={key} href={legalUrl(key, config.data?.legal?.[key])}
      target="_blank" rel="noopener noreferrer">{label} ↗</a>)}
  </nav>;
}

export function RecoveryCodeNotice({ code, onContinue, continueLabel = "확인하고 계속" }: {
  code: string; onContinue: () => void; continueLabel?: string;
}) {
  const [acknowledged, setAcknowledged] = useState(false);
  return <section className="panel recovery-notice" aria-labelledby="recovery-title">
    <h1 id="recovery-title">복구코드를 안전하게 보관해 주세요</h1>
    <p>이 코드는 지금 한 번만 표시되며 90일 동안 유효합니다. 비밀번호를 잊었을 때 필요하며 이메일로 발송되지 않습니다.</p>
    <p>앱 밖의 안전한 곳에 직접 기록하세요. 다른 사람이나 문의 게시판에 공유하지 마세요. 이 화면을 떠나면 다시 볼 수 없습니다.</p>
    <code className="recovery-code" aria-label="새 복구코드">{code}</code>
    <form onSubmit={(e) => { e.preventDefault(); if (acknowledged) onContinue(); }}>
      <label className="check"><input type="checkbox" required checked={acknowledged}
        onChange={(e) => setAcknowledged(e.target.checked)} />
        <span>복구코드를 안전한 곳에 기록했고, 다시 표시되지 않는다는 점을 확인했습니다.</span></label>
      <button disabled={!acknowledged}>{continueLabel}</button>
    </form>
  </section>;
}

export function BetaRecover() {
  const action = useAction(), nav = useNavigate(), { clear } = useAuth();
  const [form, setForm] = useState({ email: "", recovery_code: "", password: "" });
  const [newCode, setNewCode] = useState("");
  if (newCode) return <div className="narrow"><RecoveryCodeNotice code={newCode}
    continueLabel="새 코드 확인 후 로그인" onContinue={() => { setNewCode(""); nav("/login", { replace: true }); }} /></div>;
  return <div className="narrow"><PageTitle title="복구코드로 비밀번호 재설정">
    <p>가입할 때 보관한 복구코드를 입력하세요. 재설정하면 모든 기기의 기존 로그인이 해제되고 복구코드가 바뀝니다.</p>
  </PageTitle><form onSubmit={(e) => { e.preventDefault(); void action.run(async () => {
    const result = await api<{ message: string; recovery_code: string }>("/auth/recover", "POST", form);
    clear();
    setForm({ email: "", recovery_code: "", password: "" });
    if (!result.recovery_code) throw new Error("새 복구코드를 받지 못했습니다. 지원·문의에서 안내를 확인해 주세요.");
    setNewCode(result.recovery_code);
  }); }}>
    <Field label="계정 이메일" name="email" type="email" autoComplete="email" required value={form.email}
      onChange={(e) => setForm({ ...form, email: e.target.value })} />
    <Field label="보관한 복구코드" name="recovery_code" autoComplete="off" autoCapitalize="none" spellCheck={false}
      required value={form.recovery_code} onChange={(e) => setForm({ ...form, recovery_code: e.target.value })} />
    <PasswordField label="새 비밀번호" name="new-password" autoComplete="new-password" required minLength={10}
      maxLength={128} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
    <p className="hint">복구코드도 잃어버렸다면 지원·문의에서 안내를 확인하세요. 코드를 문의 내용에 적지 마세요.</p>
    <Feedback {...action} /><button disabled={action.busy}>{action.busy ? "재설정 중…" : "비밀번호 재설정"}</button>
  </form><LegalLinks /></div>;
}

export function BetaRecoveryCodeSettings() {
  const action = useAction();
  const [password, setPassword] = useState(""), [newCode, setNewCode] = useState("");
  if (newCode) return <RecoveryCodeNotice code={newCode} continueLabel="새 코드 확인 완료" onContinue={() => {
    setNewCode("");
    action.setMessage("새 복구코드를 확인했습니다. 이전 코드는 더 이상 사용할 수 없습니다.");
  }} />;
  return <section className="panel" aria-labelledby="renew-recovery-title">
    <h2 id="renew-recovery-title">복구코드 다시 발급</h2>
    <p>가입할 때 복구코드를 보관하지 못했거나 잃어버렸다면 현재 비밀번호를 확인하고 새 코드를 발급받으세요.</p>
    <p className="notice">새 코드를 발급하면 이전 복구코드는 즉시 사용할 수 없게 됩니다. 새 코드는 90일 동안 유효하며 한 번만 표시됩니다. 현재 로그인은 유지됩니다.</p>
    <form onSubmit={(e) => {
      e.preventDefault();
      void action.run(async () => {
        const result = await api<{ message: string; recovery_code: string }>("/auth/recovery-code", "POST", { password });
        setPassword("");
        if (!result.recovery_code) throw new Error("새 복구코드를 받지 못했습니다. 지원·문의에서 안내를 확인해 주세요.");
        setNewCode(result.recovery_code);
      });
    }}>
      <fieldset disabled={action.busy}><legend className="sr-only">복구코드 재발급 비밀번호 확인</legend>
        <PasswordField label="복구코드 재발급을 위한 현재 비밀번호" name="recovery-code-password"
          autoComplete="current-password" required minLength={10} maxLength={128} value={password}
          onChange={(e) => setPassword(e.target.value)} />
        <button disabled={action.busy}>{action.busy ? "새 코드 발급 중…" : "이전 코드를 폐기하고 새 코드 발급"}</button>
      </fieldset>
    </form>
    <Feedback {...action} />
  </section>;
}
