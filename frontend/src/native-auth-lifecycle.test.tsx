import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
const state=vi.hoisted(()=>({effects:[] as Array<()=>void|(()=>void)>,navigate:vi.fn(),launch:vi.fn(),listen:vi.fn(),close:vi.fn(),remove:vi.fn(),receive:null as null|((value:{url:string})=>void)}));
vi.mock("react",async()=>{const actual=await vi.importActual<typeof import("react")>("react");return {...actual,useEffect:(effect:()=>void|(()=>void))=>{state.effects.push(effect);}};});
vi.mock("react-router-dom",async()=>({...await vi.importActual<typeof import("react-router-dom")>("react-router-dom"),useNavigate:()=>state.navigate}));
vi.mock("@capacitor/core",()=>({Capacitor:{isNativePlatform:()=>true}}));
vi.mock("@capacitor/app",()=>({App:{getLaunchUrl:state.launch,addListener:state.listen}}));
vi.mock("@capacitor/browser",()=>({Browser:{close:state.close,open:vi.fn()}}));
import { NativeAuthReturn } from "./social-auth";
import { writeSessionToken } from "./session-storage";
function memory(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value);},removeItem:(key:string)=>{values.delete(key);}};}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};}
const url="kr.moduyuga.app://auth/complete?flow=ea270994-fb34-4989-82c3-af750223c761";
beforeEach(()=>{state.effects=[];state.navigate.mockReset();state.launch.mockReset();state.listen.mockReset();state.close.mockReset().mockResolvedValue(undefined);state.remove.mockReset().mockResolvedValue(undefined);state.receive=null;state.listen.mockImplementation((_event:string,receive:(value:{url:string})=>void)=>{state.receive=receive;return Promise.resolve({remove:state.remove});});vi.stubGlobal("sessionStorage",memory());vi.stubGlobal("localStorage",memory());});
afterEach(()=>vi.unstubAllGlobals());
function setup(){renderToStaticMarkup(<NativeAuthReturn/>);return state.effects[0];}
describe("NativeAuthReturn actual effect callback lifetime",()=>{
 it("does not close or navigate after cleanup while the launch URL promise is pending",async()=>{const launch=deferred<{url:string}>();state.launch.mockReturnValue(launch.promise);const cleanup=setup()() as ()=>void;cleanup();launch.resolve({url});await launch.promise;await Promise.resolve();expect(state.navigate).not.toHaveBeenCalled();expect(state.close).not.toHaveBeenCalled();expect(state.remove).toHaveBeenCalledTimes(1);});
 it("accepts only the live setup during a StrictMode-style effect cleanup/setup replay",async()=>{const first=deferred<{url:string}>(),second=deferred<{url:string}>();state.launch.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);const effect=setup(),cleanupFirst=effect() as ()=>void;cleanupFirst();const cleanupSecond=effect() as ()=>void;first.resolve({url});second.resolve({url});await Promise.all([first.promise,second.promise]);await Promise.resolve();expect(state.navigate).toHaveBeenCalledTimes(1);expect(state.close).toHaveBeenCalledTimes(1);cleanupSecond();});
 it("ignores an old launch URL after a different account was installed",async()=>{const launch=deferred<{url:string}>();state.launch.mockReturnValue(launch.promise);const cleanup=setup()() as ()=>void;writeSessionToken("synthetic-account-B");launch.resolve({url});await launch.promise;expect(state.navigate).not.toHaveBeenCalled();expect(state.close).not.toHaveBeenCalled();cleanup();});
 it("ignores queued appUrlOpen callbacks after the component's cleanup",async()=>{state.launch.mockResolvedValue(undefined);const cleanup=setup()() as ()=>void;state.receive?.({url});expect(state.navigate).toHaveBeenCalledTimes(1);cleanup();state.receive?.({url});await Promise.resolve();expect(state.navigate).toHaveBeenCalledTimes(1);expect(state.close).toHaveBeenCalledTimes(1);});
});
