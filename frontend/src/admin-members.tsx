import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "./api";
import { communityTime, ListFeedback, periodError, useCommunityResource } from "./community";
import { Feedback, Field, PageTitle, PasswordField, useAction, useAuth } from "./shared";
import { useContentSessionAttempt } from "./content-session";
import { REAUTH_KEY, SocialButtons, type Provider } from "./social-auth";
import { usePublicResource } from "./release-data";

export type AdminMember = {id:string;nickname:string;is_admin:boolean;suspended:boolean;created_at:string;updated_at:string|null;revision:number};
type MemberState = {is_admin:boolean;suspended:boolean};
export type MemberHistory = {id:string;actor_id:string;actor_nickname:string;created_at:string;reason:string;before:MemberState;after:MemberState};
type MemberList = {items:AdminMember[];has_more:boolean};
type MemberDetail = {member:AdminMember;history:MemberHistory[];history_has_more:boolean};
export type MemberChange = MemberState & {revision:number;reason:string;password?:string;reauth_token?:string};
const pageNumber=(value:string|null)=>Math.max(0,Math.min(500,Math.floor(Number(value)||0)));
const roleLabel=(state:MemberState)=>state.is_admin?"운영자":"일반 회원";
const statusLabel=(state:MemberState)=>state.suspended?"이용 정지":"정상 이용";

export function AdminNavigation(){return <nav className="actions" aria-label="운영 업무"><NavLink end to="/admin">신고 관리</NavLink><NavLink to="/admin/groupbuys">공구 정보 관리</NavLink><NavLink to="/admin/members">회원 관리</NavLink><NavLink to="/admin/insights">서비스 분석</NavLink><NavLink to="/admin/assistant">챗봇 평가</NavLink></nav>;}
export function memberListQuery(params:URLSearchParams):string {
 const query=new URLSearchParams({q:params.get("q")||"",role:["member","operator"].includes(params.get("role")||"")?params.get("role")!:"all",status:["active","suspended"].includes(params.get("status")||"")?params.get("status")!:"all",limit:"20",offset:String(pageNumber(params.get("page"))*20)});
 for(const key of ["start_date","end_date"])if(params.get(key))query.set(key,params.get(key)!);
 return query.toString();
}
export function memberHistoryQuery(params:URLSearchParams):string {
 const query=new URLSearchParams({history_limit:"20",history_offset:String(pageNumber(params.get("history_page"))*20)});
 for(const key of ["history_start_date","history_end_date"])if(params.get(key))query.set(key,params.get(key)!);
 return query.toString();
}
function MemberPages({page,hasMore,change,label,disabled=false}:{page:number;hasMore:boolean;change:(page:number)=>void;label:string;disabled?:boolean}){
 if(!page&&!hasMore)return null;
 return <nav className="actions" aria-label={label}><button type="button" className="secondary" disabled={disabled||!page} onClick={()=>change(page-1)}>이전</button><span>{page+1}페이지</span><button type="button" className="secondary" disabled={disabled||!hasMore||page>=500} onClick={()=>change(page+1)}>다음</button></nav>;
}
export function AdminMembers(){
 const {user}=useAuth(),[params,setParams]=useSearchParams();
 const fromUrl=()=>({q:params.get("q")||"",role:params.get("role")||"all",status:params.get("status")||"all",start_date:params.get("start_date")||"",end_date:params.get("end_date")||""});
 const [draft,setDraft]=useState(fromUrl),[error,setError]=useState("");
 const appliedKey=JSON.stringify([params.get("q"),params.get("role"),params.get("status"),params.get("start_date"),params.get("end_date")]);
 useEffect(()=>{setDraft(fromUrl());setError("");},[appliedKey]);
 const invalid=periodError(params.get("start_date")||"",params.get("end_date")||"");
 const result=useCommunityResource<MemberList>(invalid?null:"/release/admin/members?"+memberListQuery(params),user?.id||"guest");
 const page=pageNumber(params.get("page"));
 return <><AdminNavigation/><PageTitle title="회원 관리"><p>닉네임 또는 계정 ID로 찾고 가입일을 기준으로 조회합니다. 계정 상세에서 권한과 정지 상태를 확인하세요.</p></PageTitle>
  <form className="community-filters" aria-label="회원 검색 조건" onSubmit={event=>{event.preventDefault();const problem=periodError(draft.start_date,draft.end_date);setError(problem);if(problem){(event.currentTarget.elements.namedItem("start_date") as HTMLInputElement|null)?.focus();return;}setParams({...draft,page:"0"});}}>
   <Field label="닉네임 또는 계정 ID" type="search" maxLength={100} value={draft.q} onChange={event=>setDraft({...draft,q:event.target.value})}/>
   <div className="community-period-inputs"><label className="field"><span>역할</span><select value={draft.role} onChange={event=>setDraft({...draft,role:event.target.value})}><option value="all">전체</option><option value="member">일반 회원</option><option value="operator">운영자</option></select></label><label className="field"><span>이용 상태</span><select value={draft.status} onChange={event=>setDraft({...draft,status:event.target.value})}><option value="all">전체</option><option value="active">정상 이용</option><option value="suspended">이용 정지</option></select></label></div>
   <fieldset className="community-period"><legend>기간</legend><div className="community-period-inputs"><Field label="가입 시작일 (한국 날짜)" name="start_date" type="date" value={draft.start_date} onChange={event=>setDraft({...draft,start_date:event.target.value})}/><Field label="가입 종료일 (한국 날짜)" name="end_date" type="date" value={draft.end_date} onChange={event=>setDraft({...draft,end_date:event.target.value})}/></div></fieldset>
   <p className="hint">가입일 기준으로 양끝 날짜를 포함합니다. 기본은 전체 기간이며 최근 변경일로 가입일을 대신하지 않습니다.</p>
   <div className="actions"><button>조건 적용</button><button type="button" className="secondary" onClick={()=>{setParams({});setDraft({q:"",role:"all",status:"all",start_date:"",end_date:""});setError("");}}>조건 초기화</button><button type="button" className="secondary" onClick={result.reload}>목록 새로고침</button></div>{(error||invalid)&&<p role="alert">{error||invalid}</p>}
  </form><ListFeedback {...result} retry={result.reload}/>
  {result.data?.items.map(member=><article className="panel" key={member.id}><h2><Link to={"/admin/members/"+encodeURIComponent(member.id)+"?list="+encodeURIComponent(params.toString())}>{member.nickname}</Link></h2><p>계정 ID: {member.id}</p><p>{roleLabel(member)} · {statusLabel(member)}</p><p>가입: {communityTime(member.created_at)}</p><p>최근 권한·정지 변경: {member.updated_at?communityTime(member.updated_at):"변경 기록 없음"}</p></article>)}
  {!result.loading&&!result.error&&result.data?.items.length===0&&<p className="state">이 조건에 맞는 회원이 없습니다.</p>}
  {result.data&&<MemberPages page={page} hasMore={result.data.has_more} label="회원 목록 페이지" disabled={result.loading||!!result.stale||!!invalid} change={next=>setParams({...Object.fromEntries(params),page:String(next)})}/>}
 </>;
}
export function memberChangeProblem(member:AdminMember,actorId:string,change:MemberChange):string {
 if(member.id===actorId)return "본인 계정의 권한과 정지 상태는 변경할 수 없습니다. 다른 운영자에게 요청하세요.";
 if(change.revision!==member.revision)return "회원 정보가 변경됐어요. 상세를 새로고침한 뒤 다시 확인해 주세요.";
 if(change.reason.trim().length<2||change.reason.trim().length>1000)return "변경 사유를 공백 제외 2자 이상 1000자 이내로 입력해 주세요.";
 if(member.is_admin&&change.suspended)return "운영자는 정지할 수 없습니다. 다른 운영자가 먼저 일반 회원으로 변경한 뒤 별도로 처리하세요.";
 if(change.is_admin&&change.suspended)return "운영자 권한과 이용 정지를 동시에 적용할 수 없습니다.";
 if(change.is_admin===member.is_admin&&change.suspended===member.suspended)return "현재 상태와 달라진 항목이 없습니다.";
 if(!change.password&&!change.reauth_token)return "운영자 본인의 비밀번호 또는 소셜 재인증이 필요합니다.";
 return "";
}
export async function applyMemberChange({member,actorId,change,isCurrent,confirm,request}:{member:AdminMember;actorId:string;change:MemberChange;isCurrent:()=>boolean;confirm:(message:string)=>boolean;request:(body:MemberChange)=>Promise<unknown>}):Promise<boolean>{
 if(!isCurrent())return false;
 const problem=memberChangeProblem(member,actorId,change);if(problem)throw new Error(problem);
 const grant=!member.is_admin&&change.is_admin?" 운영자는 회원 권한과 신고를 관리할 수 있습니다. 권한이 확대됩니다.":"";
 if(!confirm("계정 "+member.nickname+" · ID "+member.id+"의 상태를 ‘"+roleLabel(member)+" / "+statusLabel(member)+"’에서 ‘"+roleLabel(change)+" / "+statusLabel(change)+"’로 변경할까요?"+grant+" 대상의 기존 로그인 세션이 종료됩니다."))return false;
 if(!isCurrent())return false;
 try{await request({...change,reason:change.reason.trim()});}catch(error){if(isCurrent())throw error;return false;}
 return isCurrent();
}
function draftKey(actorId:string,memberId:string){return "moduyuga.member-change."+actorId+"."+memberId;}
function readDraft(actorId:string,member:AdminMember):{is_admin:boolean;suspended:boolean;reason:string}|null {
 try{const value=JSON.parse(sessionStorage.getItem(draftKey(actorId,member.id))||"null");return value&&value.revision===member.revision&&Date.now()-value.created<600000&&value.created<=Date.now()&&typeof value.is_admin==="boolean"&&typeof value.suspended==="boolean"&&typeof value.reason==="string"&&value.reason.length<=1000?value:null;}catch{return null;}
}
export function MemberChangeForm({member,onChanged,disabled=false}:{member:AdminMember;onChanged:()=>void;disabled?:boolean}){
 const {user}=useAuth(),location=useLocation(),action=useAction(),attempts=useContentSessionAttempt();
 const actorId=user?.id||"",saved=readDraft(actorId,member);
 const [isAdmin,setIsAdmin]=useState(saved?.is_admin??member.is_admin),[suspended,setSuspended]=useState(saved?.suspended??member.suspended),[reason,setReason]=useState(saved?.reason||""),[password,setPassword]=useState("");
 const connections=usePublicResource<{providers:Provider[];has_password:boolean}>("/auth/social/connections");
 const self=member.id===actorId;
 function saveDraft(){try{sessionStorage.setItem(draftKey(actorId,member.id),JSON.stringify({revision:member.revision,is_admin:isAdmin,suspended,reason,created:Date.now()}));}catch{/* Draft storage is optional; the controlled form remains usable. */}}
 return <section className="panel"><h2>권한·이용 상태 변경</h2><p>대상의 ID와 상태를 확인한 뒤 변경합니다.</p><form onSubmit={event=>{event.preventDefault();if(disabled)return;const attempt=attempts.begin();if(!attempt.isCurrent())return;void action.run(async()=>{
   let proof="";try{proof=sessionStorage.getItem(REAUTH_KEY)||"";}catch{/* Password can be used if local proof storage is unavailable. */}
   const changed=await applyMemberChange({member,actorId,change:{revision:member.revision,is_admin:isAdmin,suspended,reason,...(password?{password}:proof?{reauth_token:proof}:{})},isCurrent:attempt.isCurrent,confirm:message=>window.confirm(message),request:async body=>{if(body.reauth_token)sessionStorage.removeItem(REAUTH_KEY);try{return await api("/release/admin/members/"+encodeURIComponent(member.id),"PUT",body);}finally{if(attempt.isCurrent())setPassword("");}}});
   if(changed){try{sessionStorage.removeItem(draftKey(actorId,member.id));}catch{/* Successful server changes do not depend on optional draft storage. */}action.setMessage("회원의 권한·이용 상태를 변경했습니다.");onChanged();}
  });}}><fieldset disabled={disabled||action.busy||self}><legend>변경 대상: {member.nickname} · {member.id}</legend><label className="check"><input type="checkbox" checked={isAdmin} onChange={event=>setIsAdmin(event.target.checked)}/>운영자 권한 부여</label>{!member.is_admin&&isAdmin&&<p className="notice" role="alert">권한이 확대됩니다. 이 회원은 회원 관리와 신고 처리를 수행할 수 있게 됩니다.</p>}<label className="check"><input type="checkbox" disabled={member.is_admin||isAdmin} checked={suspended} onChange={event=>setSuspended(event.target.checked)}/>이용 정지</label>{member.is_admin&&<p className="hint">운영자는 정지할 수 없습니다. 다른 운영자가 먼저 일반 회원으로 변경한 뒤 별도로 처리하세요.</p>}
   <label className="field"><span>변경 사유 (필수)</span><textarea required minLength={2} maxLength={1000} rows={3} value={reason} onChange={event=>setReason(event.target.value)}/></label>
   <PasswordField label="운영자 본인의 비밀번호" autoComplete="current-password" value={password} onChange={event=>setPassword(event.target.value)}/><p className="hint">비밀번호를 설정하지 않았다면 연결한 소셜 계정으로 재인증하세요. 확인은 5분 동안 유효하며 변경 1회에만 사용됩니다.</p>
   <button disabled={action.busy||self}>대상과 변경 내용을 확인하고 적용</button></fieldset></form>
   {self&&<p className="notice">본인 계정의 권한과 정지 상태는 변경할 수 없습니다. 다른 운영자에게 요청하세요.</p>}
   {!self&&<fieldset disabled={disabled||action.busy} onClickCapture={saveDraft}><legend>소셜 계정으로 다시 인증</legend><SocialButtons purpose="reauth" to={location.pathname+location.search} only={connections.data?.providers||[]}/></fieldset>}{connections.error&&<p role="alert">연결한 인증 방식을 확인하지 못했습니다.{connections.error}</p>}<Feedback {...action}/>
  </section>;
}
function MemberHistoryFilters(){
 const [params,setParams]=useSearchParams(),fromUrl=()=>({start:params.get("history_start_date")||"",end:params.get("history_end_date")||""});
 const [draft,setDraft]=useState(fromUrl),[error,setError]=useState("");const applied=params.get("history_start_date")+"/"+params.get("history_end_date");
 useEffect(()=>{setDraft(fromUrl());setError("");},[applied]);
 return <form className="community-filters" aria-label="회원 변경 이력 기간" onSubmit={event=>{event.preventDefault();const problem=periodError(draft.start,draft.end);setError(problem);if(problem){(event.currentTarget.elements.namedItem("history_start_date") as HTMLInputElement|null)?.focus();return;}setParams({...Object.fromEntries(params),history_start_date:draft.start,history_end_date:draft.end,history_page:"0"});}}><fieldset className="community-period"><legend>기간</legend><div className="community-period-inputs"><Field label="처리 시작일 (한국 날짜)" name="history_start_date" type="date" value={draft.start} onChange={event=>setDraft({...draft,start:event.target.value})}/><Field label="처리 종료일 (한국 날짜)" name="history_end_date" type="date" value={draft.end} onChange={event=>setDraft({...draft,end:event.target.value})}/></div></fieldset><p className="hint">실제 처리일 기준으로 양끝 날짜를 포함합니다. 기본은 전체 기간입니다.</p><div className="actions"><button>이력 조건 적용</button><button type="button" className="secondary" onClick={()=>{const next=new URLSearchParams(params);["history_start_date","history_end_date","history_page"].forEach(key=>next.delete(key));setParams(next);setDraft({start:"",end:""});setError("");}}>이력 조건 초기화</button></div>{error&&<p role="alert">{error}</p>}</form>;
}
function memberListReturn(value:string|null){const parsed=new URLSearchParams(value||"");const query=new URLSearchParams();for(const key of ["q","role","status","start_date","end_date","page"])if(parsed.get(key))query.set(key,parsed.get(key)!);return "/admin/members"+(query.size?"?"+query:"");}
export function AdminMemberDetail(){
 const {id=""}=useParams(),{user}=useAuth(),[params,setParams]=useSearchParams();
 const invalid=periodError(params.get("history_start_date")||"",params.get("history_end_date")||"");
 const result=useCommunityResource<MemberDetail>(invalid?null:"/release/admin/members/"+encodeURIComponent(id)+"?"+memberHistoryQuery(params),user?.id||"guest");
 const data=result.data;
 return <><AdminNavigation/><PageTitle title="회원 계정 상세"><p><Link to={memberListReturn(params.get("list"))}>검색 조건을 유지하고 회원 목록으로</Link></p></PageTitle><button className="secondary" onClick={result.reload}>상세·이력 새로고침</button><ListFeedback {...result} retry={result.reload}/>{invalid&&<p role="alert">{invalid}</p>}
  {data&&<><section className="panel"><h2>{data.member.nickname}</h2><p>계정 ID: {data.member.id}</p><p>역할: {roleLabel(data.member)} · {statusLabel(data.member)}</p><p>가입: {communityTime(data.member.created_at)}</p><p>최근 권한·정지 변경: {data.member.updated_at?communityTime(data.member.updated_at):"변경 기록 없음"}</p></section>
   <MemberChangeForm key={data.member.id+":"+data.member.revision+":"+user?.id} member={data.member} disabled={result.stale||result.loading||!!invalid} onChanged={result.reload}/>
  </>}
  <h2>권한·이용 상태 변경 이력</h2><MemberHistoryFilters/>{data?.history.map(item=><article className="panel" key={item.id}><p>이력 ID: {item.id} · 대상 ID: {data.member.id}</p><p>처리: {communityTime(item.created_at)}</p><p>운영자: {item.actor_nickname} · {item.actor_id}</p><p>{roleLabel(item.before)} / {statusLabel(item.before)} → {roleLabel(item.after)} / {statusLabel(item.after)}</p><p className="ugc-text">사유: {item.reason}</p></article>)}
  {data&&!result.loading&&!result.error&&!data.history.length&&<p className="state">이 기간의 변경 이력이 없습니다.</p>}
  {data&&<MemberPages page={pageNumber(params.get("history_page"))} hasMore={data.history_has_more} label="회원 변경 이력 페이지" disabled={result.loading||!!result.stale||!!invalid} change={page=>setParams({...Object.fromEntries(params),history_page:String(page)})}/>}
 </>;
}
