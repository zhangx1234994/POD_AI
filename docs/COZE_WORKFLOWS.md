# Coze 工作流联调/测试文档（PODI）

本文面向开发/联调同学，目标是：用 Coze OpenAPI 把每个 workflow 跑一遍，确认入参/出参符合评测平台与业务侧预期。

## 1. 关键概念

- **workflow_id**：Coze 工作流 ID（本文与评测平台数据库均以此为主键之一）。
- **output**：我们约定的“关键输出字段名”（Coze 返回结构里的 `data.output`）。
  - 直接出图类：`output` 为图片 URL。
  - **ComfyUI 回调类**：`output` 为 task id，需要二次查询才能拿到 `images[]`。
- **debug_url**：Coze run 的调试链接（节点级日志/报错定位入口）。
 - **参数契约**：图片输入统一为 `url`（小写字符串），像素类字段必须为纯数字（禁用 `px`）。

## 2. 网络与鉴权（最容易踩坑）

PODI 的 Coze 插件接口默认只允许内网访问（否则返回 `401 {"detail":"INTERNAL_ONLY"}`），原因是这些接口通常由 Coze 容器/工作流节点内部调用。

当 Coze 与 PODI 不在同一内网时：

- 在 PODI 后端配置 `COZE_TRUSTED_IPS=<coze_source_ip,...>` 放行 Coze 源 IP
- 或者在请求头携带 `Authorization: Bearer $SERVICE_API_TOKEN`（若后端配置了该 token）

相关部署说明见 `docs/deploy-podi.md`。

## 3. 直接调用 Coze 工作流（OpenAPI）

准备环境变量：

```bash
export COZE_BASE_URL='https://api.coze.cn'   # 以实际为准
export COZE_API_TOKEN='***'
```

执行（最小示例）：

```bash
curl -sS -X POST "$COZE_BASE_URL/v1/workflow/run" \
  -H "Authorization: Bearer $COZE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"<WORKFLOW_ID>","parameters":{}}'
```

你需要重点关注：

- `data.output`：关键输出（图片 URL 或 task id）
- `debug_url`：失败/无输出时的排查入口

## 4. 回调类（ComfyUI）怎么拿到最终图片？

回调类工作流会返回 `task id`，常见格式：

- 旧格式：`<raw_id>`
- 新格式（推荐）：`t1.<provider>.<executorId>.<raw_id>`（可解析、便于路由/排障；旧调用方无需改造）

拿最终结果有两种方式：

1) 推荐：直接调用 PODI 的 task 查询接口（无需额外 Coze 工作流）  
`POST /api/coze/podi/tasks/get`，入参 `{"taskId":"..."}`，返回 `images[]`。

2) 备选：配置 `COZE_COMFYUI_CALLBACK_WORKFLOW_ID`  
由一个专门的 Coze 回调工作流将 task id 解析为 images（评测平台可用作兜底）。

## 5. 评测平台内置文档（强烈推荐）

评测平台已提供“文档”页，后端会把 **所有 status=active 的评测工作流** 自动生成 Markdown，包含：

- 分类、workflow_id、备注
- parameters schema（字段/必填/默认值/描述）
- output 类型（图片 URL / 回调 task id）

对应接口：`GET /api/evals/docs/workflows`（由 `podi-eval-web` 展示）。

## 6. 常见报错速查

- `INTERNAL_ONLY`：PODI 拦截了非内网请求；配置 `COZE_TRUSTED_IPS` 或使用 `SERVICE_API_TOKEN`。
- `Missing required parameters`：Coze 工作流参数必填（常见：`prompt/height/width`），需要在 workflow 或调用方补齐。
- `Missing required parameters: 'pdi'`：历史工作流把 `dpi` 写成了 `pdi`。当前规范统一为 `dpi`（不要再用 `pdi`）。
- `502 Bad Gateway`：上游服务（KIE/ComfyUI）网关错误/超时；建议降低并发、检查上游健康与超时配置。
- `ERR|Q1001|...` / `ERR|Q2001|...`：队列满错误，`taskId` 字段承载错误码（详见 `docs/standards/queue-and-error-standards.md`）。

## 7. ComfyUI 多输出节点说明（为什么会出现多张结果图？）

ComfyUI 的 `/history/{promptId}` 返回结构为：

- `outputs: { "<nodeId>": { images: [...] }, ... }`

即：只要某个节点产出了图片（哪怕是中间预览/调试用 SaveImage），都会出现在 history 里。

PODI 的处理策略：

- 默认：收集所有节点的 `images[]`（更通用）
- 对“只应展示最终结果”的工作流：在能力 metadata 里配置 `output_node_ids`，仅保留指定 nodeId 的输出  
  例如 `ComfyUI · 四方连续(sifang_lianxu)` 固定只取最终 `111` 节点输出，避免混入中间图。

## 8. 测试阶段清理“未完成任务”

测试阶段如果出现大量 `queued/running` 的脏任务，会影响归因与监控面板展示，可在确认无生产业务影响后清理：

```bash
python3 backend/scripts/purge_unfinished_ability_tasks.py --yes
```

说明：
- 仅删除 `ability_tasks` 中未完成状态（queued/running/pending/created）的记录，并清理关联日志。
- 不建议在生产高峰期执行；上线前请确认“当前处于测试期且可丢弃历史未完成任务”。

## 9. 示例：DPI 增分（图片输出）

- workflow_id：`7598589746561941504`
- 入参：
  - `url`（string，图片地址）
  - `dpi`（number，建议 300）
- 出参：
  - `output`（string，图片 URL）

最小示例：

```bash
curl -sS -X POST "$COZE_BASE_URL/v1/workflow/run" \
  -H "Authorization: Bearer $COZE_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id":"7598589746561941504",
    "parameters":{
      "url":"https://podi.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-kie-input/20260126/81d56182-1769389464.webp",
      "dpi":300
    }
  }'
```

## 问题与优化记录

- 详见 `docs/standards/issue-improvement-log.md`（滚动维护）。
