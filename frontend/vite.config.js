import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), 'LEDGER_');
  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': environment.LEDGER_API_URL || 'http://127.0.0.1:8000',
      },
    },
    preview: { host: '127.0.0.1', port: 5173, strictPort: true },
  };
});
