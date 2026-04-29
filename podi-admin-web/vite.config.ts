import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // ali-oss is intentionally isolated and loaded only when a user uploads media.
    // Keep the threshold close to that known async chunk so real page bloat still warns.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) return 'react-vendor';
          if (id.includes('/tdesign-react/') || id.includes('/tdesign-icons-react/')) return 'tdesign-vendor';
          if (id.includes('/ali-oss/')) return 'storage-vendor';
          return 'vendor';
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
