import { Children, isValidElement, type ReactNode } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({ message: vi.fn(), native: false, open: vi.fn() }));
vi.mock('react', async () => ({ ...await vi.importActual('react'), useState: (value: unknown) => [value, state.message] }));
vi.mock('./client-platform', () => ({ clientPlatform: () => state.native ? 'android' : 'web' }));
vi.mock('@capacitor/browser', () => ({ Browser: { open: state.open } }));
import { GroupbuyShare } from './groupbuy-share';

function click(node: ReactNode, label: string): void {
  for (const child of Children.toArray(node)) {
    if (!isValidElement<{ children?: ReactNode; onClick?: () => void }>(child)) continue;
    if (child.type === 'button' && child.props.children === label) child.props.onClick?.();
    else click(child.props.children, label);
  }
}
beforeEach(() => { state.native = false; vi.clearAllMocks(); vi.stubEnv('VITE_KAKAO_JAVASCRIPT_KEY', 'public-js-key'); });
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it('opens the Kakao share picker with the exact groupbuy and Kakao attribution', async () => {
  const init = vi.fn(), sendDefault = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('window', { Kakao: { init, isInitialized: () => false, Share: { sendDefault } } });
  click(GroupbuyShare({ id: 'example-product', title: '육아템 공구' }), '카카오톡으로 보내기');
  await Promise.resolve();
  expect(init).toHaveBeenCalledWith('public-js-key');
  const options = sendDefault.mock.calls[0][0];
  expect(options.text).toContain('육아템 공구');
  expect(new URL(options.link.webUrl).pathname).toBe('/groupbuys/example-product');
  expect(new URL(options.link.webUrl).searchParams.get('utm_source')).toBe('kakao');
  expect(options.link.mobileWebUrl).toBe(options.link.webUrl);
});

it('reports SDK failure and keeps link copy available', async () => {
  vi.stubGlobal('window', {});
  click(GroupbuyShare({ id: 'example-product' }), '카카오톡으로 보내기');
  await Promise.resolve();
  expect(state.message).toHaveBeenCalledWith(expect.stringContaining('링크를 복사'));
});

it('copies the current product URL', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('navigator', { clipboard: { writeText } });
  click(GroupbuyShare({ id: 'current-product' }), '공구 링크 복사');
  await Promise.resolve();
  expect(new URL(writeText.mock.calls[0][0]).pathname).toBe('/groupbuys/current-product');
  expect(state.message).toHaveBeenCalledWith('공구 링크를 복사했어요.');
});

it('offers manual copying when clipboard access fails', async () => {
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) } });
  click(GroupbuyShare({ id: 'current-product' }), '공구 링크 복사');
  await Promise.resolve();
  expect(state.message).toHaveBeenCalledWith('아래 주소를 길게 눌러 복사해 주세요.');
});

it('opens the registered web sharing surface from Android', async () => {
  state.native = true;
  click(GroupbuyShare({ id: 'current-product' }), '카카오톡으로 보내기');
  await Promise.resolve();
  const url = new URL(state.open.mock.calls[0][0].url);
  expect(url.pathname).toBe('/groupbuys/current-product');
  expect(url.hash).toBe('#groupbuy-share');
});
