# 2026-05-15 业务 API 可观测性版本走查

## 版本与发布

- 线上主机：114.55.0.56
- 发布版本：`3b941d08`
- 发布内容：
  - 业务运行列表默认轻量摘要返回。
  - 业务运行列表支持 `window_hours` 时间窗口。
  - 业务运行详情改为点击单条后按需加载完整链路。
  - 业务页增加自动刷新开关。
  - 刷新业务列表时不再被统计接口阻塞。

## 发布验证

- 源码门禁：通过，HEAD 与 `origin/main` 一致。
- 后端测试：`75 passed`。
- 管理端类型检查：通过。
- 测评端类型检查：通过。
- 管理端构建：通过。
- 测评端构建：通过。
- 114 远端预检：
  - `/health`：200
  - 管理端反代：401，符合未登录预期
  - 测评端 workflow catalog：200
  - Coze OpenAPI：200
- 114 smoke：
  - OpenAPI server 与环境 `PODI_INTERNAL_BASE_URL=http://172.17.0.1:8099` 一致。
  - ComfyUI 队列汇总：2 台，容量 20，空闲 20。
  - 花纹提取、图裂变、扩图路由预览均返回默认版本。

## 性能复核

业务运行列表线上接口对比：

| 接口 | 耗时 | 返回体 | 总数 |
| --- | ---: | ---: | ---: |
| `/api/admin/business/runs?window_hours=24&limit=20&detail=summary` | 293ms | 98KB | 131 |
| `/api/admin/business/runs?window_hours=24&limit=50&detail=summary` | 449ms | 247KB | 131 |
| `/api/admin/business/runs?window_hours=24&limit=200&detail=summary` | 1124ms | 649KB | 131 |
| `/api/admin/business/runs?window_hours=24&limit=20&detail=full` | 473ms | 560KB | 131 |

结论：

- 列表页不再默认拉详情级 payload。
- 200 条列表从约 10MB 降到约 0.65MB。
- 业务页显示 `已加载 20 / 131 条`，自动刷新按钮可见。

## 业务链路复核

近 24 小时业务运行：

- 总计：131
- 成功：129
- 失败：2
- 主要分布：
  - `fission / comfyui-vl-control-v2`：123
  - `fission / gpt-image2-vl-v2`：3
  - `fission_evaluate / v1`：2

上一轮内部参数未传入问题复核：

- 最近 `comfyui-vl-control-v2` 任务中，主执行步骤包含 `bili / width / height / profile` 等内部参数。
- 未发现因为内部参数缺失导致的批量失败。
- 当前失败样本属于上游执行或历史权限问题，不是本次参数传递回归。

## API 调用记录复核

近 24 小时业务 API Key 调用：

- 总计：3982
- 状态码：
  - 200：3966
  - 400：14
  - 403：2
- 接口分布：
  - `/api/business/runs/get`：3923
  - `/api/business/fission/runs`：56
  - `/api/business/fission-evaluate/runs`：3
- 错误码：
  - `BUSINESS_RUN_ID_REQUIRED`：14
  - `BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED`：1
  - `BUSINESS_USER_SCOPE_FORBIDDEN`：1

结论：

- 管理端已有“业务 API Key 与调用记录”表，能看到调用方、接口、状态码和耗时。
- 当前记录被轮询接口大量占据，缺少按任务聚合能力，业务方是否正确调用提交接口不够直观。

## 页面走查结论

已具备：

- API 开放页已经分开展示“中台自有业务 API / 原子能力 API / Coze 工具箱”。
- 已有业务 API Key 列表和最近调用记录。
- 已有中台自有 API 清单，包含业务 OpenAPI、图裂变、裂变评分、扩图、查询接口和路由预览接口。
- 业务页的“最近业务调用”已经默认自动刷新。

不足：

- 调用记录没有筛选、分页、导出和按 runId 聚合。
- 调用记录和业务运行记录是两个页面视角，缺少一键跳转和关联排障。
- API 调用记录没有区分“提交任务”和“轮询任务”，轮询会淹没真正的业务提交。
- 返回枚举值仍未形成独立总表，业务方无法一眼确认所有状态、错误码、计费状态、回调状态的取值。
- OpenAPI 已给出 `status/taskStatus`、`variation_strength/quality/size` 枚举，但 `profile/mode/pattern_risk_type/selectedStatus/selectedBy/callbackStatus/billingStatus/errorCode` 等还没有统一枚举表。

## 固化待办

已同步标准文档：`docs/standards/business-api-enums.md`。后续业务方交付材料、OpenAPI 和管理端 API 开放页都应引用同一份枚举口径。

### P0：接口调用中心

目标：管理端需要一个真正的“接口调用清单”，用于判断业务方是否按约定调用。

必须包含：

- 时间窗口筛选。
- API Key / 调用方筛选。
- 接口路径筛选。
- 状态码 / 错误码筛选。
- runId / requestId / traceId 搜索。
- 提交接口、轮询接口、回调接口分组。
- 按 runId 聚合轮询次数，避免轮询记录淹没提交记录。
- 从调用记录跳转到业务运行详情。
- 支持导出。

### P0：对外接口枚举总表

目标：业务方文档和 OpenAPI 都能清楚说明每个枚举值含义。

必须覆盖：

- 任务状态：`queued/running/succeeded/failed`
- 轮询建议：`retryAfterSeconds`
- 计费状态：`billable/unpriced/no_charge/billing_pending`
- 回调状态：`pending/succeeded/failed/skipped`
- 路由命中：`explicit/default/rollout_allowlist/rollout_percent`
- 图裂变参数：`variation_strength/quality/size/profile`
- 常见错误码：缺参、Key 无权限、业务范围不允许、任务不存在、任务超时、执行器失败、上游限流

### P1：业务运行列表与 API 调用列表合并视角

目标：业务页从“任务列表”升级为“业务调用全链路”。

建议展示：

- 一次业务提交。
- 该提交对应的轮询次数。
- 中台任务状态。
- 底层能力步骤。
- OSS 回填。
- 回调状态。
- 计费状态。
- 错误处理建议。

### P1：OpenAPI 契约自动检查

目标：发版前自动检查对外文档是否缺枚举、缺错误示例、缺成功示例。

建议加入发版门禁：

- 所有对外接口必须有请求示例。
- 所有对外接口必须有成功响应示例。
- 所有对外接口必须有错误响应示例。
- 所有 `status/type/mode/profile/quality/size` 字段必须明确枚举或说明“自由文本”。
