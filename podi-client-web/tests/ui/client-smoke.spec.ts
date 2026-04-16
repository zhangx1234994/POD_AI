import { expect, test } from '@playwright/test';

const AUTH_STORAGE_KEY = 'podi-client-auth';
const ASSET_STORAGE_KEY = 'podi-client-asset-library';

function encodeBase64Url(value: string) {
  return Buffer.from(value).toString('base64url');
}

function createFakeJwt(sub: string, role = 'designer', expSeconds = Math.floor(Date.now() / 1000) + 3600) {
  const header = encodeBase64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = encodeBase64Url(JSON.stringify({ sub, role, exp: expSeconds }));
  return `${header}.${payload}.signature`;
}

async function seedAuthenticatedSession(
  page: import('@playwright/test').Page,
  {
    userId = 'client-user-01',
    role = 'designer',
  }: {
    userId?: string;
    role?: string;
  } = {},
) {
  const authState = {
    accessToken: createFakeJwt(userId, role),
    refreshToken: 'refresh-token',
    user: {
      id: userId,
      role,
      expiresAt: Date.now() + 60 * 60 * 1000,
    },
  };

  await page.addInitScript(
    ({ storageKey, auth }) => {
      localStorage.setItem(storageKey, JSON.stringify(auth));
    },
    { storageKey: AUTH_STORAGE_KEY, auth: authState },
  );
}

async function seedClientAssets(
  page: import('@playwright/test').Page,
  assets: Array<Record<string, unknown>>,
) {
  await page.addInitScript(
    ({ storageKey, value }) => {
      localStorage.setItem(storageKey, JSON.stringify(value));
    },
    { storageKey: ASSET_STORAGE_KEY, value: assets },
  );
}

async function mockAuthenticatedClientApis(
  page: import('@playwright/test').Page,
  {
    userId = 'client-user-01',
    balance = 8000,
    abilities,
    abilityTasks,
  }: {
    userId?: string;
    balance?: number;
    abilities?: Array<Record<string, unknown>>;
    abilityTasks?: Array<Record<string, unknown>>;
  } = {},
) {
  await page.route('**/api/abilities', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items:
          abilities || [
            {
              id: 'ability-text-01',
              provider: 'volcengine',
              category: 'design',
              capabilityKey: 'doubao_seedream_4_5',
              displayName: '火山 · Doubao Seedream 4.5',
              metadata: {
                pricing: {
                  discount_price: 18,
                },
              },
            },
          ],
      }),
    });
  });

  await page.route('**/api/ability-tasks?limit=*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: abilityTasks || [] }),
    });
  });

  await page.route('**/api/wallet/v1/balance?userId=*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        userId,
        balance,
        frozenBalance: 24,
        currency: 'CNY',
      }),
    });
  });

  await page.route('**/api/wallet/v1/statistics?userId=*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        totalPoints: 8000,
        tempPoints: 0,
        frozenPoints: 24,
        grantedToday: 100,
      }),
    });
  });

  await page.route('**/api/wallet/v1/usage-summary?userId=*&windowDays=*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        userId,
        windowDays: 30,
        totalExpensePoints: 3402,
        totalIncomePoints: 12000,
        expenseCount: 18,
        incomeCount: 4,
      }),
    });
  });

  await page.route('**/api/wallet/v1/ledger?userId=*&page=*&pageSize=*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        userId,
        page: 1,
        pageSize: 8,
        total: 1,
        items: [
          {
            id: 'ledger-01',
            changeType: 'consume',
            points: -1800,
            beforeBalance: balance + 1800,
            afterBalance: balance,
            description: '以文生款演示消耗',
            createdAt: '2026-04-16T08:00:00.000Z',
          },
        ],
      }),
    });
  });
}

async function captureConsoleErrors(page: import('@playwright/test').Page) {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  return errors;
}

function expectNoUnexpectedConsoleErrors(errors: string[], allowedPatterns: RegExp[] = []) {
  const unexpected = errors.filter((error) => !allowedPatterns.some((pattern) => pattern.test(error)));
  expect(unexpected).toEqual([]);
}

async function open(page: import('@playwright/test').Page, path: string) {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
}

test('home page renders product positioning and conversion entry', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/home');
  await expect(page.getByRole('heading', { name: '行业 SaaS 设计生产平台' })).toBeVisible();
  await expect(page.getByRole('link', { name: '进入工作室', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '登录体验真实链路' })).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors);
});

test('login dialog explains real-data boundary and visual ownership', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/home');
  await page.getByRole('button', { name: '登录体验真实链路' }).click();
  await expect(page.getByText('登录客户端')).toBeVisible();
  await expect(page.getByText('从演示前台切到真实业务前台')).toBeVisible();
  await expect(page.getByText('已登录：真实任务、真实素材、真实钱包数据')).toBeVisible();
  await expect(page.getByText('控制位置：src/config/clientVisuals.ts')).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors);
});

test('home template can seed the workspace prompt', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/home');
  await page.getByRole('link', { name: '用这条模板开始' }).first().click();
  await expect(page).toHaveURL(/\/design\/text-to-style$/);
  await expect(page.locator('h1').filter({ hasText: '以文生款' }).first()).toBeVisible();
  await expect(page.locator('textarea').first()).toHaveValue(/都市通勤女装/);
  expectNoUnexpectedConsoleErrors(errors);
});

test('studio page renders workflow and retention entry points', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/studio');
  await expect(page.getByRole('heading', { name: '今天先做哪一步？' })).toBeVisible();
  await expect(page.getByText('最近任务与最近资产')).toBeVisible();
  await expect(page.getByRole('button', { name: '复制事件快照' })).toBeVisible();
  await expect(page.getByRole('button', { name: '用模板开始' }).first()).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors);
});

test('studio analytics flush sends protocol headers and batch payload', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  let capturedRequest: null | {
    headers: Record<string, string>;
    body: Record<string, unknown>;
  } = null;
  await page.route('**/__client_analytics__', async (route) => {
    capturedRequest = {
      headers: route.request().headers(),
      body: route.request().postDataJSON() as Record<string, unknown>,
    };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    });
  });

  await open(page, '/studio');
  await page.getByRole('button', { name: '尝试上报' }).click();
  await expect(page.locator('.client-callout').filter({ hasText: /已上报 \d+ 条事件。/ })).toBeVisible();

  expect(capturedRequest).not.toBeNull();
  expect(capturedRequest?.headers['x-podi-client-source']).toBe('podi-client-web');
  expect(capturedRequest?.headers['x-podi-protocol-version']).toBe('phase1.v1');
  expect(capturedRequest?.headers['x-podi-analytics-project']).toBe('client-phase1');
  expect(capturedRequest?.headers.authorization).toBe('Bearer test-analytics-token');
  expect(capturedRequest?.body.source).toBe('podi-client-web');
  expect(capturedRequest?.body.protocolVersion).toBe('phase1.v1');
  expect(capturedRequest?.body.project).toBe('client-phase1');
  expect(capturedRequest?.body.batchId).toEqual(expect.any(String));
  expect(capturedRequest?.body.range).toMatchObject({
    eventCount: expect.any(Number),
    fromEventId: expect.any(String),
    toEventId: expect.any(String),
  });
  expect(Array.isArray(capturedRequest?.body.events)).toBe(true);
  expectNoUnexpectedConsoleErrors(errors);
});

test('studio analytics flush surfaces structured failure details', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await page.route('**/__client_analytics__', async (route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: '统计令牌无效',
        code: 'ANALYTICS_AUTH_INVALID',
        retryable: false,
      }),
    });
  });

  await open(page, '/studio');
  await page.getByRole('button', { name: '尝试上报' }).click();
  await expect(page.locator('.client-callout--warm').filter({ hasText: /统计出口返回 401：统计令牌无效/ })).toBeVisible();
  await expect(page.locator('.client-callout--warm').filter({ hasText: /ANALYTICS_AUTH_INVALID/ })).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors, [/Failed to load resource: the server responded with a status of 401 \(Unauthorized\)/]);
});

test('authenticated text-to-style submit can save result asset and update studio metrics', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await seedAuthenticatedSession(page);
  await mockAuthenticatedClientApis(page, { balance: 8000 });
  await page.route('**/api/abilities/ability-text-01/invoke', async (route) => {
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({
      inputs: {
        prompt: '轻商务女装套装，突出都市通勤感和成衣质感',
        size: '2K',
      },
      images: [],
    });
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        abilityId: 'ability-text-01',
        provider: 'volcengine',
        status: 'success',
        requestId: 'req-text-01',
        durationMs: 1800,
        images: [
          {
            ossUrl: 'https://img.example.com/generated-look-01.jpg',
            type: 'image',
          },
        ],
      }),
    });
  });

  await open(page, '/design/text-to-style');
  await expect(page.getByText('当前可用积分 8,000 点')).toBeVisible();
  await expect(page.getByText('预计消耗 1800 点')).toBeVisible();
  await page.locator('textarea').first().fill('轻商务女装套装，突出都市通勤感和成衣质感');
  await page.getByRole('button', { name: '开始创作' }).click();

  await expect(page.getByRole('heading', { name: '已生成结果' })).toBeVisible();
  await expect(page.getByText(/请求已完成/)).toBeVisible();
  const savedAssets = await page.evaluate(() => JSON.parse(localStorage.getItem('podi-client-asset-library') || '[]'));
  expect(savedAssets[0]?.title).toBe('以文生款 结果');
  expect(savedAssets[0]?.image).toBe('https://img.example.com/generated-look-01.jpg');
  expect(savedAssets[0]?.abilityKey).toBe('doubao_seedream_4_5');

  await open(page, '/assets');
  await page.getByRole('button', { name: /继续/ }).first().click();
  await expect(page).toHaveURL(/\/design\/style-to-style$/);
  await expect(page.locator('textarea').first()).toHaveValue(/以文生款 结果/);

  await open(page, '/studio');
  const activationCard = page.locator('.workbench-ops-card').filter({ hasText: '首任务发起' });
  const assetCard = page.locator('.workbench-ops-card').filter({ hasText: '结果沉淀' });
  await expect(activationCard).toContainText('1 次');
  await expect(assetCard).toContainText('1 条');
  expectNoUnexpectedConsoleErrors(errors, [/Failed to load resource: net::ERR_CONNECTION_CLOSED/]);
});

test('authenticated style-to-style async task can complete and route continue vs retry correctly', async ({ page }) => {
  test.setTimeout(90000);
  const errors = await captureConsoleErrors(page);
  await seedAuthenticatedSession(page);
  await seedClientAssets(page, [
    {
      id: 'asset-reference-look-01',
      title: '参考款图 01',
      source: '原图上传',
      createdAt: '4月16日 08:00',
      image: 'https://img.example.com/reference-look-01.jpg',
      type: 'image',
      tags: ['原图上传'],
      origin: 'upload',
      pathHint: '/design/style-to-style',
      abilityKey: 'nano_banana_pro_image_to_image',
      provider: 'kie',
    },
  ]);
  const asyncTaskId = 'task-async-01';
  let pollCount = 0;
  await mockAuthenticatedClientApis(page, {
    balance: 8000,
    abilities: [
      {
        id: 'ability-style-01',
        provider: 'kie',
        category: 'design',
        capabilityKey: 'nano_banana_pro_image_to_image',
        displayName: 'KIE · Nano Banana Pro 图生图',
        metadata: {
          pricing: {
            discount_price: 22,
          },
        },
      },
    ],
    abilityTasks: [
      {
        id: asyncTaskId,
        abilityId: 'ability-style-01',
        abilityName: '参考改款任务',
        provider: 'kie',
        capabilityKey: 'nano_banana_pro_image_to_image',
        status: 'succeeded',
        createdAt: '2026-04-16T08:00:00.000Z',
        updatedAt: '2026-04-16T08:01:00.000Z',
        requestPayload: {
          inputs: {
            prompt: '保持廓形，优化腰线与层次，增强成衣感。',
            aspect_ratio: '1:1',
            resolution: '2K',
          },
          images: [
            {
              ossUrl: 'https://img.example.com/reference-look-01.jpg',
              name: 'reference-look-01.jpg',
            },
          ],
        },
        resultPayload: {
          images: [
            {
              ossUrl: 'https://img.example.com/style-async-result-01.jpg',
            },
          ],
        },
      },
    ],
  });

  await page.route('**/api/ability-tasks', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: asyncTaskId,
        abilityId: 'ability-style-01',
        abilityName: '参考改款任务',
        provider: 'kie',
        capabilityKey: 'nano_banana_pro_image_to_image',
        status: 'queued',
        createdAt: '2026-04-16T08:00:00.000Z',
        updatedAt: '2026-04-16T08:00:00.000Z',
        requestPayload: {
          inputs: {
            prompt: '保持廓形，优化腰线与层次，增强成衣感。',
            aspect_ratio: '1:1',
            resolution: '2K',
          },
          images: [
            {
              ossUrl: 'https://img.example.com/reference-look-01.jpg',
              name: 'reference-look-01.jpg',
            },
          ],
        },
        resultPayload: null,
      }),
    });
  });

  await page.route(`**/api/ability-tasks/${asyncTaskId}`, async (route) => {
    pollCount += 1;
    const status = pollCount === 1 ? 'running' : 'succeeded';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: asyncTaskId,
        abilityId: 'ability-style-01',
        abilityName: '参考改款任务',
        provider: 'kie',
        capabilityKey: 'nano_banana_pro_image_to_image',
        status,
        createdAt: '2026-04-16T08:00:00.000Z',
        updatedAt: '2026-04-16T08:01:00.000Z',
        requestPayload: {
          inputs: {
            prompt: '保持廓形，优化腰线与层次，增强成衣感。',
            aspect_ratio: '1:1',
            resolution: '2K',
          },
          images: [
            {
              ossUrl: 'https://img.example.com/reference-look-01.jpg',
              name: 'reference-look-01.jpg',
            },
          ],
        },
        resultPayload:
          status === 'succeeded'
            ? {
                images: [
                  {
                    ossUrl: 'https://img.example.com/style-async-result-01.jpg',
                  },
                ],
              }
            : null,
      }),
    });
  });

  await open(page, '/design/style-to-style');
  await expect(page.getByText('预计消耗 2200 点')).toBeVisible();
  await page.getByRole('button', { name: '使用最近素材' }).click();
  await page.locator('textarea').first().fill('保持廓形，优化腰线与层次，增强成衣感。');
  await page.getByRole('button', { name: '开始创作' }).click();

  await expect(page.getByText(/任务已创建，正在等待执行结果。/)).toBeVisible();
  await expect(page.getByRole('heading', { name: '任务处理中' })).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/任务处理完成，可下载结果或继续创作。/)).toBeVisible({ timeout: 10000 });

  const savedAssets = await page.evaluate(() => JSON.parse(localStorage.getItem('podi-client-asset-library') || '[]'));
  expect(savedAssets[0]?.title).toBe('参考改款任务 结果');
  expect(savedAssets[0]?.abilityKey).toBe('nano_banana_pro_image_to_image');

  await open(page, '/tasks');
  const asyncTaskRow = page.locator('.client-task-table__row').filter({ hasText: '参考改款任务' }).first();
  await expect(asyncTaskRow).toBeVisible();
  await asyncTaskRow.getByRole('button', { name: '继续' }).click();
  await expect(page).toHaveURL(/\/shoot\/marketing-variants$/);
  await expect(page.locator('textarea').first()).toHaveValue(/参考改款任务/);

  await open(page, '/tasks');
  await page.locator('.client-task-table__row').filter({ hasText: '参考改款任务' }).first().getByRole('button', { name: /重做/ }).click();
  await expect(page).toHaveURL(/\/design\/style-to-style$/);
  await expect(page.locator('textarea').first()).toHaveValue(/保持廓形，优化腰线与层次，增强成衣感。/);
  expectNoUnexpectedConsoleErrors(errors, [/Failed to load resource: net::ERR_CONNECTION_CLOSED/]);
});

test('authenticated low-balance intercept can route to wallet and restore workspace draft', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await seedAuthenticatedSession(page);
  await mockAuthenticatedClientApis(page, { balance: 600 });

  await open(page, '/design/text-to-style');
  const prompt = '低余额拦截回流校验：保留当前提示词并返回工作台继续提交';
  await expect(page.getByText('预计消耗 1800 点')).toBeVisible();
  await page.locator('textarea').first().fill(prompt);
  await page.getByRole('button', { name: '开始创作' }).click();

  await expect(page.getByText('当前积分不足', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '去充值' })).toBeVisible();
  await page.getByRole('button', { name: '去充值' }).click();

  await expect(page).toHaveURL(/\/wallet\?/);
  await expect(page).toHaveURL(/returnTo=%2Fdesign%2Ftext-to-style/);
  await expect(page).toHaveURL(/requiredPoints=1800/);
  await expect(page).toHaveURL(/currentBalance=600/);
  await expect(page).toHaveURL(/shortfallPoints=1200/);
  await expect(page.getByText(/当前大约还差 1,200 点/)).toBeVisible();

  await page.getByRole('button', { name: '返回原页面' }).click();
  await expect(page).toHaveURL(/\/design\/text-to-style$/);
  await expect(page.locator('textarea').first()).toHaveValue(prompt);
  expectNoUnexpectedConsoleErrors(errors);
});

test('assets page can continue creation with seeded asset context', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/assets');
  await expect(page.getByRole('heading', { name: '把原图、结果图、视频和模板放进同一个可复用中心。' })).toBeVisible();
  await page.getByRole('button', { name: /继续/ }).first().click();
  await expect(page).toHaveURL(/\/design\/(seamless|style-to-style|pattern-recolor)$/);
  await expect(page.locator('textarea').first()).toHaveValue(/春夏花卉提取稿|四方连续纹理/);
  expectNoUnexpectedConsoleErrors(errors);
});

test('project detail page can continue creation from project assets', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/projects/board-01');
  await expect(page.getByRole('heading', { name: '春夏印花方向白板' })).toBeVisible();
  await page.locator('.client-asset-card--button').first().click();
  await expect(page).toHaveURL(/\/design\/(seamless|style-to-style|pattern-recolor)$/);
  await expect(page.locator('textarea').first()).toHaveValue(/春夏花卉提取稿|四方连续纹理|格纹连续纹理/);
  expectNoUnexpectedConsoleErrors(errors);
});

test('tasks page supports status tabs and result preview', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/tasks');
  await expect(page.getByRole('heading', { name: /查看进度、确认结果、快速重做|先用演示任务理解/ })).toBeVisible();
  await page.getByRole('button', { name: '处理中', exact: true }).click();
  await expect(page.getByRole('button', { name: '处理中', exact: true })).toHaveClass(/is-active/);
  await page.locator('.client-task-table__row').first().click();
  await expect(page.getByText('结果预览')).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors);
});

test('wallet page renders recharge packs and ledger', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(page, '/wallet');
  await expect(page.getByRole('heading', { name: '把余额、充值、账单和回流放进同一条真实业务链。' })).toBeVisible();
  await expect(page.getByText('充值套餐')).toBeVisible();
  await expect(page.getByRole('button', { name: /高频包/ })).toBeVisible();
  await expect(page.getByText('最近账单', { exact: true })).toBeVisible();
  expectNoUnexpectedConsoleErrors(errors);
});

test('wallet page can restore low-balance return context from query params', async ({ page }) => {
  const errors = await captureConsoleErrors(page);
  await open(
    page,
    '/wallet?returnTo=%2Fdesign%2Ftext-to-style&returnLabel=%E4%BB%A5%E6%96%87%E7%94%9F%E6%AC%BE&requiredPoints=1800&currentBalance=600&shortfallPoints=1200',
  );
  await expect(page.getByText(/当前大约还差 1,200 点/)).toBeVisible();
  await expect(page.getByText(/推荐套餐：高频包/)).toBeVisible();
  await expect(page.getByText(/大约还能支持 1 次同类任务/)).toBeVisible();
  await page.getByRole('button', { name: '返回原页面' }).click();
  await expect(page).toHaveURL(/\/design\/text-to-style$/);
  expectNoUnexpectedConsoleErrors(errors);
});
