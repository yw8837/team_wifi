import { useRef } from "react";
import { api } from "./api";
import { createSessionAttempt } from "./session-storage";
import { useSessionAttempt } from "./shared";

/** Private drafts belong to the session which opened this mounted editor. */
export function useContentSessionAttempt(){
 const owner=useRef(createSessionAttempt().begin()),attempts=useSessionAttempt();
 return {begin:()=>{const attempt=attempts.begin();return {...attempt,isCurrent:()=>owner.current.isCurrent()&&attempt.isCurrent()};}};
}

/** A late or replaced session cannot send a private draft or finish its old navigation. */
export function useContentRequest(){
 const attempts=useContentSessionAttempt();
 return async function request<T=unknown>(path:string,method="GET",body?:unknown):Promise<T>{
  const attempt=attempts.begin();
  const changed=()=>new Error("계정 상태가 변경됐어요. 화면을 다시 열어 현재 계정을 확인해 주세요.");
  if(!attempt.isCurrent())throw changed();
  let result:T;
  try{result=await api<T>(path,method,body);}catch(error){if(!attempt.isCurrent())throw changed();throw error;}
  if(!attempt.isCurrent())throw changed();
  return result;
 };
}
