import { useState } from "react";
import { rememberLogin, setRememberLogin } from "./session-storage";

export function RememberLogin() {
  const [checked, setChecked] = useState(rememberLogin);
  const [error, setError] = useState('');
  return <div className="login-persistence">
    <label className="check"><input type="checkbox" checked={checked} onChange={event => {
      try { setRememberLogin(event.target.checked); setChecked(rememberLogin()); setError(''); }
      catch (e) { setError(e instanceof Error ? e.message : '로그인 유지 설정을 확인해 주세요.'); }
    }}/><span>이 기기에서 로그인 유지 <small>(선택)</small></span></label>
    <p className="hint">개인 기기에서 선택하세요. 선택하면 브라우저나 앱을 다시 열어도 최대 30일간 로그인하며, 로그아웃하면 해제됩니다.</p>
    {error && <p role="alert">{error}</p>}
  </div>;
}
