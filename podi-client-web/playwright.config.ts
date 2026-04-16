import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/ui',
  fullyParallel: true,
  retries: 0,
  timeout: 60000,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8212',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command:
      'env VITE_CLIENT_ANALYTICS_ENDPOINT=http://127.0.0.1:8212/__client_analytics__ VITE_CLIENT_ANALYTICS_PROJECT=client-phase1 VITE_CLIENT_ANALYTICS_AUTH_TOKEN=test-analytics-token npm run dev -- --host 127.0.0.1 --port 8212',
    url: 'http://127.0.0.1:8212',
    reuseExistingServer: false,
    timeout: 120000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
