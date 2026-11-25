import { useEffect, useRef } from 'react';
import { api, API_BASE } from './api';
import { readCampaign } from './campaign';
import { clientPlatform } from './client-platform';

// A tab contributes one open per document load, on its first visible public screen.
// No storage or browser identifier is needed. A full reload creates a new document.
let reportedWebOpen = false;
export function isPublicScreen(path: string) {
  return ['/', '/offers', '/demands', '/chat', '/advisor', '/calculator', '/my', '/welcome', '/login', '/signup'].includes(path)
    || /^\/(groupbuys|offers|demands)\/(?!new\/?$)[\w-]+\/?$/.test(path);
}

export function useVisitTracking(path: string, authLoading: boolean, isAdmin: boolean, consentedMember?: string) {
  const memberDay = useRef('');
  useEffect(() => {
    if (authLoading || isAdmin || path.startsWith('/admin') || path.startsWith('/auth/')) return;
    function recordVisibleVisit() {
      if (document.visibilityState !== 'visible' || !navigator.onLine) return;
      if (!reportedWebOpen && isPublicScreen(path) && clientPlatform() === 'web') {
        reportedWebOpen = true;
        // Never retry an ambiguous increment. A definite rejection may retry on the next visit.
        const campaign = readCampaign(window.location.search);
        const params = new URLSearchParams();
        if (campaign) {
          params.set('source', campaign.source);
          if (campaign.medium === 'share') params.set('shared', 'true');
        }
        void fetch(API_BASE + '/release/measurement/web-opens' + (params.size ? '?' + params : ''), {
          method: 'POST', credentials: 'omit', referrerPolicy: 'no-referrer',
          headers: { 'X-Moduyuga-Client': 'web' }, keepalive: true,
        }).then(response => { if (!response.ok) reportedWebOpen = false; }).catch(() => {});
      }
      if (!consentedMember) return;
      const key = consentedMember + '/' + new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10);
      if (memberDay.current === key) return;
      memberDay.current = key;
      void api<{recorded: boolean}>('/release/measurement/member-visits', 'POST')
        .then(result => { if (!result.recorded && memberDay.current === key) memberDay.current = ''; })
        .catch(() => { if (memberDay.current === key) memberDay.current = ''; });
    }
    if (!consentedMember) memberDay.current = '';
    recordVisibleVisit();
    document.addEventListener('visibilitychange', recordVisibleVisit);
    window.addEventListener('focus', recordVisibleVisit);
    window.addEventListener('online', recordVisibleVisit);
    return () => {
      document.removeEventListener('visibilitychange', recordVisibleVisit);
      window.removeEventListener('focus', recordVisibleVisit);
      window.removeEventListener('online', recordVisibleVisit);
    };
  }, [path, authLoading, isAdmin, consentedMember]);
}
