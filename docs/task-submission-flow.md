# 任务提交流程（统一能力 API）

> 版本：2026-01-15。本文结合最新的原子能力平台，梳理客户端/管理端如何发起能力调用、提交异步任务、监听状态以及和后台调度器联动的全过程。

## 1. 总体流程

```
表单收集参数 → 调用统一能力 API（同步或异步） → AbilityService 记录日志/成本 →
(可选) AbilityTask 队列 → Executor Adapter 执行（Baidu/Volc/ComfyUI/KIE…） →
媒资入库 & 回调通知 → 客户端刷新任务/日志面板
```

关键特性：
- **能力即 API**：所有原子能力都通过 `GET /api/abilities` 列表 + `POST /api/abilities/{id}/invoke` 访问，前后端共享一套 schema/defaults。
- **异步与并发**：批量调用或耗时较长时使用 `POST /api/ability-tasks`，后端线程池（`ABILITY_TASK_MAX_WORKERS`）+ executor `max_concurrency` 控制排队；ComfyUI 节点为串行 worker，队列状态通过 `/api/admin/comfyui/queue-status` 透出。
- **日志/成本**：每次调用都会写入 `ability_invocation_logs`（包含 `logId/duration/cost/pricing/OSS 输出/raw`），管理端 “调用记录” 与客户端历史面板共享同一数据源。
- **回调**：同步/异步均可附带 `callbackUrl/callbackHeaders`，后台执行完毕后会 POST 结果，让第三方系统无需轮询。

## 2. 前端关键组件

| 组件 | 职责 |
| --- | --- |
| `AbilityForm`（客户端/管理端） | 读取 `/api/abilities` + schema 动态渲染字段、上传控件、LoRA/模型下拉（ComfyUI 通过 `/api/admin/comfyui/models` 自动填充）。 |
| `AbilityTestPanel`（管理端） | 聚合“统一能力接口说明 + 实时测试 + 调用记录 + 队列状态”，让运营同学可在 UI 内直接验证参数。 |
| `DashboardTaskList`（客户端） | 展示能力调用历史（含同步/异步）、状态、耗时、OSS 链接，支持预览/下载/重跑。 |
| `AbilityLogsDrawer` | 基于 `/api/admin/abilities/{id}/logs` 展示最近 N 次调用，带 Raw Response、错误详情、成本。 |

## 3. 同步能力调用

当用户直接点击“立即生成/测试”按钮时：

1. **收集参数**：表单值 → `AbilityInvokePayload`（`inputs`、`imageUrl/imageBase64/images[]`、`executorId` 可选、`metadata.traceId`、`callbackUrl` 等）。
2. **API 调用**：`abilityService.invokeAbility(abilityId, payload)` → `POST /api/abilities/{abilityId}/invoke`。
3. **返回结果**：`AbilityInvokeResponse` 立即包含 `status/logId/durationMs/images/videos/texts/assets/raw`。
4. **UI 处理**：
   - 将 `images`/`assets` 写入画廊或任务列表，展示耗时/成本。
   - 将 `logId` 保存，方便在“调用记录”中定位同一条链路。
5. **回调（可选）**：若传了 `callbackUrl`，后端还会在执行完成后推送一次 `{status,result,error,logId,timestamp}`，供外部系统消费。

```typescript
const handleInvoke = async (ability: AbilitySummary, values: FormValues) => {
  setSubmitting(true);
  try {
    const payload = buildPayload(values); // inputs + image url/base64
    const res = await abilityService.invokeAbility(ability.id, payload);
    showResult(res); // 预览 & 提示耗时/cost
  } catch (err) {
    toast.error(parseError(err));
  } finally {
    setSubmitting(false);
  }
};
```

## 4. 异步 AbilityTask 队列

适用于批量上传、长流程或需要排队的能力（例如 ComfyUI 多图工作流）：

1. **创建任务**：`abilityService.createAbilityTask(abilityId, payload)` → `POST /api/ability-tasks`。响应 `AbilityTask`：`id/status=queued/createdAt`。
2. **轮询 / Push**：
   - 前端可定时调用 `GET /api/ability-tasks/{taskId}`，或统一通过 `useTaskPolling` 钩子批量刷新最近任务。
   - 管理端可直接查看 `AbilityTestPanel` 下方“最近调用记录”，实时显示 `queued/running/succeeded/failed`。
3. **完成**：
   - `status=succeeded` → `resultPayload` 携带完整 `AbilityInvokeResponse`（与同步模式一致）。
   - `status=failed` → `errorMessage`/`resultPayload.error` 描述原因（如 `ABILITY_EXECUTOR_NOT_CONFIGURED`、`COMFYUI_QUEUE_STATUS_ERROR` 等）。
4. **前端联动**：
   - 客户端 Dashboard 更新任务状态，弹出成功/失败通知。
   - 若配置了 `callbackUrl`，外部系统也会收到同样的结果。

```typescript
const enqueueTask = async () => {
  const task = await abilityService.createAbilityTask(abilityId, payload);
  addTask(task);
  startPolling(task.id); // 复用 useAbilityTaskPolling
};
```

## 5. 后端调度与日志

> 更详细的执行链路见 `docs/ai-integration-management.md`。此处聚焦与前端交互最紧密的部分。

1. **AbilityService**：
   - 校验能力是否激活、是否绑定 `executorId`；未配置会返回 `400 ABILITY_EXECUTOR_NOT_CONFIGURED`。
   - 将请求写入 `ability_invocation_logs`（status=pending），生成 `request_id/log_id`，并保留截断后的 request payload（Base64 自动省略）。
2. **Executor Adapter**：
   - 根据 `ability.provider/abilityType` 选择 Baidu/Volcengine/KIE/ComfyUI 等适配器。
   - 处理鉴权、payload 转换、结果解析（例如 ComfyUI 下载文件再上传 OSS）。
3. **任务/线程池**：
   - 同步调用直接等待执行；异步任务由线程池执行，遵循 `ABILITY_TASK_MAX_WORKERS`。
   - ComfyUI 节点串行 → 如果 `/queue/status` 显示 pending>0，前端会提示“排队中”。
4. **完成/失败**：
   - 成功：更新 `ability_invocation_logs.status=success`，填充 `duration_ms/cost_amount/assets/raw`；`AbilityTask` 标记 `succeeded` 并附 `resultPayload`。
   - 失败：填充 `error_code/error_detail`，并写入能力日志（管理端“调用记录”会显示红色状态）。
5. **通知**：
   - 如果传入 `callbackUrl`，后端会 POST `{status,result,error,logId}`。
   - 管理端 UI 会自动刷新调用记录，客户端 Dashboard 通过轮询/WS 更新任务状态。

## 6. 交互与事件

### 6.1 任务预览/详情

```typescript
const handleTaskClick = (entry: AbilityTask | AbilityInvokeResponse) => {
  if (entry.status !== 'succeeded') return;
  setPreview(entry.images?.[0]?.ossUrl);
  setMetadata(entry.metadata);
};
```

### 6.2 下载 / OSS 链接

- `AbilityInvokeResponse.images[].ossUrl` 由后台 `media_ingest_service` 统一上传并带签名域名，可直接下载。
- 若接口仅返回外链（`sourceUrl`），也会伴随 `assets[].storedUrl`，优先使用自有 OSS，避免外链过期。

### 6.3 调用日志/Raw Response

- 调用记录表格会显示 `logId/duration/cost/executor`，点击行展开 Raw Response（敏感字段已脱敏）。
- 若日志状态为失败，可直接复制 `requestPayload` 与 `error` 给研发排查。

### 6.4 ComfyUI 队列 & LoRA 切换

- 管理端“队列状态”卡片调用 `/api/admin/comfyui/queue-status?executorId=...`，可手动刷新。
- LoRA、UNet、CLIP、VAE 下拉来自 `/api/admin/comfyui/models`，默认选中 workflow 定义中的版本；切换后直接写入表单 `inputs`，调用时生效。

---

随着能力/工作流扩展，以上流程会持续更新。若新增能力或工作流，请同步更新：
1. `app/constants/abilities.py`（defaults/schema/metadata.pricing）。
2. `docs/comfyui/README.md` 或对应 provider 文档，描述关键节点与参数。
3. 本文档及 `docs/api/abilities.md`，确保提交流程与后台实现保持一致。
