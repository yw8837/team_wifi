import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { completeAccountExit } from "./account-exit";
import { clearSessionToken, readSessionToken, SESSION_TOKEN_KEY, writeSessionToken } from "./session-storage";

function memoryStorage(){const values=new Map<string,string>();return {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)};}
function deferred<T>(){let resolve!:(value:T)=>void;let reject!:(error:Error)=>void;const promise=new Promise<T>((done,fail)=>{resolve=done;reject=fail;});return {promise,resolve,reject};}
beforeEach(()=>{vi.stubEnv("VITE_PUBLIC_RELEASE","0");vi.stubEnv("VITE_BETA_MODE","0");vi.stubGlobal("sessionStorage",memoryStorage());vi.stubGlobal("localStorage",memoryStorage());vi.stubGlobal("window",{dispatchEvent:vi.fn()});});
afterEach(()=>{vi.unstubAllGlobals();vi.unstubAllEnvs();});

describe("account exit completion with real API and token storage",()=>{
 it("does not let account A's delayed logout clear or navigate account B",async()=>{
  writeSessionToken("account-a");const reply=deferred<Response>(),fetch=vi.fn((_url:unknown,_options:{headers:Record<string,string>})=>reply.promise),navigate=vi.fn(),clear=vi.fn(clearSessionToken);vi.stubGlobal("fetch",fetch);
  const expectedToken=readSessionToken()!;const pending=completeAccountExit({expectedToken,request:()=>api("/auth/logout","POST"),isCurrent:()=>true,clear,onCompleted:navigate});
  expect(fetch.mock.calls[0]?.[1]?.headers.Authorization).toBe("Bearer account-a");writeSessionToken("account-b");reply.resolve(new Response(JSON.stringify({ok:true})));
  expect(await pending).toBe(false);expect(readSessionToken()).toBe("account-b");expect(clear).not.toHaveBeenCalled();expect(navigate).not.toHaveBeenCalled();
 });
 it("ignores a delayed deletion after unmount, including reauth and success side effects",async()=>{
  writeSessionToken("account-a");sessionStorage.setItem("reauth","new-grant");const reply=deferred<Response>(),clear=vi.fn(clearSessionToken),completed=vi.fn(()=>sessionStorage.removeItem("reauth"));let mounted=true;vi.stubGlobal("fetch",vi.fn(()=>reply.promise));
  const pending=completeAccountExit({expectedToken:readSessionToken()!,request:()=>api("/me","DELETE",{password:"synthetic-password"}),isCurrent:()=>mounted,clear,onCompleted:completed});mounted=false;reply.resolve(new Response(JSON.stringify({ok:true})));
  expect(await pending).toBe(false);expect(readSessionToken()).toBe("account-a");expect(sessionStorage.getItem("reauth")).toBe("new-grant");expect(clear).not.toHaveBeenCalled();expect(completed).not.toHaveBeenCalled();
 });
 it("preserves another tab's remembered account when the exiting tab has its own session",async()=>{
  writeSessionToken("tab-account-a");const reply=deferred<Response>(),completed=vi.fn();vi.stubGlobal("fetch",vi.fn(()=>reply.promise));const pending=completeAccountExit({expectedToken:readSessionToken()!,request:()=>api("/auth/logout","POST"),isCurrent:()=>true,clear:clearSessionToken,onCompleted:completed});
  localStorage.setItem(SESSION_TOKEN_KEY,"remembered-account-b");reply.resolve(new Response(JSON.stringify({ok:true})));expect(await pending).toBe(false);expect(sessionStorage.getItem(SESSION_TOKEN_KEY)).toBeNull();expect(localStorage.getItem(SESSION_TOKEN_KEY)).toBe("remembered-account-b");expect(completed).not.toHaveBeenCalled();
 });
 it("navigates only after the captured current session was successfully cleared",async()=>{
  writeSessionToken("account-a");vi.stubGlobal("fetch",vi.fn(async()=>new Response(JSON.stringify({ok:true}))));const completed=vi.fn(()=>expect(readSessionToken()).toBeNull());
  expect(await completeAccountExit({expectedToken:readSessionToken()!,request:()=>api("/auth/logout","POST"),isCurrent:()=>true,clear:clearSessionToken,onCompleted:completed})).toBe(true);expect(completed).toHaveBeenCalledTimes(1);
 });
 it("does not show completion when guarded clear refuses the old operation",async()=>{
  writeSessionToken("account-a");const completed=vi.fn();expect(await completeAccountExit({expectedToken:"account-a",request:async()=>undefined,isCurrent:()=>true,clear:()=>false,onCompleted:completed})).toBe(false);expect(readSessionToken()).toBe("account-a");expect(completed).not.toHaveBeenCalled();
 });
 it("does not navigate if clearing synchronously unmounted the old screen or a newer login appeared",async()=>{
  writeSessionToken("account-a");let mounted=true;const completed=vi.fn();expect(await completeAccountExit({expectedToken:"account-a",request:async()=>undefined,isCurrent:()=>mounted,clear:expected=>{const success=clearSessionToken(expected);mounted=false;writeSessionToken("account-b");return success;},onCompleted:completed})).toBe(false);expect(readSessionToken()).toBe("account-b");expect(completed).not.toHaveBeenCalled();
 });
 it("preserves authentication and does not retry or complete a failed request",async()=>{
  writeSessionToken("account-a");const request=vi.fn(async()=>{throw new Error("synthetic failure");}),completed=vi.fn(),clear=vi.fn(clearSessionToken);await expect(completeAccountExit({expectedToken:"account-a",request,isCurrent:()=>true,clear,onCompleted:completed})).rejects.toThrow("synthetic failure");expect(request).toHaveBeenCalledTimes(1);expect(readSessionToken()).toBe("account-a");expect(clear).not.toHaveBeenCalled();expect(completed).not.toHaveBeenCalled();
 });
});
