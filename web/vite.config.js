import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// FastAPI serves the built bundle. Dev mode proxies /api/* to the API server.
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
