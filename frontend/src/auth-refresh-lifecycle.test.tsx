import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
const state=vi.hoisted(()=>({index:0,effects:[] as Array<()=>void|(()=>void)>,setUser:vi.fn(),setLoading:vi.fn(),api:vi.fn(),listeners:new Map<string,(event:unknown)=>void>()}));
vi.mock("react",async()=>{const actual=await vi.importActual<typeof import("react")>("react");return {...actual,useState:(initial:unknown)=>{state.index++;return state.index===1?[null,state.setUser]:state.index===2?[true,state.setLoading]:actual.useState(initial);},useEffect:(effect:()=>void|(()=>void))=>{state.effects.push(effect);}};});
vi.mock("react-router-dom",async()=>({...await vi.importActual<typeof import("react-router-dom")>("react-router-dom"),useNavigate:()=>vi.fn(),useLocation:()=>({pathname:"/settings",search:"",hash:""})}));
vi.mock("./api",async()=>({...await vi.importActual<typeof import("./api")>("./api"),api:state.api}));
import { AuthProvider } from "./shared";
import { SESSION_TOKEN_KEY } from "./session-storage";
function memory(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);},removeItem:(key:string)=>{values.delete(key);}};}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};}
beforeEach(()=>{vi.stubEnv("VITE_PUBLIC_RELEASE","0");state.index=0;state.effects=[];state.listeners.clear();state.setUser.mockReset();state.setLoading.mockReset();state.api.mockReset();vi.stubGlobal("sessionStorage",memory());vi.stubGlobal("localStorage",memory());vi.stubGlobal("window",{addEventListener:(name:string,listener:(event:unknown)=>void)=>state.listeners.set(name,listener),removeEventListener:(name:string)=>state.listeners.delete(name)});});
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});
it("keeps B's loading state until B finishes when A's old /me resolves first",async()=>{
 const a=deferred<{id:string;is_admin:boolean}>(),b=deferred<{id:string;is_admin:boolean}>();localStorage.setItem(SESSION_TOKEN_KEY,"remembered-A");state.api.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
 renderToStaticMarkup(<AuthProvider><span>child</span></AuthProvider>);const cleanups=state.effects.map(effect=>effect());expect(state.api).toHaveBeenCalledTimes(1);
 localStorage.setItem(SESSION_TOKEN_KEY,"remembered-B");state.listeners.get("storage")?.({key:SESSION_TOKEN_KEY});expect(state.api).toHaveBeenCalledTimes(2);expect(state.setLoading).toHaveBeenLastCalledWith(true);
 a.resolve({id:"A",is_admin:false});await a.promise;await Promise.resolve();expect(state.setLoading).not.toHaveBeenCalledWith(false);expect(state.setUser).not.toHaveBeenCalledWith(expect.objectContaining({id:"A"}));
 b.resolve({id:"B",is_admin:false});await b.promise;await Promise.resolve();expect(state.setUser).toHaveBeenLastCalledWith({id:"B",is_admin:false});expect(state.setLoading).toHaveBeenLastCalledWith(false);
 for(const cleanup of cleanups)if(typeof cleanup==="function")cleanup();
});
it("finishes the pending tab-only A refresh when another tab changes remembered B",async()=>{
 const a=deferred<{id:string;is_admin:boolean}>();sessionStorage.setItem(SESSION_TOKEN_KEY,"tab-only-A");state.api.mockReturnValueOnce(a.promise);
 renderToStaticMarkup(<AuthProvider><span>child</span></AuthProvider>);const cleanups=state.effects.map(effect=>effect());expect(state.api).toHaveBeenCalledTimes(1);
 localStorage.setItem(SESSION_TOKEN_KEY,"remembered-B");state.listeners.get("storage")?.({key:SESSION_TOKEN_KEY});expect(state.api).toHaveBeenCalledTimes(1);expect(state.setUser).not.toHaveBeenCalled();
 a.resolve({id:"A",is_admin:false});await a.promise;await Promise.resolve();expect(state.setUser).toHaveBeenLastCalledWith({id:"A",is_admin:false});expect(state.setLoading).toHaveBeenLastCalledWith(false);
 for(const cleanup of cleanups)if(typeof cleanup==="function")cleanup();
});
