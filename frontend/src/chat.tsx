import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { date, safeExternalUrl } from "./api";
import { useAuth } from "./shared";
import { assistantActionPath, assistantRequest, recentUserHistory } from "./chat-transport";
import type { AssistantResponse, AssistantStatus, Conversation, ConversationSummary } from "./chat-transport";
import { readSessionToken } from "./session-storage";
import "./chat.css";

type Message={role:"user"|"assistant";content:string;answer?:AssistantResponse};
const basisLabels:Record<AssistantResponse["basis"],string>={public_knowledge:"검토한 공개 자료",live_data:"현재 확인한 서비스 정보",mixed:"공개 자료와 현재 서비스 정보",no_evidence:"확인할 근거가 부족해요",unsupported:"답변하기 어려운 요청이에요"};
const generationReasons:Record<string,string>={clarification_needed:"제품이나 분야의 이름을 함께 적어 주세요.",disabled:"현재 모델 생성 기능을 사용할 수 없어 자료를 안내해요.",busy:"모델이 다른 요청을 처리하고 있어요. 잠시 후 다시 질문해 주세요.",timeout:"모델 응답 시간이 초과되어 생성 답변을 표시하지 않아요.",unavailable:"모델에 연결할 수 없어 확인한 자료만 안내해요.",no_evidence:"답변을 뒷받침할 검토 자료가 부족해요.",medical:"의료 판단은 제공하지 않아요. 의료 전문가에게 확인해 주세요.",price:"현재 가격을 확인할 근거가 없어 판매처 확인이 필요해요.",certification:"인증 여부를 확인할 근거가 없어 공식 기관 확인이 필요해요.",evidence_changed:"답변 준비 중 자료나 공개 상태가 변경됐어요. 다시 질문해 주세요.",invalid_output:"생성 결과를 검증하지 못해 표시하지 않아요.",invalid_citation:"생성 답변의 출처를 검증하지 못했어요.",unsupported_claim:"확인한 자료가 생성 답변을 충분히 뒷받침하지 않아요.",unsupported_number:"숫자 정보를 근거에서 확인하지 못했어요."};
const sourceLabels:Record<string,string>={catalog_comparison:"육아템 비교",official_public:"공공기관 공개 자료",reviewed_analysis:"검토한 분석",service_guide:"서비스 안내",guide:"이용 안내"};
export function assistantStatusMessage(status:AssistantStatus|null):string {
 if(!status)return "연결 상태 확인 중";
 return status.available&&status.mode==="local"?"최근 로컬 모델 응답 확인 · 답변 방식은 아래에 표시":"공개 자료와 현재 정보를 확인해 안내해요";
}
export function AssistantAnswer({answer}:{answer:AssistantResponse}) {
 return <><p className="chat-generation">{answer.generation.mode==="generated"?"모델이 생성한 답변":answer.generation.mode==="local_extractive"?"모델이 선택한 근거 안내":answer.generation.mode==="retrieval_only"?"검색 자료 안내 · 생성 답변 아님":"답변 보류"} · {basisLabels[answer.basis]}</p><p className="ugc-text">{answer.answer}</p>{answer.generation.reason&&<p className="hint">안내: {generationReasons[answer.generation.reason]||"현재 요청에 대해 생성 답변을 제공하기 어려워요. 확인한 자료와 안내를 살펴봐 주세요."}</p>}<p className="hint">현재 정보 확인 {date(answer.live_checked_at)}. 이전 답변은 현재 상태의 근거가 아니에요.</p>{answer.citations.length>0&&<details className="chat-sources" aria-label="이 답변의 출처"><summary>직접 확인할 출처 {answer.citations.length}개</summary>{answer.citations.map((source,index)=><article key={source.chunk_id+index}><h4>{safeExternalUrl(source.url)?<a href={safeExternalUrl(source.url)!} target="_blank" rel="noopener noreferrer">{source.title} · 새 탭에서 열림</a>:source.title}</h4><p className="ugc-text">{source.quote}</p><p className="hint">{sourceLabels[source.source_type]&&sourceLabels[source.source_type]+" · "}확인 {date(source.checked_at)}</p></article>)}</details>}{answer.actions.length>0&&<nav className="actions" aria-label="답변 관련 화면">{answer.actions.map((action,index)=>{const to=assistantActionPath(action.url);return to?<Link key={index} to={to}>{action.label}</Link>:null;})}</nav>}</>;
}
export function chatEnterSubmits(event:{key:string;shiftKey:boolean;isComposing:boolean;keyCode?:number}):boolean {
 return event.key==="Enter"&&!event.shiftKey&&!event.isComposing&&event.keyCode!==229;
}
export function ChatPage({embedded=false}:{embedded?:boolean}={}) {
 const {user}=useAuth();
 const composing=useRef(false);
 const messageList=useRef<HTMLDivElement>(null);
 const ownerToken=useRef(readSessionToken());
 function scopedRequest<T>(path:string,method="GET",body?:unknown,signal?:AbortSignal){return assistantRequest<T>(path,method,body,signal,ownerToken.current);}
 const [status,setStatus]=useState<AssistantStatus|null>(null),[statusError,setStatusError]=useState("");
 const [question,setQuestion]=useState(""),[messages,setMessages]=useState<Message[]>([]),[remember,setRemember]=useState(false),[conversationId,setConversationId]=useState<string|null>(null);
 const [saved,setSaved]=useState<ConversationSummary[]>([]),[more,setMore]=useState(false),[offset,setOffset]=useState(0),[savedError,setSavedError]=useState(""),[savedLoading,setSavedLoading]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const epoch=useRef(0),savedEpoch=useRef(0),controller=useRef<AbortController|null>(null),alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;controller.current?.abort();};},[]);
 useEffect(()=>{const list=messageList.current;if(list)list.scrollTop=list.scrollHeight;},[messages,busy]);
 const current=(ticket:number)=>alive.current&&ticket===epoch.current;
 const refreshStatus=async()=>{setStatusError("");try{const value=await scopedRequest<AssistantStatus>("/status");if(alive.current)setStatus(value);}catch(error){if(alive.current)setStatusError(error instanceof Error?error.message:"연결 상태를 확인하지 못했어요.");}};
 const loadSaved=async(pageOffset=0)=>{
  if(!user)return;setSavedLoading(true);setSavedError("");const ticket=++savedEpoch.current;
  try{const value=await scopedRequest<{items:ConversationSummary[];has_more:boolean}>("/conversations?limit=20&offset="+pageOffset);if(alive.current&&ticket===savedEpoch.current){setSaved(value.items);setMore(value.has_more);setOffset(pageOffset);}}
  catch(error){if(alive.current&&ticket===savedEpoch.current)setSavedError(error instanceof Error?error.message:"저장한 대화를 불러오지 못했어요.");}
  finally{if(alive.current&&ticket===savedEpoch.current)setSavedLoading(false);}
 };
 useEffect(()=>{void refreshStatus();if(user)void loadSaved();},[]);
 const begin=()=>{const ticket=++epoch.current;controller.current?.abort();controller.current=new AbortController();setBusy(true);setError("");setNotice("");return ticket;};
 const clear=()=>{setMessages([]);setQuestion("");setConversationId(null);setRemember(false);};
 const fail=(value:unknown)=>setError(value instanceof Error?value.message:"요청을 처리하지 못했어요. 직접 다시 시도해 주세요.");
 const send=async()=>{
  if(!question.trim()||busy)return;const ticket=begin(),text=question;
  try{const answer=await scopedRequest<AssistantResponse>("/ask","POST",{question:text,remember:!!user&&remember,history:recentUserHistory(messages),...(conversationId?{conversation_id:conversationId}:{})},controller.current!.signal);
   if(current(ticket)){setMessages(old=>[...old,{role:"user" as const,content:text},{role:"assistant" as const,content:answer.answer,answer}].slice(-20));setQuestion("");setConversationId(answer.conversation_id);if(remember&&user)void loadSaved();}
  }catch(error){if(current(ticket))fail(error);}finally{if(current(ticket))setBusy(false);}
 };
 const resume=async(id:string)=>{
  if(busy)return;if((messages.length||question.trim())&&!window.confirm("현재 화면의 대화를 닫고 저장한 대화를 불러올까요? 저장하지 않은 내용은 사라집니다."))return;
  const ticket=begin();try{const value=await scopedRequest<Conversation>("/conversations/"+encodeURIComponent(id),"GET",undefined,controller.current!.signal);if(current(ticket)){setMessages(value.messages.map(({role,content})=>({role,content})));setQuestion("");setConversationId(value.id);setRemember(true);setNotice("저장한 대화를 불러왔어요. 이전 답변의 출처와 현재 상태는 다시 확인해 주세요.");}}
  catch(error){if(current(ticket))fail(error);}finally{if(current(ticket))setBusy(false);}
 };
 const remove=async(id:string,end=false)=>{
  if(busy||!window.confirm(end?"이 대화를 끝내고 저장된 대화 내용을 지울까요? 복구할 수 없어요.":"저장한 대화를 삭제할까요? 대화 내용은 복구할 수 없어요."))return;
  const ticket=begin();try{await scopedRequest<{cleared:true}>("/conversations/"+encodeURIComponent(id)+(end?"/end":""),end?"POST":"DELETE",undefined,controller.current!.signal);if(current(ticket)){if(id===conversationId)clear();setNotice(end?"대화를 끝내고 저장 내용을 지웠어요.":"저장한 대화를 삭제했어요.");void loadSaved();}}
  catch(error){if(current(ticket))fail(error);}finally{if(current(ticket))setBusy(false);}
 };
 const toggleRemember=async()=>{
  if(busy)return;if(!remember){setRemember(true);return;}
  if(!conversationId){setRemember(false);return;}
  if(!window.confirm("대화 저장을 끄고 서버에 저장된 이 대화 내용을 지울까요? 현재 화면의 내용은 임시로만 남습니다."))return;
  const ticket=begin();try{await scopedRequest("/conversations/"+encodeURIComponent(conversationId),"DELETE",undefined,controller.current!.signal);if(current(ticket)){setConversationId(null);setRemember(false);setNotice("저장을 끄고 저장된 내용을 지웠어요. 현재 화면에서만 임시로 이어집니다.");void loadSaved();}}
  catch(error){if(current(ticket))fail(error);}finally{if(current(ticket))setBusy(false);}
 };
 const temporaryEnd=()=>{if(!window.confirm("임시 대화를 끝내고 화면의 내용을 지울까요? 복구할 수 없어요."))return;epoch.current++;controller.current?.abort();clear();setBusy(false);setError("");setNotice("임시 대화를 지웠어요.");};
 const newConversation=()=>{if(!window.confirm("현재 화면을 닫고 새 대화를 시작할까요? 저장된 대화는 목록에 남고, 저장하지 않은 임시 내용은 사라집니다."))return;epoch.current++;controller.current?.abort();clear();setBusy(false);setError("");setNotice("새 임시 대화를 시작했어요. 저장하려면 다시 직접 선택해 주세요.");};
 return <section className="chat-page"><header className="chat-heading"><h1>육아 도우미</h1><p>육아템·공구·서비스 질문을 남겨 주세요.</p></header><p className="chat-mode" role="status">{assistantStatusMessage(status)}</p>{statusError&&<div className="chat-status-error" role="alert"><p>{statusError}</p><button className="secondary" onClick={()=>void refreshStatus()}>연결 상태 다시 확인</button></div>}
 <div ref={messageList} className="chat-messages" role="log" aria-label="도우미 대화" aria-live="polite" aria-relevant="additions">{messages.map((message,index)=><article className={"chat-message "+message.role} key={index}><h2>{message.role==="user"?"내 질문":"도우미"}</h2>{message.answer?<AssistantAnswer answer={message.answer}/>:<p className="ugc-text">{message.content}</p>}{message.role==="assistant"&&!message.answer&&<p className="hint">이전 대화입니다. 현재 정보와 출처는 새 질문으로 다시 확인해 주세요.</p>}</article>)}</div>
 <form className="chat-form" onSubmit={event=>{event.preventDefault();void send();}}><label className="field"><span>도우미에게 질문</span><textarea rows={embedded?2:3} required minLength={2} maxLength={1200} placeholder="예: 기저귀를 비교할 때 어떤 기준을 볼까요?" disabled={busy} value={question} onChange={event=>setQuestion(event.target.value)} onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={()=>{composing.current=false;}} onKeyDown={event=>{if(chatEnterSubmits({key:event.key,shiftKey:event.shiftKey,isComposing:composing.current||event.nativeEvent.isComposing,keyCode:event.nativeEvent.keyCode})){event.preventDefault();if(!event.repeat&&!busy)event.currentTarget.form?.requestSubmit();}}} aria-describedby="chat-input-help chat-retention-help"/></label><p className="hint" id="chat-input-help">Enter 전송 · Shift+Enter 줄바꿈 · 2~1,200자</p><div className="chat-retention">{user&&<label className="chat-checkbox"><input type="checkbox" checked={remember} disabled={busy} onChange={()=>void toggleRemember()}/><span>계정에 저장하고 이어가기</span></label>}<p className="hint" id="chat-retention-help">{remember?"선택 후 성공한 대화만 저장 · 마지막 저장 활동부터 30일 보관":user?"기본은 임시 대화예요. 저장 선택 시 30일 보관해요.":(embedded?"임시 대화 · 창을 닫아도 유지되며 새로고침하면 지워져요.":"임시 대화예요. 이동·재로그인 후에는 이어볼 수 없어요.")}</p></div><div className="actions chat-compose-actions"><button type="submit" disabled={busy||question.trim().length<2}>{busy?"응답을 기다리는 중…":error?"질문 직접 다시 보내기":"질문 보내기"}</button>{!embedded&&(messages.length>0||conversationId)&&<button type="button" className="secondary" disabled={busy} onClick={()=>conversationId?void remove(conversationId,true):temporaryEnd()}>대화 종료·삭제</button>}{!embedded&&messages.length>0&&<button type="button" className="secondary" disabled={busy} onClick={newConversation}>새 대화</button>}</div>{busy&&<p role="status">자료와 현재 접근 권한을 확인하고 답변을 준비하고 있어요. 실제 처리 방식은 응답에서 확인할 수 있어요.</p>}{error&&<div role="alert"><p>{error}</p><p>질문은 유지되며 자동 재전송하지 않아요. 저장 여부가 불확실하면 저장 목록을 먼저 확인해 주세요.</p></div>}{notice&&<p role="status">{notice}</p>}</form>
 <ChatGuidance>{embedded&&(messages.length>0||conversationId)&&<div className="actions"><button type="button" className="secondary" disabled={busy} onClick={()=>conversationId?void remove(conversationId,true):temporaryEnd()}>대화 종료·삭제</button><button type="button" className="secondary" disabled={busy} onClick={newConversation}>새 대화</button></div>}</ChatGuidance>
 {user&&<>{savedError&&<p role="alert">저장 목록을 불러오지 못했어요. 아래 ‘저장한 대화’를 열어 다시 확인해 주세요.</p>}<details className="saved-conversations"><summary>저장한 대화{savedLoading?" · 불러오는 중":savedError?" · 연결 확인 필요":""}</summary><div className="saved-conversations-content"><p>직접 저장한 대화는 같은 계정에서 이어볼 수 있어요. 보관 기간이 지난 대화는 표시하지 않아요.</p><button className="secondary" disabled={busy||savedLoading} onClick={()=>void loadSaved(offset)}>저장 목록 새로고침</button>{savedLoading&&<p role="status">저장 목록을 불러오고 있어요.</p>}{savedError&&<p role="alert">{savedError} 이전 목록은 최신 상태가 아닐 수 있어요.</p>}{!savedLoading&&!savedError&&!saved.length&&<p>저장한 대화가 없어요.</p>}{saved.map(item=><article key={item.id}><h3>{item.title}</h3><p className="hint">마지막 저장 {date(item.updated_at)} · 보관 기한 {date(item.expires_at)}</p><div className="actions"><button className="secondary" disabled={busy} onClick={()=>void resume(item.id)}>이 대화 이어보기</button><button className="secondary danger" disabled={busy} onClick={()=>void remove(item.id)}>이 대화 삭제</button></div></article>)}{(offset>0||more)&&<nav className="actions" aria-label="저장 대화 페이지"><button className="secondary" disabled={!offset||busy||savedLoading} onClick={()=>void loadSaved(Math.max(0,offset-20))}>이전</button><button className="secondary" disabled={!more||busy||savedLoading} onClick={()=>void loadSaved(offset+20)}>다음</button></nav>}</div></details></>}
 </section>;
}

export function ChatGuidance({children}:{children?:ReactNode}={}) {
 return <details className="chat-guidance"><summary>이용 안내·저장·관련 화면</summary><div className="chat-guidance-content">{children}<p>아이의 이름·생일·사진, 연락처·주소·건강정보를 적지 마세요. 계정의 비공개 정보는 외부 모델이나 분석 시스템으로 전송하지 않습니다.</p><p>의료 판단·실시간 가격·인증 여부는 확인 가능한 근거가 없으면 답변을 보류해요. 답변마다 모델이 선택한 근거 안내·자료 검색 안내·답변 보류 등 실제 처리 방식을 구분하고 출처를 표시합니다.</p><p>대화 저장은 기본으로 꺼져 있어요. 임시 대화는 화면 이동이나 새 로그인 후 이어볼 수 없어요. <Link to="/login?returnTo=%2Fchat">로그인</Link> 후 직접 선택하면 선택 이후 성공한 질문과 답변을 저장합니다. 계정당 20개 대화, 대화당 20개 메시지까지 저장하며 마지막 저장 활동부터 30일간 보관해요. 대화 종료·삭제·저장 끄기로 내용을 지울 수 있어요.</p><p>화면에는 최근 20개 메시지를 표시해요. 응답에 실패하면 질문을 유지하고 자동 재전송하지 않아요. 저장 여부가 불확실하면 목록을 확인한 뒤 직접 다시 시도해 주세요.</p><nav className="actions" aria-label="도우미 관련 화면"><Link to="/advisor">조건으로 육아템 찾기</Link><Link to="/calculator">단가 비교</Link><Link to="/">공구 찾기</Link><Link to="/demands">공구 수요·커뮤니티</Link></nav></div></details>;
}
