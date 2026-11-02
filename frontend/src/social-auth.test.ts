import { describe, expect, it } from 'vitest';
import { nativeReturn, proofPair } from './social-auth';

describe('social sign-in handoff', () => {
  it('allows only the fixed native callback with an opaque flow id', () => {
    const flow = 'ea270994-fb34-4989-82c3-af750223c761';
    expect(nativeReturn('kr.moduyuga.app://auth/complete?flow='+flow)).toBe('/auth/complete?flow='+flow);
    for (const url of ['https://evil.example/auth/complete?flow='+flow, 'kr.moduyuga.app://evil/complete?flow='+flow,
      'kr.moduyuga.app://auth/admin?flow='+flow, 'kr.moduyuga.app://auth/complete?flow=//evil.example']) expect(nativeReturn(url)).toBeNull();
  });
  it('binds every flow to a fresh 256-bit proof instead of a token in the URL', async () => {
    const first = await proofPair(), second = await proofPair();
    expect(first.verifier).toMatch(/^[a-zA-Z0-9_-]{43}$/);
    expect(first.challenge).toMatch(/^[a-zA-Z0-9_-]{43}$/);
    expect(first.verifier).not.toBe(second.verifier);
    expect(first.challenge).not.toBe(first.verifier);
  });
});
