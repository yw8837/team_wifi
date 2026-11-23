import { afterEach, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({
  cleanup: undefined as undefined | (() => void), ref: { current: '' }, memberVisit: vi.fn(),
}));
vi.mock('react', () => ({
  useRef: () => state.ref,
  useEffect: (apply: () => void | (() => void)) => { state.cleanup?.(); state.cleanup = apply() || undefined; },
}));
vi.mock('./api', () => ({ API_BASE: 'https://api.example', api: state.memberVisit }));
vi.mock('./client-platform', () => ({ clientPlatform: () => 'web' }));

afterEach(() => {
  state.cleanup?.(); state.cleanup = undefined; state.ref.current = '';
  vi.unstubAllGlobals(); vi.clearAllMocks(); vi.resetModules();
});

it('counts a visible guest share once without sending identity, URL or referrer', async () => {
  const doc = Object.assign(new EventTarget(), { visibilityState: 'hidden' });
  const win = Object.assign(new EventTarget(), { location: { search: '?utm_source=kakao&utm_medium=share&utm_campaign=groupbuy' } });
  const fetch = vi.fn().mockResolvedValue({ok: true});
  vi.stubGlobal('document', doc); vi.stubGlobal('window', win);
  vi.stubGlobal('navigator', {onLine: true}); vi.stubGlobal('fetch', fetch);
  const { useVisitTracking } = await import('./visit-tracking');
  useVisitTracking('/groupbuys/some-id', false, false);
  expect(fetch).not.toHaveBeenCalled();
  doc.visibilityState = 'visible'; doc.dispatchEvent(new Event('visibilitychange')); win.dispatchEvent(new Event('focus'));
  useVisitTracking('/', false, false);
  expect(fetch).toHaveBeenCalledExactlyOnceWith('https://api.example/release/measurement/web-opens?shared=true', {
    method: 'POST', credentials: 'omit', referrerPolicy: 'no-referrer', headers: {'X-Moduyuga-Client':'web'}, keepalive:true,
  });
  expect(state.memberVisit).not.toHaveBeenCalled();
});

it('skips the admin screen and counts a consenting member on an ordinary homepage without a campaign', async () => {
  vi.stubGlobal('document', Object.assign(new EventTarget(), {visibilityState:'visible'}));
  vi.stubGlobal('window', Object.assign(new EventTarget(), {location:{search:''}}));
  const fetch = vi.fn().mockResolvedValue({ok:true});
  vi.stubGlobal('fetch',fetch); vi.stubGlobal('navigator',{onLine:true});
  state.memberVisit.mockResolvedValue({recorded:true});
  const { useVisitTracking } = await import('./visit-tracking');
  useVisitTracking('/admin/insights',false,true);
  useVisitTracking('/',true,false);
  expect(fetch).not.toHaveBeenCalled();
  useVisitTracking('/',false,false,'member');
  window.dispatchEvent(new Event('focus'));
  expect(fetch.mock.calls[0][0]).toBe('https://api.example/release/measurement/web-opens');
  expect(state.memberVisit).toHaveBeenCalledExactlyOnceWith('/release/measurement/member-visits','POST');
});
