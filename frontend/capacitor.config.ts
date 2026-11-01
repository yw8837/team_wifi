import type { CapacitorConfig } from "@capacitor/cli";
const localAndroid = process.env.MODU_LOCAL_ANDROID === "1";
const config: CapacitorConfig = {
  appId: "kr.moduyuga.app",
  appName: "모두육아",
  webDir: "dist",
  android: { allowMixedContent: localAndroid },
  server: { cleartext: localAndroid },
};
export default config;
