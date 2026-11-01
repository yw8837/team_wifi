import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react(), {
    name: "production-content-security-policy",
    apply: "build",
    transformIndexHtml() {
      return [{ tag: "meta", attrs: {
        "http-equiv": "Content-Security-Policy",
        content: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://10.0.2.2:8000 http://127.0.0.1:8000; object-src 'none'; base-uri 'none'; form-action 'self'",
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
