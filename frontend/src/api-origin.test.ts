import { afterEach, describe, expect, it, vi } from 'vitest';
import { validateRuntimeApiOrigin } from './api-origin';

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
describe('loopback UI transport boundary', () => {
  it('allows only explicit localhost development mode and a relative API', () => {
    vi.stubEnv('DEV', true); vi.stubEnv('MODE', 'community-qa');
    vi.stubGlobal('location', { protocol: 'http:', hostname: '127.0.0.1' });
    expect(validateRuntimeApiOrigin('/api')).toBeNull();
    expect(() => validateRuntimeApiOrigin('http://127.0.0.1:18180/api')).toThrow();
    vi.stubGlobal('location', { protocol: 'http:', hostname: 'example.com' });
    expect(() => validateRuntimeApiOrigin('/api')).toThrow();
  });
  it('never relaxes release builds or normal development', () => {
    vi.stubGlobal('location', { protocol: 'http:', hostname: '127.0.0.1' });
    vi.stubEnv('DEV', false); vi.stubEnv('MODE', 'community-qa');
    expect(() => validateRuntimeApiOrigin('/api')).toThrow();
    vi.stubEnv('DEV', true); vi.stubEnv('MODE', 'development');
    expect(() => validateRuntimeApiOrigin('/api')).toThrow();
    expect(validateRuntimeApiOrigin('https://api.example.com/api')).toBe('https://api.example.com');
  });
});
