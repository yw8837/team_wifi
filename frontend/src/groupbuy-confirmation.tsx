import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { useAction } from "./shared";

type Action=ReturnType<typeof useAction>;
export type GroupbuyConfirmationOptions={title:string;description:string;details:{label:string;value:string}[];confirmLabel:string;isCurrent:()=>boolean;validate?:()=>string;work:()=>Promise<unknown>;onSuccess?:()=>void};
function restoreFocus(opener:HTMLElement|null){
 const restore=()=>{if(opener?.isConnected&&!(opener as HTMLButtonElement).disabled)opener.focus();else document.getElementById("main")?.focus();};
 if(typeof document==="undefined")return;
 if(typeof requestAnimationFrame==="function")requestAnimationFrame(restore);else restore();
}
export function useGroupbuyConfirmation(action:Action){
 const [pending,setPending]=useState<GroupbuyConfirmationOptions|null>(null),[busy,setBusy]=useState(false);
 const current=useRef<GroupbuyConfirmationOptions|null>(null),lock=useRef(false),opener=useRef<HTMLElement|null>(null);
 const close=(toMain=false)=>{current.current=null;setPending(null);restoreFocus(toMain?null:opener.current);};
 const cancel=()=>{if(!lock.current)close();};
 const request=(make:()=>GroupbuyConfirmationOptions)=>{
  if(current.current||lock.current)return;
  const next=make();if(!next.isCurrent()){action.setError("계정 상태가 변경됐어요. 현재 계정에서 화면을 다시 열어 주세요.");return;}
  opener.current=typeof document!=="undefined"&&typeof HTMLElement!=="undefined"&&document.activeElement instanceof HTMLElement?document.activeElement:null;
  current.current=next;action.setError("");action.setMessage("");setPending(next);
 };
 const apply=async()=>{
  const selected=current.current;if(!selected||lock.current)return;
  if(!selected.isCurrent()){action.setError("계정 상태가 변경돼 이전 확인 내용을 적용하지 않습니다.");close();return;}
  lock.current=true;setBusy(true);
  try{
   const succeeded=await action.run(async()=>{
    if(!selected.isCurrent())throw new Error("계정 상태가 변경돼 이전 확인 내용을 적용하지 않습니다.");
    const problem=selected.validate?.();if(problem)throw new Error(problem);
    await selected.work();
    if(!selected.isCurrent())throw new Error("계정 상태가 변경돼 이전 요청의 결과를 표시하지 않습니다.");
    selected.onSuccess?.();
   });
   // Successful actions reload content and may remove the original trigger after this frame.
   if(succeeded||!selected.isCurrent())close(true);
  }finally{lock.current=false;setBusy(false);}
 };
 return {request,waiting:!!pending,dialog:pending?<GroupbuyConfirmationDialog options={pending} busy={busy||action.busy} error={action.error} onApply={()=>void apply()} onCancel={cancel}/>:null};
}
export function GroupbuyConfirmationDialog({options,busy,error,onApply,onCancel}:{options:GroupbuyConfirmationOptions;busy:boolean;error:string;onApply:()=>void;onCancel:()=>void}){
 const id=useId(),panel=useRef<HTMLElement|null>(null),heading=useRef<HTMLHeadingElement|null>(null);
 useEffect(()=>{heading.current?.focus();},[]);
 const keyboard=(event:KeyboardEvent<HTMLElement>)=>{
  if(event.key==="Escape"){event.preventDefault();if(!busy)onCancel();return;}
  if(event.key!=="Tab")return;
  const buttons=Array.from(panel.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")||[]);
  if(!buttons.length){event.preventDefault();return;}
  const first=buttons[0],last=buttons[buttons.length-1],active=document.activeElement;
  if(event.shiftKey&&(active===first||!buttons.includes(active as HTMLButtonElement))){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&(active===last||!buttons.includes(active as HTMLButtonElement))){event.preventDefault();first.focus();}
 };
 return <div className="groupbuy-confirm-overlay"><section className="groupbuy-confirm-panel" role="alertdialog" aria-modal="true" aria-labelledby={id+"-title"} aria-describedby={id+"-description"} aria-busy={busy} ref={panel} onKeyDown={keyboard}>
  <h2 id={id+"-title"} tabIndex={-1} ref={heading}>{options.title}</h2><p id={id+"-description"}>{options.description}</p><dl className="groupbuy-confirm-details">{options.details.map((detail,index)=><div key={detail.label+index}><dt>{detail.label}</dt><dd className="ugc-text">{detail.value}</dd></div>)}</dl>
  {error&&<p role="alert" className="error">{error}</p>}{busy&&<p role="status">처리하고 있어요. 완료될 때까지 기다려 주세요.</p>}
  <div className="actions"><button type="button" className="secondary" disabled={busy} onClick={onCancel}>취소</button><button type="button" disabled={busy} onClick={onApply}>{busy?"적용 중…":options.confirmLabel}</button></div>
 </section></div>;
}
