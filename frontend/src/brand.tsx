import { IconBabyBottle, IconBabyCarriage, IconDroplet, IconHeartHandshake, IconHorseToy, IconWash } from "@tabler/icons-react";

export const BRAND_NAME = "모두의육아";
export const APP_NAME = "모두의 육아 - 육아템 공동구매,핫딜";

/** Uses the user's original transparent lettering; the pasted vector was truncated. */
export function BrandLockup({ stacked = false }: { stacked?: boolean }) {
  return (
    <span className={stacked ? "brand-lockup stacked" : "brand-lockup"} role="img" aria-label={BRAND_NAME}>
      <img className="brand-symbol" src="/brand/symbol.svg" alt="" width="860" height="714" />
      <img className="brand-lettering" src="/brand/wordmark.png" alt="" width="3066" height="744" />
    </span>
  );
}

export function CategoryIcon({ category, size = 30 }: { category: string; size?: number }) {
  const icons = {
    "기저귀·물티슈": IconWash,
    "수유·이유식": IconBabyBottle,
    "목욕·위생": IconDroplet,
    "외출·안전": IconBabyCarriage,
    "놀이·도서": IconHorseToy,
    "육아생활": IconHeartHandshake,
  };
  const Icon = icons[category as keyof typeof icons] || IconHeartHandshake;
  return <Icon size={size} stroke={1.7} aria-hidden="true" focusable="false" />;
}
