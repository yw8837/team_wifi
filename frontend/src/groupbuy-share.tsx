import { useState } from 'react';
import { clientPlatform } from './client-platform';
import { groupbuyShareLink } from './share-link';

export function GroupbuyShare({ id }: { id: string }) {
  const [message, setMessage] = useState('');
  const [manualCopy, setManualCopy] = useState(false);
  const url = groupbuyShareLink(id, clientPlatform());

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
    <section aria-label="공구 링크 공유">
      <button type="button" className="secondary" onClick={() => void copyLink()}>
        공구 링크 복사
      </button>
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
