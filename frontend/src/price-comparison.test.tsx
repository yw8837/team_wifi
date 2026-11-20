import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { calculateSavings, PriceComparison } from "./price-comparison";

const amount=(price:string,shipping="0",quantity="1")=>({price,shipping,quantity});
describe("comparable total prices",()=>{
  it("calculates the collected online price saving",()=>{
    const value=calculateSavings(amount("109000"),amount("129000"))!;
    expect(value.saving).toBe(20000);expect(value.percent).toBeCloseTo(15.5038759);
  });
  it("normalizes quantities and includes shipping",()=>{
    const value=calculateSavings(amount("20000","3000","2"),amount("12000","1000","1"))!;
    expect(value.referenceTotal).toBe(26000);expect(value.saving).toBe(3000);
  });
  it("preserves higher group-buy costs instead of claiming a discount",()=>{
    expect(calculateSavings(amount("15000"),amount("12000"))!.saving).toBe(-3000);
  });
  it("does not infer missing shipping, zero quantity, or free reference prices",()=>{
    for(const value of [amount("100",""),amount("100","0","0"),amount("0"),amount("-1")])
      expect(calculateSavings(amount("50"),value)).toBeNull();
  });
  it("shows missing references and an unchecked product match with no invented offline price",()=>{
    const html=renderToStaticMarkup(<PriceComparison item={{price:109000,shipping_fee:0,comparison_quantity:1}}/>);
    expect(html).toContain("오프라인 매장");expect(html).toContain("가격 확인일");
    expect(html).not.toContain('checked=""');expect(html).not.toContain("저렴해요");
  });
});
