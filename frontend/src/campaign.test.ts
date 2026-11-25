import { expect, it } from 'vitest';
import { readCampaign } from './campaign';

it('accepts known campaign labels and discards unrelated query values', () => {
  expect(readCampaign('?utm_source=kakao&utm_medium=social&utm_campaign=community_launch&email=private')).toEqual({
    source: 'kakao', medium: 'social', campaign: 'community_launch',
  });
});

it.each(['', '?utm_source=user@example.com&utm_medium=share&utm_campaign=groupbuy', '?utm_source=web&utm_medium=share'])('ignores incomplete or unknown tags', search => {
  expect(readCampaign(search)).toBeNull();
});
