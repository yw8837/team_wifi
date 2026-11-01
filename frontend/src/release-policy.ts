import { matchRoutes } from "react-router-dom";
export const PUBLIC_RELEASE = import.meta.env.VITE_PUBLIC_RELEASE === "1";
export const DEPLOYED_MODE = PUBLIC_RELEASE || import.meta.env.VITE_BETA_MODE === "1";
export function publicConfigMatches(config: unknown): boolean {
  if (!config || typeof config !== "object") return false;
  const value = config as Record<string, unknown>;
  return value.public_release === true && value.beta_mode === false;
}
export function publicBrowsePath(path: string): string {
  const match=matchRoutes([ {path:"/demands/new",handle:{owned:true}}, ...["/", "/offers/:id", "/demands", "/demands/:id", "/calculator", "/welcome", "/my"].map(path => ({ path, handle: {owned:false} }))], path);
  return match && !match.some(route=>route.route.handle?.owned) ? path : "/";
}
export type ComparisonInput = { price: string; shipping: string; quantity: string };
export function compareUnit(input: ComparisonInput): {total:number; unit:number} | null {
  if ([input.price, input.shipping, input.quantity].some(v => !v.trim())) return null;
  const [price, shipping, quantity] = [input.price, input.shipping, input.quantity].map(Number);
  if (![price, shipping, quantity].every(Number.isFinite) || price < 0 || shipping < 0 || quantity <= 0 || quantity > 1e12 || price + shipping > 1e12) return null;
  const unit=(price+shipping)/quantity;
  return Number.isFinite(unit)?{ total: price + shipping, unit }:null;
}

export function publicReturnPath(path:string):string {
 return matchRoutes(["/", "/offers/:id", "/demands", "/demands/new", "/demands/:id", "/calculator", "/welcome", "/my", "/my/saved", "/settings", "/admin"].map(path=>({path})),path)?path:"/";
}
