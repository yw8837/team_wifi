import { useState } from "react";
import { money, safeExternalUrl } from "./api";
import { communityTime } from "./community";
import { compareUnit } from "./release-policy";
import type { ComparisonInput } from "./release-policy";
import { Field } from "./shared";
import "./price-comparison.css";

export type PriceReference = {
  channel:"online"|"offline"; seller_name:string; url:string; price:number;
  shipping_fee:number|null; quantity:number; scope:string; checked_at:string; fresh_until:number;
};
type Offer = {price:number|null;shipping_fee:number|null;comparison_quantity?:number|null;price_references?:PriceReference[]};

export function calculateSavings(group:ComparisonInput, reference:ComparisonInput) {
  const deal=compareUnit(group), regular=compareUnit(reference);
  if (!deal || !regular || regular.unit<=0) return null;
  const equivalent=regular.unit*Number(group.quantity);
  if (!Number.isFinite(equivalent) || equivalent>1e12) return null;
  const saving=equivalent-deal.total;
  return {groupTotal:deal.total, referenceTotal:equivalent, saving, percent:saving/equivalent*100};
}

function Savings({value}:{value:ReturnType<typeof calculateSavings>}) {
  if (!value) return <p className="hint">가격·배송비·수량을 모두 확인하면 차액을 계산합니다.</p>;
  const difference=Math.abs(value.saving);
  return <output className="price-saving" aria-live="polite">
    <strong>{difference<0.005?"같은 금액이에요":`공구가 ${money(difference)} ${value.saving>0?"저렴해요":"더 비싸요"}`}</strong>
    <span>{Math.abs(value.percent).toFixed(1)}% 차이 · 공구 총액 {money(value.groupTotal)}</span>
    <span>같은 수량으로 환산한 비교 총액 {money(value.referenceTotal)}</span>
  </output>;
}

const toInput=(price:number|null,shipping:number|null,quantity?:number|null):ComparisonInput=>({
  price:price==null?"":String(price),shipping:shipping==null?"":String(shipping),quantity:quantity==null?"":String(quantity)
});

export function PriceComparison({item}: {item:Offer}) {
  const original=toInput(item.price,item.shipping_fee,item.comparison_quantity);
  const [group,setGroup]=useState(original);
  const [reference,setReference]=useState<ComparisonInput>({price:"",shipping:"0",quantity:""});
  const [channel,setChannel]=useState("offline"),[shop,setShop]=useState(""),[checked,setChecked]=useState("");
  const [matched,setMatched]=useState(false);
  const now=Date.now()/1000;
  const today=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
  const references=(item.price_references||[]).filter(row=>row.fresh_until>now);
  const manual=matched&&shop.trim()&&checked&&checked<=today?calculateSavings(group,reference):null;
  function fields(value:ComparisonInput,change:(value:ComparisonInput)=>void,prefix:string) {
    return <div className="price-inputs">{([
      ["price","할인 적용 후 상품 금액 (원)"],["shipping","배송비 (원)"],["quantity","수량 (같은 단위)"]
    ] as const).map(([key,label])=><Field key={key} label={prefix+" "+label} type="number" inputMode="decimal"
      min={key==="quantity"?"0.000001":"0"} max="1000000000000" step="any" value={value[key]}
      onChange={event=>change({...value,[key]:event.target.value})}/>)}</div>;
  }
  return <section className="price-comparison" aria-labelledby="price-comparison-title">
    <h2 id="price-comparison-title">공구로 얼마나 아낄까요?</h2>
    <p className="hint">같은 제품·구성·수량의 배송비 포함 금액을 비교해요. 회원·쿠폰·카드 할인은 실제 적용 가능한 금액으로 확인하세요.</p>
    {references.length>0?<div className="price-reference-grid">{references.map(row=><article className="price-reference" key={row.url}>
      <h3>{row.channel==="online"?"온라인":"오프라인"} · {row.seller_name}</h3>
      <p>{row.scope}</p>
      <p>공구 {item.price==null?"미확인":money(item.price)} / 비교 가격 {money(row.price)}</p>
      <Savings value={calculateSavings(original,toInput(row.price,row.shipping_fee,row.quantity))}/>
      <p className="hint">출처 확인 {communityTime(row.checked_at)} · 추가 옵션·지역 배송비는 판매처에서 확인하세요.</p>
      {safeExternalUrl(row.url)&&<a href={safeExternalUrl(row.url)!} target="_blank" rel="noopener noreferrer">비교 판매처 확인 ↗</a>}
    </article>)}</div>:<p>확인된 비교 가격을 수집 중이에요. 직접 확인한 가격을 아래에 입력해 비교할 수 있어요.</p>}
    <details className="price-manual"><summary>매장·다른 온라인 가격과 직접 비교</summary>
      <p>입력값은 이 화면에서만 계산합니다. 같은 모델·용량·구성을 확인하고, 수량 단위도 맞춰 주세요.</p>
      <div className="price-manual-grid"><div><h3>공구 구매 조건</h3>{fields(group,setGroup,"공구")}</div>
        <div><h3>비교 구매 조건</h3><label className="field"><span>비교 채널</span><select value={channel} onChange={event=>setChannel(event.target.value)}><option value="offline">오프라인 매장</option><option value="online">온라인 판매처</option></select></label>
          <Field label={channel==="offline"?"매장명·지점":"온라인 판매처 이름"} value={shop} maxLength={100} onChange={event=>setShop(event.target.value)}/>
          <Field label="가격 확인일" type="date" value={checked} max={today} onChange={event=>setChecked(event.target.value)}/>
          {fields(reference,setReference,"비교")}</div></div>
      <label className="price-match"><input type="checkbox" checked={matched} onChange={event=>setMatched(event.target.checked)}/>같은 제품·규격·구성이며 수량 단위를 맞췄어요.</label>
      {manual?<><p className="hint">직접 입력 · {shop} · {checked} 확인</p><Savings value={manual}/></>:<p className="hint">판매처·확인일·금액·수량을 입력하고 동일 제품 여부를 확인해 주세요.</p>}
    </details>
  </section>;
}
