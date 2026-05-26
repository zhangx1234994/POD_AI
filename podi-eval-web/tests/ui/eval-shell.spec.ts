import { expect, test } from "@playwright/test";

const NOW = "2026-02-25T10:00:00Z";
const WORKFLOWS = [
  {
    id: "wf-1",
    category: "通用类",
    name: "Seedream 4.5 文生图",
    version: "v1",
    workflow_id: "volc.seedream.4_5",
    status: "active",
    notes: "文生图基础能力，支持 LoRA 批测。",
    created_at: NOW,
    updated_at: NOW,
    parameters_schema: {
      fields: [
        { name: "url", label: "图片 URL", type: "text", required: false },
        { name: "prompt", label: "提示词 Prompt", type: "textarea", required: true, defaultValue: "高清面料纹理" },
        {
          name: "lora",
          label: "LoRA",
          type: "select",
          required: false,
          options: [
            { label: "Floral V1", value: "floral_v1" },
            { label: "Texture V2", value: "texture_v2" },
          ],
          defaultValue: "floral_v1",
        },
        {
          name: "resolution",
          label: "分辨率 Resolution",
          type: "select",
          options: [
            { label: "1K", value: "1K" },
            { label: "2K", value: "2K" },
          ],
          defaultValue: "1K",
        },
      ],
    },
    output_schema: { fields: [{ name: "image_url", label: "结果图", type: "image" }] },
  },
  {
    id: "wf-2",
    category: "花纹提取类",
    name: "印花提取",
    version: "v2",
    workflow_id: "comfyui.yinhua_tiqu",
    status: "active",
    notes: "提取花纹并保持边界过渡平滑。",
    created_at: NOW,
    updated_at: NOW,
    parameters_schema: {
      fields: [
        { name: "url", label: "图片 URL", type: "text", required: true },
        { name: "prompt", label: "提示词", type: "textarea", required: false, defaultValue: "保持原始纹理" },
      ],
    },
    output_schema: { fields: [{ name: "storedUrl", label: "沉淀地址", type: "text" }] },
  },
];

const RUNS = [
  {
    id: "run-1",
    workflow_version_id: "wf-1",
    status: "succeeded",
    duration_ms: 3200,
    created_by: "eval-ui",
    created_at: NOW,
    updated_at: NOW,
    input_oss_urls_json: ["https://static.podi.test/source-1.jpg"],
    result_image_urls_json: ["https://static.podi.test/result-1.png"],
    parameters_json: { prompt: "高清面料纹理", lora: "floral_v1", resolution: "1K" },
    latest_annotation: {
      rating: 4,
      comment: "细节稳定，可继续放量",
      created_at: NOW,
      created_by: "eval-ui",
    },
  },
  {
    id: "run-2",
    workflow_version_id: "wf-1",
    status: "running",
    duration_ms: 980,
    created_by: "eval-ui",
    created_at: NOW,
    updated_at: NOW,
    input_oss_urls_json: ["https://static.podi.test/source-2.jpg"],
    result_image_urls_json: [],
    parameters_json: { prompt: "清晰棉麻肌理", lora: "texture_v2", resolution: "1K" },
    latest_annotation: null,
  },
];

const QUALITY_SAMPLES = [
  {
    id: "bizsample-text-1",
    businessKey: "text_fission",
    sampleKey: "poster-text-a",
    label: "文字海报样例",
    description: "文字清晰度回归",
    imageUrl: "https://static.podi.test/source-1.jpg",
    prompt: "保持文字清晰，强化商业海报质感",
    generatedImageUrl: null,
    inputTags: ["文字海报", "高清"],
    defaultParams: { resolution: "1K" },
    status: "active",
    sortOrder: 1,
    createdByUserId: null,
    createdByUsername: "admin",
    createdAt: NOW,
    updatedAt: NOW,
  },
  {
    id: "bizsample-pattern-1",
    businessKey: "pattern_extract",
    sampleKey: "dense-pattern-a",
    label: "满版花纹样例",
    description: "边界与细节回归",
    imageUrl: "https://static.podi.test/source-2.jpg",
    prompt: "保持原始纹理和边界过渡",
    generatedImageUrl: null,
    inputTags: ["满版图案", "细节"],
    defaultParams: {},
    status: "active",
    sortOrder: 2,
    createdByUserId: null,
    createdByUsername: "admin",
    createdAt: NOW,
    updatedAt: NOW,
  },
];

const DOC_WORKFLOWS = [
  {
    category: "通用类",
    name: "Seedream 4.5 文生图",
    workflow_id: "volc.seedream.4_5",
    notes: "用于图案生成与风格探索",
    output_kind: "image",
    parameters: [
      { name: "url", label: "图片 URL", type: "text", required: false, description: "可选输入图链接" },
      { name: "prompt", label: "提示词 Prompt", type: "textarea", required: true, description: "描述目标图像" },
    ],
    outputs: [{ name: "result_image_urls_json", label: "输出图列表", type: "array", description: "结果图 URL 列表" }],
    errors: ["ERR|Q1001|并发限制", "ERR|T1002|任务超时"],
    request: {
      method: "POST",
      path: "/api/evals/runs",
      body: {
        workflow_version_id: "wf-1",
        input_oss_urls_json: ["https://static.podi.test/source-1.jpg"],
        parameters_json: { prompt: "高清面料纹理" },
      },
    },
  },
];

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(body),
});

test.describe("Eval shell visual regression", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.removeItem("podi_eval_admin_token");
    });

    await page.route("**/api/**", async (route) => {
      const reqUrl = new URL(route.request().url());
      const path = reqUrl.pathname;

      if (path === "/api/evals/me") {
        await route.fulfill(mockJson({ raterId: "eval-ui-reviewer" }));
        return;
      }
      if (path === "/api/evals/workflow-versions") {
        await route.fulfill(mockJson(WORKFLOWS));
        return;
      }
      if (path === "/api/evals/business/quality-samples") {
        await route.fulfill(mockJson({ total: QUALITY_SAMPLES.length, items: QUALITY_SAMPLES }));
        return;
      }
      if (path === "/api/evals/metrics/workflows") {
        await route.fulfill(
          mockJson({
            metrics: {
              "wf-1": { ratingCount: 26, avgRating: 4.5 },
              "wf-2": { ratingCount: 9, avgRating: 4.2 },
            },
          }),
        );
        return;
      }
      if (path === "/api/evals/runs/with-latest-annotation") {
        const workflowId = reqUrl.searchParams.get("workflow_version_id");
        const filtered = workflowId ? RUNS.filter((item) => item.workflow_version_id === workflowId) : RUNS;
        await route.fulfill(mockJson({ total: filtered.length, items: filtered }));
        return;
      }
      if (path === "/api/evals/docs/workflows") {
        await route.fulfill(
          mockJson({
            markdown: "# Eval API\\n\\n- 统一能力评测接口文档",
            generatedAt: NOW,
            workflows: DOC_WORKFLOWS,
          }),
        );
        return;
      }
      if (path === "/api/evals/batches") {
        await route.fulfill(
          mockJson({
            total: 1,
            items: [
              {
                id: "batch-1",
                workflow_version_id: "wf-1",
                status: "running",
                planned_image_count: 2,
                repeat_count: 2,
                planned_run_count: 4,
                submitted_count: 4,
                running_count: 1,
                succeeded_count: 2,
                failed_count: 1,
                canceled_count: 0,
                created_at: NOW,
                updated_at: NOW,
              },
            ],
          }),
        );
        return;
      }
      if (path === "/api/evals/batches/batch-1/items") {
        await route.fulfill(
          mockJson({
            total: 1,
            items: [
              {
                id: "batch-item-1",
                batch_session_id: "batch-1",
                asset_id: "asset-1",
                asset_source_key: "batch-1::source-1",
                asset_file_name: "sample-1.jpg",
                asset_oss_url: "https://static.podi.test/source-1.jpg",
                repeat_index: 1,
                eval_run_id: "run-batch-1",
                status: "succeeded",
                run_status: "succeeded",
                run_prompt: "高清面料纹理",
                run_output_urls_json: ["https://static.podi.test/result-batch-1.png"],
                run_error_message: null,
                error_code: null,
                error_message: null,
              },
            ],
          }),
        );
        return;
      }
      if (path === "/api/evals/batches/batch-1/assets") {
        await route.fulfill(
          mockJson({
            total: 1,
            items: [
              {
                id: "asset-1",
                source_key: "batch-1::source-1",
                file_name: "sample-1.jpg",
                oss_url: "https://static.podi.test/source-1.jpg",
                upload_status: "uploaded",
              },
            ],
          }),
        );
        return;
      }
      if (path === "/api/evals/admin/workflow-versions") {
        await route.fulfill(mockJson(WORKFLOWS));
        return;
      }

      await route.fulfill(mockJson({}));
    });
  });

  test("home view baseline", async ({ page }) => {
    await page.goto("/?view=home&category=%E5%B9%B3%E5%8F%B0%E5%B7%A5%E5%85%B7");
    await expect(page.locator("body")).toContainText("业务方验收入口");
    await expect(page.locator("body")).toContainText("固定样例");
    await expect(page).toHaveScreenshot("eval-home-default.png", { fullPage: true });
  });

  test("tool view baseline", async ({ page }) => {
    await page.goto("/?view=tool&category=%E8%8A%B1%E7%BA%B9%E6%8F%90%E5%8F%96&tool=wf-2");
    await expect(page.locator("body")).toContainText("一次测试");
    await expect(page.locator("body")).toContainText("满版花纹样例");
    await expect(page).toHaveScreenshot("eval-tool-default.png", { fullPage: true });
  });

  test("tasks view baseline", async ({ page }) => {
    await page.goto("/?view=tasks&category=%E9%80%9A%E7%94%A8%E7%B1%BB");
    await expect(page.locator("body")).toContainText("任务追踪结论");
    await expect(page).toHaveScreenshot("eval-tasks-default.png", { fullPage: true });
  });

  test("lora batch view baseline", async ({ page }) => {
    await page.goto("/?view=loraBatch&category=%E9%80%9A%E7%94%A8%E7%B1%BB");
    await expect(page.locator("body")).toContainText("LoRA 批量回归测试");
    await expect(page).toHaveScreenshot("eval-lora-batch-default.png", { fullPage: true });
  });

  test("docs view baseline", async ({ page }) => {
    await page.goto("/?view=docs&category=%E9%80%9A%E7%94%A8%E7%B1%BB");
    await expect(page.locator("body")).toContainText("开发文档");
    await expect(page).toHaveScreenshot("eval-docs-default.png", { fullPage: true });
  });

  test("admin view baseline", async ({ page }) => {
    await page.goto("/?view=admin&category=%E9%80%9A%E7%94%A8%E7%B1%BB");
    await expect(page.locator("body")).toContainText("功能维护");
    await expect(page).toHaveScreenshot("eval-admin-default.png", { fullPage: true });
  });
});
