import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { App } from '@capacitor/app';
import { api, safeReturnPath } from './api';
import { publicReturnPath } from './release-policy';
import { usePublicResource } from './release-data';
import { Feedback, Field, PageTitle, useAction, useAuth, useSessionAttempt } from './shared';
import { createSessionAttempt, OAUTH_PROOF_PREFIX, sessionFingerprint } from './session-storage';
import { LegalLinks } from './beta';
import { PUBLIC_AGE_CONFIRMATION, PUBLIC_AGE_HELP } from './signup-policy';
import type { User } from './types';
import { interestOnboardingPath } from './interest-onboarding';

export type Provider = 'google' | 'kakao' | 'naver';
type Purpose = 'login' | 'link' | 'reauth';
const names = { google: 'Google', kakao: '카카오', naver: '네이버' };
const prefix = OAUTH_PROOF_PREFIX;
export const REAUTH_KEY = 'moduyuga.social-reauth';
type Pending = { verifier: string; to: string; purpose?: Purpose; created: number; sessionFingerprint: string };
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
    let active = true;
    const launchAttempt = createSessionAttempt().begin();
    const receive = ({ url }: { url: string }) => {
      if (!active) return;
      const path = nativeReturn(url);
      if (path) { void Browser.close().catch(() => {}); navigate.current(path, { replace: true }); }
    };
    const listener = App.addListener('appUrlOpen', receive);
    void App.getLaunchUrl().then(result => { if (active && launchAttempt.isCurrent() && result) receive(result); }).catch(() => {});
    return () => { active = false; void listener.then(handle => handle.remove()).catch(() => {}); };
  }, []); // Read the launch URL once; route changes must not replay an old callback.
  return null;
}
export function socialReturnPath(to: string, purpose: Purpose): string {
  const path = safeReturnPath(to);
  if (purpose !== 'reauth') return publicReturnPath(path);
  const parsed = new URL(path, 'https://local.invalid');
  return parsed.pathname === '/settings' || /^\/admin\/members\/[A-Za-z0-9_-]{1,128}$/.test(parsed.pathname) ? path : '/settings';
}
export function socialAuthorizationUrl(value: string, provider: Provider): string {
  const url = new URL(value);
  const endpoints: Record<Provider, [string,string]> = {google:['accounts.google.com','/o/oauth2/v2/auth'],kakao:['kauth.kakao.com','/oauth/authorize'],naver:['nid.naver.com','/oauth2.0/authorize']};
  const expected = endpoints[provider];
  if (url.protocol !== 'https:' || url.username || url.password || url.port || !expected || url.hostname !== expected[0] || url.pathname !== expected[1]) throw new Error('로그인 연결 주소를 확인하지 못했습니다.');
  return url.href;
}
export function SocialButtons({ to = '/', purpose = 'login', only }: { to?: string; purpose?: Purpose; only?: Provider[] }) {
  const attempts = useSessionAttempt();
  const available = usePublicResource<{ providers: Provider[] }>('/auth/social/providers');
  const action = useAction();
  const providers = Array.isArray(available.data?.providers) ? available.data.providers.filter(p => p in names && (!only || only.includes(p))) : [];
  async function begin(provider: Provider) {
    const attempt = attempts.begin(), fingerprint = await sessionFingerprint();
    const proof = await proofPair();
    if (!attempt.isCurrent()) return;
    const result = await api<{ flow_id: string; authorization_url: string }>('/auth/social/' + provider + '/start', 'POST', {
      challenge: proof.challenge, platform: Capacitor.isNativePlatform() ? 'android' : 'web', purpose,
    });
    if (!attempt.isCurrent()) return;
    // Expired client proofs are discarded; no provider/session token is placed in a URL.
    for (const key of Object.keys(sessionStorage).filter(key => key.startsWith(prefix))) sessionStorage.removeItem(key);
    sessionStorage.setItem(prefix + result.flow_id, JSON.stringify({ verifier: proof.verifier, to: socialReturnPath(to, purpose), purpose, created: Date.now(), sessionFingerprint: fingerprint }));
    const url = new URL(socialAuthorizationUrl(result.authorization_url, provider));
    if (Capacitor.isNativePlatform()) await Browser.open({ url: url.href });
    else window.location.assign(url.href);
  }
  if (available.loading) return <section className="social-login" aria-label="소셜 로그인"><p role="status">소셜 로그인 연결을 확인하고 있어요…</p></section>;
  if (available.error) return <section className="social-login" aria-label="소셜 로그인"><p role="alert">{available.error}</p><button type="button" className="secondary" onClick={available.reload}>소셜 로그인 다시 확인</button></section>;
  if (!providers.length) return purpose === 'login' ? <section className="social-login" aria-label="소셜 로그인"><p>현재 소셜 로그인을 이용할 수 없어요. 잠시 후 다시 확인하거나 이메일 로그인을 이용해 주세요.</p><button type="button" className="secondary" onClick={available.reload}>소셜 로그인 다시 확인</button></section> : null;
  return <section className="social-login" aria-label="소셜 로그인"><div className="social-buttons">{providers.map(provider => <button key={provider} type="button" className={'social-button social-' + provider} disabled={action.busy}
    onClick={() => void action.run(() => begin(provider))}>{names[provider]}로 {purpose === 'link' ? '계정 연결' : purpose === 'reauth' ? '다시 인증' : '계속하기'}</button>)}</div><Feedback {...action}/>{purpose === 'login' && <p className="hint">기존 이메일 회원은 먼저 이메일로 로그인한 뒤 계정 관리에서 연결해 주세요. 같은 소셜 계정으로 앱과 웹의 저장·관심을 함께 이용할 수 있어요.</p>}</section>;
}
type Result = { status: 'pending' | 'onboarding' | 'authenticated' | 'linked' | 'reauthenticated'; user?: User; access_token?: string; reauth_token?: string };
export function SocialReturn() {
  const attempts = useSessionAttempt();
  const [params] = useSearchParams(), nav = useNavigate(), { setSession, refresh } = useAuth(), action = useAction();
  const flow = params.get('flow') || '';
  const started = useRef('');
  const [onboarding, setOnboarding] = useState(false), [waiting, setWaiting] = useState(false);
  const [nickname, setNickname] = useState(''), [ageConfirmed, setAgeConfirmed] = useState(false), [terms, setTerms] = useState(false), [privacy, setPrivacy] = useState(false);
  async function claim() {
    const attempt = attempts.begin();
    let pending: Pending | undefined;
    try { pending = JSON.parse(sessionStorage.getItem(prefix + flow) || 'null') || undefined; } catch { /* invalid local state */ }
    if (!pending || !Number.isFinite(pending.created) || Date.now() - pending.created > 600_000 || pending.created > Date.now() + 60_000) throw new Error('로그인을 시작한 탭·앱에서 다시 진행해 주세요. 요청이 10분 뒤 만료됩니다.');
    if (pending.sessionFingerprint !== await sessionFingerprint()) throw new Error('로그인 중 계정 상태가 변경됐어요. 현재 계정을 확인하고 다시 시작해 주세요.');
    if (!attempt.isCurrent()) return;
    const result = await api<Result>('/auth/social/claim', 'POST', { flow_id: flow, verifier: pending.verifier, nickname, age_confirmed: ageConfirmed, terms_accepted: terms, privacy_accepted: privacy });
    if (!attempt.isCurrent()) return;
    setWaiting(result.status === 'pending');
    if (result.status === 'pending') return;
    if (result.status === 'onboarding') { setOnboarding(true); return; }
    sessionStorage.removeItem(prefix + flow);
    if (result.status === 'authenticated' && result.access_token && result.user) {
      setSession(result.access_token, result.user, attempt.expectedToken); nav(onboarding ? interestOnboardingPath(socialReturnPath(pending.to, 'login')) : socialReturnPath(pending.to, 'login'), { replace: true });
    } else if (result.status === 'reauthenticated' && result.reauth_token) {
      sessionStorage.setItem(REAUTH_KEY, result.reauth_token); nav(socialReturnPath(pending.to, 'reauth'), { replace: true });
    } else if (result.status === 'linked') { await refresh(); if (attempt.isCurrent()) nav('/settings', { replace: true }); }
    else throw new Error('로그인 응답을 확인하지 못했습니다. 다시 시작해 주세요.');
  }
  useEffect(() => { if (started.current !== flow) { started.current = flow; void action.run(claim); } }, [flow]); // one-use claim must not be replayed by StrictMode
  return <div className="narrow"><PageTitle title={onboarding ? '처음 오셨네요' : '로그인 확인'}><p>{onboarding ? '이메일·비밀번호 입력 없이, 닉네임과 서비스 이용 동의를 확인하면 가입이 완료됩니다.' : '로그인을 시작한 기기와 소셜 계정을 확인합니다.'}</p></PageTitle>
    {onboarding && <form onSubmit={e => { e.preventDefault(); void action.run(claim); }}><Field label="닉네임" required minLength={2} maxLength={30} value={nickname} onChange={e => setNickname(e.target.value)}/><p className="hint">닉네임은 글·댓글에 표시할 이름이에요. 실명을 입력할 필요는 없어요.</p><LegalLinks/>
      <label className="check"><input type="checkbox" required checked={ageConfirmed} aria-describedby="social-age-help" onChange={e => setAgeConfirmed(e.target.checked)}/>{PUBLIC_AGE_CONFIRMATION}</label>
      <p id="social-age-help" className="hint">{PUBLIC_AGE_HELP}</p>
      <label className="check"><input type="checkbox" required checked={terms} onChange={e => setTerms(e.target.checked)}/>이용약관에 동의합니다.</label>
      <label className="check"><input type="checkbox" required checked={privacy} onChange={e => setPrivacy(e.target.checked)}/>개인정보 처리에 동의합니다.</label>
      <p className="hint">소셜 계정의 고유 식별자와 직접 입력한 닉네임을 보관합니다. 구글·카카오·네이버 비밀번호는 받지 않습니다. 카카오에서 이 서비스 연결을 해제하면 카카오 로그인 연결이 삭제됩니다. 다른 로그인 수단이 없는 카카오 전용 회원은 계정과 작성·활동 기록도 함께 삭제됩니다.</p><button disabled={action.busy}>가입 완료</button></form>}
    {waiting && <button disabled={action.busy} onClick={() => void action.run(claim)}>로그인 완료 확인</button>}<Feedback {...action}/><Link to="/login">로그인부터 다시 시작</Link></div>;
}
export function SocialAccountSettings() {
  const result = usePublicResource<{ providers: Provider[]; has_password: boolean }>('/auth/social/connections');
  return <section className="panel"><h2>소셜 계정 연결</h2><p>연결한 소셜 계정으로 앱과 웹의 같은 기록을 이용합니다. 다른 회원의 기록을 자동으로 합치지 않습니다.</p>
    {result.error && <p role="alert">{result.error}</p>}<p>{result.data?.providers.length ? '연결됨: ' + result.data.providers.map(p => names[p]).join(', ') : '연결된 소셜 계정 없음'}</p>
    <SocialButtons purpose="link" to="/settings" only={(['google', 'kakao', 'naver'] as Provider[]).filter(p => !result.data?.providers.includes(p))}/>
    {result.data?.providers.includes('kakao') && <p className="hint">카카오에서 서비스 연결을 해제하면 카카오 연결과 현재 로그인 세션을 폐기합니다. 이메일 비밀번호나 다른 소셜 연결이 있으면 계정은 유지됩니다. 다른 로그인 수단이 없는 카카오 전용 회원은 계정과 작성·활동 기록도 삭제됩니다.</p>}
    {result.data?.has_password === false && <><p>계정을 삭제하려면 연결된 소셜 계정으로 다시 인증해 주세요. 확인은 5분 동안 유효합니다.</p><SocialButtons purpose="reauth" only={result.data.providers} to="/settings"/></>}
  </section>;
}
