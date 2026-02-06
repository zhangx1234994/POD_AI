# Coze 工作流测试用例（评测平台/中台）

> 目标：在上线前确认「入参/出参一致性、回调稳定性、队列上限、OSS落盘」等关键路径可交付。

## 1. 冒烟测试（功能可用）
- 工具：`scripts/coze_workflow_smoke.py`
- 目的：逐个工作流验证是否可跑通、是否返回预期字段（`output/prompt/ip`），并拉取回调任务状态。
- 步骤：
  1) 启动本地后端与评测前端。
  2) 执行 `python3 scripts/coze_workflow_smoke.py --poll 60 --image <path>`（或传 `--image-url`）。
  3) 查看 `reports/coze_workflow_smoke_*.md`，确认“参数一致=是”。
- 期望：
  - callback 类工作流返回 `output=task id`；
  - ComfyUI 类工作流额外返回 `ip`（执行节点）。

## 1.1 回归脚本（批量/历史对比）
- 工具：`scripts/eval_workflow_regression.py`
- 目的：批量回归 Coze 工作流，支持在回调接口不可达时走 Coze 回调 workflow 兜底解析。
- 示例：
  - `python3 scripts/eval_workflow_regression.py --poll 600 --callback-workflow-id <workflow_id>`
- 说明：
  - 当 `/api/coze/podi/tasks/get` 不可达（如 401）时，会触发回调 workflow 轮询。

## 2. 入参/出参一致性（防“对接参数不一致”）
- 覆盖点：
  - 关键字段命名（`url/Url`、`width/height`、`bili/similarity`）。
  - 必填项缺失时，Coze 返回可识别错误。
- 期望：
  - 文档与 Coze workflow 参数一致；
  - 若存在历史 workflow 参数不统一，应在文档备注中明确提示。

## 3. 回调链路
- 覆盖点：
  - `output` 返回 task id 后，`/api/coze/podi/tasks/get` 能正常拉取 `images`；
  - 回调失败时 error 信息可追踪。
- 期望：
  - 业务能在 1~3 次轮询内获取图片；
  - 失败时 error 有明确提示（如 `COMFYUI_STATUS_error`）。

## 4. OSS 链路（上传+回写）
- 覆盖点：
  - 上传后可访问，且落盘 URL 为 OSS 域名；
  - 输入图片为 URL 的工作流能正常处理并产出 OSS URL。
- 期望：
  - `storedUrl` / `imageUrls` 均可访问。

## 5. 队列上限/并发压力
- 覆盖点：
  - ComfyUI 队列上限（10）；
  - 商业模型队列上限（10）。
- 期望：
  - 超出上限时，工作流返回明确错误信息（通过 `output` 字段传递）。

## 6. 并发测试（压力）
- 建议方案：
  - 以单工作流 30 并发，跑 1~3 分钟；
  - 观察任务成功率、平均耗时、队列峰值、错误占比。
- 工具（建议实现）：
  - 自定义脚本/并发 runner（可扩展到 KIE/Volcengine/ComfyUI）。

## 7. UI 回归（评测平台）
- 覆盖点：
  - 文档展示：分类、入参/出参、枚举值清晰；
  - 输出区显示 `ip`、`prompt`；
  - 失败提示明确（401/502/HTML 错误页）。

---
维护要求：每次上线前必须完成 1~3；上线后再完成 4~7。
