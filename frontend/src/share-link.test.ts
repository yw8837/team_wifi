import { readFileSync } from 'node:fs';
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

it('exposes the public share image to crawlers before the app starts', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  const head = html.split('</head>')[0];
  const tags = new Map(Array.from(head.matchAll(/<meta property="(og:[^"]+)" content="([^"]+)"/g),
    ([, name, content]) => [name, content]));
  expect(tags.get('og:title')).toContain('모두의 육아');
  expect(tags.get('og:description')).toBeTruthy();
  const imageUrl = new URL(tags.get('og:image')!);
  expect(imageUrl.origin).toBe('https://moduyuga.yeolmaeapps.kr');
  const png = readFileSync(new URL('../public' + imageUrl.pathname, import.meta.url));
  expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  expect(png.readUInt32BE(16)).toBe(Number(tags.get('og:image:width')));
  expect(png.readUInt32BE(20)).toBe(Number(tags.get('og:image:height')));
});
