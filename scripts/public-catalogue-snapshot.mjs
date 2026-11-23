import { sellerPreviewUrl } from './cloudflare-public-worker.mjs';

export function catalogueSnapshot(items) {
  return items.filter(item => item.status === 'active' && item.review_state === 'clear' &&
    item.source_type === 'seller_page' && !item.is_demo && sellerPreviewUrl(item.seller_url) &&
    Number.isFinite(Date.parse(item.source_checked_at))).map(item => ({
    id: item.id, title: item.title, seller: item.seller_name, url: item.seller_url,
    checked: item.source_checked_at, expires: item.expires_at || item.source_fresh_until,
  }));
}
