import { defineConfig, loadEnv } from "vite";
import { buildCsp } from "./src/beta-policy";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const csp = buildCsp(env.VITE_BETA_MODE === "1", env.VITE_API_BASE_URL);
  return ({
  plugins: [react(), {
    name: "production-content-security-policy",
    apply: "build",
    transformIndexHtml() {
      return [{ tag: "meta", attrs: {
        "http-equiv": "Content-Security-Policy",
        content: csp,
      }, injectTo: "head-prepend" }];
    },
  }],
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
});
