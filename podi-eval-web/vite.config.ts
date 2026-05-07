import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // Default to local backend; can override via VITE_API_BASE_URL=http://x.x.x.x:8099
  const apiBase = (env.VITE_API_BASE_URL || 'http://127.0.0.1:8099').replace(/\/$/, '');

  return {
    plugins: [react()],
    server: {
      port: 8200,
      host: '0.0.0.0',
      proxy: {
        // Make `/api/...` work in dev without configuring CORS or hardcoding base urls.
        '/api': {
          target: apiBase,
          changeOrigin: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('/node_modules/')) return undefined;
            if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) return 'react-vendor';
            if (id.includes('/tdesign-icons-react/')) return 'tdesign-icons-vendor';
            if (
              id.includes('/lodash-es/') ||
              id.includes('/dayjs/') ||
              id.includes('/@popperjs/') ||
              id.includes('/sortablejs/') ||
              id.includes('/validator/') ||
              id.includes('/react-transition-group/')
            ) {
              return 'tdesign-runtime-vendor';
            }
            if (id.includes('/tdesign-react/')) return 'tdesign-vendor';
            if (id.includes('/react-markdown/') || id.includes('/remark-gfm/') || id.includes('/unified/') || id.includes('/micromark/')) {
              return 'markdown-vendor';
            }
            return undefined;
          },
        },
      },
    },
  };
});
