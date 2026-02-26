import { expect, test } from '@playwright/test';

test.describe('Admin shell visual regression', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('podi_admin_access_token', 'playwright-token');
      window.localStorage.removeItem('podi_admin_token_invalid');
    });
    await page.route('**/api/**', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'PLAYWRIGHT_MOCK_BACKEND_DOWN' }),
      });
    });
  });

  test('overview with warning state', async ({ page }) => {
    await page.goto('/#nav=overview');
    await expect(page.locator('body')).toContainText('AI 管理端');
    await expect(page).toHaveScreenshot('admin-overview-warning.png', { fullPage: true });
  });

  test('hash navigation keeps section in url', async ({ page }) => {
    await page.goto('/#nav=executors');
    await expect(page).toHaveURL(/#nav=executors/);
    await expect(page).toHaveScreenshot('admin-executors-warning.png', { fullPage: true });
  });
});
