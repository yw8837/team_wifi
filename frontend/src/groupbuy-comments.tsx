import { useState } from "react";
import { Link } from "react-router-dom";
import { CommentEditor } from "./community-editors";
import { communityTime, ListFeedback, useCommunityResource } from "./community";
import { useContentRequest } from "./content-session";
import { Moderation } from "./public-app";
import type { Comment } from "./release-data";
import { Feedback, useAction, useAuth } from "./shared";

export function GroupbuyComments({id}:{id:string}) {
  const {user,requireLogin}=useAuth();
  const [page,setPage]=useState(0),[body,setBody]=useState(""),[editing,setEditing]=useState<string|null>(null);
  const action=useAction(),request=useContentRequest();
  const path="/release/groupbuys/"+encodeURIComponent(id)+"/comments";
  const result=useCommunityResource<Comment[]>(path+"?limit=20&offset="+page*20,user?.id||"guest");
  return <section className="comments" aria-labelledby="groupbuy-comments-title">
    <h2 id="groupbuy-comments-title">이 육아템, 함께 이야기해요</h2>
    <p>구성·사용법이 궁금하거나 직접 사용한 경험이 있다면 남겨 주세요.</p>
    <Link to="/demands">커뮤니티 게시판 보기</Link>
    <ListFeedback {...result} retry={result.reload}/>
    {result.data?.map(comment=><article className="comment" id={"comment-"+comment.id} key={comment.id}>
      <p className="muted">{comment.author.nickname} · {communityTime(comment.created_at)}{comment.updated_at&&" · 수정 "+communityTime(comment.updated_at)}</p>
      {editing===comment.id&&comment.own?<CommentEditor item={comment} onSaved={()=>{setEditing(null);result.reload();}} onCancel={()=>setEditing(null)}/>:<>
        <p className="ugc-text">{comment.body}</p>
        {comment.own&&<button type="button" className="secondary" onClick={()=>setEditing(comment.id)}>내 댓글 수정</button>}
      </>}
      <Moderation kind="comment" id={comment.id} author={comment.author} own={comment.own} preview={comment.body}
        sourceHref={"/groupbuys/"+encodeURIComponent(id)+"#comment-"+comment.id} onChange={result.reload}
        onDelete={async()=>{await request("/release/comments/"+encodeURIComponent(comment.id),"DELETE");result.reload();}}/>
    </article>)}
    {!result.loading&&!result.error&&!result.data?.length&&<p>아직 댓글이 없어요. 첫 질문이나 경험을 나눠 주세요.</p>}
    {(page>0||(result.data?.length||0)>=20)&&<nav className="actions" aria-label="공구 댓글 페이지">
      <button className="secondary" disabled={page===0||result.loading} onClick={()=>setPage(page-1)}>이전</button>
      <span>{page+1}페이지</span>
      <button className="secondary" disabled={(result.data?.length||0)<20||result.loading||page>=500} onClick={()=>setPage(page+1)}>다음</button>
    </nav>}
    <p className="hint" id="groupbuy-comment-privacy">연락처·주소·아이의 개인정보를 적지 마세요. 주문·배송 문의는 판매처 고객센터에서 확인해 주세요.</p>
    <form aria-describedby="groupbuy-comment-privacy" onSubmit={event=>{
      event.preventDefault();
      if(requireLogin())void action.run(async()=>{
        await request(path,"POST",{body});setBody("");setPage(0);result.reload();
      },"댓글을 등록했습니다.");
    }}>
      <label className="field"><span>댓글 작성</span><textarea required minLength={2} maxLength={1000} rows={3} value={body} onChange={event=>setBody(event.target.value)}/></label>
      <button disabled={action.busy}>{user?"댓글 등록":"로그인하고 댓글 등록"}</button>
    </form>
    <Feedback {...action}/>
  </section>;
}
