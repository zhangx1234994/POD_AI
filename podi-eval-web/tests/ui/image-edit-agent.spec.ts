import { expect, test } from '@playwright/test';

const NOW = '2026-06-05T10:00:00Z';
const SOURCE_IMAGE = 'https://static.podi.test/source-pattern.png';
const FIRST_OUTPUT = 'https://static.podi.test/generated-first.png';

const CHAT_WORKFLOW = {
  id: 'wf-image-edit-chat',
  category: '图编辑',
  name: 'AI 图片助手',
  version: 'image-edit-chat-v1',
  workflow_id: 'business_image_edit_chat_gpt_image2_assistant_v1',
  status: 'active',
  notes: '图片 Agent 入口。',
  metadata: { eval_execution: { mode: 'business_agent', business_key: 'image_edit_chat' } },
  created_at: NOW,
  updated_at: NOW,
  parameters_schema: {
    fields: [
      { name: 'imageUrl', label: '图片 URL', type: 'text', required: false },
      { name: 'message', label: '图片处理目标', type: 'textarea', required: true },
      { name: 'quality', label: '质量', type: 'select', defaultValue: 'auto', options: [{ label: '自动', value: 'auto' }] },
      { name: 'size', label: '尺寸', type: 'select', defaultValue: 'auto', options: [{ label: '自动', value: 'auto' }] },
      { name: 'output_format', label: '格式', type: 'select', defaultValue: 'png', options: [{ label: 'PNG', value: 'png' }] },
    ],
  },
  output_schema: { fields: [{ name: 'imageUrls', label: '结果图', type: 'image' }] },
};

const DIRECT_WORKFLOW = {
  id: 'wf-image-edit-direct',
  category: '图编辑',
  name: '直接图编辑',
  version: 'gpt-image2-editor-v1',
  workflow_id: 'business_image_edit_gpt_image2_editor_v1',
  status: 'active',
  notes: '直接提交图编辑任务。',
  metadata: { eval_execution: { mode: 'business_run', business_key: 'image_edit' } },
  created_at: NOW,
  updated_at: NOW,
  parameters_schema: { fields: [] },
  output_schema: { fields: [] },
};

const mockJson = (body: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify(body),
});

const tinyPng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/azX9qkAAAAASUVORK5CYII=',
  'base64',
);

test('image edit agent keeps run results in the chat stream and continues from previous output', async ({ page }) => {
  const messagePayloads: Array<Record<string, unknown>> = [];
  let latestSession = {
    id: 'sess-agent-1',
    agentKey: 'agent.image_edit_assistant',
    status: 'awaiting_confirmation',
    title: '把这张图改得更高级一些',
    imageUrl: SOURCE_IMAGE,
    latestPlanId: 'plan-1',
    latestRunId: null,
    traceId: 'trace-agent-1',
    messages: [
      {
        id: 'msg-user-1',
        sessionId: 'sess-agent-1',
        role: 'user',
        content: '把这张图改得更高级一些，适合服装面料。',
        attachments: [{ url: SOURCE_IMAGE }],
        planId: 'plan-1',
      },
      {
        id: 'msg-assistant-1',
        sessionId: 'sess-agent-1',
        role: 'assistant',
        content: '已整理为局部修改任务。',
        planId: 'plan-1',
      },
    ],
    toolCalls: [],
    latestToolCall: null,
    latestPlan: null,
  };

  const plan = (id: string, baseRole: string, imageUrl: string, parentRunId?: string) => ({
    id,
    sessionId: 'sess-agent-1',
    agentKey: 'agent.image_edit_assistant',
    status: 'awaiting_confirmation',
    intent: 'image_edit',
    title: baseRole === 'previous_result' ? '继续优化上一轮结果' : '局部/整体轻改图',
    summary: '已整理为受控图编辑任务。',
    editPlan: [{ step: '保护原图主体', reason: '保持主体结构和构图稳定。' }],
    toolName: 'business.image_edit',
    toolPayload: {
      imageUrl,
      instruction: '把这张图改得更高级一些，适合服装面料。',
      editSkill: 'local_modify',
      quality: 'auto',
      size: 'auto',
      output_format: 'png',
    },
    estimatedCostLevel: 'low',
    riskLevel: 'low',
    routeEvidence: {
      targetAbility: 'business.image_edit',
      confidence: 0.84,
      baseImageRole: baseRole,
      parentRunId: parentRunId || null,
      routeReason: baseRole === 'previous_result' ? '用户继续同一会话，因此默认基于上一轮成功输出继续修改。' : '本轮基于原始主图执行。',
    },
  });

  await page.route('https://static.podi.test/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/png', body: tinyPng });
  });

  await page.route('**/api/**', async (route) => {
    const reqUrl = new URL(route.request().url());
    const path = reqUrl.pathname;

    if (path === '/api/evals/me') {
      await route.fulfill(mockJson({ raterId: 'eval-ui-reviewer' }));
      return;
    }
    if (path === '/api/evals/workflow-versions') {
      await route.fulfill(mockJson([CHAT_WORKFLOW, DIRECT_WORKFLOW]));
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
      await route.fulfill(mockJson({ markdown: '', generatedAt: NOW, workflows: [] }));
      return;
    }
    if (path === '/api/business/image-edit-chat/sessions' && route.request().method() === 'POST') {
      latestSession.latestPlan = plan('plan-1', 'source_image', SOURCE_IMAGE);
      await route.fulfill(mockJson({ session: latestSession, plan: latestSession.latestPlan }));
      return;
    }
    if (path === '/api/business/image-edit-chat/sessions/sess-agent-1/messages') {
      const payload = route.request().postDataJSON() as Record<string, unknown>;
      messagePayloads.push(payload);
      latestSession = {
        ...latestSession,
        status: 'awaiting_confirmation',
        latestPlanId: 'plan-2',
        latestPlan: plan('plan-2', 'previous_result', String(payload.imageUrl || FIRST_OUTPUT), 'run-first'),
        messages: [
          ...latestSession.messages,
          {
            id: 'msg-user-2',
            sessionId: 'sess-agent-1',
            role: 'user',
            content: String(payload.message || ''),
            attachments: [{ url: payload.imageUrl }],
            planId: 'plan-2',
          },
          {
            id: 'msg-assistant-2',
            sessionId: 'sess-agent-1',
            role: 'assistant',
            content: '已整理为继续修改上一轮结果。',
            planId: 'plan-2',
          },
        ],
      };
      await route.fulfill(mockJson({ session: latestSession, plan: latestSession.latestPlan }));
      return;
    }
    if (path === '/api/business/image-edit-chat/sessions/sess-agent-1/confirm') {
      latestSession = {
        ...latestSession,
        status: 'running',
        latestRunId: 'run-first',
        messages: [
          ...latestSession.messages,
          {
            id: 'msg-tool-1',
            sessionId: 'sess-agent-1',
            role: 'tool',
            content: '已提交图编辑任务，runId=run-first',
            planId: 'plan-1',
            runId: 'run-first',
          },
        ],
        toolCalls: [{ id: 'tool-call-1', sessionId: 'sess-agent-1', planId: 'plan-1', toolName: 'business.image_edit', runId: 'run-first', status: 'submitted' }],
        latestToolCall: { id: 'tool-call-1', sessionId: 'sess-agent-1', planId: 'plan-1', toolName: 'business.image_edit', runId: 'run-first', status: 'submitted' },
      };
      await route.fulfill(mockJson({ session: latestSession, plan: plan('plan-1', 'source_image', SOURCE_IMAGE), toolCall: latestSession.latestToolCall, run: { runId: 'run-first', status: 'queued' } }));
      return;
    }
    if (path === '/api/business/image-edit-chat/sessions/sess-agent-1') {
      await route.fulfill(mockJson({ session: latestSession }));
      return;
    }
    if (path === '/api/business/runs/get') {
      await route.fulfill(mockJson({ runId: 'run-first', id: 'run-first', status: 'succeeded', imageUrls: [FIRST_OUTPUT] }));
      return;
    }

    await route.fulfill(mockJson({}));
  });

  await page.goto('/?view=tool&category=%E5%9B%BE%E7%BC%96%E8%BE%91&tool=wf-image-edit-chat');

  const agent = page.locator('.podi-image-edit-agent');
  await expect(agent).toContainText('AI 图片助手');
  await page.locator('.podi-image-edit-agent__source summary').click();
  await page.locator('.podi-image-edit-agent__source input').fill(SOURCE_IMAGE);
  await agent.locator('textarea').fill('把这张图改得更高级一些，适合服装面料。');
  await agent.getByRole('button', { name: '发送' }).click();

  await expect(agent.getByRole('button', { name: '执行这版' })).toHaveCount(0);
  await expect(agent.locator('.podi-image-edit-agent__message.is-tool')).toContainText('已完成');
  await expect(agent.locator('.podi-image-edit-agent__message.is-tool img')).toHaveCount(1);
  await expect(agent.locator('.podi-image-edit-agent__chat-head')).toContainText('当前基准图：上一轮结果');

  await agent.locator('textarea').fill('继续基于这张结果，把颜色压低一点。');
  await agent.getByRole('button', { name: '发送' }).click();

  await expect.poll(() => messagePayloads.length).toBe(1);
  expect(messagePayloads.at(-1)?.context).toMatchObject({ baseImageRole: 'previous_result', previousRunId: 'run-first' });

  await agent.getByRole('button', { name: '新建任务' }).click();
  await expect(agent.locator('.podi-image-edit-agent__chat-head')).toContainText('新图片任务');
  await expect(agent.locator('.podi-image-edit-agent__thread-list')).toContainText('已完成');
});
