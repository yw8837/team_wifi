import type { Campaign } from "./types";
export function recruitmentStatus(
  c: Campaign,
): NonNullable<Campaign["recruitment_status"]> {
  if (c.recruitment_status) return c.recruitment_status;
  if (!["active", "ended"].includes(c.status)) return "cancelled";
  const met = c.reserved_quantity >= c.minimum_quantity;
  return c.status === "ended" || new Date(c.ends_at).getTime() <= Date.now()
    ? met
      ? "closed_met"
      : "closed_shortfall"
    : met
      ? "minimum_met"
      : "collecting";
}
export function recruitmentLabel(c: Campaign) {
  return {
    collecting: "최소 수량 모집 중",
    minimum_met: "최소 모집수량 충족",
    closed_met: "모집 종료 · 최소 수량 충족",
    closed_shortfall: "모집 종료 · 최소 수량 미달",
    cancelled: "공개 모집 취소·미공개 종료",
  }[recruitmentStatus(c)];
}
export function remainingQuantity(c: Campaign) {
  return Math.max(0, c.remaining_quantity ?? c.stock - c.reserved_quantity);
}
