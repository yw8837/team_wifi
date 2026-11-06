import { useEffect, useRef, useState } from "react";
import { readSessionToken } from "./session-storage";

type ClearAccount=(expectedToken?:string|null)=>boolean;
type ExitOptions={expectedToken:string;request:()=>Promise<unknown>;isCurrent:()=>boolean;clear:ClearAccount;onCompleted:()=>void};

/** A successful old request cannot clear or navigate a newer session. */
export async function completeAccountExit({expectedToken,request,isCurrent,clear,onCompleted}:ExitOptions):Promise<boolean> {
 if(!isCurrent()||readSessionToken()!==expectedToken)return false;
 await request();
 if(!isCurrent()||readSessionToken()!==expectedToken||!clear(expectedToken))return false;
 if(!isCurrent()||readSessionToken()!==null)return false;
 onCompleted();
 return true;
}

export function useAccountExit(owner:string|undefined,clear:ClearAccount) {
 const token=readSessionToken(),mounted=useRef(true),sequence=useRef(0),lock=useRef<number|null>(null);
 const scope=useRef({owner,token});
 if(scope.current.owner!==owner||scope.current.token!==token){scope.current={owner,token};sequence.current++;lock.current=null;}
 const [state,setState]=useState({owner,token,busy:false,error:""});
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;sequence.current++;lock.current=null;};},[]);
 async function run(request:()=>Promise<unknown>,onCompleted:()=>void):Promise<boolean> {
  const expectedToken=readSessionToken(),expectedOwner=owner;
  if(!mounted.current||lock.current!==null||expectedOwner!==scope.current.owner||expectedToken!==scope.current.token)return false;
  if(!expectedToken){setState({owner,token:expectedToken,busy:false,error:"로그인 상태가 변경됐어요. 현재 계정을 확인하고 다시 진행해 주세요."});return false;}
  const ticket=++sequence.current;lock.current=ticket;
  const ownsRequest=()=>mounted.current&&sequence.current===ticket&&scope.current.owner===expectedOwner&&scope.current.token===expectedToken;
  const isCurrent=()=>ownsRequest()&&readSessionToken()===expectedToken;
  setState({owner,token:expectedToken,busy:true,error:""});
  try{const completed=await completeAccountExit({expectedToken,request,isCurrent:ownsRequest,clear,onCompleted});if(!completed&&isCurrent())setState({owner,token:expectedToken,busy:false,error:"로그인 정보를 지우지 못했어요. 현재 계정을 확인한 뒤 다시 시도해 주세요."});return completed;}
  catch(error){if(isCurrent())setState({owner,token:expectedToken,busy:false,error:error instanceof Error?error.message:"요청을 처리하지 못했어요. 입력 내용은 유지됩니다."});return false;}
  finally{if(lock.current===ticket)lock.current=null;if(isCurrent())setState(old=>({...old,busy:false}));}
 }
 const current=state.owner===owner&&state.token===token;
 return {busy:current&&state.busy,error:current?state.error:"",message:"",run};
}
