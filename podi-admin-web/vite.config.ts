import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  build: {
    // ali-oss is intentionally isolated and loaded only when a user uploads media.
    // Keep the threshold close to that known async chunk so real page bloat still warns.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Keep heavy upload SDK lazy, but let Vite/Rollup place React and UI libraries.
          // Hand-splitting React/TDesign caused a production-only circular chunk that crashed
          // static admin builds with "Cannot access before initialization".
          if (id.includes('/ali-oss/')) return 'storage-vendor';
          if (id.includes('node_modules')) return undefined;
          return undefined;
        },
      },
    },
  },
  server: {
    port: 8199,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8099',
        changeOrigin: true,
      },
    },
  },
});
