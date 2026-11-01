export type User = {
  id: string;
  email: string;
  nickname: string;
  is_admin: boolean;
  seller_status: string | null;
  points_balance: number;
  email_verified: boolean;
};
export type Campaign = {
  id: string;
  brand_id: string;
  title: string;
  description: string;
  category: string;
  kind: string;
  price: number;
  shipping_fee: number;
  unit: string;
  minimum_quantity: number;
  stock: number;
  reserved_quantity: number;
  recruitment_status?:
    | "collecting"
    | "minimum_met"
    | "closed_met"
    | "closed_shortfall"
    | "cancelled";
  remaining_quantity?: number;
  ends_at: string;
  status: string;
  revision: number;
  is_demo: boolean;
  brand_name: string;
  seller_name: string;
  refund_policy: string;
  shipping_policy: string;
  source_url: string | null;
  verified_at: string;
  saved?: boolean;
};
export type Hotdeal = {
  id: string;
  title: string;
  category: string;
  price: number;
  shipping_fee: number;
  seller_name: string;
  source_url: string | null;
  source_name: string;
  verified_at: string;
  ends_at: string;
  status: string;
  is_demo: boolean;
};
export type Brand = {
  id: string;
  name: string;
  description: string;
  logo_text: string;
};
export type Reservation = {
  id: string;
  campaign_id: string;
  title: string;
  quantity: number;
  status: string;
  created_at?: string;
  buyer_alias?: string;
};
export type Coupon = {
  id: string;
  brand_id: string;
  brand_name: string;
  title: string;
  amount: number;
  min_spend: number;
  stock: number;
  issued_count: number;
  ends_at: string;
  points_cost: number;
  claimed: boolean;
  is_demo: boolean;
};
export type Wallet = {
  balance: number;
  ledger: { id: string; delta: number; reason: string; created_at: string }[];
  coupons: {
    id: string;
    coupon_id: string;
    code: string;
    title: string;
    brand_name: string;
    amount: number;
    min_spend: number;
    ends_at: string;
    status: string;
    is_demo: boolean;
  }[];
};
export type Question = {
  id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
};
export type Application = {
  status: string;
  review_note: string;
  fields: Record<string, string | boolean>;
  user_id?: string;
  nickname?: string;
};
export type Report = {
  id: string;
  target_type: string;
  target_id: string;
  reason: string;
  status: string;
};
