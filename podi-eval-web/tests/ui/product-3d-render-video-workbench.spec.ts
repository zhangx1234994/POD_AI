import { expect, test } from '@playwright/test';

const TEXTURE_IMAGE = 'http://127.0.0.1:8200/samples/product-video/mug-front.png';

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

test('3d render video workbench exports a local preview video', async ({ page }) => {
  const previewPayloads: Array<Record<string, unknown>> = [];
  const serverPayloads: Array<Record<string, unknown>> = [];

  await page.addInitScript(() => {
    class FakeMediaRecorder {
      static isTypeSupported(type: string) {
        return type.startsWith('video/mp4') || type.startsWith('video/webm');
      }

      mimeType = 'video/webm';
      state: 'inactive' | 'recording' = 'inactive';
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onerror: (() => void) | null = null;
      onstop: (() => void) | null = null;

      constructor(_stream: MediaStream, options?: MediaRecorderOptions) {
        this.mimeType = options?.mimeType || 'video/webm';
      }

      start() {
        this.state = 'recording';
        window.setTimeout(() => {
          this.ondataavailable?.({ data: new Blob(['podi-mp4-preview'], { type: this.mimeType }) });
        }, 20);
      }

      stop() {
        this.state = 'inactive';
        this.onstop?.();
      }
    }

    Object.defineProperty(window, 'MediaRecorder', { value: FakeMediaRecorder });
    HTMLCanvasElement.prototype.captureStream = function captureStream() {
      (window as any).__podiCapturedCanvasSize = { width: this.width, height: this.height };
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
    if (path === '/api/business/product-3d-render-video/catalog') {
      await route.fulfill(
        mockJson({
          businessKey: 'product_3d_render_video',
          version: 'product-3d-render-video-catalog-v1',
          status: 'active',
          defaults: {
            modelKey: 'cup_1660',
            materialSlot: 'front',
            cameraPreset: 'orbit_360',
            cameraDistance: 'wide',
            scenePreset: 'clean_studio',
            durationSeconds: 6,
            aspectRatio: '16:9',
            motionPath: [
              { x: 0.22, y: 0.66 },
              { x: 0.5, y: 0.5 },
              { x: 0.78, y: 0.42 },
            ],
            cameraPlan: {
              template: 'orbit_360',
              productMotion: 'fixed',
              cameraMotion: 'path_playback',
              playbackConfirmed: false,
            },
          },
          models: [
            {
              modelKey: 'cup_1660',
              displayName: '1660 杯子',
              preferredFile: '1660.glb',
              productType: 'cup',
              recommendedMaterialSlot: 'front',
              materialSlots: ['front', 'mouth', 'cover', 'bottom', 'handshank', 'else', 'else1'],
              hasUv: true,
              hasAnimation: false,
              notes: ['GLB/GLTF 均存在，首版渲染优先使用 GLB。'],
            },
            {
              modelKey: 'backpack_2551',
              displayName: '2551 笔记本电脑背包',
              preferredFile: '2551.glb',
              productType: 'backpack',
              recommendedMaterialSlot: 'front',
              materialSlots: ['front', 'bottom', 'back'],
              hasUv: true,
              hasAnimation: false,
              notes: ['材质槽较多，建议先从 front 验证方向和比例。'],
            },
          ],
          scenePresets: [
            {
              key: 'clean_studio',
              label: '干净摄影棚',
              lighting: 'softbox key light',
              background: 'matte light gray seamless backdrop',
              sceneModel: 'studio_seamless_sweep',
              placement: {
                anchor: 'center',
                scalePolicy: 'fit product to 70% frame height',
                safeZones: ['leave top/bottom breathing room', 'no props crossing product silhouette'],
              },
              asset: {
                assetId: 'podi.scene.procedural.clean_studio.v1',
                assetStatus: 'ready',
                renderFidelity: 'mvp_procedural',
                source: 'podi_internal',
                license: { type: 'internal_procedural', commercialUse: true },
                externalCandidates: [
                  {
                    provider: 'Poly Haven',
                    kind: 'studio HDRI',
                    license: 'CC0',
                    ingestStage: 'staging_candidate',
                    workerReadiness: { highFidelityWorker: 'requires_asset_import_test' },
                  },
                ],
              },
              sceneVisualAcceptance: {
                status: 'mvp_ready',
                summary: 'Current procedural scene is ready for preview and lightweight MP4/OSS output; high-fidelity external scene candidates remain staging-only until visual/import gates pass.',
                checks: [
                  {
                    code: 'CURRENT_SCENE_ASSET_READY',
                    label: '当前场景资产可执行',
                    status: 'passed',
                    evidence: 'podi.scene.procedural.clean_studio.v1 · mvp_procedural',
                  },
                  {
                    code: 'SAFE_FRAMING',
                    label: '镜头完整入画',
                    status: 'passed',
                    evidence: 'wide · frame 56% · margin 7%',
                  },
                  {
                    code: 'HIGH_FIDELITY_IMPORT_SMOKE',
                    label: '高保真候选待入库',
                    status: 'planned',
                    evidence: '1 candidates need staging/import smoke before promotion',
                  },
                ],
                candidateSummary: { total: 1, cc0Count: 1, readyCount: 0, blockedCount: 1 },
                candidateAssets: [
                  {
                    assetId: 'blocky_photo_studio',
                    displayName: 'Blocky Photo Studio',
                    provider: 'Poly Haven',
                    kind: 'studio HDRI',
                    license: 'CC0',
                    status: 'candidate_review_required',
                    blockingReasons: ['asset_not_downloaded', 'high_fidelity_import_smoke_missing'],
                    promotionNextAction: 'download asset, record hash/version, run visual + import smoke checks, then promote',
                  },
                ],
              },
              renderElements: [
                {
                  elementId: 'cyclorama_backdrop',
                  type: 'seamless_backdrop',
                  depthLayer: 'background',
                  zone: 'full_frame',
                  occlusion: 'never_cross_product_silhouette',
                },
                {
                  elementId: 'matte_floor',
                  type: 'floor_plane',
                  depthLayer: 'surface',
                  zone: 'bottom_20_percent',
                  occlusion: 'shadow_receiver_only',
                },
              ],
              fusion: {
                landingZone: 'center_ellipse_floor_zone',
                productScale: '56-70% frame height',
                occlusionPolicy: 'no foreground props may cross the product silhouette',
                propDepth: 'lighting cards and backdrop stay behind the product',
              },
            },
          ],
          sceneAssetSources: [
            {
              provider: 'Poly Haven',
              sourceType: 'hdri_and_3d_models',
              license: 'CC0',
              commercialUse: true,
              ingestStatus: 'candidate_source',
              candidateAssets: [
                {
                  assetId: 'blocky_photo_studio',
                  ingestStage: 'staging_candidate',
                  assetVersion: 'to_be_recorded',
                  downloadDate: 'not_downloaded',
                },
              ],
            },
            {
              provider: 'ambientCG',
              sourceType: 'pbr_materials_and_models',
              license: 'CC0 1.0 Universal',
              commercialUse: true,
              ingestStatus: 'candidate_source',
            },
            {
              provider: 'internal_or_cc0',
              sourceType: 'generic_scene_model',
              license: 'to_be_verified_per_asset',
              commercialUse: false,
              ingestStatus: 'needs_license_review',
            },
          ],
          cameraPresets: [
            { key: 'orbit_360', label: '360 环绕', description: '围绕商品一圈，适合商品展示短视频。' },
            { key: 'slow_push_in', label: '慢速推进', description: '从全景推进到主体细节。' },
          ],
          cameraDistances: [
            {
              key: 'wide',
              label: '远景完整商品',
              description: '优先保证商品完整入画。',
              frameHeightRatio: 0.56,
              safeMarginRatio: 0.07,
              cameraZ: 4.35,
              fov: 35,
            },
            {
              key: 'close',
              label: '近景细节镜头',
              description: '靠近材质和贴图区域，但仍保留安全边界。',
              frameHeightRatio: 0.76,
              safeMarginRatio: 0.06,
              cameraZ: 2.85,
              fov: 42,
            },
          ],
          durationOptions: [3, 5, 6, 8, 12],
          aspectRatioOptions: ['16:9', '1:1', '4:5', '9:16'],
          renderers: {},
          endpoints: {},
        }),
      );
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
            sceneAssetReady: true,
            sceneAssetId: 'podi.scene.procedural.clean_studio.v1',
            renderWorkerReady: true,
            renderWorker: 'lightweight_scene_renderer_v1',
          },
          renderPlan: {
            textureApplication: { mode: 'slot_texture_mapping', materialSlot: 'front' },
            camera: { label: '360 环绕', description: '围绕商品一圈，适合商品展示短视频。' },
            cameraPlan: {
              version: 'camera-plan-v1',
              template: 'slow_push_in',
              productMotion: 'fixed',
              cameraMotion: 'path_playback',
              playbackConfirmed: true,
              confirmationRequiredBeforeRender: true,
              path: {
                coordinateSpace: 'normalized_camera_path_preview',
                points: [
                  { x: 0.22, y: 0.66 },
                  { x: 0.5, y: 0.5 },
                  { x: 0.78, y: 0.42 },
                ],
                pointCount: 3,
              },
              constraints: {
                productFixed: true,
                keepFullProductInFrame: true,
                avoidTextureDistortion: true,
              },
            },
            scene: {
              label: '干净摄影棚',
              lighting: 'softbox key light',
              background: 'matte light gray seamless backdrop',
              fusion: {
                landingZone: 'center_ellipse_floor_zone',
                occlusionRule: 'no foreground props may cross the product silhouette',
              },
            },
            sceneVisualAcceptance: {
              status: 'mvp_ready',
              summary: 'Current procedural scene is ready for preview and lightweight MP4/OSS output.',
              checks: [
                { code: 'CURRENT_SCENE_ASSET_READY', label: '当前场景资产可执行', status: 'passed', evidence: 'ready' },
                { code: 'SAFE_FRAMING', label: '镜头完整入画', status: 'passed', evidence: 'wide' },
              ],
              candidateSummary: { total: 1, cc0Count: 1, readyCount: 0, blockedCount: 1 },
              candidateAssets: [
                {
                  assetId: 'blocky_photo_studio',
                  displayName: 'Blocky Photo Studio',
                  provider: 'Poly Haven',
                  kind: 'studio HDRI',
                  license: 'CC0',
                  status: 'candidate_review_required',
                  blockingReasons: ['asset_not_downloaded', 'high_fidelity_import_smoke_missing'],
                  promotionNextAction: 'download asset, record hash/version, run visual + import smoke checks, then promote',
                },
              ],
            },
          },
          review: { issues: [] },
        }),
      );
      return;
    }
    if (path === '/api/business/product-3d-render-video/runs') {
      serverPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
      await route.fulfill(mockJson({ runId: 'p3d-server-run-001', businessKey: 'product_3d_render_video', status: 'queued' }));
      return;
    }
    if (path === '/api/business/runs/get') {
      await route.fulfill(
        mockJson({
          runId: 'p3d-server-run-001',
          businessKey: 'product_3d_render_video',
          status: 'succeeded',
          taskStatus: 'succeeded',
          videoUrls: ['https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001.mp4'],
          imageUrls: ['https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001-cover.png'],
          resultPayload: {
            businessKey: 'product_3d_render_video',
            status: 'succeeded',
            renderAssetPackage: {
              deliveryStatus: 'assets_ready',
              renderer: 'lightweight_scene_renderer_v1',
              videoUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001.mp4',
              coverFrameUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001-cover.png',
              manifestUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001-manifest.json',
              assets: [
                {
                  type: 'video',
                  role: 'rendered_video',
                  ossUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001.mp4',
                },
                {
                  type: 'image',
                  role: 'cover_frame',
                  ossUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001-cover.png',
                },
                {
                  type: 'manifest',
                  role: 'render_manifest',
                  ossUrl: 'https://podi.oss-cn-hangzhou.aliyuncs.com/p3d-server-run-001-manifest.json',
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

  await page.goto('/?view=home&category=3D%E6%B8%B2%E6%9F%93%E8%A7%86%E9%A2%91');

  const stageMain = page.locator('.podi-product-commercialization__stage-main');
  await expect(page.getByRole('heading', { name: '固定模型区域贴图与渲染方案' })).toBeVisible();
  await expect(page.getByTitle('本地预览')).toBeVisible();
  await expect(page.getByTitle('OSS 视频')).toBeVisible();
  await expect(page.getByText('能力目录已同步', { exact: true })).toBeVisible();
  await expect(page.getByText(/已同步 2 个模型 \/ 1 个场景/)).toBeVisible();

  await stageMain.getByPlaceholder('https://...').fill(TEXTURE_IMAGE);
  await expect(page.getByText(/模型已加载|已按材质名应用/)).toBeVisible({ timeout: 20_000 });

  const controlSelects = stageMain.locator('.podi-product-commercialization__controls .t-select');
  await controlSelects.nth(0).click();
  await page.getByText('慢速推进').click();
  await controlSelects.nth(1).click();
  await page.getByText('近景细节镜头').click();
  await expect(stageMain.getByLabel('3D 视频生成主操作')).toBeVisible();
  await expect(stageMain.getByText('主执行区：先检查方案，再播放镜头轨迹确认，最后生成本地预览或提交服务端 MP4/OSS。调整镜头、场景或轨迹后需要重新确认。')).toBeVisible();
  await expect(stageMain.getByLabel('3D 视频输出状态')).toBeVisible();
  await expect(stageMain.getByLabel('3D 视频输出状态').getByText('待播放确认')).toBeVisible();
  await expect(stageMain.getByLabel('3D 视频输出状态').getByText('尚未生成')).toBeVisible();
  await expect(stageMain.getByLabel('3D 视频输出状态').getByText('尚未提交')).toBeVisible();
  await expect(stageMain.locator('.podi-product-3d-render__video-output')).toHaveCount(0);
  const checkPlanButton = stageMain.locator('.t-button').filter({ hasText: '检查 3D 贴图方案' });
  const playCameraPathButton = stageMain.locator('.t-button').filter({ hasText: '播放并确认镜头轨迹' });
  const localPreviewButton = stageMain.locator('.t-button').filter({ hasText: '生成本地预览视频' });
  const serverRenderButton = stageMain.locator('.t-button').filter({ hasText: '生成服务端 MP4/OSS 视频' });

  await expect(localPreviewButton).toHaveClass(/t-is-disabled/);
  await expect(serverRenderButton).toHaveClass(/t-is-disabled/);

  const motionEditor = stageMain.getByLabel('3D 镜头轨迹编辑器');
  const motionEditorPanel = stageMain.locator('.podi-product-3d-render__motion-editor');
  await motionEditor.scrollIntoViewIfNeeded();
  const motionBox = await motionEditor.boundingBox();
  expect(motionBox).not.toBeNull();
  if (!motionBox) throw new Error('motion editor box missing');
  await page.mouse.move(motionBox.x + motionBox.width * 0.14, motionBox.y + motionBox.height * 0.74);
  await page.mouse.down();
  await page.mouse.move(motionBox.x + motionBox.width * 0.38, motionBox.y + motionBox.height * 0.57);
  await page.mouse.move(motionBox.x + motionBox.width * 0.68, motionBox.y + motionBox.height * 0.43);
  await page.mouse.up();

  await checkPlanButton.click();
  await expect(stageMain.getByText('准备度', { exact: true })).toBeVisible();
  await expect(stageMain.getByText(/已就绪 · podi.scene.procedural.clean_studio.v1/)).toBeVisible();
  await expect(stageMain.getByText('渲染 worker', { exact: true })).toBeVisible();

  await expect(stageMain.getByText('选择镜头方案并确认轨迹')).toBeVisible();
  await expect(stageMain.getByText(/镜头模板/)).toBeVisible();
  await expect(stageMain.getByText('场景模型', { exact: true })).toBeVisible();
  await expect(stageMain.locator('.podi-product-3d-render__scene-thumb').first()).toBeVisible();
  const sceneRail = stageMain.locator('.podi-product-3d-render__scene-rail');
  await expect(sceneRail.getByText('无道具遮挡商品轮廓')).toBeVisible();
  const shootingBrief = stageMain.locator('.podi-product-3d-render__shooting-brief');
  await expect(shootingBrief.getByText('融合检查', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('中心椭圆落地区', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('podi.scene.procedural.clean_studio.v1', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('内部生成 · 可商用')).toBeVisible();
  await expect(shootingBrief.getByText('场景验收', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('当前可执行')).toBeVisible();
  await expect(shootingBrief.getByText('当前场景资产可执行 · 通过')).toBeVisible();
  await expect(shootingBrief.getByText('镜头完整入画 · 通过')).toBeVisible();
  await expect(shootingBrief.getByText('高保真候选', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('Poly Haven · Blocky Photo Studio · studio HDRI · CC0')).toBeVisible();
  await expect(shootingBrief.getByText(/asset_not_downloaded/)).toBeVisible();
  await expect(shootingBrief.getByText(/high_fidelity_import_smoke_missing/)).toBeVisible();
  await expect(shootingBrief.getByText('来源治理', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('Poly Haven · CC0 · 候选来源')).toBeVisible();
  await expect(shootingBrief.getByText('ambientCG · CC0 1.0 Universal · 候选来源')).toBeVisible();
  await expect(shootingBrief.getByText('internal_or_cc0 · to_be_verified_per_asset · 需授权复核')).toBeVisible();
  await expect(shootingBrief.getByText('外部素材必须先过授权、版本、视觉和性能验收')).toBeVisible();
  await expect(shootingBrief.getByText('场景结构', { exact: true })).toBeVisible();
  await expect(shootingBrief.getByText('背景层 · Cyclorama Backdrop')).toBeVisible();
  await expect(shootingBrief.getByText('承载面 · Matte Floor')).toBeVisible();
  await expect(shootingBrief.getByText('never_cross_product_silhouette')).toBeVisible();
  await expect(stageMain.getByText(/安全取景/)).toBeVisible();
  await expect(motionEditorPanel.getByText('镜头轨迹预览', { exact: true })).toBeVisible();
  await expect(motionEditorPanel.getByTitle('商品固定')).toBeVisible();
  await expect(motionEditorPanel.getByText('待播放确认', { exact: true })).toBeVisible();
  const resultShotList = stageMain.locator('.podi-product-commercialization__shot-list');
  await expect(resultShotList.getByText('融合规则', { exact: true })).toBeVisible();
  await expect(resultShotList.getByText('center_ellipse_floor_zone', { exact: true })).toBeVisible();
  await expect(resultShotList.getByText('场景验收合同', { exact: true })).toBeVisible();
  await expect(resultShotList.getByText(/当前可执行 · 候选 1 · 阻断 1/)).toBeVisible();
  await expect(serverRenderButton).toHaveClass(/t-is-disabled/);
  await playCameraPathButton.click();
  await expect(stageMain.getByLabel('3D 视频输出状态').getByText('已播放确认')).toBeVisible({ timeout: 10_000 });
  await expect(localPreviewButton).not.toHaveClass(/t-is-disabled/);
  await expect(serverRenderButton).not.toHaveClass(/t-is-disabled/);
  await localPreviewButton.click();
  await expect(stageMain.locator('.podi-product-3d-render__video-output').getByText(/KB · MP4/)).toBeVisible({ timeout: 15_000 });
  await expect
    .poll(async () => page.evaluate(() => (window as any).__podiCapturedCanvasSize), { timeout: 8_000 })
    .toEqual({ width: 960, height: 540 });
  await expect(stageMain.locator('video')).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '下载 MP4' })).toBeVisible();
  await serverRenderButton.click();
  await expect(stageMain.getByText('服务端 OSS 视频')).toBeVisible();
  await expect(stageMain.getByText('runId=p3d-server-run-001', { exact: true })).toBeVisible();
  await expect(stageMain.getByText('MP4 1 个 · 封面 1 张 · manifest 1 个')).toBeVisible();
  await expect(stageMain.getByAltText('服务端渲染封面帧')).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '打开 OSS 视频' })).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '打开封面帧' })).toBeVisible();
  await expect(stageMain.getByRole('button', { name: '打开 manifest' })).toBeVisible();

  expect(previewPayloads).toHaveLength(1);
  expect(previewPayloads[0]).toMatchObject({
    modelKey: 'cup_1660',
    materialSlot: 'front',
    cameraPreset: 'slow_push_in',
    cameraDistance: 'close',
    durationSeconds: 6,
    outputMode: 'plan_only',
    cameraPlan: expect.objectContaining({
      template: 'slow_push_in',
      productMotion: 'fixed',
      cameraMotion: 'path_playback',
    }),
  });
  const previewMotionPath = previewPayloads[0].motionPath as Array<{ x: number; y: number }>;
  expect(previewMotionPath.length).toBeGreaterThanOrEqual(2);
  expect(previewMotionPath[0].x).toBeCloseTo(0.14, 1);
  expect(previewMotionPath[0].y).toBeCloseTo(0.74, 1);
  expect(previewMotionPath[previewMotionPath.length - 1].x).toBeCloseTo(0.68, 1);
  expect(previewMotionPath[previewMotionPath.length - 1].y).toBeCloseTo(0.43, 1);
  expect(serverPayloads).toHaveLength(1);
  expect(serverPayloads[0]).toMatchObject({
    modelKey: 'cup_1660',
    materialSlot: 'front',
    cameraPreset: 'slow_push_in',
    cameraDistance: 'close',
    scenePreset: 'clean_studio',
    durationSeconds: 6,
    outputMode: 'render_video',
    cameraPlan: expect.objectContaining({
      template: 'slow_push_in',
      productMotion: 'fixed',
      cameraMotion: 'path_playback',
      playbackConfirmed: true,
    }),
  });
  expect(serverPayloads[0].motionPath).toEqual(previewMotionPath);
  expect(serverPayloads[0].textureSlots).toEqual([
    expect.objectContaining({ materialSlot: 'front', imageUrl: TEXTURE_IMAGE }),
  ]);
});
