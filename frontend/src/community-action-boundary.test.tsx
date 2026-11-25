import { Children, isValidElement, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const state=vi.hoisted(()=>({index:0,first:undefined as unknown,setters:[] as ReturnType<typeof vi.fn>[],clear:vi.fn(),navigate:vi.fn(),api:vi.fn(),pending:[] as Promise<unknown>[],saved:vi.fn(),effects:[] as Array<()=>void|(()=>void)>}));
vi.mock("react",async()=>({...await vi.importActual<typeof import("react")>("react"),useRef:(initial:unknown)=>({current:initial}),useEffect:(effect:()=>void|(()=>void))=>state.effects.push(effect),useState:(initial:unknown)=>{const index=state.index++,setter=vi.fn();state.setters[index]=setter;return [index===0&&state.first!==undefined?state.first:typeof initial==="function"?(initial as ()=>unknown)():initial,setter];}}));
vi.mock("./api",async()=>({...await vi.importActual<typeof import("./api")>("./api"),api:state.api}));
vi.mock("./shared",async()=>{const actual=await vi.importActual<typeof import("./shared")>("./shared");return {...actual,useAuth:()=>({user:{id:"synthetic-A",nickname:"원래 이름",is_admin:false},updateProfile:vi.fn(),clear:state.clear,requireLogin:()=>true}),useAction:()=>{const action=actual.useAction();return {...action,run:(...args:Parameters<typeof action.run>)=>{const pending=action.run(...args);state.pending.push(pending);return pending;}};}};});
vi.mock("react-router-dom",async()=>({...await vi.importActual<typeof import("react-router-dom")>("react-router-dom"),useNavigate:()=>state.navigate}));
import { BetaRecover, BetaRecoveryCodeSettings } from "./beta";
import { ProfileSettings } from "./profile-settings";
import { PreferenceForm } from "./discovery";
import { AdvisorForm } from "./advisor";
import { DemandEditor, CommentEditor } from "./community-editors";
import { SESSION_TOKEN_KEY, writeSessionToken } from "./session-storage";
function memory(){const map=new Map<string,string>();return {getItem:(key:string)=>map.get(key)??null,setItem:(key:string,value:string)=>{map.set(key,value);},removeItem:(key:string)=>{map.delete(key);}};}
function findForm(node:ReactNode):{onSubmit:(event:{preventDefault:()=>void})=>void}|undefined{for(const child of Children.toArray(node))if(isValidElement<{children?:ReactNode;onSubmit:(event:{preventDefault:()=>void})=>void}>(child)){if(child.type==="form")return child.props;const found=findForm(child.props.children);if(found)return found;}}
const author={id:"synthetic-A",nickname:"합성 작성자"};
beforeEach(()=>{state.index=0;state.first=undefined;state.setters=[];state.clear.mockReset().mockReturnValue(true);state.navigate.mockReset();state.api.mockReset().mockResolvedValue({});state.pending=[];state.saved.mockReset();state.effects=[];vi.stubGlobal("sessionStorage",memory());vi.stubGlobal("localStorage",memory());sessionStorage.setItem(SESSION_TOKEN_KEY,"synthetic-token-A");});afterEach(()=>vi.unstubAllGlobals());
it.each(["post","comment"])("does not submit the prior account's %s draft after the token changes before rerender",async kind=>{const node=kind==="post"?DemandEditor({item:{id:"d1",title:"합성 글 제목",body:"이전 계정의 작성 중 본문입니다.",category:"육아생활",author,created_at:"2026-11-06T00:00:00Z",revision:2,own:true,interest_count:0,interested:false,comment_count:0},onSaved:state.saved,onCancel:vi.fn()}):CommentEditor({item:{id:"c1",body:"이전 계정 댓글 초안",author,created_at:"2026-11-06T00:00:00Z",revision:2,own:true},onSaved:state.saved,onCancel:vi.fn()});writeSessionToken("synthetic-token-B");findForm(node)!.onSubmit({preventDefault:vi.fn()});await Promise.all(state.pending);expect(state.api).not.toHaveBeenCalled();expect(state.saved).not.toHaveBeenCalled();});

it.each(["profile","preferences","advisor"])("blocks a prior account's %s choices before the first network write",async kind=>{
 if(kind==="profile")state.first="변경할 닉네임";
 const node=kind==="profile"?ProfileSettings():kind==="preferences"?PreferenceForm({initial:{categories:["육아생활"],priority:"care"},onSaved:state.saved}):AdvisorForm({signedIn:true,saved:null});
 writeSessionToken("synthetic-token-B");findForm(node)!.onSubmit({preventDefault:vi.fn()});await Promise.all(state.pending);await Promise.resolve();
 expect(state.api).not.toHaveBeenCalled();expect(state.saved).not.toHaveBeenCalled();
});

it("locks duplicate advisor submits before React can render the busy state",async()=>{
 let finish!:(value:unknown)=>void;const pending=new Promise(resolve=>{finish=resolve;});state.api.mockReturnValue(pending);vi.stubGlobal("requestAnimationFrame",(callback:(time:number)=>void)=>{callback(0);return 0;});
 const node=AdvisorForm({signedIn:true,saved:null}),form=findForm(node)!;form.onSubmit({preventDefault:vi.fn()});form.onSubmit({preventDefault:vi.fn()});expect(state.api).toHaveBeenCalledTimes(1);
 finish({});await pending;await Promise.resolve();await Promise.resolve();
});

it.each(["reset","renew"])("does not clear a replacement account or show its predecessor's late %s recovery code",async kind=>{
 let finish!:(value:unknown)=>void;const pending=new Promise(resolve=>{finish=resolve;});state.api.mockReturnValue(pending);
 const node=kind==="reset"?BetaRecover():BetaRecoveryCodeSettings();findForm(node)!.onSubmit({preventDefault:vi.fn()});expect(state.api).toHaveBeenCalledTimes(1);
 writeSessionToken("synthetic-token-B");finish({message:"ok",recovery_code:"synthetic-private-code-A"});await Promise.all(state.pending);
 expect(state.clear).not.toHaveBeenCalled();expect(state.setters[4]).not.toHaveBeenCalledWith("synthetic-private-code-A");
});
it("does not show a recovery code when guarded clear preserves an independent remembered account",async()=>{
 state.clear.mockReturnValue(false);state.api.mockResolvedValue({message:"ok",recovery_code:"synthetic-private-code-A"});
 const node=BetaRecover();findForm(node)!.onSubmit({preventDefault:vi.fn()});await Promise.all(state.pending);
 expect(state.clear).toHaveBeenCalledWith("synthetic-token-A");expect(state.setters[4]).not.toHaveBeenCalledWith("synthetic-private-code-A");
});
