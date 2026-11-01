import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
export type Offer = { id:string; title:string; category:string; summary:string; source_name:string; source_url:string; source_checked_at:string; entry_type:"shopping_reference"|"verified_offer"; price:number|null; shipping_fee:number|null; unit:string|null; expires_at:string|null; comparison_notes:string[]; is_affiliate:boolean; saved:boolean };
export type Author = {id:string;nickname:string};
export type Demand = {id:string;title:string;body:string;category:string;author:Author;created_at:string;interest_count:number;interested:boolean;comment_count:number;own:boolean};
export type Comment = {id:string;body:string;author:Author;created_at:string;own:boolean};
export async function readPublic<T>(path:string):Promise<T> {
  try { return await api<T>(path); } catch (e) {
    if (!(e instanceof ApiError) || ![0,502,503,504].includes(e.status)) throw e;
    await new Promise(resolve => setTimeout(resolve, 700));
    return api<T>(path);
  }
}
export function usePublicResource<T>(path:string|null, sessionKey="") {
  const [data,setData]=useState<T|null>(null), [error,setError]=useState(""), [loading,setLoading]=useState(!!path), [version,setVersion]=useState(0);
  const reload=useCallback(()=>setVersion(v=>v+1),[]);
  useEffect(()=>{
    let live=true;
    setData(null);setError("");setLoading(!!path);
    if (path) void readPublic<T>(path).then(value=>{if(live)setData(value);}).catch(e=>{if(live)setError(e instanceof Error?e.message:"정보를 불러오지 못했습니다.");}).finally(()=>{if(live)setLoading(false);});
    return ()=>{live=false;};
  },[path,sessionKey,version]);
  return {data,error,loading,reload};
}
export const releasePath=(kind:string,id?:string)=>"/release/"+kind+(id?"/"+encodeURIComponent(id):"");
