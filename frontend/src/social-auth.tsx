import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { App } from '@capacitor/app';
import { api, safeReturnPath } from './api';
import { publicReturnPath } from './release-policy';
import { usePublicResource } from './release-data';
import { Feedback, Field, PageTitle, useAction, useAuth } from './shared';
import { LegalLinks } from './beta';
import type { User } from './types';

type Provider = 'google' | 'kakao';
type Purpose = 'login' | 'link' | 'reauth';
const names = { google: 'Google', kakao: '카카오' };
const prefix = 'moduyuga.oauth.';
export const REAUTH_KEY = 'moduyuga.social-reauth';
type Pending = { verifier: string; to: string; created: number };
const encode = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
export async function proofPair() {
  const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
  return { verifier, challenge: encode(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)))) };
}
export function nativeReturn(url: string): string | null {
  try {
    const parsed = new URL(url), flow = parsed.searchParams.get('flow');
    return parsed.protocol === 'kr.moduyuga.app:' && parsed.hostname === 'auth' && !parsed.username && !parsed.password && !parsed.port && parsed.pathname === '/complete' && flow && /^[a-f0-9-]{36}$/.test(flow)
      ? '/auth/complete?flow=' + encodeURIComponent(flow) : null;
  } catch { return null; }
}
export function NativeAuthReturn() {
  const nav = useNavigate();
  const navigate = useRef(nav);
  navigate.current = nav;
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    const receive = ({ url }: { url: string }) => {
      const path = nativeReturn(url);
      if (path) { void Browser.close().catch(() => {}); navigate.current(path, { replace: true }); }
    };
    const listener = App.addListener('appUrlOpen', receive);
    void App.getLaunchUrl().then(result => { if (result) receive(result); });
    return () => { void listener.then(handle => handle.remove()); };
  }, []); // Read the launch URL once; route changes must not replay an old callback.
  return null;
}
export function SocialButtons({ to = '/', purpose = 'login', only }: { to?: string; purpose?: Purpose; only?: Provider[] }) {
  const available = usePublicResource<{ providers: Provider[] }>('/auth/social/providers');
  const action = useAction();
  const providers = Array.isArray(available.data?.providers) ? available.data.providers.filter(p => p in names && (!only || only.includes(p))) : [];
  async function begin(provider: Provider) {
    const proof = await proofPair();
    const result = await api<{ flow_id: string; authorization_url: string }>('/auth/social/' + provider + '/start', 'POST', {
      challenge: proof.challenge, platform: Capacitor.isNativePlatform() ? 'android' : 'web', purpose,
    });
    // Expired client proofs are discarded; no provider/session token is placed in a URL.
    for (const key of Object.keys(sessionStorage).filter(key => key.startsWith(prefix))) sessionStorage.removeItem(key);
    sessionStorage.setItem(prefix + result.flow_id, JSON.stringify({ verifier: proof.verifier, to: publicReturnPath(safeReturnPath(to)), created: Date.now() }));
    const url = new URL(result.authorization_url);
    if (url.protocol !== 'https:' || !['accounts.google.com', 'kauth.kakao.com'].includes(url.hostname)) throw new Error('로그인 연결 주소를 확인하지 못했습니다.');
    if (Capacitor.isNativePlatform()) await Browser.open({ url: url.href });
    else window.location.assign(url.href);
  }
  if (!providers.length) return null;
  return <section className="social-login" aria-label="소셜 로그인"><div className="social-buttons">{providers.map(provider => <button key={provider} type="button" className={'social-button social-' + provider} disabled={action.busy}
    onClick={() => void action.run(() => begin(provider))}>{names[provider]}로 {purpose === 'link' ? '계정 연결' : purpose === 'reauth' ? '다시 인증' : '계속하기'}</button>)}</div><Feedback {...action}/>{purpose === 'login' && <p className="hint">기존 이메일 회원은 먼저 이메일로 로그인한 뒤 계정 관리에서 연결해 주세요. 같은 소셜 계정으로 앱과 웹의 저장·관심을 함께 이용할 수 있어요.</p>}</section>;
}
type Result = { status: 'pending' | 'onboarding' | 'authenticated' | 'linked' | 'reauthenticated'; user?: User; access_token?: string; reauth_token?: string };
export function SocialReturn() {
  const [params] = useSearchParams(), nav = useNavigate(), { setSession, refresh } = useAuth(), action = useAction();
  const flow = params.get('flow') || '';
  const started = useRef('');
  const [onboarding, setOnboarding] = useState(false), [waiting, setWaiting] = useState(false);
  const [nickname, setNickname] = useState(''), [adult, setAdult] = useState(false), [terms, setTerms] = useState(false), [privacy, setPrivacy] = useState(false);
  async function claim() {
    let pending: Pending | undefined;
    try { pending = JSON.parse(sessionStorage.getItem(prefix + flow) || 'null') || undefined; } catch { /* invalid local state */ }
    if (!pending || Date.now() - pending.created > 600_000) throw new Error('로그인을 시작한 탭·앱에서 다시 진행해 주세요. 요청이 10분 뒤 만료됩니다.');
    const result = await api<Result>('/auth/social/claim', 'POST', { flow_id: flow, verifier: pending.verifier, nickname, adult_confirmed: adult, terms_accepted: terms, privacy_accepted: privacy });
    setWaiting(result.status === 'pending');
    if (result.status === 'pending') return;
    if (result.status === 'onboarding') { setOnboarding(true); return; }
    sessionStorage.removeItem(prefix + flow);
    if (result.status === 'authenticated' && result.access_token && result.user) {
      setSession(result.access_token, result.user); nav(pending.to, { replace: true });
    } else if (result.status === 'reauthenticated' && result.reauth_token) {
      sessionStorage.setItem(REAUTH_KEY, result.reauth_token); nav('/settings', { replace: true });
    } else if (result.status === 'linked') { await refresh(); nav('/settings', { replace: true }); }
    else throw new Error('로그인 응답을 확인하지 못했습니다. 다시 시작해 주세요.');
  }
  useEffect(() => { if (started.current !== flow) { started.current = flow; void action.run(claim); } }, [flow]); // one-use claim must not be replayed by StrictMode
  return <div className="narrow"><PageTitle title={onboarding ? '처음 오셨네요' : '로그인 확인'}><p>{onboarding ? '닉네임과 서비스 이용 동의를 확인하면 가입이 완료됩니다.' : '로그인을 시작한 기기와 소셜 계정을 확인합니다.'}</p></PageTitle>
    {onboarding && <form onSubmit={e => { e.preventDefault(); void action.run(claim); }}><Field label="닉네임" required minLength={2} maxLength={30} value={nickname} onChange={e => setNickname(e.target.value)}/><LegalLinks/>
      <label className="check"><input type="checkbox" required checked={adult} onChange={e => setAdult(e.target.checked)}/>만 18세 이상입니다.</label>
      <label className="check"><input type="checkbox" required checked={terms} onChange={e => setTerms(e.target.checked)}/>이용약관에 동의합니다.</label>
      <label className="check"><input type="checkbox" required checked={privacy} onChange={e => setPrivacy(e.target.checked)}/>개인정보 처리에 동의합니다.</label>
      <p className="hint">소셜 계정의 고유 식별자와 직접 입력한 닉네임을 보관합니다. 구글·카카오 비밀번호는 받지 않습니다.</p><button disabled={action.busy}>가입 완료</button></form>}
    {waiting && <button disabled={action.busy} onClick={() => void action.run(claim)}>로그인 완료 확인</button>}<Feedback {...action}/><Link to="/login">로그인부터 다시 시작</Link></div>;
}
export function SocialAccountSettings() {
  const result = usePublicResource<{ providers: Provider[]; has_password: boolean }>('/auth/social/connections');
  return <section className="panel"><h2>소셜 계정 연결</h2><p>연결한 소셜 계정으로 앱과 웹의 같은 기록을 이용합니다. 다른 회원의 기록을 자동으로 합치지 않습니다.</p>
    {result.error && <p role="alert">{result.error}</p>}<p>{result.data?.providers.length ? '연결됨: ' + result.data.providers.map(p => names[p]).join(', ') : '연결된 소셜 계정 없음'}</p>
    <SocialButtons purpose="link" to="/settings" only={(['google', 'kakao'] as Provider[]).filter(p => !result.data?.providers.includes(p))}/>
    {result.data?.has_password === false && <><p>계정을 삭제하려면 연결된 소셜 계정으로 다시 인증해 주세요. 확인은 5분 동안 유효합니다.</p><SocialButtons purpose="reauth" only={result.data.providers} to="/settings"/></>}
  </section>;
}
