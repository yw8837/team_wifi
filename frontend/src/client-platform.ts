import { Capacitor } from '@capacitor/core';

export function clientPlatform(): 'android' | 'web' {
  return Capacitor.isNativePlatform() ? 'android' : 'web';
}
