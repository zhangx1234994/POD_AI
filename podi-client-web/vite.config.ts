import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('ali-oss')) return 'aliyun-oss-sdk';
          if (id.includes('react-router')) return 'router';
          if (id.includes('tdesign-react') || id.includes('tdesign-icons-react')) return 'tdesign';
          if (id.includes('react') || id.includes('scheduler')) return 'react-vendor';
          return undefined;
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 8210,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8099',
        changeOrigin: true,
      },
    },
  },
});
