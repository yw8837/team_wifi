import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, categories } from "./api";
import { Field, PageTitle, useAction, Feedback, useAuth, useSessionAttempt } from "./shared";
import { readPublic } from "./release-data";
import type { Comment, Demand, PostType } from "./release-data";
import "./community.css";

export const postTypes:Record<PostType,string>={question:"질문",experience:"경험",information:"정보",demand:"공구 수요"};
export const postType=(post:Demand):PostType=>post.post_type??"demand";
export function periodError(start:string,end:string):string {
  const valid=(value:string)=>!value||/^\d{4}-\d{2}-\d{2}$/.test(value)&&!value.startsWith("0000-")&&!Number.isNaN(Date.parse(value+"T00:00:00Z"))&&new Date(value+"T00:00:00Z").toISOString().slice(0,10)===value;
  if(!valid(start)||!valid(end))return "날짜를 올바르게 입력해 주세요.";
  return start&&end&&start>end?"시작일은 종료일보다 늦을 수 없어요.":"";
}
export function communityQuery(params:URLSearchParams,activity=false):string {
 const page=Math.max(0,Math.min(500,Math.floor(Number(params.get("page"))||0)));
 const query=new URLSearchParams({q:params.get("q")||"",limit:"20",offset:String(page*20)});
 for(const key of ["start_date","end_date",...(activity?[]:["category","post_type"])])if(params.get(key))query.set(key,params.get(key)!);
 if(activity)query.set("tab",["posts","comments","interests"].includes(params.get("tab")||"")?params.get("tab")!:"posts");
 return query.toString();
}

// Retain a previous successful list on refresh failure, only within the same account.
// State is tagged before rendering as well as before applying asynchronous results.
export function useCommunityResource<T>(path:string|null,identity:string) {
 const [version,setVersion]=useState(0);
 const [state,setState]=useState<{identity:string;requested:string|null;dataPath:string|null;data:T|null;error:string;loading:boolean}>({identity,requested:path,dataPath:null,data:null,error:"",loading:!!path});
 useEffect(()=>{
  let live=true;
  setState(old=>({identity,requested:path,dataPath:old.identity===identity?old.dataPath:null,data:old.identity===identity?old.data:null,error:"",loading:!!path}));
  if(path)void readPublic<T>(path).then(data=>{if(live)setState({identity,requested:path,dataPath:path,data,error:"",loading:false});}).catch(error=>{if(live)setState(old=>({...old,error:error instanceof Error?error.message:"목록을 불러오지 못했어요.",loading:false}));});
  return()=>{live=false;};
 },[path,identity,version]);
 const scoped=state.identity===identity&&path!==null;
 return {data:scoped?state.data:null,error:scoped?state.error:"",loading:!!path&&(!scoped||state.requested!==path||state.loading),stale:scoped&&!!state.data&&(!!state.error||state.dataPath!==path),reload:()=>setVersion(v=>v+1)};
}

const communityClock=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Seoul",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"});
export function communityTime(value:string):string {
 const parsed=new Date(value);if(!value||Number.isNaN(parsed.getTime()))return "시각 미확인";
 const parts=Object.fromEntries(communityClock.formatToParts(parsed).map(part=>[part.type,part.value]));
 return `${parts.year}.${parts.month}.${parts.day} ${parts.hour}:${parts.minute}`;
}
export function communityFilterSummary(params:URLSearchParams,activity=false,history=false):{count:number;text:string} {
 const values:string[]=[];
 if(params.get("q"))values.push("검색: "+params.get("q"));
 if(!activity&&params.get("post_type"))values.push(postTypes[params.get("post_type") as PostType]||params.get("post_type")!);
 if(!activity&&params.get("category"))values.push(params.get("category")!);
 if(params.get("start_date")||params.get("end_date"))values.push((params.get("start_date")||"처음")+" ~ "+(params.get("end_date")||"현재"));
 if(history&&params.get("date_basis")==="action")values.push("처리일 기준");
 return {count:values.length,text:values.length?values.join(" · "):"전체 "+(history?"신고":activity?"활동":"이야기")+" · 전체 기간"};
}
export function CommunityFilters({activity=false,history=false}:{activity?:boolean;history?:boolean}) {
 const [params,setParams]=useSearchParams(),[error,setError]=useState("");const advanced=useRef<HTMLDetailsElement>(null);
 const fromUrl=()=>({q:params.get("q")||"",category:params.get("category")||"",post_type:params.get("post_type")||"",start_date:params.get("start_date")||"",end_date:params.get("end_date")||"",...(history?{date_basis:params.get("date_basis")==="action"?"action":"received"}:{})});
 const [draft,setDraft]=useState(fromUrl),applied=communityFilterSummary(params,activity,history);
 const appliedKey=JSON.stringify([params.get("q"),params.get("category"),params.get("post_type"),params.get("start_date"),params.get("end_date"),history?params.get("date_basis"):null]);
 useEffect(()=>{setDraft(fromUrl());setError("");},[appliedKey]);
 const periodBasis=history?"선택한 접수일 또는 처리일":activity&&params.get("tab")==="interests"?"관심 표시일":"작성일";
 return <form className="community-filters" aria-label={history?"신고 이력 검색 조건":activity?"내 활동 검색 조건":"커뮤니티 검색 조건"} onSubmit={event=>{event.preventDefault();const invalid=periodError(draft.start_date,draft.end_date);setError(invalid);if(invalid){if(advanced.current)advanced.current.open=true;(event.currentTarget.elements.namedItem("start_date") as HTMLInputElement|null)?.focus();return;}setParams({...Object.fromEntries(params),...draft,page:"0"});}}>
  <div className={"community-filter-primary"+(activity?" activity":"")}><Field label={history?"신고 검색":activity?"내 활동 검색":"커뮤니티 검색"} type="search" maxLength={100} value={draft.q} onChange={event=>setDraft({...draft,q:event.target.value})}/>
  {!activity&&<label className="field"><span>글 유형</span><select value={draft.post_type} onChange={event=>setDraft({...draft,post_type:event.target.value})}><option value="">전체</option>{Object.entries(postTypes).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>}<button type="submit">조건 적용</button></div>
  <details ref={advanced} className="community-advanced"><summary><strong>상세 조건</strong><span className="community-applied" aria-live="polite">적용 중 {applied.count}개 · {applied.text}</span></summary><div className="community-advanced-fields">
   {!activity&&<label className="field"><span>카테고리</span><select value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value})}><option value="">전체 분야</option>{categories.map(category=><option key={category}>{category}</option>)}</select></label>}
   {history&&<label className="field"><span>기간 기준</span><select value={draft.date_basis||"received"} onChange={event=>setDraft({...draft,date_basis:event.target.value})}><option value="received">신고 접수일</option><option value="action">신고 처리일</option></select></label>}
   <fieldset className="community-period"><legend>기간</legend><div className="community-period-inputs"><Field label="시작일 (한국 날짜)" name="start_date" type="date" value={draft.start_date} onChange={event=>setDraft({...draft,start_date:event.target.value})}/><Field label="종료일 (한국 날짜)" name="end_date" type="date" value={draft.end_date} onChange={event=>setDraft({...draft,end_date:event.target.value})}/></div></fieldset>
   <p className="hint">{periodBasis} 기준, 한국 시간으로 시작일과 종료일을 모두 포함해요. 기본은 전체 기간입니다.{history&&" 처리일 기준에는 아직 처리하지 않은 신고가 포함되지 않아요."}</p><div className="actions"><button type="submit">상세 조건 적용</button><button type="button" className="secondary" onClick={()=>{setDraft({q:"",category:"",post_type:"",start_date:"",end_date:"",...(history?{date_basis:"received"}:{})});setParams(params.get("tab")?{tab:params.get("tab")!,page:"0"}:{});}}>조건 초기화</button></div>
  </div></details>{error&&<p role="alert">{error}</p>}
 </form>;
}
export function ListFeedback({loading,error,stale,retry}:{loading:boolean;error:string;stale:boolean;retry:()=>void}) {
 return <>{loading&&<p role="status">목록을 불러오고 있어요.</p>}{error&&<div className="notice" role="alert"><p>{error}</p><p>{stale?"이전 검색 결과를 표시하고 있어요. 현재 검색 조건의 최신 목록이 아닙니다.":"목록을 확인하지 못했어요."}</p><button type="button" className="secondary" onClick={retry}>목록 다시 불러오기</button></div>}</>;
}
function ListPages({hasMore,disabled=false}:{hasMore:boolean;disabled?:boolean}) {
 const [params,setParams]=useSearchParams();const page=Math.max(0,Math.min(500,Math.floor(Number(params.get("page"))||0)));
 if(!page&&!hasMore)return null;
 return <nav className="actions" aria-label="목록 페이지"><button className="secondary" disabled={!page||disabled} onClick={()=>setParams({...Object.fromEntries(params),page:String(page-1)})}>이전</button><span>{page+1}페이지</span><button className="secondary" disabled={!hasMore||disabled||page>=500} onClick={()=>setParams({...Object.fromEntries(params),page:String(page+1)})}>다음</button></nav>;
}
export function CommunityFeed({renderItem}:{renderItem:(post:Demand,reload:()=>void)=>ReactNode}) {
 const {user}=useAuth(),[params]=useSearchParams();const invalid=periodError(params.get("start_date")||"",params.get("end_date")||"");
 const result=useCommunityResource<Demand[]>(invalid?null:"/release/demands?"+communityQuery(params),user?.id||"guest");
 return <section className="community-feed"><header className="community-heading"><div><h1>커뮤니티</h1><Link className="button" to="/demands/new">이야기 쓰기</Link></div><p>궁금한 점과 경험을 함께 나눠요.</p></header><nav className="actions community-board-tabs" aria-label="커뮤니티 게시판">{[["","전체"],...Object.entries(postTypes)].map(([key,label])=>{const query=new URLSearchParams(params);query.delete("page");if(key)query.set("post_type",key);else query.delete("post_type");return <Link key={key} className={"button"+(params.get("post_type")===key||(!params.get("post_type")&&!key)?"":" secondary")} aria-current={(params.get("post_type")||"")===key?"page":undefined} to={"/demands?"+query.toString()}>{label}</Link>;})}</nav><CommunityFilters/>{invalid&&<p role="alert">{invalid}</p>}<ListFeedback {...result} retry={result.reload}/>{result.data?.map(post=><div key={post.id}>{renderItem(post,result.reload)}</div>)}{!invalid&&!result.loading&&!result.error&&!result.data?.length&&<section className="panel"><h2>아직 조건에 맞는 이야기가 없어요</h2><p>다른 조건으로 찾아보거나 첫 이야기를 나눠 주세요.</p><Link to="/demands/new">첫 이야기 쓰기</Link></section>}{!!result.data?.length&&!result.stale&&<p className="hint">이 페이지에 {result.data.length}개의 이야기가 있어요.</p>}<ListPages hasMore={(result.data?.length||0)>=20} disabled={result.loading||result.stale||!!invalid}/></section>;
}
type Activity={tab:string;items:({post:Demand}|{comment:Comment;post_id:string;post_title:string;parent_kind?:"groupbuy"|"demand"})[];has_more:boolean};
export function MyActivity() {
 const {user}=useAuth(),[params,setParams]=useSearchParams();const invalid=periodError(params.get("start_date")||"",params.get("end_date")||"");
 const result=useCommunityResource<Activity>(user&&!invalid?"/release/activity?"+communityQuery(params,true):null,user?.id||"guest");const tab=["posts","comments","interests"].includes(params.get("tab")||"")?params.get("tab")!:"posts";
 return <section><Link to="/my">← 마이페이지</Link><PageTitle title="내 커뮤니티 활동"><p>현재 볼 수 있는 글에 연결된 내 활동만 표시해요.</p></PageTitle><div className="actions" aria-label="활동 종류">{[["posts","내 글"],["comments","내 댓글"],["interests","관심 공구 수요"]].map(([key,label])=><button key={key} className={tab===key?"":"secondary"} aria-pressed={tab===key} onClick={()=>setParams({...Object.fromEntries(params),tab:key,page:"0"})}>{label}</button>)}</div><CommunityFilters activity/>{invalid&&<p role="alert">{invalid}</p>}<ListFeedback {...result} retry={result.reload}/>{result.data?.items.map(item=>"post" in item?<article className="demand-card" key={item.post.id}><p className="eyebrow">{postTypes[postType(item.post)]} · {item.post.category}</p><h2><Link to={"/demands/"+encodeURIComponent(item.post.id)}>{item.post.title}</Link></h2><p>작성 {communityTime(item.post.created_at)}{item.post.updated_at&&" · 수정 "+communityTime(item.post.updated_at)}</p></article>:<article className="demand-card" key={item.comment.id}><h2><Link to={(item.parent_kind==="groupbuy"?"/groupbuys/":"/demands/")+encodeURIComponent(item.post_id)+"#comment-"+item.comment.id}>{item.post_title}</Link></h2><p className="ugc-text">{item.comment.body}</p><p>댓글 작성 {communityTime(item.comment.created_at)}{item.comment.updated_at&&" · 수정 "+communityTime(item.comment.updated_at)}</p></article>)}{!invalid&&!result.loading&&!result.error&&!result.data?.items.length&&<p>이 조건에 맞는 내 활동이 없어요.</p>}<ListPages hasMore={result.data?.has_more||false} disabled={result.loading||result.stale||!!invalid}/></section>;
}
type Notice={id:string;report_id:string;target_type:string;target_id:string;action:string;reason:string;created_at:string;acknowledged_at:string|null};
export function ModerationNotices() {
 const {user}=useAuth(),action=useAction(),attempts=useSessionAttempt();const result=useCommunityResource<{items:Notice[];has_more:boolean}>(user?"/release/notices?pending_only=true&limit=20&offset=0":null,user?.id||"guest");
 const pending=result.data?.items.filter(item=>!item.acknowledged_at)||[];
 if(!user)return null;
 return <>{result.error&&<div className="notice" role="alert"><p>운영 안내를 확인하지 못했어요. {result.error}</p><button type="button" className="secondary" onClick={result.reload}>안내 다시 확인</button></div>}{pending.length>0&&<aside className="moderation-notices" aria-label="내 콘텐츠 운영 안내"><h2>확인할 운영 안내가 있어요</h2>{pending.map(item=><article key={item.id}><p>{item.target_type==="comment"?"댓글":item.target_type==="groupbuy"?"공구 정보":"글"} · {item.action==="suspend"?"계정 이용 제한":"콘텐츠 운영 조치"}</p><p>{item.reason}</p>{item.target_type==="groupbuy"&&<p><Link to="/my/groupbuys">내 공구에서 상태 확인</Link></p>}<p className="hint">대상 번호 {item.target_id} · 처리 {communityTime(item.created_at)}</p><button type="button" disabled={action.busy} onClick={()=>{const attempt=attempts.begin();if(!attempt.isCurrent())return;void action.run(async()=>{try{await api("/release/notices/"+encodeURIComponent(item.id)+"/ack","POST");}catch(error){if(attempt.isCurrent())throw error;return;}if(attempt.isCurrent()){result.reload();action.setMessage("안내를 확인했습니다.");}});}}>이 안내 확인</button></article>)}{result.data?.has_more&&<p className="hint" role="status">확인할 안내가 더 있어요. 이 페이지의 안내를 확인하면 다음 안내를 불러와요.</p>}<Feedback {...action}/></aside>}</>;
}
