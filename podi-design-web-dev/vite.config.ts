
import { defineConfig } from 'vite';
  import react from '@vitejs/plugin-react-swc';
  import path from 'path';

  export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['chunk-U3XJZLTS'],
  },
  resolve: {
    extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
    alias: {
      // Remove versioned package aliases (e.g. 'lucide-react@0.487.0') because
      // TypeScript/tsc cannot resolve module names that include version suffixes.
      // Keep only project-local alias for source code.
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    target: 'esnext',
    outDir: 'build',
  },
  server: {
    port: 8080,
    open: true,
    proxy: {
      '/api/os/v1/': {
        target: 'http://localhost:8090',
        changeOrigin: true,
        secure: false,
      },
      '/api/op/v1': {
        target: 'http://localhost:8099',
        changeOrigin: true,
        secure: false,
      },
      '/api/media': {
        target: 'http://localhost:8099',
        changeOrigin: true,
        secure: false,
      },
      '/api/tasks': {
        target: 'http://localhost:8099',
        changeOrigin: true,
        secure: false,
      },
      '/api/admin': {
        target: 'http://localhost:8099',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
