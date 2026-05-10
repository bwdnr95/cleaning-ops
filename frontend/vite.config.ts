import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5175,
    allowedHosts: ['cleanjob.tono-operation.com', 'localhost', '127.0.0.1'],
    proxy: {
      '/api':     { target: 'http://localhost:8002', changeOrigin: true },
      '/uploads': { target: 'http://localhost:8002', changeOrigin: true },
    },
  },
});
