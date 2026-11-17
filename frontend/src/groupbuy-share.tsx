import { useState } from 'react';
import { Browser } from '@capacitor/browser';
import { clientPlatform } from './client-platform';
import { groupbuyShareLink } from './share-link';

type KakaoSdk = {
  init(key: string): void;
  isInitialized(): boolean;
  Share: { sendDefault(options: { objectType: 'text'; text: string; link: { webUrl: string; mobileWebUrl: string }; buttonTitle: string }): Promise<unknown> };
};

export function GroupbuyShare({ id, title = '함께 볼 육아템 공구' }: { id: string; title?: string }) {
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState(false);
  const url = groupbuyShareLink(id, clientPlatform());

  async function shareKakao() {
    setMessage('');
    try {
      if (clientPlatform() === 'android') {
        await Browser.open({ url: url + '#groupbuy-share' });
        setMessage('열린 웹 화면에서 카카오톡으로 보내기를 눌러 주세요.');
        return;
      }
      const sdk = (window as Window & { Kakao?: KakaoSdk }).Kakao;
      const key = import.meta.env.VITE_KAKAO_JAVASCRIPT_KEY;
      if (!sdk || !key) throw new Error('Kakao sharing unavailable');
      if (!sdk.isInitialized()) sdk.init(key);
      const kakaoUrl = groupbuyShareLink(id, 'kakao');
      await sdk.Share.sendDefault({
        objectType: 'text', text: `${title}\n모두의 육아에서 공구 구성과 조건을 함께 확인해 보세요.`,
        link: { webUrl: kakaoUrl, mobileWebUrl: kakaoUrl }, buttonTitle: '공구 자세히 보기',
      });
    } catch {
      setMessage('카카오톡 공유를 열지 못했어요. 다시 시도하거나 링크를 복사해 주세요.');
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setManualCopy(false);
      setMessage('공구 링크를 복사했어요.');
    } catch {
      setManualCopy(true);
      setMessage('아래 주소를 길게 눌러 복사해 주세요.');
    }
  }

  return (
    <section id="groupbuy-share" aria-label="공구 링크 공유">
      <div className="actions">
      <button type="button" className="secondary kakao-share" onClick={() => void shareKakao()}>
        카카오톡으로 보내기
      </button>
      <button type="button" className="secondary" onClick={() => void copyLink()}>
        공구 링크 복사
      </button>
      </div>
      <p role="status">{message}</p>
      {manualCopy && (
        <label className="field">
          <span>공유할 주소</span>
          <input readOnly value={url} onFocus={event => event.currentTarget.select()} />
        </label>
      )}
    </section>
  );
}
