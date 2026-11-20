import { registerPlugin } from '@capacitor/core';

export const KakaoShare = registerPlugin<{
  share(options: { text: string }): Promise<void>;
}>('KakaoShare');
