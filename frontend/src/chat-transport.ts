import { API_BASE, ApiError, formatError } from "./api";
import { readSessionToken, clearSessionToken } from "./session-storage";
import { validateRuntimeApiOrigin } from "./api-origin";
import { clientPlatform } from "./client-platform";

export type Citation={source_id:string;chunk_id:string;title:string;url:string;source_type:string;checked_at:string;revision:string;quote:string};
export type AssistantResponse={answer:string;citations:Citation[];actions:{label:string;url:string;kind:"community"|"saved"|"preferences"|"item"|"login"|"groupbuy"}[];basis:"public_knowledge"|"live_data"|"mixed"|"no_evidence"|"unsupported";live_checked_at:string;generation:{mode:"generated"|"local_extractive"|"retrieval_only"|"abstained";reason:string|null;model:string|null};conversation_id:string|null;request_id:string};
export type AssistantStatus={enabled:boolean;availability_basis:"recent_request"|"no_recent_request"|"disabled";available:boolean;mode:"local"|"retrieval_only";model:string|null;history_retention_days:number;remember_default:false};
export type ConversationSummary={id:string;title:string;updated_at:string;expires_at:string;revision:number;status:"active"};
export type Conversation=ConversationSummary&{messages:{role:"user"|"assistant";content:string;created_at:string}[];remember:true};
export type AssistantHistory={role:"user";content:string};

export function recentUserHistory(messages:readonly {role:"user"|"assistant";content:string}[]):AssistantHistory[] {
 return messages.filter(message=>message.role==="user"&&typeof message.content==="string"&&message.content.trim()).slice(-3).map(message=>({role:"user",content:message.content.trim().slice(0,1200)}));
}

function validateAskPayload(body:unknown):void {
 const fail=()=>{throw new ApiError(422,"질문과 최근 대화 입력을 확인해 주세요. 질문은 2~1,200자이며 최근 사용자 질문만 보낼 수 있어요.");};
 if(!body||typeof body!=="object"||Array.isArray(body))return fail();
 const value=body as Record<string,unknown>;
 if(Object.keys(value).some(key=>!["question","remember","conversation_id","history"].includes(key))||typeof value.question!=="string"||value.question.trim().length<2||value.question.length>1200)return fail();
 if(value.remember!==undefined&&typeof value.remember!=="boolean")return fail();
 if(value.conversation_id!==undefined&&value.conversation_id!==null&&(typeof value.conversation_id!=="string"||!/^[0-9a-f-]{36}$/.test(value.conversation_id)))return fail();
 if(value.history!==undefined){
  if(!Array.isArray(value.history)||value.history.length>3)return fail();
  for(const item of value.history)if(!item||typeof item!=="object"||Array.isArray(item)||Object.keys(item).some(key=>key!=="role"&&key!=="content")||item.role!=="user"||typeof item.content!=="string"||!item.content.trim()||item.content.length>1200)return fail();
 }
}

/** One bounded attempt. A timed-out write may have succeeded; never replay it automatically. */
export async function assistantRequest<T>(path:string,method="GET",body?:unknown,signal?:AbortSignal,expectedToken?:string|null):Promise<T> {
 if(!/^\/(?:status|ask|conversations(?:\/[A-Za-z0-9_-]+(?:\/end)?)?)(?:\?[^#]*)?$/.test(path))throw new ApiError(0,"허용되지 않은 도우미 요청입니다.");
 if(path==="/ask"&&method==="POST")validateAskPayload(body);
 if(import.meta.env.VITE_PUBLIC_RELEASE==="1"||import.meta.env.VITE_BETA_MODE==="1")validateRuntimeApiOrigin(API_BASE);
 const token=readSessionToken(),controller=new AbortController();
 if(expectedToken!==undefined&&token!==expectedToken)throw new ApiError(0,"계정이 변경되어 이전 대화를 전송하지 않습니다. 현재 계정에서 대화를 다시 열어 주세요.");
 const cancel=()=>controller.abort();signal?.addEventListener("abort",cancel,{once:true});if(signal?.aborted)controller.abort();
 const timeout=setTimeout(cancel,path==="/ask"?65_000:15_000);
 try {
  let response:Response;
  try { response=await fetch(API_BASE+"/release/assistant"+path,{method,headers:{"X-Moduyuga-Client":clientPlatform(),...(body!==undefined?{"Content-Type":"application/json"}:{}),...(token?{Authorization:"Bearer "+token}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal}); }
  catch {throw new ApiError(0,signal?.aborted?"요청을 취소했습니다.":controller.signal.aborted?"응답 시간이 초과됐어요. 저장한 대화 목록에서 처리 여부를 확인한 뒤 직접 다시 시도해 주세요. 입력 내용은 유지됩니다.":"도우미에 연결할 수 없어요. 입력 내용은 유지됩니다. 연결을 확인하고 직접 다시 시도해 주세요.");}
  const data=await response.json().catch(()=>null);
  if(token!==readSessionToken()||signal?.aborted)throw new ApiError(0,"계정이 변경되어 응답을 표시하지 않습니다.");
  if(!response.ok){
   if(response.status===401&&token&&token===readSessionToken()){clearSessionToken(token);window.dispatchEvent(new CustomEvent("auth-expired",{detail:{redirect:false,publicRead:true}}));}
   throw new ApiError(response.status,formatError(data?.detail));
  }
  if(data===null)throw new ApiError(0,"도우미 응답을 확인할 수 없어요. 직접 다시 시도해 주세요.");
  if(path==="/ask"&&(typeof data.answer!=="string"||!Array.isArray(data.citations)||!Array.isArray(data.actions)||!["generated","local_extractive","retrieval_only","abstained"].includes(data.generation?.mode)||!["public_knowledge","live_data","mixed","no_evidence","unsupported"].includes(data.basis)))throw new ApiError(0,"도우미 응답 형식을 확인할 수 없어요. 입력 내용은 유지됩니다.");
  return data as T;
 } finally {clearTimeout(timeout);signal?.removeEventListener("abort",cancel);}
}

export function assistantActionPath(value:string):string|null {
 if(!value.startsWith("/")||value.startsWith("//")||/[\\\r\n]/.test(value))return null;
 const path=value.split(/[?#]/)[0];
 return /^\/(?:$|offers(?:\/[^/]+)?|groupbuys(?:\/[^/]+)?|demands(?:\/[^/]+)?|my\/(?:saved|preferences)|login|advisor|calculator)$/.test(path)?value:null;
}
