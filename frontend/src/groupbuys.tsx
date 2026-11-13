import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, categories, money } from "./api";
import { communityTime, ListFeedback, useCommunityResource } from "./community";
import { Feedback, Field, PageTitle, useAction, useAuth } from "./shared";
import { useContentSessionAttempt } from "./content-session";
import { useGroupbuyConfirmation } from "./groupbuy-confirmation";
import { AdminNavigation } from "./admin-members";
import { useExposure } from "./measurement";
import { usePublicResource } from "./release-data";
import type { Demand } from "./release-data";
import "./groupbuys.css";
import { GroupbuyComments } from "./groupbuy-comments";
import { PriceComparison } from "./price-comparison";
import type { PriceReference } from "./price-comparison";

export const BROKER_NOTICE="모두의 육아는 통신판매중개자로서 거래 당사자가 아닙니다. 상품 정보와 거래 책임은 각 판매처에 있으며 주문·결제·배송·환불은 판매처에서 진행합니다.";
export const SHARING_NOTICE="아이·가족의 이름, 생일, 사진, 연락처, 주소, 건강정보를 적지 마세요. 회원 간 계좌 이체·연락처 교환 등 직접 거래 요청과 광고·불법 정보는 신고 대상입니다.";
export type Groupbuy={fulfillment_notes?:string[];option_labels?:string[];return_note?:string;order_minimum?:number|null;order_step?:number|null;is_demo?:boolean;comparison_quantity?:number;price_references?:PriceReference[];source_type?:string;source_url?:string;source_fresh_until?:string;id:string;title:string;body:string;category:string;seller_name:string;seller_url:string;price:number|null;shipping_fee:number|null;minimum_quantity?:number|null;unit:string;price_conditions:string;expires_at:string;source_checked_at:string;author:{id:string;nickname:string};created_at:string;updated_at:string|null;revision:number;own:boolean;can_edit?:boolean;status:"active"|"ended"|"hidden";review_state:"clear"|"needs_review";queried_at:string;broker_notice:string};
type GroupbuyList={items:Groupbuy[];has_more:boolean;queried_at:string};
export type GroupbuyInput=Pick<Groupbuy,"title"|"body"|"category"|"seller_name"|"seller_url"|"price"|"shipping_fee"|"unit"|"price_conditions"|"expires_at"|"source_checked_at"|"minimum_quantity">;
export type GroupbuyDraft=Omit<GroupbuyInput,"price"|"shipping_fee"|"minimum_quantity">&{price:string;shipping_fee:string;minimum_quantity:string};
type GroupbuyReport={id:string;groupbuy_id:string;reason:string;status:"active"|"resolved";created_at:string;resolved_at:string|null;resolved_by:string|null;action:"hide"|"needs_review"|"dismiss"|null;note:string;groupbuy:Groupbuy|null};
const pageNumber=(value:string|null)=>Math.max(0,Math.min(500,Math.floor(Number(value)||0)));
const route=(id:string)=>"/groupbuys/"+encodeURIComponent(id);
const statusText=(item:Groupbuy)=>item.status==="hidden"?"숨김":item.status==="ended"?(item.source_type==="seller_page"?"판매처 재확인 필요":"종료"):(item.source_type==="seller_page"?"판매처 게시 확인":"진행 중");
export function publicSellerUrl(value:string):string|null{
 try{if(/[\\\x00-\x20\x7f]/.test(value))return null;const url=new URL(value);const host=url.hostname.toLowerCase().replace(/\.$/,"");
  if(url.protocol!=="https:"||url.username||url.password||url.port||host==="localhost"||!host.includes(".")||host.endsWith(".localhost")||host.endsWith(".local")||host.endsWith(".internal")||host.includes(":")||host.startsWith("[")||/^\d+(?:\.\d+){3}$/.test(host))return null;
  return host.split(".").every(label=>/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))?url.href:null;
 }catch{return null;}
}
export function groupbuyListQuery(params:URLSearchParams,mine=false):string{
 const query=new URLSearchParams({q:params.get("q")||"",category:params.get("category")||"",status:["active","ended","all"].includes(params.get("status")||"")?params.get("status")!:mine?"all":"active",sort:params.get("sort")==="recent"?"recent":"ending",limit:"20",offset:String(pageNumber(params.get("page"))*20)});
 return query.toString();
}
export function kstInput(value:string):string{const parsed=new Date(value);return Number.isNaN(parsed.getTime())?"":new Date(parsed.getTime()+9*3600000).toISOString().slice(0,16);}
export function kstInstant(value:string):string|null{
 if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)||value.startsWith("0000-"))return null;
 const parsed=new Date(value+":00+09:00");return !Number.isNaN(parsed.getTime())&&kstInput(parsed.toISOString())===value?parsed.toISOString():null;
}
export function groupbuyDraft(item?:Groupbuy):GroupbuyDraft{return {title:item?.title||"",body:item?.body||"",category:item?.category||categories[0],seller_name:item?.seller_name||"",seller_url:item?.seller_url||"",price:item?.price==null?"":String(item.price),shipping_fee:item?.shipping_fee==null?"":String(item.shipping_fee),minimum_quantity:item?.minimum_quantity==null?"":String(item.minimum_quantity),unit:item?.unit||"",price_conditions:item?.price_conditions||"",expires_at:item?kstInput(item.expires_at):"",source_checked_at:item?kstInput(item.source_checked_at):""};}
export function validateGroupbuyDraft(draft:GroupbuyDraft,now=Date.now()):GroupbuyInput{
 const text=(value:string,min:number,max:number,label:string)=>{const trimmed=value.trim();if(trimmed.length<min||trimmed.length>max)throw new Error(label+" 항목은 "+min+"자 이상 "+max+"자 이내로 입력해 주세요.");return trimmed;};
 const amount=(value:string,label:string)=>{if(!value.trim())return null;if(!/^\d+$/.test(value.trim()))throw new Error(label+"은 0 이상의 정수로 입력하거나 모르면 비워 주세요.");const number=Number(value);if(!Number.isSafeInteger(number)||number>1e9)throw new Error(label+" 금액을 확인해 주세요.");return number;};
 const minimumQuantity=amount(draft.minimum_quantity,"최소 수량");if(minimumQuantity!==null&&minimumQuantity<1)throw new Error("최소 수량은 1 이상으로 입력하거나 비워 주세요.");
 const sellerUrl=publicSellerUrl(draft.seller_url);if(!sellerUrl||sellerUrl.length>2048)throw new Error("판매처 링크는 로그인 정보가 없는 공개 HTTPS 주소로 입력해 주세요.");
 const expires=kstInstant(draft.expires_at),checked=kstInstant(draft.source_checked_at);
 if(!expires||new Date(expires).getTime()<=now)throw new Error("공구 종료 일시는 현재보다 나중인 한국 시간으로 입력해 주세요.");
 if(!checked||new Date(checked).getTime()>now+300000)throw new Error("출처 확인 일시를 실제 확인한 한국 시간으로 입력해 주세요. 미래 시각은 사용할 수 없어요.");
 return {title:text(draft.title,3,120,"제목"),body:text(draft.body,10,3000,"공구 내용"),category:text(draft.category,1,40,"카테고리"),seller_name:text(draft.seller_name,1,100,"판매처 이름"),seller_url:sellerUrl,price:amount(draft.price,"가격"),shipping_fee:amount(draft.shipping_fee,"배송비"),minimum_quantity:minimumQuantity,unit:text(draft.unit,0,100,"수량·단위"),price_conditions:text(draft.price_conditions,0,1000,"가격·참여 조건"),expires_at:expires,source_checked_at:checked};
}
export function BrokerFooter(){return <footer className="broker-footer"><p>{BROKER_NOTICE}</p><nav aria-label="공개 서비스 안내"><Link to="/my/policies">약관·개인정보·삭제 안내</Link><Link to="/offers">육아템 공식 정보</Link><Link to="/my">도움말·문의 안내</Link></nav></footer>;}
function GroupbuyPages({page,hasMore,change,disabled=false}:{page:number;hasMore:boolean;change:(page:number)=>void;disabled?:boolean}){if(!page&&!hasMore)return null;return <nav className="actions" aria-label="공구 목록 페이지"><button className="secondary" disabled={disabled||!page} onClick={()=>change(page-1)}>이전</button><span>{page+1}페이지</span><button className="secondary" disabled={disabled||!hasMore||page>=500} onClick={()=>change(page+1)}>다음</button></nav>;}
function HiddenGroupbuyDelete({item,reload}:{item:Groupbuy;reload:()=>void}){
 const action=useAction(),attempts=useContentSessionAttempt(),confirmation=useGroupbuyConfirmation(action);
 return <><button className="danger secondary" disabled={action.busy||confirmation.waiting} onClick={()=>confirmation.request(()=>{const attempt=attempts.begin();return {title:"숨긴 공구 정보 삭제",description:"‘"+item.title+"’ 공구 정보를 삭제할까요?",details:[{label:"공구",value:item.title},{label:"삭제 결과",value:"공유한 정보와 수요 글의 연결이 삭제되며 복구할 수 없습니다."}],confirmLabel:"공구 영구 삭제",isCurrent:attempt.isCurrent,work:()=>api("/release/groupbuys/"+encodeURIComponent(item.id),"DELETE",{revision:item.revision}),onSuccess:()=>{reload();action.setMessage("공구 정보를 삭제했습니다.");}};})}>내 숨긴 공구 삭제</button><Feedback {...action}/>{confirmation.dialog}</>;
}
function GroupbuyQuickFacts({ item }: { item: Groupbuy }) {
  return (
    <dl className="groupbuy-quick-facts">
      <div><dt>배송비</dt><dd>{item.shipping_fee === null ? "판매처 확인" : item.shipping_fee === 0 ? "무료배송" : money(item.shipping_fee)}</dd></div>
      <div><dt>마감</dt><dd>{item.expires_at ? communityTime(item.expires_at) : "종료 일시 미확인"}</dd></div>
    </dl>
  );
}

export function GroupbuyCard({ item, reload }: { item: Groupbuy; reload?: () => void }) {
  const exposure = useExposure(item.id, "groupbuy_list");
  return (
    <article className="groupbuy-card" ref={exposure.ref}>
      <div className="groupbuy-card-meta">
        <span>{item.category}</span>
        <span className={"groupbuy-status " + item.status}>{statusText(item)}</span>
        {item.review_state === "needs_review" && <strong>정보 확인 필요</strong>}
      </div>
      <h2>{item.status === "hidden" ? item.title : <Link to={route(item.id)} onClick={() => void exposure.click("detail")}>{item.title}</Link>}</h2>
      <p className="groupbuy-seller">{item.seller_name}</p>
      <p className="groupbuy-price">{item.price === null ? "가격 정보 미확인" : money(item.price)}{item.unit && <span>{item.unit}</span>}</p>
      <GroupbuyQuickFacts item={item}/>
      <details className="groupbuy-preview">
        <summary>조건 미리보기</summary>
        <div>
          <p className="ugc-text">{item.price_conditions || item.body}</p>
          {!!item.option_labels?.length && <p>선택 옵션 {item.option_labels.join(" · ")}</p>}
          <p className="hint">출처 확인 {communityTime(item.source_checked_at)}</p>
          <p className="hint">공유 {communityTime(item.created_at)}{item.updated_at && " · 수정 " + communityTime(item.updated_at)}</p>
          {item.status !== "hidden" && <Link to={route(item.id)} onClick={() => void exposure.click("detail")}>상세 정보 보기 →</Link>}
        </div>
      </details>
      {item.status === "hidden" && <p className="hint">운영 조치로 공개되지 않는 정보입니다.</p>}
      {item.own && item.status === "hidden" && reload && <HiddenGroupbuyDelete item={item} reload={reload}/>}
    </article>
  );
}

function GroupbuyOverview({ item }: { item: Groupbuy }) {
  return (
    <section className="groupbuy-overview" aria-label="공구 핵심 조건">
      <div className="groupbuy-overview-price">
        <span>판매처 표시 가격</span>
        <strong>{item.price === null ? "가격 확인 필요" : money(item.price)}</strong>
        {item.unit && <span>{item.unit}</span>}
        <p>{item.seller_name}</p>
      </div>
      <div>
        <GroupbuyQuickFacts item={item}/>
        <p className="hint">출처 확인 {communityTime(item.source_checked_at)}</p>
        <a className="button" href="#groupbuy-seller">판매처·구매 조건 확인 ↓</a>
      </div>
    </section>
  );
}

function PopularDemandCard({demand}:{demand:Demand}){
 const exposure=useExposure(demand.id,"demand_list");
 return <article className="demand-card" ref={exposure.ref}><p className="eyebrow">{demand.category}</p><h3><Link onClick={()=>void exposure.click("detail")} to={"/demands/"+encodeURIComponent(demand.id)}>{demand.title}</Link></h3><p>관심 {demand.interest_count}명 · 댓글 {demand.comment_count}개</p><p className="hint">{demand.author.nickname} · {communityTime(demand.created_at)}</p>{demand.linked_groupbuy&&<p><Link to={route(demand.linked_groupbuy.id)}>연결된 공구: {demand.linked_groupbuy.title}</Link></p>}</article>;
}
function EndingGroupbuyPreview({item}:{item:Groupbuy}){
 const exposure=useExposure(item.id,"groupbuy_list");
 return <li><article ref={exposure.ref}><h3><Link to={route(item.id)} onClick={()=>void exposure.click("detail")}>{item.title}</Link></h3><p>{item.seller_name} · 마감 {item.expires_at?communityTime(item.expires_at):"판매처 확인"}</p></article></li>;
}
export function PopularDemands(){
 const {user}=useAuth();const result=usePublicResource<Demand[]>("/release/demands?post_type=demand&sort=popular&limit=3&offset=0",user?.id);
 return <section className="popular-demands" aria-labelledby="popular-demands-title"><div className="groupbuy-heading"><h2 id="popular-demands-title">관심이 많은 공구 수요</h2><Link to="/demands?post_type=demand">공구 수요 모두 보기</Link></div><p className="hint">관심 수가 많은 순서로 살펴보세요. 관심은 주문이나 공구 개설 약속이 아닙니다.</p><ListFeedback loading={result.loading} error={result.error} stale={false} retry={result.reload}/>{result.data&&!result.loading&&!result.error&&(result.data.length?<div className="popular-demand-grid">{result.data.map(demand=><PopularDemandCard key={demand.id} demand={demand}/>)}</div>:<p>아직 등록된 공구 수요가 없어요. <Link to="/demands/new?post_type=demand">필요한 공구 수요 쓰기</Link></p>)}</section>;
}
function GroupbuyCategories({ params, mine }: { params: URLSearchParams; mine: boolean }) {
  const selected = params.get("category") || "";
  const pathname = mine ? "/my/groupbuys" : "/";

  return (
    <nav className="groupbuy-categories" aria-label="공구 카테고리 바로 선택">
      {["", ...categories].map(category => {
        const next = new URLSearchParams(params);
        next.set("category", category);
        next.set("page", "0");
        return (
          <Link
            key={category}
            to={pathname + "?" + next.toString()}
            aria-current={selected === category ? "true" : undefined}
          >
            {category || "전체"}
          </Link>
        );
      })}
    </nav>
  );
}

export function GroupbuyFeed({mine=false}:{mine?:boolean}){
 const {user}=useAuth(),[params,setParams]=useSearchParams();const fromUrl=()=>({q:params.get("q")||"",category:params.get("category")||"",status:params.get("status")||(mine?"all":"active"),sort:params.get("sort")||"ending"});
 const [draft,setDraft]=useState(fromUrl);const applied=JSON.stringify([params.get("q"),params.get("category"),params.get("status"),params.get("sort"),mine]);useEffect(()=>setDraft(fromUrl()),[applied]);
 const result=useCommunityResource<GroupbuyList>("/release/groupbuys"+(mine?"/mine":"")+"?"+groupbuyListQuery(params,mine),user?.id||"guest");const page=pageNumber(params.get("page"));
 return <section className="groupbuy-feed"><header className="groupbuy-heading"><div><h1>{mine?"내가 공유한 공구":"공구 찾기"}</h1><Link className="button" to="/groupbuys/new">공구 정보 공유</Link></div><p>육아 경험을 나누고, 필요한 육아템의 공구 조건을 함께 확인해요.</p></header><nav className="actions" aria-label="공구와 육아템 탐색"><Link to="/demands?post_type=question">육아 질문·답변</Link><Link to="/offers">육아템 정보</Link>{mine?<Link to="/">전체 공구</Link>:<Link to="/my/groupbuys">내 공구</Link>}</nav><GroupbuyCategories params={params} mine={mine}/>
  <h2>{mine?"내 공구 목록":"공구 목록 · 마감과 조건을 확인하세요"}</h2><form className="groupbuy-filters" aria-label="공구 검색 조건" onSubmit={event=>{event.preventDefault();setParams({...draft,page:"0"});}}><div className="groupbuy-search-primary"><Field label="공구 검색" name="q" autoComplete="off" type="search" maxLength={100} value={draft.q} onChange={event=>setDraft({...draft,q:event.target.value})}/><button>검색 적용</button></div><details className="groupbuy-advanced"><summary>상세 조건 <span>{(params.get("status")||(mine?"all":"active"))==="active"?"진행 중":params.get("status")==="ended"?"종료":"전체"} · {params.get("category")||"전체 분야"} · {params.get("sort")==="recent"?"최근 공유순":"마감 임박순"}</span></summary><div className="groupbuy-advanced-fields"><label className="field"><span>카테고리</span><select value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value})}><option value="">전체 분야</option>{categories.map(category=><option key={category}>{category}</option>)}</select></label><label className="field"><span>공구 상태</span><select value={draft.status} onChange={event=>setDraft({...draft,status:event.target.value})}><option value="active">진행 중</option><option value="ended">종료</option><option value="all">전체</option></select></label><label className="field"><span>정렬</span><select value={draft.sort} onChange={event=>setDraft({...draft,sort:event.target.value})}><option value="ending">마감 임박순</option><option value="recent">최근 공유순</option></select></label><div className="actions"><button>상세 조건 적용</button><button type="button" className="secondary" onClick={()=>{setParams({});setDraft({q:"",category:"",status:mine?"all":"active",sort:"ending"});}}>초기화</button></div></div></details></form>
  <ListFeedback {...result} retry={result.reload}/>{result.data&&<><div className="groupbuy-grid">{result.data.items.map(item=><GroupbuyCard key={item.id} item={item} reload={result.reload}/>)}</div>{!result.loading&&!result.error&&!result.data.items.length&&<div className="state"><p>{params.get("q")||params.get("category")?"이 조건에 맞는 공구가 없습니다.":mine?"아직 공유한 공구가 없습니다.":"등록된 공구 정보가 없습니다."}</p><p>검색 조건을 바꾸거나 판매처에서 확인한 공구 정보를 공유해 주세요.</p><div className="actions"><Link to="/demands/new?post_type=demand">필요한 공구 수요 쓰기</Link><Link to="/groupbuys/new">첫 공구 정보 공유</Link></div></div>}{result.data.items.length>0&&<p className="hint" role="status" aria-live="polite">현재 {page*20+1}–{page*20+result.data.items.length}개 표시 · 조회 {communityTime(result.data.queried_at)}</p>}<GroupbuyPages page={page} hasMore={result.data.has_more} disabled={result.loading||!!result.stale} change={next=>setParams({...Object.fromEntries(params),page:String(next)})}/></>}{!mine&&page===0&&!params.get("q")&&!params.get("category")&&!params.get("status")&&!params.get("sort")&&<div className="home-discovery-highlights"><section className="ending-groupbuys" aria-labelledby="ending-groupbuys-title"><h2 id="ending-groupbuys-title">판매처에서 확인할 공구</h2><p className="hint">조건은 공유 시점 기준이에요. 판매처에서 다시 확인하세요.</p><ListFeedback {...result} retry={result.reload}/>{result.data&&!result.loading&&!result.error&&(result.data.items.length?<ul className="plain-list">{result.data.items.filter(item=>item.status==="active").slice(0,2).map(item=><EndingGroupbuyPreview key={item.id} item={item}/>)}</ul>:<p>현재 진행 중 공구가 없어요. <Link to="/demands/new?post_type=demand">필요한 공구 수요 쓰기</Link></p>)}</section><PopularDemands/></div>}</section>;
}
export function GroupbuyEditor({item,onSaved}:{item?:Groupbuy;onSaved:(item:Groupbuy)=>void}){
 const [draft,setDraft]=useState(()=>groupbuyDraft(item)),action=useAction(),attempts=useContentSessionAttempt();const {requireLogin}=useAuth();
 const field=(key:keyof GroupbuyDraft,value:string)=>setDraft(old=>({...old,[key]:value}));
 return <form className="groupbuy-editor panel" aria-describedby="groupbuy-sharing-notice" onSubmit={event=>{event.preventDefault();if(!requireLogin())return;const attempt=attempts.begin();if(!attempt.isCurrent())return;void action.run(async()=>{const input=validateGroupbuyDraft(draft);let saved:Groupbuy;try{saved=await api<Groupbuy>("/release/groupbuys"+(item?"/"+encodeURIComponent(item.id):""),item?"PUT":"POST",{...input,...(item?{revision:item.revision}:{})});}catch(error){if(attempt.isCurrent())throw error;return;}if(attempt.isCurrent())onSaved(saved);});}}>
  <p className="notice" id="groupbuy-sharing-notice">{SHARING_NOTICE}</p><p className="hint">실제로 확인한 판매처 정보만 공유하세요. 확인하지 못한 가격·배송비는 비워 두세요. 등록은 주문·예약·공구 개설을 대신하지 않습니다.</p>
  <fieldset disabled={action.busy}><legend>{item?"공구 정보 수정":"확인한 공구 정보"}</legend><Field label="제목" required minLength={3} maxLength={120} value={draft.title} onChange={event=>field("title",event.target.value)}/><label className="field"><span>카테고리</span><select required value={draft.category} onChange={event=>field("category",event.target.value)}>{!categories.includes(draft.category)&&<option>{draft.category}</option>}{categories.map(category=><option key={category}>{category}</option>)}</select></label>
  <label className="field"><span>공구 내용 (필수)</span><textarea required minLength={10} maxLength={3000} rows={5} value={draft.body} onChange={event=>field("body",event.target.value)}/></label><Field label="판매처 이름" required maxLength={100} value={draft.seller_name} onChange={event=>field("seller_name",event.target.value)}/><Field label="판매처 공개 HTTPS 링크" required type="url" maxLength={2048} placeholder="https://" value={draft.seller_url} onChange={event=>field("seller_url",event.target.value)}/>
  <div className="groupbuy-form-pair"><Field label="판매처 표시 가격 (원, 모르면 비움)" inputMode="numeric" value={draft.price} onChange={event=>field("price",event.target.value)}/><Field label="배송비 (원, 모르면 비움)" inputMode="numeric" value={draft.shipping_fee} onChange={event=>field("shipping_fee",event.target.value)}/></div><Field label="최소 수량 (선택)" type="number" inputMode="numeric" min="1" step="1" value={draft.minimum_quantity} onChange={event=>field("minimum_quantity",event.target.value)}/><Field label="수량·단위 (선택)" maxLength={100} value={draft.unit} onChange={event=>field("unit",event.target.value)}/><label className="field"><span>가격·참여 조건 (선택)</span><textarea maxLength={1000} rows={3} value={draft.price_conditions} onChange={event=>field("price_conditions",event.target.value)}/></label>
  <div className="groupbuy-form-pair"><Field label="공구 종료 일시 (한국 시간)" required type="datetime-local" value={draft.expires_at} onChange={event=>field("expires_at",event.target.value)}/><Field label="출처를 직접 확인한 일시 (한국 시간)" required type="datetime-local" value={draft.source_checked_at} onChange={event=>field("source_checked_at",event.target.value)}/></div><p className="hint">출처 확인 시각은 작성 시각과 다릅니다. 판매처에서 실제 조건을 확인한 시각을 입력하세요.</p><p className="hint">응답이 지연되면 자동 재전송하지 않습니다. 내 공구에서 처리 여부를 먼저 확인한 뒤 다시 시도해 주세요.</p><button disabled={action.busy}>{action.busy?"처리 중…":item?"수정한 공구 저장":"공구 정보 공유"}</button></fieldset><Feedback {...action}/><Link to="/my/groupbuys">내 공구에서 처리 여부 확인</Link>
 </form>;
}
export function GroupbuyEditorPage(){
 const {id}=useParams(),{user}=useAuth(),nav=useNavigate();const result=useCommunityResource<Groupbuy>(id?"/release/groupbuys/"+encodeURIComponent(id):null,user?.id||"guest");
 return <><nav className="actions"><Link to={id?route(id):"/"}>← {id?"공구 상세":"공구 찾기"}</Link></nav><PageTitle title={id?"공구 정보 수정":"공구 정보 공유"}/>{id&&<ListFeedback {...result} retry={result.reload}/>}{!id?<GroupbuyEditor key={user?.id} onSaved={saved=>nav(route(saved.id),{replace:true})}/>:result.data&&!result.loading&&!result.error&&(result.data.can_edit??(result.data.own&&result.data.status==="active"))?<GroupbuyEditor key={id+":"+user?.id} item={result.data} onSaved={saved=>nav(route(saved.id),{replace:true})}/>:result.data&&!result.loading&&!result.error&&<p className="notice">본인이 공유한 진행 중 공구만 수정할 수 있습니다. 종료하거나 숨겨진 공구는 수정·재개할 수 없습니다.</p>}</>;
}
export function GroupbuyIssueForm({item,reload}:{item:Groupbuy;reload:()=>void}){
 const {requireLogin}=useAuth(),action=useAction(),attempts=useContentSessionAttempt(),[reason,setReason]=useState("");
 return <details className="moderation"><summary>잘못된 정보 제보·신고{!item.own&&"·작성자 차단"}</summary><p>제보 대상 공구: {item.title}</p><p className="ugc-text preview">{item.body.slice(0,200)}</p><p className="hint">가격·기간·판매처 오류, 개인정보, 직접 거래 요청과 광고·불법 정보를 운영자에게 알려 주세요.</p><form onSubmit={event=>{event.preventDefault();if(!requireLogin())return;const attempt=attempts.begin();if(!attempt.isCurrent())return;void action.run(async()=>{const text=reason.trim();if(text.length<5)throw new Error("제보 사유를 공백 제외 5자 이상 입력해 주세요.");let receipt:{message:string};try{receipt=await api<{message:string}>("/release/groupbuys/"+encodeURIComponent(item.id)+"/reports","POST",{reason:text});}catch(error){if(attempt.isCurrent())throw error;return;}if(attempt.isCurrent()){setReason("");action.setMessage(receipt.message);}});}}><label className="field"><span>제보 사유 (필수)</span><textarea required minLength={5} maxLength={1000} rows={3} value={reason} onChange={event=>setReason(event.target.value)}/></label><button className="secondary" disabled={action.busy}>이 공구 정보 제보</button></form>{!item.own&&<button className="secondary" disabled={action.busy} onClick={()=>{if(!requireLogin()||!window.confirm("작성자 "+item.author.nickname+"을 차단할까요? 이 작성자의 정보가 내 로그인 화면에서 숨겨집니다."))return;const attempt=attempts.begin();if(!attempt.isCurrent())return;void action.run(async()=>{try{await api("/blocks/"+encodeURIComponent(item.author.id),"POST");}catch(error){if(attempt.isCurrent())throw error;return;}if(attempt.isCurrent()){reload();action.setMessage("작성자를 차단했습니다.");}});}}>작성자 {item.author.nickname} 차단</button>}<Feedback {...action}/></details>;
}
export function GroupbuyDetail(){
 const {id=""}=useParams(),{user}=useAuth(),nav=useNavigate(),action=useAction(),attempts=useContentSessionAttempt();const result=useCommunityResource<Groupbuy>("/release/groupbuys/"+encodeURIComponent(id),user?.id||"guest"),item=result.data;const exposure=useExposure(item?.id,"groupbuy_detail");
 const confirmation=useGroupbuyConfirmation(action),latest=useRef(item);latest.current=item;
 const url=item&&!item.is_demo?publicSellerUrl(item.seller_url):null;
 return <><nav className="actions"><Link to="/">← 공구 찾기</Link><Link to="/my/groupbuys">내 공구</Link><a href={route(id)+"/public"}>공구 공개 안내 페이지</a></nav><ListFeedback {...result} retry={result.reload}/>{item&&!result.error&&<article className="groupbuy-detail" ref={exposure.ref}><PageTitle eyebrow={statusText(item)+" · "+item.category} title={item.title}><p>{item.author.nickname} · 공유 {communityTime(item.created_at)}{item.updated_at&&" · 수정 "+communityTime(item.updated_at)}</p></PageTitle><GroupbuyOverview item={item}/>{item.is_demo&&<p className="notice">시연용 데이터입니다. 표시된 가격·판매처·마감은 기능 확인용이며 실제 구매로 연결되지 않습니다.</p>}{item.review_state==="needs_review"&&<p className="notice" role="status">정보 확인 필요: 제보된 내용이 있습니다. 현재 조건을 판매처에서 직접 확인하세요.</p>}{item.status==="ended"&&<p className="notice">종료된 공구 정보입니다. 현재 가격·재고·참여 가능 여부를 보장하지 않습니다.</p>}{item.own&&(item.can_edit??item.status==="active")&&<nav className="author-tools actions" aria-label="내 공구 관리"><Link className="button secondary" to={route(item.id)+"/edit"}>공구 정보 수정</Link><button className="secondary" disabled={action.busy||confirmation.waiting||result.loading||!!result.stale} onClick={()=>confirmation.request(()=>{const attempt=attempts.begin(),revision=item.revision;return {title:"공구 정보 종료",description:"‘"+item.title+"’ 공구 정보의 공유를 종료할까요?",details:[{label:"공구",value:item.title},{label:"종료 후",value:"수정하거나 다시 진행할 수 없습니다."}],confirmLabel:"공구 종료",isCurrent:attempt.isCurrent,validate:()=>!latest.current||latest.current.id!==item.id||latest.current.revision!==revision||latest.current.status!=="active"?"공구 정보가 변경됐어요. 취소한 뒤 최신 상태를 확인해 주세요.":"",work:()=>api("/release/groupbuys/"+encodeURIComponent(item.id)+"/end","POST",{revision}),onSuccess:()=>{result.reload();action.setMessage("공구 정보를 종료했습니다.");}};})}>공구 종료</button></nav>}{item.own&&<button className="danger secondary" disabled={action.busy||confirmation.waiting||result.loading||!!result.stale} onClick={()=>confirmation.request(()=>{const attempt=attempts.begin(),revision=item.revision;return {title:"공구 정보 삭제",description:"‘"+item.title+"’ 공구 정보를 삭제할까요?",details:[{label:"공구",value:item.title},{label:"삭제 결과",value:"공유한 정보와 수요 글의 연결이 삭제되며 복구할 수 없습니다."}],confirmLabel:"공구 영구 삭제",isCurrent:attempt.isCurrent,validate:()=>!latest.current||latest.current.id!==item.id||latest.current.revision!==revision?"공구 정보가 변경됐어요. 취소한 뒤 최신 상태를 확인해 주세요.":"",work:()=>api("/release/groupbuys/"+encodeURIComponent(item.id),"DELETE",{revision}),onSuccess:()=>nav("/my/groupbuys",{replace:true})};})}>내 공구 삭제</button>}<Feedback {...action}/><section className="groupbuy-description"><h2>공구 안내</h2><p className="ugc-text">{item.body}</p></section><details className="groupbuy-full-conditions"><summary>상품 구성·배송·반품 자세히 보기</summary><dl className="groupbuy-conditions"><dt>판매처</dt><dd>{item.seller_name}</dd><dt>표시 가격</dt><dd>{item.price===null?"미확인":money(item.price)}{item.unit&&" · "+item.unit}</dd><dt>배송비</dt><dd>{item.shipping_fee===null?"미확인":money(item.shipping_fee)}</dd>{item.order_minimum!=null&&<><dt>주문 최소 수량</dt><dd>{item.order_minimum}개</dd></>}{item.order_step!=null&&<><dt>구매 단위</dt><dd>{item.order_step}개씩</dd></>}<dt>공구 성사 수량</dt><dd>{item.minimum_quantity==null?"판매처가 공개한 성사 기준을 확인하지 못했어요.":item.minimum_quantity+"개"}</dd>{!!item.option_labels?.length&&<><dt>선택 옵션</dt><dd>{item.option_labels.join(" · ")}</dd></>}{!!item.fulfillment_notes?.length&&<><dt>배송·출고 안내</dt><dd>{item.fulfillment_notes.map(note=><p key={note}>{note}</p>)}</dd></>}{item.return_note&&<><dt>교환·반품 안내</dt><dd>{item.return_note}</dd></>}<dt>가격·참여 조건</dt><dd className="ugc-text">{item.price_conditions||"공유된 조건이 없습니다. 판매처에서 확인하세요."}</dd><dt>종료 일시</dt><dd>{item.expires_at?communityTime(item.expires_at):"판매처에 종료 일시를 확인해 주세요."}</dd><dt>출처 확인</dt><dd>{communityTime(item.source_checked_at)}</dd><dt>현재 조회</dt><dd>{communityTime(item.queried_at)}</dd></dl></details>
  {!item.is_demo&&<PriceComparison key={item.id+":"+item.revision} item={item}/>}<section id="groupbuy-seller" className="groupbuy-broker" aria-label="판매처 이동과 중개 안내"><h2>거래는 판매처에서 진행해요</h2><p>{BROKER_NOTICE}</p><p className="hint">공구 조건은 공유 시점 기준입니다. 표시된 가격·재고·배송 조건은 바뀔 수 있습니다. 이동한 판매처의 조건을 다시 확인하세요.</p>{url?<details><summary>판매처로 이동 안내</summary><p>이동할 판매처: {item.seller_name} · {new URL(url).hostname}</p><p>{BROKER_NOTICE}</p><a className="button" href={url} target="_blank" rel="noopener noreferrer" onClick={()=>void exposure.click("source")}>판매처 페이지 열기 · 새 탭</a></details>:<p role="alert">공개 HTTPS 판매처 주소를 확인하지 못해 이동을 제공하지 않습니다.</p>}</section><GroupbuyComments key={item.id+":"+(user?.id||"guest")} id={item.id}/><GroupbuyIssueForm key={item.id+":"+user?.id} item={item} reload={result.reload}/></article>}{confirmation.dialog}</>;
}
export function DemandGroupbuyLink({demand,reload}:{demand:Demand;reload:()=>void}){
 const {requireLogin,user}=useAuth(),action=useAction(),attempts=useContentSessionAttempt();const [selected,setSelected]=useState(""),[query,setQuery]=useState(""),[draftQuery,setDraftQuery]=useState(""),[optionPage,setOptionPage]=useState(0);
 const linked=demand.linked_groupbuy;const options=useCommunityResource<GroupbuyList>(user?"/release/groupbuys?status=active&sort=ending&limit=20&offset="+optionPage*20+"&q="+encodeURIComponent(query):null,user?.id||"guest");
 const confirmation=useGroupbuyConfirmation(action),latest=useRef(demand);latest.current=demand;
 return <section className="groupbuy-demand-link"><h2>이 수요와 연결한 공구</h2>{linked?<div><Link to={route(linked.id)}>{linked.title}</Link><p>{linked.seller_name} · 종료 {communityTime(linked.expires_at)}</p><p className="hint">공구 연결은 참여·주문·예약이 아닙니다. 거래는 판매처에서 진행합니다.</p></div>:<p className="hint">현재 공개된 진행 중 공구가 연결되어 있지 않습니다.</p>}{user&&(demand.own||!linked)&&<details><summary>{demand.own?"진행 중 공구 연결·해제":"진행 중 공구 연결"}</summary><form onSubmit={event=>{event.preventDefault();setQuery(draftQuery);setSelected("");setOptionPage(0);}}><Field label="연결할 공구 검색" type="search" maxLength={100} value={draftQuery} onChange={event=>setDraftQuery(event.target.value)}/><button className="secondary">공구 검색</button></form><ListFeedback {...options} retry={options.reload}/><label className="field"><span>연결할 진행 중 공구</span><select value={selected} onChange={event=>setSelected(event.target.value)}><option value="">공구를 선택하세요</option>{options.data?.items.map(item=><option key={item.id} value={item.id}>{item.title} · {item.seller_name}</option>)}</select></label><p className="hint">검색 결과를 페이지별로 확인해 선택하세요. 찾는 정보가 없으면 공구 찾기에서 확인하거나 직접 공유하세요.</p>{options.data&&<GroupbuyPages page={optionPage} hasMore={options.data.has_more} disabled={options.loading||!!options.stale} change={page=>{setOptionPage(page);setSelected("");}}/>}<div className="actions"><button disabled={action.busy||confirmation.waiting||!selected||options.loading||!!options.stale} onClick={()=>{if(!requireLogin())return;const chosen=options.data?.items.find(item=>item.id===selected);if(!chosen)return;confirmation.request(()=>{const attempt=attempts.begin(),revision=demand.revision;return {title:"공구 연결 확인",description:"이 수요 글에 ‘"+chosen.title+"’을 연결할까요?",details:[{label:"수요 글",value:demand.title},{label:"연결할 공구",value:chosen.title},{label:"안내",value:"연결은 참여·주문·예약이 아닙니다. 거래는 판매처에서 진행합니다."}],confirmLabel:"공구 연결",isCurrent:attempt.isCurrent,validate:()=>!Number.isInteger(revision)||latest.current.id!==demand.id||latest.current.revision!==revision?"수요 글이 변경됐어요. 취소한 뒤 최신 상태를 확인해 주세요.":"",work:()=>api("/release/demands/"+encodeURIComponent(demand.id)+"/groupbuy","PUT",{groupbuy_id:chosen.id,revision}),onSuccess:()=>{reload();action.setMessage("공구 정보를 연결했습니다. 주문은 발생하지 않습니다.");}};});}}>선택한 공구 연결</button>{linked&&demand.own&&<button className="secondary" disabled={action.busy||confirmation.waiting} onClick={()=>confirmation.request(()=>{const attempt=attempts.begin(),revision=demand.revision;return {title:"공구 연결 해제",description:"이 수요 글의 공구 연결을 해제할까요?",details:[{label:"수요 글",value:demand.title},{label:"연결한 공구",value:linked.title}],confirmLabel:"연결 해제",isCurrent:attempt.isCurrent,validate:()=>!Number.isInteger(revision)||latest.current.id!==demand.id||latest.current.revision!==revision?"수요 글이 변경됐어요. 취소한 뒤 최신 상태를 확인해 주세요.":"",work:()=>api("/release/demands/"+encodeURIComponent(demand.id)+"/unlink-groupbuy","POST",{revision}),onSuccess:()=>{reload();action.setMessage("공구 연결을 해제했습니다.");}};})}>연결 해제</button>}<Link to="/groupbuys/new">새 공구 정보 공유</Link></div><Feedback {...action}/></details>}{confirmation.dialog}</section>;
}
const adminActionNames={hide:"공구 숨김",needs_review:"정보 확인 필요 표시",dismiss:"조치 없이 종결"};
export function AdminGroupbuyReport({report,reload}:{report:GroupbuyReport;reload:()=>void}){
 const [choice,setChoice]=useState(""),[note,setNote]=useState(""),action=useAction(),attempts=useContentSessionAttempt(),item=report.groupbuy,url=item?publicSellerUrl(item.seller_url):null;
 const confirmation=useGroupbuyConfirmation(action),latest=useRef(report);latest.current=report;
 return <article className="panel groupbuy-report"><h2>{item?.title||"공구 정보 제보"}</h2><p>제보 ID: {report.id} · 공구 ID: {report.groupbuy_id}</p><p>접수: {communityTime(report.created_at)} · 상태: {report.status==="active"?"검토 필요":"처리 완료"}</p>{item?<section aria-label="운영자 공구 원문 검토"><p>작성자: {item.author.nickname} · {item.author.id}</p><p className="ugc-text">{item.body}</p><p>판매처: {item.seller_name}</p>{url&&<a href={url} target="_blank" rel="noopener noreferrer">판매처 원문 확인 · 새 탭</a>}<p><Link to={route(item.id)}>현재 공개 가능한 공구 확인</Link></p><p>정보 공유 {communityTime(item.created_at)} · 출처 확인 {communityTime(item.source_checked_at)}</p></section>:<p>검토 가능한 원문이 없습니다. 대상 ID와 제보를 확인하세요.</p>}<p className="ugc-text">제보 사유: {report.reason}</p>{report.resolved_at?<p>실제 처리: {communityTime(report.resolved_at)} · 운영자 ID: {report.resolved_by}</p>:<p>처리 시각: 아직 처리하지 않음</p>}{report.action&&<p>적용한 조치: {adminActionNames[report.action]}</p>}{report.note&&<p className="ugc-text">처리 사유: {report.note}</p>}{report.status==="active"&&<form onSubmit={event=>{event.preventDefault();if(!(choice in adminActionNames))return;const reason=note.trim();if(reason.length<2){action.setError("처리 사유를 공백 제외 2자 이상 입력해 주세요.");return;}confirmation.request(()=>{const attempt=attempts.begin();return {title:"공구 검토 조치 확인",description:"대상과 처리 사유를 확인한 뒤 조치를 적용해 주세요.",details:[{label:"공구",value:item?.title||"원문을 확인할 수 없는 공구"},{label:"감사 대상",value:"제보 "+report.id+" · 공구 "+report.groupbuy_id},{label:"조치",value:adminActionNames[choice as keyof typeof adminActionNames]},{label:"처리 사유",value:reason}],confirmLabel:"확인한 조치 적용",isCurrent:attempt.isCurrent,validate:()=>latest.current.id!==report.id||latest.current.status!=="active"?"이 제보는 이미 처리됐거나 상태가 변경됐어요. 취소한 뒤 새로고침해 주세요.":"",work:()=>api("/release/admin/groupbuys/reports/"+encodeURIComponent(report.id)+"/resolve","POST",{action:choice,note:reason}),onSuccess:()=>{reload();action.setMessage("공구 정보 제보를 처리했습니다.");}};});}}><fieldset disabled={action.busy||confirmation.waiting}><legend>공구 검토 조치</legend><label className="field"><span>처리 선택</span><select required value={choice} onChange={event=>setChoice(event.target.value)}><option value="">대상 확인 후 선택하세요</option>{Object.entries(adminActionNames).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><label className="field"><span>처리 사유 (필수)</span><textarea required minLength={2} maxLength={1000} value={note} onChange={event=>setNote(event.target.value)}/></label><button disabled={action.busy}>대상과 처리 확인 후 적용</button></fieldset></form>}<Feedback {...action}/>{confirmation.dialog}</article>;
}
export function AdminGroupbuys(){
 const {user}=useAuth(),[params,setParams]=useSearchParams(),page=pageNumber(params.get("page"));const status=["active","resolved","all"].includes(params.get("status")||"")?params.get("status")!:"active";
 const result=useCommunityResource<{items:GroupbuyReport[];has_more:boolean}>("/release/admin/groupbuys/reports?"+new URLSearchParams({status,limit:"30",offset:String(page*30)}),user?.id||"guest");
 return <><AdminNavigation/><PageTitle title="공구 정보 관리"><p>제보된 공구의 원문과 판매처를 확인하고 조치를 기록합니다. 운영 검토는 상품·판매처의 품질이나 거래 안전을 보증하지 않습니다.</p></PageTitle><label className="field"><span>처리 상태</span><select value={status} onChange={event=>setParams({status:event.target.value,page:"0"})}><option value="active">검토 필요</option><option value="resolved">처리 완료</option><option value="all">전체</option></select></label><button className="secondary" onClick={result.reload}>제보 새로고침</button><ListFeedback {...result} retry={result.reload}/>{result.data?.items.map(report=><AdminGroupbuyReport key={report.id} report={report} reload={result.reload}/>)}{result.data&&!result.loading&&!result.error&&!result.data.items.length&&<p className="state">이 조건에 맞는 공구 제보가 없습니다.</p>}{result.data&&<GroupbuyPages page={page} hasMore={result.data.has_more} disabled={result.loading||!!result.stale} change={next=>setParams({...Object.fromEntries(params),page:String(next)})}/>}</>;
}
