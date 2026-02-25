import { expect, test } from '@playwright/test';

test.describe('Eval shell visual regression', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/**', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'PLAYWRIGHT_MOCK_BACKEND_DOWN' }),
      });
    });
  });

  test('home view baseline', async ({ page }) => {
    await page.goto('/?view=home&category=%E9%80%9A%E7%94%A8%E7%B1%BB');
    await expect(page.locator('body')).toContainText('PODI · 能力评测');
    await expect(page).toHaveScreenshot('eval-home-warning.png', { fullPage: true });
  });

  test('tasks view baseline', async ({ page }) => {
    await page.goto('/?view=tasks&category=%E9%80%9A%E7%94%A8%E7%B1%BB');
    await expect(page).toHaveURL(/view=tasks/);
    await expect(page).toHaveScreenshot('eval-tasks-warning.png', { fullPage: true });
  });
});
