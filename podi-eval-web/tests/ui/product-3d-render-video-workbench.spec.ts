import { expect, test } from '@playwright/test';

const TEXTURE_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-front.svg';

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

test('3d render video workbench exports a local preview video', async ({ page }) => {
  const previewPayloads: Array<Record<string, unknown>> = [];

  await page.addInitScript(() => {
    class FakeMediaRecorder {
      static isTypeSupported() {
        return true;
      }

      mimeType = 'video/webm';
      state: 'inactive' | 'recording' = 'inactive';
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onerror: (() => void) | null = null;
      onstop: (() => void) | null = null;

      constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}

      start() {
        this.state = 'recording';
        window.setTimeout(() => {
          this.ondataavailable?.({ data: new Blob(['podi-webm-preview'], { type: 'video/webm' }) });
        }, 20);
      }

      stop() {
        this.state = 'inactive';
        this.onstop?.();
      }
    }

    Object.defineProperty(window, 'MediaRecorder', { value: FakeMediaRecorder });
    HTMLCanvasElement.prototype.captureStream = function captureStream() {
      return {
        getTracks: () => [{ stop() {} }],
      } as unknown as MediaStream;
    };
  });

  await page.route('**/api/**', async (route) => {
    const reqUrl = new URL(route.request().url());
    const path = reqUrl.pathname;

    if (path === '/api/evals/me') {
      await route.fulfill(mockJson({ raterId: 'eval-ui-reviewer' }));
      return;
    }
    if (path === '/api/evals/workflow-versions') {
      await route.fulfill(mockJson([]));
      return;
    }
    if (path === '/api/evals/business/quality-samples') {
      await route.fulfill(mockJson({ total: 0, items: [] }));
      return;
    }
    if (path === '/api/evals/metrics/workflows') {
      await route.fulfill(mockJson({ metrics: {} }));
      return;
    }
    if (path === '/api/evals/runs/with-latest-annotation') {
      await route.fulfill(mockJson({ total: 0, items: [] }));
      return;
    }
    if (path === '/api/evals/docs/workflows') {
      await route.fulfill(mockJson({ markdown: '', generatedAt: '2026-06-12T10:00:00Z', workflows: [] }));
      return;
    }
    if (path === '/api/business/product-3d-render-video/preview') {
      previewPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(
        mockJson({
          businessKey: 'product_3d_render_video',
          status: 'previewed',
          model: { preferredFile: '1660.glb' },
          assetReadiness: {
            score: 92,
            modelReady: true,
            uvReady: true,
            textureProvided: true,
            renderWorkerReady: false,
          },
          renderPlan: {
            textureApplication: { mode: 'slot_texture_mapping', materialSlot: 'front' },
            camera: { label: '360 环绕', description: '围绕商品一圈，适合商品展示短视频。' },
            scene: { label: '干净摄影棚', lighting: 'softbox key light', background: 'matte light gray seamless backdrop' },
          },
          review: { issues: [] },
        }),
      );
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=home&category=3D%E6%B8%B2%E6%9F%93%E8%A7%86%E9%A2%91');

  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await expect(page.getByRole('heading', { name: '固定模型区域贴图与渲染方案' })).toBeVisible();
  await expect(page.getByText('本地 WebM', { exact: true })).toBeVisible();

  await stageMain.getByPlaceholder('https://...').fill(TEXTURE_IMAGE);
  await expect(page.getByText(/模型已加载|已按材质名应用/)).toBeVisible({ timeout: 20_000 });

  await stageMain.getByRole('button', { name: '检查 3D 贴图方案' }).click();
  await expect(stageMain.getByText('准备度', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('渲染 worker', { exact: true })).toBeVisible();

  await stageMain.getByRole('button', { name: '生成 6s 本地预览视频' }).click();
  await expect(stageMain.getByText(/KB · WebM/)).toBeVisible({ timeout: 15_000 });
  await expect(stageMain.locator('video')).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '下载 WebM' })).toBeVisible();

  expect(previewPayloads).toHaveLength(1);
  expect(previewPayloads[0]).toMatchObject({
    modelKey: 'cup_1660',
    materialSlot: 'front',
    cameraPreset: 'orbit_360',
    durationSeconds: 6,
    outputMode: 'plan_only',
  });
});
