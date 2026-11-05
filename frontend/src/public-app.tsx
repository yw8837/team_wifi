import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { IconHome, IconMessages, IconCalculator, IconBookmark, IconUser } from "@tabler/icons-react";
import { api, categories, date, money, safeExternalUrl } from "./api";
import { APP_NAME, BrandLockup, CategoryIcon } from "./brand";
import { Login, Reset, Signup } from "./auth-pages";
import { BetaRecoveryCodeSettings, LegalLinks, legalUrl } from "./beta";
import { Feedback, Field, PageTitle, PasswordField, Protected, ResourceState, useAction, useAuth } from "./shared";
import { compareUnit, publicConfigMatches } from "./release-policy";
import type { ComparisonInput } from "./release-policy";
import { releasePath, usePublicResource } from "./release-data";
import type { Author, Comment, Demand, Offer } from "./release-data";
import { PersonalDiscovery, PreferencePage, ServiceInsights } from "./discovery";
import { NativeAuthReturn, SocialReturn, SocialAccountSettings, REAUTH_KEY } from "./social-auth";
import { MeasurementProvider, MeasurementSettings, useExposure } from "./measurement";
import "./public.css";
import { ProfileSettings } from "./profile-settings";
import { DemandEditor, CommentEditor } from "./community-editors";
import { AdvisorPage, ComparisonCta, CompanionList } from "./advisor";

const privacyNotice="아이의 이름·생일·사진, 연락처·주소, 건강정보 등 아이와 가족의 개인정보는 적지 마세요. 광고·거래 유도·불법 정보는 신고 대상입니다.";
function Pagination({page,count,change}:{page:number;count:number;change:(page:number)=>void}){if(page===0&&count<20)return null;return <nav className="actions" aria-label="목록 페이지"><button className="secondary" disabled={page===0} onClick={()=>change(page-1)}>이전</button><span>{page+1}페이지</span><button className="secondary" disabled={count<20||page>=500} onClick={()=>change(page+1)}>다음</button></nav>;}
const routeId=(id?:string)=>encodeURIComponent(id || "");
export function PublicGate({enabled,children}:{enabled:boolean;children:ReactNode}) {
  const config=usePublicResource<unknown>(enabled?"/config":null);
  const location=useLocation();
  const [slow,setSlow]=useState(false);
  useEffect(()=>{
    setSlow(false);
    if(!config.loading)return;
    const timer=window.setTimeout(()=>setSlow(true),10_000);
    return()=>window.clearTimeout(timer);
  },[config.loading]);
  if(!enabled)return children;
  if((config.loading||config.error||!publicConfigMatches(config.data))&&location.pathname==="/calculator")return <main className="public-main"><Link className="wordmark" to="/"><BrandLockup/></Link><Calculator/><p><Link to="/">육아템으로 돌아가기 · 서버 연결 확인</Link></p></main>;
  if(config.loading)return <main className="narrow public-gate"><BrandLockup stacked/><h1>육아템을 불러오고 있어요</h1><p role="status">{slow?"연결이 평소보다 늦어지고 있어요. 연결되면 자동으로 열립니다.":"잠시만 기다려 주세요."}</p>{slow&&<p>처음 접속할 때는 1분 이상 걸릴 수 있어요.</p>}<Link to="/calculator">기다리는 동안 단가 비교하기</Link><p><a href={legalUrl("support")}>도움말과 문의</a></p></main>;
  if(config.error || !publicConfigMatches(config.data))return <main className="narrow public-gate"><BrandLockup stacked/><h1>서비스 연결을 확인해 주세요</h1><p role="alert">{config.error || "현재 서버와 앱 버전이 맞지 않아 정보를 안전하게 표시할 수 없습니다."}</p><button onClick={config.reload}>연결 다시 확인</button><p>입력이나 가입 없이 다시 연결할 수 있어요.</p><Link to="/calculator">연결 없이 단가 비교 계산기 이용</Link><p><a href={legalUrl("support")}>도움말과 문의</a></p></main>;
  return children;
}
export function PublicApp(){
  const location=useLocation(),{user}=useAuth();
  const [offline,setOffline]=useState(!navigator.onLine);
  useEffect(()=>{const online=()=>setOffline(false),off=()=>setOffline(true);window.addEventListener("online",online);window.addEventListener("offline",off);return()=>{window.removeEventListener("online",online);window.removeEventListener("offline",off);};},[]);
  useEffect(()=>{window.scrollTo(0,0);document.title=APP_NAME;let robots=document.querySelector<HTMLMetaElement>('meta[name="robots"]');if(!robots){robots=document.createElement("meta");robots.name="robots";document.head.appendChild(robots);}robots.content=/^\/(my|settings|admin|auth|login|signup|reset)(\/|$)/.test(location.pathname)?"noindex,nofollow":"index,follow";document.getElementById("main")?.focus({preventScroll:true});},[location.pathname]);
  const auth=["/login","/signup","/reset"].includes(location.pathname);
  return <MeasurementProvider><NativeAuthReturn/><a className="skip-link" href="#main">본문으로 이동</a><header className="app-header"><Link className="wordmark" to="/"><BrandLockup/></Link><Link className="header-account" to={user?"/my":"/login"}>{user?user.nickname:"로그인"}</Link></header>
    {offline&&<p className="offline" role="alert">오프라인입니다. 계산기는 계속 이용할 수 있어요. 연결 후 정보를 다시 불러와 주세요.</p>}
    <main id="main" tabIndex={-1} className={auth?"auth-main":"public-main"}><Routes>
      <Route path="/auth/complete" element={<SocialReturn/>}/><Route path="/" element={<Offers/>}/><Route path="/offers/:id" element={<OfferDetail/>}/>
      <Route path="/demands" element={<Demands/>}/><Route path="/demands/new" element={<Protected><NewDemand/></Protected>}/><Route path="/demands/:id" element={<DemandDetail/>}/>
      <Route path="/advisor" element={<AdvisorPage/>}/><Route path="/calculator" element={<Calculator/>}/><Route path="/my/saved" element={<Protected><Offers saved/></Protected>}/><Route path="/my" element={<PublicMy/>}/><Route path="/settings" element={<Protected><PublicSettings/></Protected>}/>
      <Route path="/my/policies" element={<PublicPolicies/>}/>
      <Route path="/my/preferences" element={<Protected><PreferencePage/></Protected>}/><Route path="/admin/insights" element={<Protected admin><ServiceInsights/></Protected>}/>
      <Route path="/admin" element={<Protected admin><PublicAdmin/></Protected>}/><Route path="/login" element={<Login/>}/><Route path="/signup" element={<Signup/>}/><Route path="/reset" element={<Reset/>}/><Route path="/welcome" element={<PublicWelcome/>}/>
      <Route path="*" element={<section className="panel"><h1>화면을 찾을 수 없어요</h1><Link to="/">육아템 둘러보기</Link></section>}/>
    </Routes></main>
    {!auth&&<nav className="bottom-nav" aria-label="주요 메뉴">{[["/","육아템",IconHome],["/demands","공구 수요",IconMessages],["/calculator","단가 비교",IconCalculator],["/my/saved","저장",IconBookmark],["/my","마이",IconUser]].map(([to,label,Icon])=>{const Glyph=Icon as typeof IconHome;return <NavLink key={String(to)} end={to==="/"} to={String(to)}><span className="nav-icon"><Glyph size={23} stroke={1.7} aria-hidden="true"/></span><span>{String(label)}</span></NavLink>;})}</nav>}
  </MeasurementProvider>;
}
function OfferCard({offer}:{offer:Offer}){
 const exposure=useExposure(offer.id,"catalog");
 return <article ref={exposure.ref} className="reference-card"><div className="reference-symbol"><CategoryIcon category={offer.category}/></div><div><p className="eyebrow">{offer.category} · {offer.entry_type==="verified_offer"?"확인한 판매 정보":"공식 참고 정보"}</p><h2><Link onClick={()=>void exposure.click("detail")} to={"/offers/"+routeId(offer.id)}>{offer.title}</Link></h2><p>{offer.summary}</p><p className="muted">출처 {offer.source_name} · 확인 {date(offer.source_checked_at)}</p>{offer.price!==null&&<p><strong>{money(offer.price)}</strong>{offer.unit&&" / "+offer.unit}</p>}</div></article>;
}
function Offers({saved=false}:{saved?:boolean}){
 const {user}=useAuth(),[params,setParams]=useSearchParams();
 const q=params.get("q")||"",category=params.get("category")||"";
 const page=Math.max(0,Math.min(500,Math.floor(Number(params.get("page"))||0)));
 const result=usePublicResource<Offer[]>((saved?"/release/saved":"/release/offers")+"?"+new URLSearchParams({limit:"20",offset:String(page*20),...(saved?{}:{q,category})}),user?.id);
 const filtered=result.data;
 return <section className="home-catalog"><PageTitle eyebrow="함께 고르는 육아생활" title={saved?"저장한 육아템":"육아템, 꼼꼼히 알아보고 준비해요"}><p>{saved?"다시 보고 싶은 육아템을 모아뒀어요.":"공식 출처와 비교 기준을 살펴보고, 필요한 공구 수요를 나눠요."}</p></PageTitle>
 {!saved&&<><label className="field"><span className="sr-only">육아템 검색</span><input type="search" placeholder="육아템 검색" maxLength={100} value={q} onChange={e=>setParams({...Object.fromEntries(params),q:e.target.value,page:"0"},{replace:true})}/></label><div className="public-categories" aria-label="카테고리">{["",...categories].map(c=><button key={c} className={category===c?"selected":"secondary"} aria-pressed={category===c} onClick={()=>setParams({...Object.fromEntries(params),category:c,page:"0"})}>{c&&<CategoryIcon category={c} size={24}/>}<span>{c||"전체"}</span></button>)}</div><aside className="public-intro"><strong>가격보다 먼저, 우리에게 맞는 기준부터</strong><p>참고 링크는 특가·제휴 판매가 아닙니다. 가격과 재고는 판매처에서 확인해 주세요.</p><Link to="/calculator">배송비까지 단가 비교하기 →</Link><p><a href="https://moduyuga.onrender.com/guides.html" target="_blank" rel="noopener noreferrer">육아템 선택 가이드와 데이터 활용 근거 ↗</a></p></aside></>}
 {!saved&&!q&&!category&&page===0&&<><Link to="/advisor" className="advisor-entry"><span><strong>어떤 육아템이 필요하세요?</strong><small>분야·비교 기준·예산으로 차근차근 찾아요</small></span><span aria-hidden="true">→</span></Link><PersonalDiscovery/></>}
 <ResourceState {...result} retry={result.reload}/>{!result.loading&&!result.error&&(filtered?.length?<div className="reference-list">{filtered.map(o=><OfferCard key={o.id} offer={o}/>)}</div>:<section className="panel"><h2>{saved?"아직 저장한 육아템이 없어요":"검색 결과가 없어요"}</h2><p>{saved?"육아템 상세의 저장 버튼으로 관심 있는 제품을 모아 보세요.":"다른 검색어 또는 전체 카테고리를 선택해 보세요."}</p><Link to="/">육아템 전체 보기</Link></section>)}
 {!result.loading&&!result.error&&<Pagination page={page} count={result.data?.length||0} change={next=>setParams({...Object.fromEntries(params),page:String(next)})}/>}
 </section>;
}
function OfferDetail(){
 const {id}=useParams(),{user,requireLogin}=useAuth(),action=useAction();const result=usePublicResource<Offer>(releasePath("offers",id),user?.id),o=result.data;const exposure=useExposure(o?.id,"detail");
 return <><Link to="/">← 육아템</Link><ResourceState {...result} retry={result.reload}/>{o&&!result.loading&&!result.error&&<article className="public-detail"><PageTitle eyebrow={o.category} title={o.title}><p>{o.summary}</p></PageTitle><span className="badge">{o.entry_type==="verified_offer"?"확인한 판매 정보":"공식 참고 정보 · 특가 아님"}</span><section ref={exposure.ref} className="panel"><h2>출처와 확인 정보</h2><p>{o.source_name}</p><p>확인 시각 {date(o.source_checked_at)}</p><p>{o.price===null?"가격 정보 없음 · 판매처에서 확인":money(o.price)+(o.unit?" / "+o.unit:"")}</p><p>{o.shipping_fee===null?"배송비 정보 없음": "배송비 "+money(o.shipping_fee)}</p><p>{o.expires_at?"안내 기한 "+date(o.expires_at):"별도 판매 기한 정보 없음"}</p>{safeExternalUrl(o.source_url)&&<a className="button secondary" onClick={()=>void exposure.click("source")} href={safeExternalUrl(o.source_url)!} target="_blank" rel="noopener noreferrer">{o.source_name} 공식 출처 보기 ↗</a>}<p className="hint">외부 사이트로 이동합니다. 가격·재고·제품 사양과 구매 조건은 원문에서 다시 확인하세요.{o.is_affiliate?" 제휴 링크가 포함되어 있습니다.":" 제휴 수수료를 받지 않습니다."}</p></section><section className="panel"><h2>비교할 때 살펴보세요</h2><ul>{o.comparison_notes.map((n,i)=><li key={i}>{n}</li>)}</ul><Link onClick={()=>void exposure.click("calculator")} to="/calculator">단가·배송비 계산하기 →</Link></section><ComparisonCta offer={o}/><p><a href={"https://moduyuga.onrender.com/items/"+encodeURIComponent(o.id)+".html"}>출처가 정리된 공개 비교 안내 →</a></p><Feedback {...action}/><button aria-pressed={o.saved} disabled={action.busy} onClick={()=>{if(requireLogin())void action.run(async()=>{await exposure.click("save");await api(releasePath("offers",id)+"/saved",o.saved?"DELETE":"PUT");result.reload();},o.saved?"저장을 해제했습니다.":"육아템을 저장했습니다.");}}>{o.saved?"저장 해제":"육아템 저장"}</button><CompanionList key={o.id} offerId={o.id}/></article>}</>;
}
function Calculator(){
 const blank={price:"",shipping:"0",quantity:""};const [inputs,setInputs]=useState<ComparisonInput[]>([{...blank},{...blank}]);
 const results=inputs.map(compareUnit);const delta=results[0]&&results[1]?results[0].unit-results[1].unit:null;
 return <><PageTitle eyebrow="배송비까지 함께" title="단가 비교 계산기"><p>같은 단위의 수량으로 비교하세요. 입력값은 이 화면에서만 계산되며 서버에 전송하거나 저장하지 않습니다.</p></PageTitle><div className="comparison-grid">{inputs.map((input,i)=><section className="panel" key={i}><h2>상품 {i===0?"A":"B"}</h2>{[["price","상품 총액 (원)"],["shipping","배송비 (원)"],["quantity","총 수량 (개·매·mL 등)"]].map(([key,label])=><Field key={key} label={label} type="number" inputMode="decimal" min={key==="quantity"?"0.000001":"0"} step="any" value={input[key as keyof ComparisonInput]} onChange={e=>setInputs(inputs.map((v,j)=>j===i?{...v,[key]:e.target.value}:v))}/>)}<p className="hint">음수·빈 값은 계산하지 않으며 수량은 0보다 커야 합니다. 단위가 다른 제품은 비교할 수 없어요.</p><output className="comparison-result" aria-live="polite">{results[i]?<>배송 포함 {money(results[i]!.total)}<br/><strong>단위당 {results[i]!.unit.toLocaleString("ko-KR",{maximumFractionDigits:2})}원</strong></>:"금액과 수량을 입력해 주세요."}</output></section>)}</div><p className="notice" role="status">{delta===null?"두 상품을 모두 입력하면 단가 차이를 확인할 수 있어요.":delta===0?"두 상품의 배송 포함 단가가 같아요.":`상품 ${delta<0?"A":"B"}의 단가가 ${Math.abs(delta).toLocaleString("ko-KR",{maximumFractionDigits:2})}원 낮아요.`}</p><p>쿠폰·묶음 조건·반품비는 반영하지 않습니다. 실제 결제 금액은 판매처에서 확인하세요.</p><button className="secondary" onClick={()=>setInputs([{...blank},{...blank}])}>입력 초기화</button></>;
}
function Moderation({kind,id,author,own,onChange,onDelete}:{kind:"demand"|"comment";id:string;author:Author;own:boolean;onChange:()=>void;onDelete:()=>Promise<void>}){
 const {requireLogin}=useAuth(),action=useAction();const [reason,setReason]=useState("");
 return <details className="moderation"><summary>신고·차단{own?"·삭제":""}</summary><p className="hint">신고는 운영자에게만 전달됩니다. 차단하면 해당 작성자의 글과 댓글이 내 로그인 화면에서 숨겨집니다.</p><form onSubmit={e=>{e.preventDefault();if(requireLogin())void action.run(async()=>{await api("/release/reports","POST",{target_type:kind,target_id:id,reason});setReason("");},"신고를 접수했습니다. 운영자가 확인합니다.");}}><label className="field"><span>신고 사유</span><textarea required minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)} placeholder="개인정보·욕설·광고 등 문제를 설명해 주세요."/></label><button className="secondary" disabled={action.busy}>이 {kind==="demand"?"글":"댓글"} 신고</button></form>{!own&&<button className="secondary" disabled={action.busy} onClick={()=>{if(requireLogin()&&window.confirm("이 작성자를 차단할까요? 작성자의 글과 댓글이 내 목록에서 숨겨집니다. 계정 설정에서 해제할 수 있어요."))void action.run(async()=>{await api("/blocks/"+routeId(author.id),"POST");onChange();},"작성자를 차단했습니다.");}}>작성자 {author.nickname} 차단</button>}{own&&<button className="danger secondary" disabled={action.busy} onClick={()=>{if(window.confirm("직접 작성한 내용을 삭제할까요? 삭제한 내용은 복구할 수 없습니다."))void action.run(onDelete,"삭제했습니다.");}}>내 {kind==="demand"?"글":"댓글"} 삭제</button>}<Feedback {...action}/></details>;
}
function Demands(){
 const {user}=useAuth(),[params,setParams]=useSearchParams();const query=params.get("q")||"",category=params.get("category")||"";const page=Math.max(0,Math.min(500,Math.floor(Number(params.get("page"))||0)));const result=usePublicResource<Demand[]>("/release/demands?"+new URLSearchParams({q:query,category,limit:"20",offset:String(page*20)}),user?.id);
 const items=result.data;
 return <><PageTitle eyebrow="필요한 것을 함께 이야기해요" title="공구 수요 모으기"><p>찾고 있는 육아템과 궁금한 점을 나누세요. 관심은 구매 의사 조사이며 예약·주문·결제가 아닙니다.</p></PageTitle><div className="actions"><Link className="button" to="/demands/new">수요 제안하기</Link></div><div className="public-filter"><Field label="수요 검색" type="search" maxLength={100} value={query} onChange={e=>setParams({...Object.fromEntries(params),q:e.target.value,page:"0"},{replace:true})}/><label className="field"><span>카테고리</span><select value={category} onChange={e=>setParams({...Object.fromEntries(params),category:e.target.value,page:"0"},{replace:true})}><option value="">전체</option>{categories.map(c=><option key={c}>{c}</option>)}</select></label></div><ResourceState {...result} retry={result.reload}/>{!result.loading&&!result.error&&(items?.length?items.map(d=><MeasuredDemand key={d.id} d={d} reload={result.reload}/>):<section className="panel"><h2>{query||category?"조건에 맞는 수요가 없어요":"아직 올라온 수요가 없어요"}</h2><p>필요한 제품의 종류와 비교 기준을 먼저 제안해 보세요. 판매자나 공구 개설을 보장하지 않습니다.</p><Link to="/demands/new">첫 수요 제안하기</Link></section>)}{!result.loading&&!result.error&&<Pagination page={page} count={result.data?.length||0} change={next=>setParams({...Object.fromEntries(params),page:String(next)})}/>}</>;
}
function NewDemand(){
 const action=useAction(),nav=useNavigate();const [form,setForm]=useState({title:"",body:"",category:categories[0]});
 return <div className="narrow"><Link to="/demands">← 공구 수요</Link><PageTitle title="어떤 육아템이 필요한가요?"><p>제품의 종류·선택 기준·궁금한 점을 나눠 주세요. 판매·배송 약속이나 연락처 교환은 받지 않습니다.</p></PageTitle><p className="notice" id="post-privacy">{privacyNotice}</p><form aria-describedby="post-privacy" onSubmit={e=>{e.preventDefault();void action.run(async()=>{const value=await api<Demand>("/release/demands","POST",form);nav("/demands/"+routeId(value.id),{replace:true});});}}><fieldset disabled={action.busy}><legend className="sr-only">수요 제안 내용</legend><Field label="제목" required minLength={3} maxLength={120} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/><label className="field"><span>카테고리</span><select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><label className="field"><span>필요한 제품과 질문</span><textarea required minLength={10} maxLength={3000} rows={7} value={form.body} onChange={e=>setForm({...form,body:e.target.value})}/></label><button disabled={action.busy}>수요 제안 올리기</button></fieldset><Feedback {...action}/></form></div>;
}
function DemandDetail(){
 const {id}=useParams(),{user,requireLogin}=useAuth(),nav=useNavigate(),action=useAction();const [body,setBody]=useState(""),[commentPage,setCommentPage]=useState(0),[editing,setEditing]=useState(false),[editingComment,setEditingComment]=useState<string|null>(null);
 useEffect(()=>{setCommentPage(0);setEditing(false);setEditingComment(null);},[id,user?.id]);
 const result=usePublicResource<Demand>(releasePath("demands",id),user?.id),comments=usePublicResource<Comment[]>(releasePath("demands",id)+"/comments?limit=20&offset="+commentPage*20,user?.id),d=result.data;const exposure=useExposure(d?.id,"demand_detail");
 const reload=()=>{result.reload();comments.reload();};
 return <><Link to="/demands">← 공구 수요</Link><ResourceState {...result} retry={result.reload}/>{d&&!result.loading&&!result.error&&<article className="public-detail"><PageTitle eyebrow={d.category} title={d.title}><p>{d.author.nickname} · {date(d.created_at)}{d.updated_at&&" · 수정됨"}</p></PageTitle>{editing&&d.own?<DemandEditor key={d.id} item={d} onSaved={()=>{setEditing(false);reload();action.setMessage("글을 수정했습니다.");}} onCancel={()=>{setEditing(false);reload();}}/>:<><p className="ugc-text">{d.body}</p>{d.own&&<button type="button" className="secondary" onClick={()=>setEditing(true)}>내 글 수정</button>}</>}<section ref={exposure.ref}><p className="notice">관심은 수요 조사입니다. 실제 주문·예약·결제·배송은 발생하지 않습니다. 운영자나 판매자의 공구 개설을 보장하지 않습니다.</p><p>현재 관심 {d.interest_count}명</p><button aria-pressed={d.interested} disabled={action.busy} onClick={()=>{if(requireLogin())void action.run(async()=>{if(!d.interested)await exposure.click("interest");await api(releasePath("demands",id)+"/interest",d.interested?"DELETE":"PUT");result.reload();},d.interested?"관심을 취소했습니다.":"관심을 표시했습니다. 주문이나 예약은 발생하지 않습니다.");}}>{d.interested?"관심 취소":"나도 관심 있어요"}</button></section><Feedback {...action}/><Moderation kind="demand" id={d.id} author={d.author} own={d.own} onChange={()=>nav("/demands",{replace:true})} onDelete={async()=>{await api(releasePath("demands",id),"DELETE");nav("/demands",{replace:true});}}/>
 <section className="comments"><h2>질문과 이야기</h2><ResourceState {...comments} retry={comments.reload}/>{!comments.loading&&!comments.error&&(comments.data?.length?comments.data.map(c=><article className="comment" key={c.id}><p className="muted">{c.author.nickname} · {date(c.created_at)}{c.updated_at&&" · 수정됨"}</p>{editingComment===c.id&&c.own?<CommentEditor item={c} onSaved={()=>{setEditingComment(null);reload();action.setMessage("댓글을 수정했습니다.");}} onCancel={()=>{setEditingComment(null);reload();}}/>:<><p className="ugc-text">{c.body}</p>{c.own&&<button type="button" className="secondary" onClick={()=>setEditingComment(c.id)}>내 댓글 수정</button>}</>}<Moderation kind="comment" id={c.id} author={c.author} own={c.own} onChange={reload} onDelete={async()=>{await api(releasePath("comments",c.id),"DELETE");reload();}}/></article>):<p>이 페이지에는 댓글이 없어요. 제품을 고를 때 궁금한 점을 나눠 보세요.</p>)}{!comments.loading&&!comments.error&&<Pagination page={commentPage} count={comments.data?.length||0} change={setCommentPage}/>}<p className="notice" id="comment-privacy">{privacyNotice}</p><form aria-describedby="comment-privacy" onSubmit={e=>{e.preventDefault();if(requireLogin())void action.run(async()=>{await api(releasePath("demands",id)+"/comments","POST",{body});setBody("");setCommentPage(0);reload();},"댓글을 등록했습니다.");}}><label className="field"><span>댓글 작성</span><textarea required minLength={2} maxLength={1000} rows={3} value={body} onChange={e=>setBody(e.target.value)}/></label><button disabled={action.busy}>{user?"댓글 등록":"로그인하고 댓글 등록"}</button></form></section></article>}</>;
}
function PublicWelcome(){return <section className="welcome"><div className="welcome-emblem"><img src="/brand/symbol.svg" alt="" width="128"/></div><p className="eyebrow">함께 고르는 육아생활</p><h1>우리에게 맞는 육아템,<br/>차근차근 골라요.</h1><p className="lead">공식 정보의 출처를 살펴보고,<br/>단가를 비교하고, 공구 수요를 나누세요.</p><Link className="button" to="/">로그인 없이 육아템 둘러보기</Link><p>실제 주문·결제·배송은 제공하지 않습니다.</p><LegalLinks/></section>;}
function PublicMy() {
  const {user}=useAuth();
  return <div className="my-page">
    <PageTitle title="마이페이지"><p>내가 모은 정보부터 계정 관리까지.</p></PageTitle>
    <section className="my-profile" aria-labelledby="my-profile-title">
      <div className="my-avatar"><IconUser size={28} stroke={1.6} aria-hidden="true"/></div>
      <div className="my-profile-copy">
        <h2 id="my-profile-title">{user ? user.nickname+"님, 반가워요" : "함께 고르는 육아생활"}</h2>
        <p>{user ? "필요한 육아템을 모아 두고, 궁금한 점을 나눠요." : "둘러보기는 자유롭게, 저장과 글쓰기는 로그인 후에."}</p>
        {!user&&<div className="my-auth-actions"><Link className="button" to="/login?returnTo=%2Fmy">로그인</Link><Link to="/signup?returnTo=%2Fmy">회원가입</Link></div>}
      </div>
    </section>
    <section className="my-section" aria-labelledby="my-activity-title">
      <h2 id="my-activity-title">내 활동과 계정</h2>
      <nav className="my-menu" aria-label="내 활동과 계정">
        <Link to="/my/preferences"><IconHome size={23} aria-hidden="true"/><span><strong>관심 육아템 설정</strong><small>관심 분야와 비교 기준 · 앱·웹 함께 적용</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>
        <Link to="/my/saved"><IconBookmark size={23} aria-hidden="true"/><span><strong>저장한 육아템</strong><small>다시 보고 싶은 육아템을 한곳에</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>
        <Link to="/settings"><IconUser size={23} aria-hidden="true"/><span><strong>프로필 · 계정 관리</strong><small>닉네임 변경 · 로그인 연결 · 차단 · 계정 삭제</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>
        {user?.is_admin&&<Link to="/admin"><span><strong>콘텐츠 신고 관리</strong><small>접수된 신고 확인과 처리</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>}
        {user?.is_admin&&<Link to="/admin/insights"><span><strong>육아템 관심 분석</strong><small>저장·수요 현황과 제공 데이터 분석</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>}
      </nav>
    </section>
    <PublicHelp/>
    <p className="my-footer">모두의 육아 · Team_Wifi</p>
  </div>;
}

function PublicHelp() {
  return <>
    <section className="my-section" aria-labelledby="my-help-title">
      <h2 id="my-help-title">도움말</h2>
      <nav className="my-menu" aria-label="서비스와 이용 안내">
        <a href={legalUrl("support")} target="_blank" rel="noopener noreferrer"><span><strong>도움말과 문의</strong><small>자주 묻는 질문 · 오류 신고 · 운영 문의</small></span><span className="my-chevron" aria-hidden="true">↗</span><span className="visually-hidden"> (새 탭에서 열림)</span></a>
        <Link to="/welcome"><span><strong>모두의 육아 소개</strong><small>지금 이용할 수 있는 기능을 알아보세요</small></span><span className="my-chevron" aria-hidden="true">›</span></Link>
      </nav>
    </section>
    <nav className="my-policy-footer" aria-label="정책 안내"><Link to="/my/policies">약관 및 정책 <span aria-hidden="true">›</span></Link><p>이용약관 · 개인정보 · 데이터 삭제 안내</p></nav>
  </>;
}

function PublicPolicies() {
  return <div className="my-page policy-index">
    <Link className="back-link" to="/my">← 마이페이지</Link>
    <PageTitle title="약관 및 정책"><p>서비스 이용 기준과 내 정보 관리 방법을 확인하세요.</p></PageTitle>
    <nav className="my-menu" aria-label="약관 및 정책 문서">
      {[
        ["terms","이용약관","서비스 이용 기준과 커뮤니티 규칙"],
        ["privacy","개인정보 처리방침","수집하는 정보와 보관·삭제 기준"],
        ["deletion","계정·데이터 삭제 안내","탈퇴 방법과 기록별 삭제 방법"],
      ].map(([key,title,description])=><a key={key} href={legalUrl(key)} target="_blank" rel="noopener noreferrer">
        <span><strong>{title}</strong><small>{description}</small></span><span className="my-chevron" aria-hidden="true">↗</span><span className="visually-hidden"> (새 탭에서 열림)</span>
      </a>)}
    </nav>
    <p className="my-help-note">각 문서는 로그인 없이 새 탭에서 열립니다.</p>
    <div className="policy-contact"><p>내용이 궁금하거나 내 정보에 관한 요청이 있나요?</p><a href={legalUrl("support")} target="_blank" rel="noopener noreferrer">도움말과 문의 <span className="visually-hidden">(새 탭에서 열림)</span><span aria-hidden="true">↗</span></a></div>
    <p className="my-footer">모두의 육아 · Team_Wifi</p>
  </div>;
}
function PublicSettings(){
 const {user,clear}=useAuth(),nav=useNavigate(),action=useAction();const [deleting,setDeleting]=useState(false),[password,setPassword]=useState(""),[confirmed,setConfirmed]=useState(false),[blockPage,setBlockPage]=useState(0);const blocks=usePublicResource<Author[]>("/blocks?limit=20&offset="+blockPage*20,user?.id);
 return <div className="narrow account-settings"><Link className="back-link" to="/my">← 마이페이지</Link><PageTitle title="계정 관리"/>
 <ProfileSettings key={user?.id}/>
 <section className="panel"><h2>현재 계정</h2><p>{user?.nickname} · {user?.email}</p><p className="muted">로그인은 현재 탭·앱 세션에 유지됩니다. 소셜 연결은 아래에서 관리하며, 이메일 가입은 이메일 소유 확인을 제공하지 않습니다.</p><button className="secondary" disabled={action.busy} onClick={()=>void action.run(async()=>{await api("/auth/logout","POST");clear();nav("/",{replace:true});})}>로그아웃</button></section>{user?.has_password!==false&&<BetaRecoveryCodeSettings/>}<SocialAccountSettings/><MeasurementSettings/>
 <section className="panel"><h2>차단한 작성자</h2><p>차단은 내 로그인 화면에 적용됩니다. 차단을 해제하면 작성자의 글과 댓글이 다시 표시됩니다.</p><ResourceState {...blocks} retry={blocks.reload}/>{!blocks.loading&&!blocks.error&&(blocks.data?.length?<ul className="plain-list">{blocks.data.map(b=><li key={b.id}><span>{b.nickname}</span><button className="secondary" disabled={action.busy} onClick={()=>void action.run(async()=>{await api("/blocks/"+routeId(b.id),"DELETE");blocks.reload();},"차단을 해제했습니다.")}>차단 해제</button></li>)}</ul>:<p>이 페이지에 차단한 작성자가 없습니다.</p>)}{!blocks.loading&&!blocks.error&&<Pagination page={blockPage} count={blocks.data?.length||0} change={setBlockPage}/>}</section>
 <section className="panel"><h2>계정과 데이터 삭제</h2><p>직접 작성한 수요·댓글과 저장·관심·신고·차단 기록을 삭제합니다. 내 수요 글에 달린 다른 회원의 댓글과 관심 기록도 함께 삭제되며, 모든 로그인과 복구코드를 사용할 수 없게 됩니다. 삭제 후에는 복구할 수 없습니다.</p><p>이메일·닉네임·비밀번호는 사용할 수 없게 바뀌고, 데이터 연결 관계를 위한 임의 계정 ID와 탈퇴 상태가 남습니다. <a href={legalUrl("deletion")} target="_blank" rel="noopener noreferrer">삭제 범위와 남는 기록 확인 (새 탭)</a></p>
 {!deleting?<button className="danger secondary" onClick={()=>setDeleting(true)}>계정 삭제 진행</button>:<form onSubmit={e=>{e.preventDefault();if(confirmed)void action.run(async()=>{await api("/me","DELETE",{password,reauth_token:sessionStorage.getItem(REAUTH_KEY)||""});sessionStorage.removeItem(REAUTH_KEY);clear();nav("/",{replace:true});});}}>{user?.has_password!==false?<PasswordField label="현재 비밀번호" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/>:<p>위의 연결된 소셜 계정으로 다시 인증한 후 삭제하세요. 인증 결과는 5분간 유효합니다.</p>}<label className="check"><input type="checkbox" required checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>삭제 결과와 복구 불가를 확인했으며 계정을 삭제합니다.</span></label><div className="actions"><button className="danger" disabled={action.busy}>계정 영구 삭제</button><button type="button" className="secondary" disabled={action.busy} onClick={()=>{setDeleting(false);setPassword("");setConfirmed(false);}}>취소</button></div></form>}</section><Feedback {...action}/><PublicHelp/></div>;
}
type ReleaseReport={id:string;target_type:string;target_id:string;reason:string;status:string;created_at?:string;note?:string;target_preview?:string;demand_id?:string|null;author_nickname?:string};
export function PublicAdmin(){const [page,setPage]=useState(0);const reports=usePublicResource<ReleaseReport[]>("/release/admin/reports?limit=20&offset="+page*20);return <><PageTitle title="콘텐츠 신고 관리"><p>신고 대상과 사유를 확인한 뒤 처리하세요. 숨김·정지는 즉시 실제 콘텐츠와 계정에 적용됩니다.</p></PageTitle><ResourceState {...reports} retry={reports.reload}/>{!reports.loading&&!reports.error&&(reports.data?.length?reports.data.map(report=><AdminReport key={report.id} report={report} reload={reports.reload}/>):<p className="state">이 페이지에 접수된 공개 콘텐츠 신고가 없습니다.</p>)}{!reports.loading&&!reports.error&&<Pagination page={page} count={reports.data?.length||0} change={setPage}/>}</>;}
function AdminReport({report,reload}:{report:ReleaseReport;reload:()=>void}){const action=useAction(),[choice,setChoice]=useState(""),[note,setNote]=useState("");return <article className="panel"><h2>{report.target_type==="demand"?"수요 글":report.target_type==="comment"?"댓글":"사용자"} 신고</h2><p>대상 ID: {report.target_id}</p>{report.author_nickname&&<p>작성자: {report.author_nickname}</p>}{report.target_preview&&<blockquote className="ugc-text">{report.target_preview}</blockquote>}<p className="ugc-text">{report.reason}</p><p>처리 상태: {report.status==="active"?"접수 · 검토 필요":report.status==="resolved"?"처리 완료":report.status}</p>{report.created_at&&<p>{date(report.created_at)}</p>}{report.demand_id&&<Link to={"/demands/"+routeId(report.demand_id)}>대상 글·댓글 확인</Link>}{report.note&&<p>{report.note}</p>}{report.status==="active"&&<form onSubmit={e=>{e.preventDefault();if(choice&&window.confirm("선택한 신고 처리를 실제로 적용할까요?"))void action.run(async()=>{await api("/release/admin/reports/"+routeId(report.id)+"/resolve","POST",{action:choice,note});reload();},"신고를 처리했습니다.");}}><label className="field"><span>처리 선택</span><select required value={choice} onChange={e=>setChoice(e.target.value)}><option value="">대상 확인 후 선택하세요</option>{report.target_type!=="user"&&<option value="hide">콘텐츠 숨김</option>}<option value="dismiss">신고 종결 · 조치 없음</option><option value="suspend">작성자 계정 정지</option></select></label><Field label="처리 메모" required minLength={2} maxLength={1000} value={note} onChange={e=>setNote(e.target.value)}/><button disabled={action.busy}>선택한 처리 적용</button></form>}<Feedback {...action}/></article>;}

function MeasuredDemand({d,reload}:{d:Demand;reload:()=>void}) {const exposure=useExposure(d.id,"demand_list");return <article className="demand-card" ref={exposure.ref}><p className="eyebrow">{d.category}</p><h2><Link onClick={()=>void exposure.click("detail")} to={"/demands/"+routeId(d.id)}>{d.title}</Link></h2><p className="ugc-text preview">{d.body}</p><p className="muted">{d.author.nickname} · {date(d.created_at)}</p><p>관심 {d.interest_count}명 · 댓글 {d.comment_count}개</p><Moderation kind="demand" id={d.id} author={d.author} own={d.own} onChange={reload} onDelete={async()=>{await api(releasePath("demands",d.id),"DELETE");reload();}}/></article>;}
