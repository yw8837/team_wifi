import type { CapacitorConfig } from "@capacitor/cli";
const localAndroid = process.env.MODU_LOCAL_ANDROID === "1";
const config: CapacitorConfig = {
  appId: "kr.moduyuga.app",
  appName: "모두의 육아 - 육아템 공동구매,핫딜",
  webDir: "dist",
  android: { allowMixedContent: localAndroid },
  server: { cleartext: localAndroid },
};
export default config;
