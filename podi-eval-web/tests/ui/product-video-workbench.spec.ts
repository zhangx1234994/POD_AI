import { expect, test } from '@playwright/test';

const FRONT_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-front.svg';
const BACK_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-back.svg';
const DETAIL_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-detail.svg';

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

for (const marketWorkbench of [
  {
    category: '%E4%BA%A7%E5%93%81%E8%A7%86%E9%A2%91',
    heading: '产品视频素材包',
  },
  {
    category: '3D%E6%B8%B2%E6%9F%93%E8%A7%86%E9%A2%91',
    heading: '固定模型区域贴图与渲染方案',
  },
]) {
  test(`${marketWorkbench.heading} keeps the workbench primary path visible when the public workflow list is unavailable`, async ({ page }) => {
    await page.route('**/api/**', async (route) => {
      const reqUrl = new URL(route.request().url());
      const path = reqUrl.pathname;

      if (path === '/api/evals/me') {
        await route.fulfill(mockJson({ raterId: 'eval-ui-reviewer' }));
        return;
      }
      if (path === '/api/evals/workflow-versions') {
        await route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'workflow list temporarily unavailable' }),
        });
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
      if (path === '/api/evals/docs/workflows') {
        await route.fulfill(mockJson({ markdown: '', generatedAt: '2026-06-13T10:00:00Z', workflows: [] }));
        return;
      }
      if (path === '/api/business/product-3d-render-video/catalog') {
        await route.fulfill(mockJson({ models: [], scenePresets: [], cameraPresets: [], cameraDistances: [] }));
        return;
      }
      await route.fulfill(mockJson({}));
    });

    await page.goto(`/?view=home&category=${marketWorkbench.category}`);

    const compactWarning = page.locator('.podi-workflow-inline-warning');
    await expect(compactWarning).toHaveCount(0);
    await expect(page.getByRole('heading', { name: marketWorkbench.heading })).toBeVisible();
    await expect(page.getByText('测评功能列表加载失败')).toHaveCount(0);
  });
}

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
    if (path === '/api/business/promo-video/plan') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      previewPayloads.push(payload);
      await route.fulfill(
        mockJson({
          businessKey: 'promo_video',
          underlyingBusinessKey: 'product_commercialization',
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
            videoType: {
              key: 'product_showcase_short',
              label: '商品多角度展示',
              assetFocus: '主体、轮廓、材质和基础角度素材',
              planningGoal: '先建立完整商品识别，再安排全景、角度和细节镜头。',
              planningReminder: '适合做上架页、详情页或通用商品展示素材；不要过早裁切主体。',
            },
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
              targetAudience: 'overseas gift buyers and coffee commuters',
              visualStyle: 'Clean ecommerce lighting with soft lifestyle cues.',
              continuityRule: 'Keep mug shape, handle position, floral print and ceramic material consistent across shots.',
            },
            editablePlanningFields: [
              {
                id: 'core_message',
                label: '核心信息',
                value: 'Reusable marketplace and social video material for a floral ceramic travel mug.',
                source: 'auto',
                sourceLabel: '后端 VL 回填合同',
                editable: true,
              },
              {
                id: 'target_audience',
                label: '目标人群',
                value: 'overseas gift buyers and coffee commuters',
                source: 'auto',
                sourceLabel: '后端 VL 回填合同',
                editable: true,
              },
              {
                id: 'usage_scene',
                label: '使用场景',
                value: 'bright kitchen tabletop with clean commercial background',
                source: 'auto',
                sourceLabel: '后端分镜场景规划',
                editable: true,
              },
              {
                id: 'shot_preference',
                label: '镜头偏好',
                value: 'slow clockwise tabletop orbit',
                source: 'auto',
                sourceLabel: '后端镜头规划',
                editable: true,
              },
              {
                id: 'avoid',
                label: '禁止内容',
                value: 'no text, no watermark, no logo, no product deformation',
                source: 'auto',
                sourceLabel: '后端风险约束',
                editable: true,
              },
            ],
            planningFieldContract: {
              frontendEditable: true,
              manualChangesRequireReplan: true,
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
            shotPackages: [
              {
                shotNo: 1,
                segmentIndex: 1,
                label: 'Hero rotation',
                goal: 'Show the complete mug silhouette and floral print.',
                keepSeconds: 8,
                subject: 'Floral ceramic travel mug',
                scene: 'bright kitchen tabletop with clean commercial background',
                cameraMovement: 'slow clockwise tabletop orbit',
                referenceImage: { role: 'primary', url: FRONT_IMAGE },
                videoPrompt:
                  'Create a 15-second POD product showcase video for a floral ceramic travel mug. Preserve product shape, color, and print. No text, watermark, logo, or price tag.',
                firstFramePrompt: 'Front hero frame of the floral ceramic travel mug on a clean tabletop.',
                lastFramePrompt: 'Three-quarter view that keeps the handle and wraparound floral print visible.',
                keyframeNeeds: [
                  {
                    role: 'normalized_first_frame',
                    shot: 1,
                    prompt: 'Normalized 16:9 first frame of the floral ceramic travel mug, clean ecommerce lighting.',
                    reason: 'Required before Vidu fixed-aspect video execution.',
                  },
                ],
                confirmationRequired: true,
                executionState: 'needs_keyframes',
              },
              {
                shotNo: 2,
                segmentIndex: 2,
                label: 'Back detail',
                goal: 'Show the handle and wraparound pattern continuity.',
                keepSeconds: 5,
                subject: 'Mug handle and back print',
                scene: 'same tabletop, closer crop around handle',
                cameraMovement: 'slow push from back angle to handle detail',
                referenceImage: { role: 'back', url: BACK_IMAGE },
                videoPrompt: 'Second segment keeps the tabletop scene and pushes toward the handle detail.',
                keyframeNeeds: [],
                confirmationRequired: false,
                executionState: 'ready_without_keyframes',
              },
              {
                shotNo: 3,
                segmentIndex: 3,
                label: 'Texture close-up',
                goal: 'Close-up on ceramic surface and printed detail.',
                keepSeconds: 3,
                subject: 'Ceramic texture',
                scene: 'macro commercial detail scene with neutral light',
                cameraMovement: 'micro lateral slide across printed surface',
                referenceImage: { role: 'detail', url: DETAIL_IMAGE },
                videoPrompt: 'Third segment captures the printed ceramic texture in a short macro pass.',
                keyframeNeeds: [],
                confirmationRequired: false,
                executionState: 'ready_without_keyframes',
              },
            ],
            keyframeNeeds: [],
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
    if (path === '/api/business/promo-video/keyframes/runs') {
      runPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'keyframe-shot-1-run', businessKey: 'promo_video', status: 'queued' }));
      return;
    }
    if (path === '/api/business/promo-video/runs') {
      runPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'video-run', businessKey: 'promo_video', status: 'queued' }));
      return;
    }
    if (path === '/api/business/runs/get') {
      await route.fulfill(
        mockJson({
          runId: 'keyframe-shot-1-run',
          businessKey: 'promo_video',
          status: 'succeeded',
          taskStatus: 'succeeded',
          imageUrls: ['https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-1.png'],
          resultPayload: {
            businessKey: 'promo_video',
            underlyingBusinessKey: 'product_commercialization',
            status: 'succeeded',
            videoPlan: {
              videoPrompt:
                'Create a 15-second POD product showcase video for a floral ceramic travel mug. Preserve product shape, color, and print. No text, watermark, logo, or price tag.',
              storyboard: [
                {
                  shot: 1,
                  label: 'Hero rotation',
                  keepSeconds: 8,
                  subject: 'Floral ceramic travel mug',
                  prompt: 'Create the hero rotation segment.',
                },
              ],
              keyframePlan: [
                {
                  role: 'normalized_first_frame',
                  shot: 1,
                  prompt: 'Normalized 16:9 first frame of the floral ceramic travel mug, clean ecommerce lighting.',
                },
              ],
            },
            videoAssetPackagePlan: {
              keyframeNeeds: [
                {
                  role: 'normalized_first_frame',
                  shot: 1,
                  prompt: 'Normalized 16:9 first frame of the floral ceramic travel mug, clean ecommerce lighting.',
                },
              ],
            },
            videoAssetPackage: {
              deliveryStatus: 'keyframes_ready',
              keyframes: [
                {
                  role: 'normalized_first_frame',
                  shot: 1,
                  segmentIndex: 1,
                  imageUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-1.png',
                  prompt: 'Normalized 16:9 first frame of the floral ceramic travel mug, clean ecommerce lighting.',
                },
              ],
              segmentVideos: [],
            },
            videoResult: {
              status: 'keyframes_ready',
              keyframes: [
                {
                  role: 'normalized_first_frame',
                  shot: 1,
                  segmentIndex: 1,
                  imageUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-1.png',
                },
              ],
            },
          },
        }),
      );
      return;
    }
    if (path === '/api/business/product-commercialization/preview' || path === '/api/business/product-commercialization/runs') {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'legacy endpoint should not be called' }) });
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=home&category=%E4%BA%A7%E5%93%81%E8%A7%86%E9%A2%91');

  await expect(page.getByRole('heading', { name: '产品视频素材包' })).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const content = document.querySelector('.podi-shell__content');
        return content ? Math.round(content.scrollTop) : -1;
      }),
    )
    .toBe(0);
  await expect(page.getByText('产品文案内容包')).toHaveCount(0);
  await expect(page.getByText('预览只生成视频脚本、分镜和执行参数')).toBeVisible();
  await expect(page.getByText('POST /api/business/promo-video/plan')).toBeVisible();
  await expect(page.getByText('POST /api/business/product-commercialization/preview')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /核对商品与视频策略/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /确认商品事实/ })).toHaveCount(0);
  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await expect(stageMain.getByRole('button', { name: /上传产品图 拖拽图片/ })).toBeVisible();
  await stageMain.getByPlaceholder('https://...').fill(FRONT_IMAGE);
  await stageMain
    .getByPlaceholder(/每行一张/)
    .fill(`front,${FRONT_IMAGE},正面\nback,${BACK_IMAGE},背面\ndetail,${DETAIL_IMAGE},杯身纹理细节`);

  await expect(stageMain.getByAltText('产品图预览')).toBeVisible();
  await expect(page.getByText('图组 3')).toBeVisible();
  await stageMain.getByRole('button', { name: '下一步：核对并设置视频策略' }).click();

  await expect(stageMain.getByText('核对商品并规划视频素材包')).toBeVisible();
  await stageMain.getByRole('button', { name: '填入示例字段' }).click();
  await expect(stageMain.getByText('商品：产品图已锁定，待规划识别')).toBeVisible();
  await expect(stageMain.getByText('分类：待规划识别')).toBeVisible();
  await expect(stageMain.getByText('视频规划不会要求你预先确认 JSON 一定正确')).toBeVisible();
  await stageMain.locator('input[placeholder="例如 15"]').fill('15');
  await expect(stageMain.getByText('8 + 5 + 3s')).toBeVisible();
  await expect(stageMain.getByText('视频类型 / 资产类型')).toBeVisible();
  await expect(stageMain.getByText('商品多角度展示')).toBeVisible();
  await expect(stageMain.getByText('先选这次要交付的素材类型')).toBeVisible();
  await expect(stageMain.getByText('请先生成并确认目标画幅首帧，再提交视频素材任务')).toBeVisible();
  await expect(stageMain.getByText('提交视频前系统会先生成并归一目标画幅首帧')).toHaveCount(0);
  await stageMain.getByPlaceholder('例如：突出材质纹理和商品轮廓，不要出现文字和水印。').fill('强调杯身花纹和杯柄轮廓，适合海外礼品场景。');
  await stageMain.getByRole('button', { name: '生成素材包规划' }).click();

  await expect(stageMain.getByText('确认脚本与分镜')).toBeVisible();
  await stageMain.getByRole('button', { name: '调整方案' }).click();
  await expect(stageMain.getByText('视频规划要素')).toBeVisible();
  await stageMain.getByPlaceholder(/镜头偏好可由/).fill('固定远景开场，然后慢速环绕杯身花纹。');
  await expect(stageMain.getByText('当前视频规划要素已经变更')).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '重新生成素材包规划' })).toBeVisible();
  await stageMain.getByRole('button', { name: '重新生成素材包规划' }).click();

  await expect(stageMain.getByText('确认脚本与分镜')).toBeVisible();
  await expect(stageMain.getByText('视频规划')).toBeVisible();
  await expect(stageMain.getByText('产品图 / VL 识别')).toBeVisible();
  await expect(stageMain.getByText('规划器证据')).toBeVisible();
  await expect(stageMain.getByText('模型规划')).toBeVisible();
  await expect(stageMain.getByText('视频类型策略')).toBeVisible();
  await expect(stageMain.getByText('类型决定素材包规划方式')).toBeVisible();
  await expect(stageMain.getByText('主体、轮廓、材质和基础角度素材')).toBeVisible();
  await expect(stageMain.getByText('模型回填要素')).toBeVisible();
  await expect(stageMain.getByText('后端 VL 回填合同').first()).toBeVisible();
  await expect(stageMain.getByText('模型回填').first()).toBeVisible();
  await expect(stageMain.getByText('商品理解', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('脚本', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('分镜', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('关键帧', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('分段视频', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('合成片', { exact: true })).toBeVisible();
  await expect(stageMain.getByLabel('脚本确认与执行稿')).toBeVisible();
  await expect(stageMain.getByText('先核对或改写这份总执行稿，再按镜头生成关键帧/首尾帧。')).toBeVisible();
  await expect(stageMain.getByText('镜头 1 · Hero rotation')).toBeVisible();
  await expect(stageMain.getByText('Normalized 16:9 first frame of the floral ceramic travel mug')).toBeVisible();
  await expect(stageMain.getByText('Vidu 归一化首帧').first()).toBeVisible();
  await expect(stageMain.getByText('用于固定目标画幅，确认后作为 Vidu 视频参考首帧').first()).toBeVisible();
  await expect(stageMain.getByText('关键帧提示词与结果').first()).toBeVisible();
  await expect(stageMain.getByText('计划 1 项')).toBeVisible();
  await expect(stageMain.getByText('已生成 0 张').first()).toBeVisible();
  await expect(stageMain.getByText('先生成关键帧再提交视频').first()).toBeVisible();
  await expect(stageMain.getByText('成本动作提示')).toBeVisible();
  await expect(stageMain.getByText(/都会提交异步任务并返回 runId/)).toBeVisible();

  await expect(stageMain.getByText('生成 15s 分段视频素材包', { exact: true })).toBeVisible();
  await stageMain.getByLabel('我已核对当前脚本和分镜；按当前稿提交视频素材包任务。').check();
  const keyframeButton = stageMain.getByRole('button', { name: '生成全部关键帧' });
  await expect(keyframeButton).toBeEnabled();
  const firstShot = stageMain.locator('.podi-product-commercialization__storyboard-group').filter({ hasText: '镜头 1 · Hero rotation' });
  await expect(firstShot.getByRole('button', { name: '生成本镜头关键帧' })).toBeEnabled();
  const paidButton = stageMain.locator('.t-button:has-text("生成 15s 分段视频素材包")');
  await expect(paidButton).toHaveClass(/t-is-disabled/);
  await firstShot.getByRole('button', { name: '生成本镜头关键帧' }).click();
  await expect.poll(() => runPayloads.length).toBe(1);
  expect(runPayloads[0]).toMatchObject({
    action: 'video_keyframes',
    keyframeShotScope: '1',
    videoPromptOverride:
      'Create a 15-second POD product showcase video for a floral ceramic travel mug. Preserve product shape, color, and print. No text, watermark, logo, or price tag.',
  });
  await expect(firstShot.getByText('已生成 1 张')).toBeVisible();
  await expect(firstShot.getByText('Vidu 归一化首帧').first()).toBeVisible();
  await expect(firstShot.getByText('生成后待确认')).toBeVisible();
  await expect(stageMain.getByText('关键帧确认进度 0/1 个镜头。')).toBeVisible();
  await expect(stageMain.getByLabel('关键帧确认门禁')).toBeVisible();
  await expect(stageMain.getByLabel(/我已逐个核对所有关键帧/)).toHaveCount(0);
  await expect(paidButton).toHaveClass(/t-is-disabled/);
  await firstShot.getByLabel(/我确认镜头 1 关键帧\/首尾帧可用/).check();
  await expect(firstShot.getByText('本镜头已确认').first()).toBeVisible();
  await expect(stageMain.getByText('关键帧确认进度 1/1 个镜头。')).toBeVisible();
  await expect(stageMain.getByText('可提交视频素材任务')).toBeVisible();
  await expect(paidButton).not.toHaveClass(/t-is-disabled/);

  await firstShot.getByRole('button', { name: '重生成本镜头关键帧' }).click();
  await expect.poll(() => runPayloads.length).toBe(2);
  expect(runPayloads[1]).toMatchObject({
    action: 'video_keyframes',
    keyframeShotScope: '1',
  });
  await expect(firstShot.getByText('生成后待确认')).toBeVisible();
  await expect(stageMain.getByText('关键帧确认进度 0/1 个镜头。')).toBeVisible();
  await expect(paidButton).toHaveClass(/t-is-disabled/);
  await firstShot.getByLabel(/我确认镜头 1 关键帧\/首尾帧可用/).check();
  await expect(firstShot.getByText('本镜头已确认').first()).toBeVisible();
  await expect(stageMain.getByText('关键帧确认进度 1/1 个镜头。')).toBeVisible();
  await expect(paidButton).not.toHaveClass(/t-is-disabled/);

  await paidButton.click();
  await expect.poll(() => runPayloads.length).toBe(3);

  expect(previewPayloads).toHaveLength(2);
  const latestPreviewPayload = previewPayloads[previewPayloads.length - 1];
  expect(latestPreviewPayload).toMatchObject({
    action: 'video_preview',
    productImageUrl: FRONT_IMAGE,
    targetDurationSeconds: 15,
    durationSeconds: 8,
    executorId: 'executor_vidu_default',
    aspectRatio: '16:9',
  });
  expect(latestPreviewPayload.copyScenarios).toBeUndefined();
  expect(latestPreviewPayload.commercePlatform).toBeUndefined();
  expect(latestPreviewPayload.copyTone).toBeUndefined();
  expect(latestPreviewPayload.visualSupportMode).toBeUndefined();
  expect(latestPreviewPayload.videoPlanningContext).toMatchObject({
    userRequirement: '强调杯身花纹和杯柄轮廓，适合海外礼品场景。',
    shotPreference: '固定远景开场，然后慢速环绕杯身花纹。',
    avoid: expect.stringContaining('不要出现文字'),
    fields: expect.arrayContaining([
      expect.objectContaining({ id: 'avoid', value: expect.stringContaining('不要出现文字') }),
      expect.objectContaining({ id: 'shot_preference', source: 'manual', value: '固定远景开场，然后慢速环绕杯身花纹。' }),
    ]),
  });
  expect(latestPreviewPayload.productFields).toMatchObject({
    英文名称: "Women's knitted woolen socks",
  });
  expect(latestPreviewPayload.productImages).toEqual([
    expect.objectContaining({ role: 'primary', url: FRONT_IMAGE, isPrimary: true }),
    expect.objectContaining({ role: 'back', url: BACK_IMAGE }),
    expect.objectContaining({ role: 'detail', url: DETAIL_IMAGE }),
  ]);
  expect(String(latestPreviewPayload.extraPrompt)).toContain('用户目标成片时长：15 秒');
  expect(String(latestPreviewPayload.extraPrompt)).toContain('Vidu · viduq3-turbo');
  expect(runPayloads[2]).toMatchObject({
    action: 'video_generate',
    videoPlanningContext: expect.objectContaining({
      userRequirement: '强调杯身花纹和杯柄轮廓，适合海外礼品场景。',
      targetAudience: expect.stringContaining('overseas gift buyers'),
      shotPreference: expect.stringContaining('固定远景开场'),
      fields: expect.arrayContaining([
        expect.objectContaining({ id: 'target_audience', value: expect.stringContaining('overseas gift buyers') }),
        expect.objectContaining({ id: 'shot_preference', source: 'manual', value: expect.stringContaining('固定远景开场') }),
      ]),
    }),
    confirmedVideoKeyframes: [
      expect.objectContaining({
        shot: '1',
        segmentIndex: 1,
        imageUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-shot-1.png',
        confirmed: true,
      }),
    ],
  });
});

test('product video workbench can ask the model to fill planning fields before a plan exists', async ({ page }) => {
  const previewPayloads: Array<Record<string, unknown>> = [];

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
      await route.fulfill(mockJson({ markdown: '', generatedAt: '2026-06-13T10:00:00Z', workflows: [] }));
      return;
    }
    if (path === '/api/business/promo-video/plan') {
      previewPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(
        mockJson({
          businessKey: 'promo_video',
          underlyingBusinessKey: 'product_commercialization',
          status: 'previewed',
          productCard: { confidence: 0.9 },
          resolvedProductFacts: {
            summary: 'Floral ceramic travel mug',
            source: 'product_image_primary',
            confidence: 0.9,
          },
          contentPackage: {
            imageFactAssessment: { confidence: 0.9, fieldConflicts: [] },
            commercePositioning: {},
          },
          copyGeneration: { method: 'skipped_for_video_preview', skipped: true, fallback: false },
          copyPackage: {},
          copyScenarios: [],
          videoPlan: {
            provider: 'vidu',
            model: 'viduq3-turbo',
            planner: { method: 'openai_responses', provider: 'openai', model: 'gpt-5.5', fallback: false },
            editablePlanningFields: [
              {
                id: 'core_message',
                label: '核心信息',
                value: 'Show the floral mug shape, handle, and wraparound print clearly.',
                source: 'auto',
                sourceLabel: '模型识别回填',
                editable: true,
              },
              {
                id: 'target_audience',
                label: '目标人群',
                value: 'overseas gift buyers and daily coffee users',
                source: 'auto',
                sourceLabel: '模型识别回填',
                editable: true,
              },
              {
                id: 'usage_scene',
                label: '使用场景',
                value: 'clean kitchen tabletop and marketplace listing video',
                source: 'auto',
                sourceLabel: '模型识别回填',
                editable: true,
              },
            ],
            targetDurationSeconds: 8,
            aspectRatio: '16:9',
            storyboard: [],
            videoPrompt: 'Create an 8-second POD product video for a floral ceramic travel mug.',
          },
          videoAssetPackagePlan: { script: { status: 'draft' }, storyboard: [], shotPackages: [] },
          review: { score: 86, videoReady: true, issues: [] },
        }),
      );
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=home&category=%E4%BA%A7%E5%93%81%E8%A7%86%E9%A2%91');

  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await stageMain.getByPlaceholder('https://...').fill(FRONT_IMAGE);
  await stageMain.getByRole('button', { name: '下一步：核对并设置视频策略' }).click();

  const fillButton = stageMain.getByRole('button', { name: '用模型填写' });
  await expect(fillButton).toBeEnabled();
  await fillButton.click();

  await expect.poll(() => previewPayloads.length).toBe(1);
  await expect(stageMain.getByText('核对商品并规划视频素材包')).toBeVisible();
  await expect(stageMain.getByPlaceholder(/核心信息可由/)).toHaveValue('Show the floral mug shape, handle, and wraparound print clearly.');
  await expect(stageMain.getByPlaceholder(/目标人群可由/)).toHaveValue('overseas gift buyers and daily coffee users');
  await expect(stageMain.getByText('模型回填').first()).toBeVisible();
});

test('product video workbench keeps keyframe confirmation locked when a required frame role is missing', async ({ page }) => {
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
      await route.fulfill(mockJson({ markdown: '', generatedAt: '2026-06-13T10:00:00Z', workflows: [] }));
      return;
    }
    if (path === '/api/business/promo-video/plan') {
      await route.fulfill(
        mockJson({
          businessKey: 'promo_video',
          underlyingBusinessKey: 'product_commercialization',
          status: 'previewed',
          productCard: { confidence: 0.9 },
          resolvedProductFacts: {
            summary: 'Floral travel mug',
            source: 'product_image_primary',
            confidence: 0.9,
          },
          contentPackage: {
            imageFactAssessment: { confidence: 0.9, fieldConflicts: [] },
            commercePositioning: {},
          },
          copyGeneration: { method: 'skipped_for_video_preview', skipped: true, fallback: false },
          copyPackage: {},
          copyScenarios: [],
          videoPlan: {
            provider: 'vidu',
            model: 'viduq3-turbo',
            planner: { method: 'openai_responses', provider: 'openai', model: 'gpt-5.5', fallback: false },
            targetDurationSeconds: 8,
            aspectRatio: '16:9',
            storyboard: [
              {
                shot: 1,
                label: 'Hero turn',
                keepSeconds: 8,
                subject: 'Floral travel mug',
                scene: 'clean tabletop',
                cameraMovement: 'slow orbit',
                firstFramePrompt: 'Opening hero frame for the floral mug.',
                lastFramePrompt: 'Ending three-quarter frame for the floral mug.',
                referenceImage: { role: 'primary', url: FRONT_IMAGE },
              },
            ],
            videoPrompt: 'Create an 8-second product video for a floral travel mug.',
          },
          videoAssetPackagePlan: {
            script: { status: 'draft' },
            storyboard: [{ shot: 1 }],
            shotPackages: [
              {
                shotNo: 1,
                segmentIndex: 1,
                label: 'Hero turn',
                keepSeconds: 8,
                subject: 'Floral travel mug',
                scene: 'clean tabletop',
                cameraMovement: 'slow orbit',
                videoPrompt: 'Create an 8-second product video for a floral travel mug.',
                keyframeNeeds: [
                  { role: 'first_frame', shot: 1, prompt: 'Opening hero frame for the floral mug.' },
                  { role: 'last_frame', shot: 1, prompt: 'Ending three-quarter frame for the floral mug.' },
                ],
                confirmationRequired: true,
                executionState: 'needs_keyframes',
              },
            ],
            keyframeNeeds: [
              { role: 'first_frame', shot: 1, prompt: 'Opening hero frame for the floral mug.' },
              { role: 'last_frame', shot: 1, prompt: 'Ending three-quarter frame for the floral mug.' },
            ],
          },
          review: { score: 86, videoReady: true, issues: [] },
        }),
      );
      return;
    }
    if (path === '/api/business/promo-video/keyframes/runs') {
      runPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'keyframe-role-mismatch-run', businessKey: 'promo_video', status: 'queued' }));
      return;
    }
    if (path === '/api/business/promo-video/runs') {
      runPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'video-should-not-run', businessKey: 'promo_video', status: 'queued' }));
      return;
    }
    if (path === '/api/business/runs/get') {
      await route.fulfill(
        mockJson({
          runId: 'keyframe-role-mismatch-run',
          businessKey: 'promo_video',
          status: 'succeeded',
          taskStatus: 'succeeded',
          imageUrls: [
            'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-first-a.png',
            'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-first-b.png',
          ],
          resultPayload: {
            businessKey: 'promo_video',
            underlyingBusinessKey: 'product_commercialization',
            status: 'succeeded',
            videoPlan: {
              videoPrompt: 'Create an 8-second product video for a floral travel mug.',
              storyboard: [{ shot: 1, label: 'Hero turn', keepSeconds: 8, subject: 'Floral travel mug' }],
            },
            videoAssetPackagePlan: {
              shotPackages: [
                {
                  shotNo: 1,
                  segmentIndex: 1,
                  label: 'Hero turn',
                  keyframeNeeds: [
                    { role: 'first_frame', shot: 1, prompt: 'Opening hero frame for the floral mug.' },
                    { role: 'last_frame', shot: 1, prompt: 'Ending three-quarter frame for the floral mug.' },
                  ],
                },
              ],
              keyframeNeeds: [
                { role: 'first_frame', shot: 1, prompt: 'Opening hero frame for the floral mug.' },
                { role: 'last_frame', shot: 1, prompt: 'Ending three-quarter frame for the floral mug.' },
              ],
            },
            videoAssetPackage: {
              deliveryStatus: 'keyframes_partial',
              keyframes: [
                {
                  role: 'first_frame',
                  shot: 1,
                  segmentIndex: 1,
                  imageUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-first-a.png',
                },
                {
                  role: 'first_frame',
                  shot: 1,
                  segmentIndex: 1,
                  imageUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/keyframe-first-b.png',
                },
              ],
            },
          },
        }),
      );
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=home&category=%E4%BA%A7%E5%93%81%E8%A7%86%E9%A2%91');

  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await stageMain.getByPlaceholder('https://...').fill(FRONT_IMAGE);
  await stageMain.getByRole('button', { name: '下一步：核对并设置视频策略' }).click();
  await stageMain.getByRole('button', { name: '生成素材包规划' }).click();

  await expect(stageMain.getByText('确认脚本与分镜')).toBeVisible();
  await expect(stageMain.getByText('计划 2 项')).toBeVisible();
  await expect(stageMain.getByText('缺少 首帧、尾帧')).toBeVisible();
  await stageMain.getByLabel('我已核对当前脚本和分镜；按当前稿提交视频素材包任务。').check();
  await stageMain.getByRole('button', { name: '生成本镜头关键帧' }).click();

  const firstShot = stageMain.locator('.podi-product-commercialization__storyboard-group').filter({ hasText: '镜头 1 · Hero turn' });
  await expect.poll(() => runPayloads.length).toBe(1);
  await expect(firstShot.getByText('已生成 2 张')).toBeVisible();
  await expect(firstShot.getByText('缺少 尾帧')).toBeVisible();
  await expect(firstShot.getByText('待生成对应图片')).toBeVisible();
  await expect(firstShot.getByLabel(/我确认镜头 1 关键帧\/首尾帧可用/)).toBeDisabled();
  await expect(stageMain.getByText('关键帧确认进度 0/1 个镜头。')).toBeVisible();
  await expect(stageMain.locator('.t-button:has-text("生成 8s 单段视频素材")')).toHaveClass(/t-is-disabled/);
  expect(runPayloads).toHaveLength(1);
});
