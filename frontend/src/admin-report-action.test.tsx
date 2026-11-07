import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Children, isValidElement, type ReactNode } from "react";
const state=vi.hoisted(()=>({index:0,choice:"remove",note:"  공개 개인정보 삭제  ",api:vi.fn(),reload:vi.fn(),message:vi.fn(),pending:undefined as Promise<unknown>|undefined}));
vi.mock("react",async()=>({...await vi.importActual<typeof import("react")>("react"),useRef:(value:unknown)=>({current:value}),useState:()=>{state.index++;return [state.index===1?state.choice:state.note,vi.fn()];}}));
vi.mock("./api",async()=>({...await vi.importActual<typeof import("./api")>("./api"),api:state.api}));
vi.mock("./shared",async()=>({...await vi.importActual<typeof import("./shared")>("./shared"),useSessionAttempt:()=>({begin:()=>({expectedToken:null,isCurrent:()=>true})}),useAction:()=>({busy:false,message:"",error:"",setMessage:state.message,run:(work:()=>Promise<unknown>)=>{state.pending=work();return state.pending;}})}));
import { AdminReport } from "./public-app";
function findForm(node:ReactNode):{onSubmit:(event:{preventDefault:()=>void})=>void}|undefined{
 for(const child of Children.toArray(node))if(isValidElement<{children?:ReactNode;onSubmit:(event:{preventDefault:()=>void})=>void}>(child)){
  if(child.type==="form")return child.props;
  const found=findForm(child.props.children);if(found)return found;
 }
}
function submit(){const form=findForm(AdminReport({report:{id:"report-exact",target_type:"comment",target_id:"comment-exact",reason:"개인정보",status:"active"},reload:state.reload}));expect(form).toBeDefined();form!.onSubmit({preventDefault:vi.fn()});return state.pending!;}
beforeEach(()=>{state.index=0;state.choice="remove";state.note="  공개 개인정보 삭제  ";state.pending=undefined;state.api.mockReset().mockResolvedValue({ok:true});state.reload.mockReset();state.message.mockReset();vi.stubGlobal("window",{confirm:vi.fn(()=>true)});});
afterEach(()=>vi.unstubAllGlobals());
it("requires an explicit removal confirmation naming the exact report and content target",async()=>{await submit();expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("신고 report-exact · 대상 comment / comment-exact"));expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("삭제하면 회원 화면에서 대상 본문을 볼 수 없습니다."));expect(state.api).toHaveBeenCalledExactlyOnceWith("/release/admin/reports/report-exact/resolve","POST",{action:"remove",note:"공개 개인정보 삭제"});expect(state.reload).toHaveBeenCalledTimes(1);expect(state.message).toHaveBeenCalledWith("신고를 처리했습니다.");});
it("does not send or show completion after cancelling removal",async()=>{vi.mocked(window.confirm).mockReturnValue(false);await submit();expect(state.api).not.toHaveBeenCalled();expect(state.reload).not.toHaveBeenCalled();expect(state.message).not.toHaveBeenCalled();});
it("retains the form and does not show removal success after a server rejection",async()=>{state.api.mockRejectedValue(new Error("revision conflict"));await expect(submit()).rejects.toThrow("revision conflict");expect(state.reload).not.toHaveBeenCalled();expect(state.message).not.toHaveBeenCalled();});
it("rejects a blank removal reason before the confirmation or API",async()=>{state.note="   ";await expect(submit()).rejects.toThrow("처리 사유");expect(window.confirm).not.toHaveBeenCalled();expect(state.api).not.toHaveBeenCalled();});
