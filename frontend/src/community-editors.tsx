import { useState } from "react";
import { api, categories } from "./api";
import { Feedback, Field, useAction } from "./shared";
import { releasePath } from "./release-data";
import type { Comment, Demand } from "./release-data";

export function DemandEditor({ item, onSaved, onCancel }: { item: Demand; onSaved: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({ title: item.title, body: item.body, category: item.category });
  const action = useAction();
  return <form aria-label="내 글 수정" onSubmit={e => {
    e.preventDefault();
    void action.run(async () => {
      await api(releasePath("demands", item.id), "PUT", { ...form, revision: item.revision ?? 1 });
      onSaved();
    });
  }}>
    <fieldset disabled={action.busy}>
      <legend>내 글 수정</legend>
      <Field label="제목" autoFocus required minLength={3} maxLength={120} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })}/>
      <label className="field"><span>카테고리</span><select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
        {[...new Set([...categories, form.category])].map(c => <option key={c}>{c}</option>)}
      </select></label>
      <label className="field"><span>필요한 제품과 질문</span><textarea required minLength={10} maxLength={3000} rows={7} value={form.body} onChange={e => setForm({ ...form, body: e.target.value })}/></label>
      <p className="hint">수정해도 기존 관심과 댓글은 유지돼요. 아이와 가족의 개인정보는 적지 마세요.</p>
      <div className="actions"><button type="submit">{action.busy ? "저장 중…" : "수정 저장"}</button><button type="button" className="secondary" onClick={onCancel}>수정 취소</button></div>
    </fieldset>
    <Feedback {...action}/>
  </form>;
}

export function CommentEditor({ item, onSaved, onCancel }: { item: Comment; onSaved: () => void; onCancel: () => void }) {
  const [body, setBody] = useState(item.body);
  const action = useAction();
  return <form aria-label="내 댓글 수정" onSubmit={e => {
    e.preventDefault();
    void action.run(async () => {
      await api(releasePath("comments", item.id), "PUT", { body, revision: item.revision ?? 1 });
      onSaved();
    });
  }}>
    <fieldset disabled={action.busy}>
      <legend>내 댓글 수정</legend>
      <label className="field"><span>댓글 내용</span><textarea autoFocus required minLength={2} maxLength={1000} rows={3} value={body} onChange={e => setBody(e.target.value)}/></label>
      <div className="actions"><button type="submit">{action.busy ? "저장 중…" : "수정 저장"}</button><button type="button" className="secondary" onClick={onCancel}>수정 취소</button></div>
    </fieldset>
    <Feedback {...action}/>
  </form>;
}
