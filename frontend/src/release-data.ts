import type { Groupbuy } from "./groupbuys";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
export type Offer = { id:string; title:string; category:string; summary:string; source_name:string; source_url:string; source_checked_at:string; entry_type:"shopping_reference"|"verified_offer"; price:number|null; shipping_fee:number|null; unit:string|null; expires_at:string|null; comparison_notes:string[]; is_affiliate:boolean; saved:boolean };
export type Author = {id:string;nickname:string};
export type PostType = "question"|"experience"|"information"|"demand";
export type Demand = {linked_groupbuy?:Groupbuy|null;post_type?:PostType;id:string;title:string;body:string;category:string;author:Author;created_at:string;updated_at?:string|null;revision?:number;interest_count:number;interested:boolean;comment_count:number;own:boolean};
export type Comment = {id:string;body:string;author:Author;created_at:string;updated_at?:string|null;revision?:number;own:boolean};
export async function readPublic<T>(path:string):Promise<T> {
  try { return await api<T>(path); } catch (e) {
    if (!(e instanceof ApiError) || ![0,502,503,504].includes(e.status)) throw e;
    await new Promise(resolve => setTimeout(resolve, 700));
    return api<T>(path);
  }
}
export function usePublicResource<T>(path:string|null, sessionKey="") {
  const [data,setData]=useState<T|null>(null), [error,setError]=useState(""), [loading,setLoading]=useState(!!path), [version,setVersion]=useState(0);
  const [scope,setScope]=useState({path,sessionKey});
  const reload=useCallback(()=>setVersion(v=>v+1),[]);
  useEffect(()=>{
    let live=true;
    setScope({path,sessionKey});setData(null);setError("");setLoading(!!path);
    if (path) void readPublic<T>(path).then(value=>{if(live)setData(value);}).catch(e=>{if(live)setError(e instanceof Error?e.message:"정보를 불러오지 못했습니다.");}).finally(()=>{if(live)setLoading(false);});
    return ()=>{live=false;};
  },[path,sessionKey,version]);
  const current=scope.path===path&&scope.sessionKey===sessionKey;
  return {data:current?data:null,error:current?error:"",loading:!!path&&(!current||loading),reload};
}
export const releasePath=(kind:string,id?:string)=>"/release/"+kind+(id?"/"+encodeURIComponent(id):"");
