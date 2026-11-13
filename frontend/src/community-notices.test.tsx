import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ReactElement, ReactNode } from "react";
const hooks=vi.hoisted(()=>({index:0,slots:[] as unknown[],effects:[] as Array<{deps?:unknown[];cleanup?:()=>void}>,pending:[] as Array<()=>void>,user:{id:"A"} as {id:string}|null,read:vi.fn(),api:vi.fn()}));
vi.mock("react",async()=>({...await vi.importActual<typeof import("react")>("react"),
 useState:(initial:unknown)=>{const index=hooks.index++;if(!(index in hooks.slots))hooks.slots[index]=typeof initial==="function"?initial():initial;return [hooks.slots[index],(next:unknown)=>{hooks.slots[index]=typeof next==="function"?next(hooks.slots[index]):next;}];},
 useRef:(initial:unknown)=>{const index=hooks.index++;if(!(index in hooks.slots))hooks.slots[index]={current:initial};return hooks.slots[index];},
 useEffect:(effect:()=>void|(()=>void),deps?:unknown[])=>{const index=hooks.index++,previous=hooks.effects[index];if(!previous||!deps||deps.some((value,i)=>!Object.is(value,previous.deps?.[i]))){hooks.pending.push(()=>{previous?.cleanup?.();const cleanup=effect();hooks.effects[index]={deps,cleanup:typeof cleanup==="function"?cleanup:undefined};});}},
}));
vi.mock("./shared",async()=>({...await vi.importActual<typeof import("./shared")>("./shared"),useAuth:()=>({user:hooks.user})}));
vi.mock("./release-data",async()=>({...await vi.importActual<typeof import("./release-data")>("./release-data"),readPublic:hooks.read}));
vi.mock("./api",async()=>({...await vi.importActual<typeof import("./api")>("./api"),api:hooks.api}));
import { ModerationNotices } from "./community";
import { SESSION_TOKEN_KEY } from "./session-storage";
function memory(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);},removeItem:(key:string)=>{values.delete(key);}};}
function deferred<T>(){let resolve!:(value:T)=>void,reject!:(reason:Error)=>void;const promise=new Promise<T>((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};}
function render(){hooks.index=0;const tree=ModerationNotices();for(const effect of hooks.pending.splice(0))effect();return tree;}
function elements(node:ReactNode):ReactElement<Record<string,unknown>>[]{if(Array.isArray(node))return node.flatMap(elements);if(!node||typeof node!=="object"||!("props" in node))return [];const element=node as ReactElement<Record<string,unknown>>;return [element,...elements(element.props.children as ReactNode)];}
function text(node:ReactNode):string{if(Array.isArray(node))return node.map(text).join("");if(typeof node==="string"||typeof node==="number")return String(node);if(node&&typeof node==="object"&&"props" in node)return text((node as ReactElement<{children?:ReactNode}>).props.children);return "";}
function acknowledge(tree:ReactNode){const button=elements(tree).find(item=>item.type==="button"&&text(item.props.children as ReactNode)==="이 안내 확인");expect(button).toBeDefined();(button!.props.onClick as ()=>void)();}
async function settle(){for(let index=0;index<5;index++)await Promise.resolve();}
const notice=(id:string)=>({id,report_id:"r",target_type:"demand",target_id:"p",action:"hide",reason:"안내 "+id,created_at:"2026-11-06T00:00:00Z",acknowledged_at:null});
beforeEach(()=>{hooks.index=0;hooks.slots=[];hooks.effects=[];hooks.pending=[];hooks.user={id:"A"};hooks.read.mockReset();hooks.api.mockReset();vi.stubGlobal("sessionStorage",memory());vi.stubGlobal("localStorage",memory());sessionStorage.setItem(SESSION_TOKEN_KEY,"token-A");});
afterEach(()=>{for(const effect of hooks.effects)effect?.cleanup?.();vi.unstubAllGlobals();});
it("requests pending notices and promotes the older unread notice after acknowledgement",async()=>{
 hooks.read.mockResolvedValueOnce({items:Array.from({length:20},(_,index)=>notice(String(index))),has_more:true}).mockResolvedValueOnce({items:[...Array.from({length:19},(_,index)=>notice(String(index+1))),notice("older-21")],has_more:false});hooks.api.mockResolvedValue({});
 render();await settle();let tree=render();expect(hooks.read).toHaveBeenCalledWith("/release/notices?pending_only=true&limit=20&offset=0");expect(text(tree)).toContain("확인할 안내가 더 있어요");acknowledge(tree);await settle();render();await settle();tree=render();
 expect(hooks.api).toHaveBeenCalledWith("/release/notices/0/ack","POST");expect(hooks.read).toHaveBeenCalledTimes(2);expect(text(tree)).toContain("안내 older-21");expect(text(tree)).not.toContain("확인할 안내가 더 있어요");
});
it("discards A's late list response after switching to B",async()=>{
 const a=deferred<unknown>(),b=deferred<unknown>();hooks.read.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);render();hooks.user={id:"B"};sessionStorage.setItem(SESSION_TOKEN_KEY,"token-B");expect(text(render())).not.toContain("안내 A");b.resolve({items:[notice("B")],has_more:false});await settle();expect(text(render())).toContain("안내 B");a.resolve({items:[notice("A")],has_more:false});await settle();const tree=render();expect(text(tree)).toContain("안내 B");expect(text(tree)).not.toContain("안내 A");
});
it.each(["success","error"])("does not reload B or display A's late acknowledgement %s",async outcome=>{
 const ack=deferred<unknown>();hooks.read.mockResolvedValueOnce({items:[notice("A")],has_more:false}).mockResolvedValueOnce({items:[notice("B")],has_more:false});hooks.api.mockReturnValue(ack.promise);render();await settle();acknowledge(render());hooks.user={id:"B"};sessionStorage.setItem(SESSION_TOKEN_KEY,"token-B");render();await settle();if(outcome==="success")ack.resolve({});else ack.reject(new Error("A-only failure"));await settle();const tree=render();
 expect(hooks.read).toHaveBeenCalledTimes(2);expect(text(tree)).toContain("안내 B");const feedback=elements(tree).find(item=>typeof item.type==="function"&&item.type.name==="Feedback");expect(feedback?.props.message).toBe("");expect(feedback?.props.error).toBe("");
});
