import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dedicated loopback UI verification using the real public API, SCRAM PostgreSQL,
// authentication, rate limits and role checks. This config cannot make a build.
export default defineConfig(({ command, mode }) => {
  if (command !== 'serve' || mode !== 'community-qa') throw new Error('Loopback UI harness is development-only.');
  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_PUBLIC_RELEASE': JSON.stringify('1'),
      'import.meta.env.VITE_BETA_MODE': JSON.stringify('0'),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api'),
    },
    server: {
      host: '127.0.0.1', port: 18181, strictPort: true,
      proxy: {
        '/api': { target: 'http://127.0.0.1:18180', changeOrigin: true },
        '/legal': { target: 'http://127.0.0.1:18180', changeOrigin: true },
      },
    },
  };
});
