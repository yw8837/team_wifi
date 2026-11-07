import { useState } from "react";
import { useContentRequest } from "./content-session";
import { Feedback, Field, useAction, useAuth } from "./shared";
import type { User } from "./types";

export function ProfileSettings() {
  const { user, updateProfile } = useAuth();
  const [nickname, setNickname] = useState(user?.nickname || "");
  const action = useAction(), request = useContentRequest();
  const trimmed = nickname.trim();
  const length = Array.from(trimmed).length;
  return <section className="panel" aria-labelledby="profile-settings-title">
    <h2 id="profile-settings-title">프로필 설정</h2>
    <form aria-label="프로필 설정" onSubmit={event => {
      event.preventDefault();
      if (length < 2 || length > 30 || trimmed === user?.nickname) return;
      void action.run(async () => {
        const updated = await request<User>("/auth/profile", "PUT", { nickname: trimmed });
        updateProfile(updated);
        setNickname(updated.nickname);
      }, "닉네임을 변경했어요.");
    }}>
      <Field label="닉네임" autoComplete="nickname" value={nickname} disabled={action.busy}
        hint="글·댓글에 표시할 이름을 2~30자로 입력하세요."
        onChange={event => { setNickname(event.target.value); action.setError(""); action.setMessage(""); }}/>
      <p className="hint">모두의 육아에서 사용하는 이름이에요. 카카오 프로필 이름은 바뀌지 않아요.</p>
      <button disabled={action.busy || length < 2 || length > 30 || trimmed === user?.nickname}>
        {action.busy ? "저장 중…" : "닉네임 저장"}
      </button>
      <Feedback {...action}/>
    </form>
  </section>;
}
