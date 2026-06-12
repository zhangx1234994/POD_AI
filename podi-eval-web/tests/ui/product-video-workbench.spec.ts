import { expect, test } from '@playwright/test';

const FRONT_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-front.svg';
const BACK_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-back.svg';
const DETAIL_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-detail.svg';

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

test('product video workbench previews a material package without triggering paid generation', async ({ page }) => {
  const previewPayloads: Array<Record<string, unknown>> = [];
  const runPayloads: Array<Record<string, unknown>> = [];

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
    if (path === '/api/business/product-commercialization/preview') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      previewPayloads.push(payload);
      await route.fulfill(
        mockJson({
          businessKey: 'product_commercialization',
          status: 'previewed',
          productCard: { confidence: 0.88 },
          resolvedProductFacts: {
            summary: 'Floral ceramic travel mug with wraparound print',
            source: 'product_image_primary',
            confidence: 0.88,
          },
          contentPackage: {
            imageFactAssessment: { confidence: 0.88, fieldConflicts: [] },
            commercePositioning: {},
          },
          copyGeneration: {
            method: 'skipped_for_video_preview',
            skipped: true,
            fallback: false,
          },
          copyPackage: {},
          copyScenarios: [],
          videoPlan: {
            provider: 'vidu',
            model: 'viduq3-turbo',
            planner: {
              method: 'openai_responses',
              provider: 'openai',
              model: 'gpt-5.5',
              fallback: false,
            },
            directorBrief: {
              productUnderstanding: 'A floral ceramic travel mug with visible handle and wraparound print.',
              commercialGoal: 'Create reusable marketplace and social video material for overseas gift buyers.',
              visualStyle: 'Clean ecommerce lighting with soft lifestyle cues.',
              continuityRule: 'Keep mug shape, handle position, floral print and ceramic material consistent across shots.',
            },
            targetDurationSeconds: 15,
            aspectRatio: '16:9',
            aspectPolicy: { mode: 'input_image_ratio', executionAspectRatio: 'input_image_ratio' },
            referenceImageSet: { count: 3 },
            storyboard: [
              {
                shot: 1,
                label: 'Hero rotation',
                goal: 'Show the complete mug silhouette and floral print.',
                keepSeconds: 8,
                subject: 'Floral ceramic travel mug',
                scene: 'bright kitchen tabletop with clean commercial background',
                cameraMovement: 'slow clockwise tabletop orbit',
                firstFramePrompt: 'Front hero frame of the floral ceramic travel mug on a clean tabletop.',
                lastFramePrompt: 'Three-quarter view that keeps the handle and wraparound floral print visible.',
                negativePrompt: 'no text, no watermark, no logo, no product deformation',
                referenceImage: { role: 'primary', url: FRONT_IMAGE },
              },
              {
                shot: 2,
                label: 'Back detail',
                goal: 'Show the handle and wraparound pattern continuity.',
                keepSeconds: 5,
                subject: 'Mug handle and back print',
                scene: 'same tabletop, closer crop around handle',
                cameraMovement: 'slow push from back angle to handle detail',
                firstFramePrompt: 'Back-side frame showing mug handle and floral print continuity.',
                lastFramePrompt: 'Close frame on ceramic handle and print edge.',
                negativePrompt: 'no text, no watermark, no logo, no unrealistic liquid',
                referenceImage: { role: 'back', url: BACK_IMAGE },
              },
              {
                shot: 3,
                label: 'Texture close-up',
                goal: 'Close-up on ceramic surface and printed detail.',
                keepSeconds: 3,
                subject: 'Ceramic texture',
                scene: 'macro commercial detail scene with neutral light',
                cameraMovement: 'micro lateral slide across printed surface',
                firstFramePrompt: 'Macro frame of ceramic surface and printed floral detail.',
                lastFramePrompt: 'Final clean macro frame with print texture still sharp.',
                negativePrompt: 'no text, no watermark, no logo, no blur',
                referenceImage: { role: 'detail', url: DETAIL_IMAGE },
              },
            ],
            videoPrompt:
              'Create a 15-second POD product showcase video for a floral ceramic travel mug. Preserve product shape, color, and print. No text, watermark, logo, or price tag.',
          },
          videoAssetPackagePlan: {
            script: { status: 'draft', planner: { method: 'openai_responses', fallback: false } },
            storyboard: [{ shot: 1 }, { shot: 2 }, { shot: 3 }],
            keyframeNeeds: [
              {
                role: 'first_frame',
                shot: 1,
                prompt: 'Front hero keyframe of the floral ceramic travel mug, clean ecommerce lighting.',
                reason: 'Anchor the first product view.',
              },
            ],
            compositionPlan: { availableAsOptionalAction: true },
          },
          review: {
            score: 82,
            videoReady: true,
            issues: [
              {
                level: 'info',
                code: 'PRODUCT_FACTS_INFERRED_FROM_IMAGE',
                message: 'Some product facts are inferred from the uploaded image and require manual review.',
              },
            ],
            nextActions: ['Review script and storyboard before submitting paid video material generation.'],
          },
        }),
      );
      return;
    }
    if (path === '/api/business/product-commercialization/runs') {
      runPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'should-not-be-called', status: 'queued' }));
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=home&category=%E4%BA%A7%E5%93%81%E8%A7%86%E9%A2%91');

  await expect(page.getByRole('heading', { name: '产品视频素材包' })).toBeVisible();
  await expect(page.getByText('产品文案内容包')).toHaveCount(0);
  await expect(page.getByText('预览只生成视频脚本、分镜和执行参数')).toBeVisible();
  await expect(page.getByRole('button', { name: /核对商品与视频策略/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /确认商品事实/ })).toHaveCount(0);

  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await stageMain.getByPlaceholder('https://...').fill(FRONT_IMAGE);
  await stageMain
    .getByPlaceholder(/每行一张/)
    .fill(`front,${FRONT_IMAGE},正面\nback,${BACK_IMAGE},背面\ndetail,${DETAIL_IMAGE},杯身纹理细节`);

  await expect(stageMain.getByAltText('产品图预览')).toBeVisible();
  await expect(page.getByText('图组 3')).toBeVisible();
  await stageMain.getByRole('button', { name: '下一步：核对并设置视频策略' }).click();

  await expect(stageMain.getByText('核对商品并规划视频素材包')).toBeVisible();
  await stageMain.getByRole('button', { name: '清空字段，仅用产品图' }).click();
  await stageMain.locator('input[placeholder="例如 15"]').fill('15');
  await expect(stageMain.getByText('8 + 5 + 3s')).toBeVisible();
  await stageMain.getByPlaceholder('例如：突出材质纹理和商品轮廓，不要出现文字和水印。').fill('强调杯身花纹和杯柄轮廓，适合海外礼品场景。');
  await stageMain.getByRole('button', { name: '生成素材包规划' }).click();

  await expect(stageMain.getByText('确认脚本与分镜')).toBeVisible();
  await expect(stageMain.getByText('视频规划')).toBeVisible();
  await expect(stageMain.getByText('规划器证据')).toBeVisible();
  await expect(stageMain.getByText('模型规划')).toBeVisible();
  await expect(stageMain.getByText('商品理解')).toBeVisible();
  await expect(stageMain.getByText('脚本', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('分镜', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('关键帧', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('分段视频', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('合成片', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('镜头 1 · Hero rotation')).toBeVisible();
  await expect(stageMain.getByText(/首帧：Front hero frame/)).toBeVisible();
  await expect(stageMain.getByText('首尾帧 / 关键帧计划')).toBeVisible();

  await expect(stageMain.getByText('生成 15s 分段视频素材包', { exact: true })).toBeVisible();
  await stageMain.getByLabel('我已核对当前脚本和分镜；按当前稿提交视频素材包任务。').check();
  const paidButton = stageMain.getByRole('button', { name: '生成 15s 分段视频素材包' });
  await expect(paidButton).toBeEnabled();

  expect(runPayloads).toHaveLength(0);
  expect(previewPayloads).toHaveLength(1);
  expect(previewPayloads[0]).toMatchObject({
    action: 'video_preview',
    productImageUrl: FRONT_IMAGE,
    targetDurationSeconds: 15,
    durationSeconds: 8,
    executorId: 'executor_vidu_default',
    aspectRatio: '16:9',
  });
  expect(previewPayloads[0].copyScenarios).toBeUndefined();
  expect(previewPayloads[0].commercePlatform).toBeUndefined();
  expect(previewPayloads[0].copyTone).toBeUndefined();
  expect(previewPayloads[0].visualSupportMode).toBeUndefined();
  expect(previewPayloads[0].productImages).toEqual([
    expect.objectContaining({ role: 'primary', url: FRONT_IMAGE, isPrimary: true }),
    expect.objectContaining({ role: 'back', url: BACK_IMAGE }),
    expect.objectContaining({ role: 'detail', url: DETAIL_IMAGE }),
  ]);
  expect(String(previewPayloads[0].extraPrompt)).toContain('用户目标成片时长：15 秒');
  expect(String(previewPayloads[0].extraPrompt)).toContain('Vidu · viduq3-turbo');
});
