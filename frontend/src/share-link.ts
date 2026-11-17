/** Build a fresh campaign URL so incoming tracking and login parameters never leak. */
export function groupbuyShareLink(id: string, platform: 'web' | 'android'): string {
  const origin = import.meta.env.VITE_PUBLIC_WEB_ORIGIN || 'https://moduyuga.yeolmaeapps.kr';
  const url = new URL('/groupbuys/' + encodeURIComponent(id), origin);
  url.searchParams.set('utm_source', platform);
  url.searchParams.set('utm_medium', 'share');
  url.searchParams.set('utm_campaign', 'groupbuy');
  return url.href;
}
