import { Children, isValidElement, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const state=vi.hoisted(()=>({index:0,firstIndex:0,first:undefined as unknown,setters:[] as ReturnType<typeof vi.fn>[],effects:[] as Array<()=>void|(()=>void)>,resource:null as unknown,confirmation:null as import("./groupbuy-confirmation").GroupbuyConfirmationOptions|null,overrides:{} as Record<number,unknown>,api:vi.fn(),saved:vi.fn(),allowLogin:true,pending:[] as Promise<unknown>[]}));
vi.mock("react",async()=>({...await vi.importActual<typeof import("react")>("react"),useRef:(initial:unknown)=>({current:initial}),useEffect:(effect:()=>void|(()=>void))=>{state.effects.push(effect);},useState:(initial:unknown)=>{const index=state.index++,set=vi.fn();state.setters[index]=set;return [Object.prototype.hasOwnProperty.call(state.overrides,index)?state.overrides[index]:index===state.firstIndex&&state.first!==undefined?state.first:typeof initial==="function"?(initial as ()=>unknown)():initial,set];}}));
vi.mock("./api",async()=>({...await vi.importActual<typeof import("./api")>("./api"),api:state.api}));
vi.mock("./shared",async()=>{
 const actual=await vi.importActual<typeof import("./shared")>("./shared");
 return {...actual,
  useAuth:()=>({user:{id:"synthetic-author"},requireLogin:()=>state.allowLogin}),
  useAction:()=>{
   const action=actual.useAction();
   return {...action,run:(...args:Parameters<typeof action.run>)=>{
    const pending=action.run(...args);state.pending.push(pending);return pending;
   }};
  }
 };
});
vi.mock("react-router-dom",async()=>({...await vi.importActual<typeof import("react-router-dom")>("react-router-dom"),useParams:()=>({id:"synthetic-g1"})}));
vi.mock("./community",async()=>({...await vi.importActual<typeof import("./community")>("./community"),useCommunityResource:()=>({data:state.resource,error:"",loading:false,stale:false,reload:vi.fn()})}));
vi.mock("./measurement",()=>({useExposure:()=>({ref:{current:null},click:vi.fn()})}));
vi.mock("./groupbuy-confirmation",()=>({useGroupbuyConfirmation:()=>({waiting:false,dialog:null,request:(make:()=>import("./groupbuy-confirmation").GroupbuyConfirmationOptions)=>{state.confirmation=make();}})}));
import { AdminGroupbuyReport, BROKER_NOTICE, DemandGroupbuyLink, GroupbuyDetail, GroupbuyEditor, GroupbuyIssueForm, groupbuyDraft, type Groupbuy } from "./groupbuys";
import { SESSION_TOKEN_KEY, writeSessionToken } from "./session-storage";
const item:Groupbuy={id:"synthetic-g1",title:"합성 공구 검증",body:"테스트 전용 합성 공구 내용입니다.",category:"기저귀·물티슈",seller_name:"합성 판매처",seller_url:"https://seller.example.org/deal",price:null,shipping_fee:null,unit:"",price_conditions:"",expires_at:"2099-01-01T00:00:00Z",source_checked_at:"2026-11-06T00:00:00Z",author:{id:"synthetic-author",nickname:"합성 작성자"},created_at:"2026-11-06T01:00:00Z",updated_at:null,revision:2,own:true,can_edit:true,status:"active",review_state:"clear",queried_at:"2026-11-06T02:00:00Z",broker_notice:BROKER_NOTICE};
function memory(){const map=new Map<string,string>();return {getItem:(key:string)=>map.get(key)??null,setItem:(key:string,value:string)=>{map.set(key,value);},removeItem:(key:string)=>{map.delete(key);}};}
function form(node:ReactNode):{onSubmit:(event:{preventDefault:()=>void})=>void}|undefined{for(const child of Children.toArray(node))if(isValidElement<{children?:ReactNode;onSubmit:(event:{preventDefault:()=>void})=>void}>(child)){if(child.type==="form")return child.props;const found=form(child.props.children);if(found)return found;}}
function submit(node:ReactNode){form(node)!.onSubmit({preventDefault:vi.fn()});return state.pending.at(-1);}
function deferred(){let resolve!:(value:Groupbuy)=>void,reject!:(error:Error)=>void;const promise=new Promise<Groupbuy>((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};}
beforeEach(()=>{vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-06T02:00:00Z"));state.index=0;state.firstIndex=0;state.first=groupbuyDraft(item);state.setters=[];state.effects=[];state.overrides={};state.confirmation=null;state.pending=[];state.saved.mockReset();state.api.mockReset().mockResolvedValue(item);state.allowLogin=true;vi.stubGlobal("sessionStorage",memory());vi.stubGlobal("localStorage",memory());sessionStorage.setItem(SESSION_TOKEN_KEY,"synthetic-token-A");vi.stubGlobal("window",{dispatchEvent:vi.fn(),confirm:vi.fn(()=>true)});});
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
it("shares only after explicit submit and navigates only after the confirmed server result",async()=>{const node=GroupbuyEditor({onSaved:state.saved});expect(state.api).not.toHaveBeenCalled();await submit(node);expect(state.api).toHaveBeenCalledTimes(1);expect(state.api.mock.calls[0]?.slice(0,2)).toEqual(["/release/groupbuys","POST"]);expect(state.api.mock.calls[0]?.[2]).toMatchObject({title:item.title,seller_url:item.seller_url,price:null,shipping_fee:null});expect(state.api.mock.calls[0]?.[2]).not.toHaveProperty("revision");expect(state.saved).toHaveBeenCalledWith(item);});
it("keeps the exact target revision on edit and preserves input after server conflict",async()=>{state.api.mockRejectedValue(new Error("409 revision conflict"));const node=GroupbuyEditor({item,onSaved:state.saved});await submit(node);expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/groupbuys/synthetic-g1","PUT",expect.objectContaining({revision:2}));expect(state.saved).not.toHaveBeenCalled();expect(state.setters[0]).not.toHaveBeenCalled();expect(state.setters[2]).toHaveBeenCalledWith("409 revision conflict");});
it("locks a duplicate submit while the first write is pending and does not retry an ambiguous failure",async()=>{const pending=deferred();state.api.mockReturnValue(pending.promise);const node=GroupbuyEditor({onSaved:state.saved});submit(node);submit(node);expect(state.api).toHaveBeenCalledTimes(1);pending.reject(new Error("응답 시간 초과, 내 공구에서 처리 여부 확인"));await Promise.all(state.pending);expect(state.api).toHaveBeenCalledTimes(1);expect(state.saved).not.toHaveBeenCalled();expect(state.setters[0]).not.toHaveBeenCalled();});
it("does not replay sharing automatically after requiring login",async()=>{state.allowLogin=false;const node=GroupbuyEditor({onSaved:state.saved});expect(submit(node)).toBeUndefined();state.allowLogin=true;await Promise.resolve();expect(state.api).not.toHaveBeenCalled();});
it("blocks an old editor's draft before transmission when storage switches accounts before rerender",()=>{const node=GroupbuyEditor({onSaved:state.saved});writeSessionToken("synthetic-token-B");expect(submit(node)).toBeUndefined();expect(state.api).not.toHaveBeenCalled();expect(state.saved).not.toHaveBeenCalled();});
it("does not navigate or show old failure after account replacement during a pending response",async()=>{const pending=deferred();state.api.mockReturnValue(pending.promise);const node=GroupbuyEditor({onSaved:state.saved});submit(node);writeSessionToken("synthetic-token-B");pending.reject(new Error("old-private-error"));await Promise.all(state.pending);expect(state.saved).not.toHaveBeenCalled();expect(state.setters[2]).not.toHaveBeenCalledWith("old-private-error");});
it("reports a precise groupbuy with trimmed reason and retains the reason on failure",async()=>{state.firstIndex=3;state.first="  가격이 판매처와 달라요  ";state.api.mockRejectedValue(new Error("network failure"));const node=GroupbuyIssueForm({item,reload:vi.fn()});await submit(node);expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/groupbuys/synthetic-g1/reports","POST",{reason:"가격이 판매처와 달라요"});expect(state.setters[3]).not.toHaveBeenCalled();expect(state.setters[1]).toHaveBeenCalledWith("network failure");});

function button(node:ReactNode,label:string):{onClick:()=>void}|undefined{
 for(const child of Children.toArray(node))if(isValidElement<{children?:ReactNode;onClick:()=>void}>(child)){
  if(child.type==="button"&&child.props.children===label)return child.props;
  const found=button(child.props.children,label);if(found)return found;
 }
}
const demand={id:"synthetic-demand-id",title:"합성 수요",body:"합성 수요 본문입니다.",category:"육아생활",author:item.author,created_at:item.created_at,revision:7,own:true,interest_count:0,interested:false,comment_count:0,linked_groupbuy:item};
it("confirms a demand link by the readable title while keeping exact IDs in the request",async()=>{
 state.firstIndex=3;state.first=item.id;state.resource={items:[item],has_more:false,queried_at:item.queried_at};
 const node=DemandGroupbuyLink({demand,reload:vi.fn()});button(node,"선택한 공구 연결")!.onClick();expect(state.api).not.toHaveBeenCalled();expect(state.confirmation?.description).toBe("이 수요 글에 ‘"+item.title+"’을 연결할까요?");await applyCaptured();
 expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/demands/synthetic-demand-id/groupbuy","PUT",{groupbuy_id:item.id,revision:7});
});
it("confirms unlinking without showing an internal demand identifier",async()=>{
 state.first=undefined;state.resource={items:[item],has_more:false,queried_at:item.queried_at};
 const node=DemandGroupbuyLink({demand,reload:vi.fn()});button(node,"연결 해제")!.onClick();expect(state.api).not.toHaveBeenCalled();expect(state.confirmation?.description).toBe("이 수요 글의 공구 연결을 해제할까요?");await applyCaptured();
 expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/demands/synthetic-demand-id/unlink-groupbuy","POST",{revision:7});
});
it("confirms ending by title and consequence while preserving the exact mutation target",async()=>{
 state.first=undefined;state.resource=item;const node=GroupbuyDetail();button(node,"공구 종료")!.onClick();expect(state.api).not.toHaveBeenCalled();expect(state.confirmation?.description).toBe("‘"+item.title+"’ 공구 정보의 공유를 종료할까요?");expect(state.confirmation?.details).toContainEqual({label:"종료 후",value:"수정하거나 다시 진행할 수 없습니다."});await applyCaptured();
 expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/groupbuys/synthetic-g1/end","POST",{revision:2});
});

async function applyCaptured(){expect(state.confirmation).not.toBeNull();const pending=state.confirmation!;expect(pending.isCurrent()).toBe(true);expect(pending.validate?.()).toBe("");await pending.work();pending.onSuccess?.();expect(window.confirm).not.toHaveBeenCalled();}
it("reviews the exact report in a second step with the selected action and trimmed reason",async()=>{
 state.firstIndex=0;state.first="needs_review";state.overrides[1]="  판매 조건 확인 필요  ";
 const node=AdminGroupbuyReport({report:{id:"synthetic-report",groupbuy_id:item.id,groupbuy:item,reason:"잘못된 조건",status:"active",created_at:item.created_at,resolved_at:null,resolved_by:null,action:null,note:""},reload:vi.fn()});
 await submit(node);expect(state.api).not.toHaveBeenCalled();expect(state.confirmation?.details).toContainEqual({label:"처리 사유",value:"판매 조건 확인 필요"});expect(state.confirmation?.details).toContainEqual({label:"감사 대상",value:"제보 synthetic-report · 공구 synthetic-g1"});await applyCaptured();expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/admin/groupbuys/reports/synthetic-report/resolve","POST",{action:"needs_review",note:"판매 조건 확인 필요"});
});
