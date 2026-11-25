const sources = ['web', 'android', 'kakao', 'instagram', 'naver', 'google', 'youtube', 'discord', 'presentation', 'qr'];
const media = ['share', 'social', 'search', 'referral', 'qr', 'presentation'];
const campaigns = ['groupbuy', 'community_launch', 'midterm'];

export function readCampaign(search: string) {
  const params = new URLSearchParams(search);
  const source = params.get('utm_source') || '';
  const medium = params.get('utm_medium') || '';
  const campaign = params.get('utm_campaign') || '';
  if (!sources.includes(source) || !media.includes(medium) || !campaigns.includes(campaign)) return null;
  return { source, medium, campaign };
}
