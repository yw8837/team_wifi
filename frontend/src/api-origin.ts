import { betaApiOrigin } from './beta-policy';

/** An explicit Vite development-only UI harness; production URL policy is unchanged. */
export function validateRuntimeApiOrigin(base: string): string | null {
  if (import.meta.env.DEV && import.meta.env.MODE === 'community-qa' && base === '/api'
      && typeof location !== 'undefined' && location.protocol === 'http:'
      && location.hostname === '127.0.0.1') return null;
  return betaApiOrigin(true, base);
}
