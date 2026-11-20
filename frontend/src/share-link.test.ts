import { describe, expect, it } from 'vitest';
import { groupbuyShareLink } from './share-link';

describe('groupbuy campaign links', () => {
  it.each(['web', 'android', 'kakao'] as const)('identifies %s sharing without account information', platform => {
    const url = new URL(groupbuyShareLink('public-product-id', platform));
    expect(url.protocol).toBe('https:');
    expect(url.pathname).toBe('/groupbuys/public-product-id');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      utm_source: platform,
      utm_medium: 'share',
      utm_campaign: 'groupbuy',
    });
  });

  it('keeps a malformed product identifier inside the path', () => {
    const url = new URL(groupbuyShareLink('id?token=private#fragment', 'web'));
    expect(url.searchParams.has('token')).toBe(false);
    expect(url.hash).toBe('');
    expect(url.pathname).toContain('%3F');
  });
});
