import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

type Listing = { id:string; title:string; seller:string; url:string; checked:string; expires:string };
const clock = new Intl.DateTimeFormat("ko-KR", {timeZone:"Asia/Seoul",month:"long",day:"numeric",hour:"numeric",minute:"2-digit"});
export function RecentCatalogue({retry}:{retry:()=>void}) {
  const {pathname} = useLocation();
  const detail = /^\/groupbuys\/([0-9a-f-]{36})(?:\/public)?\/?$/.exec(pathname)?.[1];
  const browsing = pathname === "/" || !!detail;
  const [items,setItems] = useState<Listing[]|null>(null);
  useEffect(()=>{
    if (!browsing) return;
    const controller = new AbortController();
    fetch("/recent-groupbuys.json",{signal:controller.signal,credentials:"omit"}).then(async response=>{
      if (!response.ok) throw Error();
      const rows:Listing[] = await response.json();
      setItems(rows.filter(row=>row && typeof row.url==="string" && /^https:\/\//.test(row.url) &&
        Date.parse(row.checked) <= Date.now() && Date.now()-Date.parse(row.checked)<72*3600000 &&
        Date.parse(row.expires)>Date.now()));
    }).catch(()=>{if (!controller.signal.aborted) setItems([])});
    return ()=>controller.abort();
  },[browsing]);
  const shown = items?.filter(row=>!detail || row.id===detail);
  return <section className="public-main" aria-label="공구 연결 안내">
    <h1>{browsing?"최근 확인한 공구":"서비스 연결이 지연되고 있어요"}</h1>
    <p role="status">{browsing?"최신 목록을 불러오는 중이에요. 아래 상품의 현재 가격과 주문 가능 여부는 판매처에서 확인해 주세요.":"로그인, 찜, 게시판, 방문 통계는 서버 연결이 필요해요."}</p>
    {shown?.map(row=><article className="panel" key={row.id}><h2>{row.title}</h2><p>{row.seller} · {clock.format(Date.parse(row.checked))} 확인</p><a className="button secondary" href={row.url} target="_blank" rel="noopener noreferrer">판매처에서 보기 ↗</a></article>)}
    {browsing && shown?.length===0 && <p>최근 확인한 자료에 표시할 상품이 없어요.</p>}
    <nav className="actions">{pathname!=="/"&&<Link to="/">최근 공구 보기</Link>}<Link to="/calculator">단가 계산기</Link><button type="button" onClick={retry}>연결 다시 확인</button></nav>
  </section>;
}
