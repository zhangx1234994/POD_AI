# PODI 中台 & 评测平台 TODO（封版后路线图）

目标：把“能跑通”提升到“可运营、可排障、可扩容”的产品级状态；按优先级（P0→P2）推进。

## P0 稳定性 / 运维必做

- Alembic 迁移规范
  - 多 head 情况必须使用 `python3 -m alembic upgrade heads`
  - `alembic_version.version_num` 建议 `VARCHAR(64)+`，避免 revision 被截断导致“半迁移”
- 部署口径统一（开发机=线上）
  - 禁止线上跑 `npm run dev`（避免 websocket/HMR、资源错配、样式乱）
  - 统一使用 prod-like 脚本：`scripts/deploy_prodlike_nodocker.sh`（无 Docker）或 `scripts/deploy_prodlike.sh`（有 Docker）
- Coze 插件网络/鉴权
  - 明确 `INTERNAL_ONLY` 的触发条件
  - 完整补齐 `COZE_TRUSTED_IPS` / `SERVICE_API_TOKEN` 的部署说明与排查手册
- 评测工作流口径固定
  - 侧边栏分类固定（花纹提取/图延伸/四方连续/图裂变/通用）
  - seed 对已废弃 workflow 只做 `inactive` 标记，不强改用户自建条目
- 失败可解释
  - UI：表单必填校验 + 统一错误提示（避免“报错没提示”）
  - Backend：关键错误码映射（KIE/ComfyUI/Coze）→ 稳定的 error_code + 可读 message

## P1 可观测性 / 数据闭环

- 能力调用记录（AbilityInvocationLog）
  - 导出：CSV/JSON（按时间窗口/能力/节点/状态过滤）
  - 聚合指标：近 24h success rate / p50 / p95 / 次数（按 provider/capability_key，可选按 executor）
  - 查询能力：按 `trace_id / workflow_run_id / task_id` 快速定位一次调用链
- 评测平台（EvalRun）
  - 输出类型兼容：图片 & JSON（如打标签 output 为 JSON）
  - 一键清理评测记录：只清 `eval_run/eval_annotation`，便于重新回归
  - 关键字段透出：run 的 `debug_url / execute_id / task_id / duration_ms`

## P2 并发与限流（能力层优先）

- 能力层并发（PODI 内部）
  - 单节点：按 `Executor.max_concurrency` 做并发闸门（已做）；管理端修改并发可立即生效（无需重启）
  - 多实例：需要全局并发控制（Redis/DB 分布式信号量），避免“每个进程各放 1 个”导致超卖
- QPS 控制（对外）
  - 对 Coze 工具接口/能力接口加可配置限流（例如 4~5 QPS），返回明确的 429 + retry-after
- 重试策略
  - 502/timeout/connection reset：指数退避 + 限次数重试
  - 上游配额/鉴权失败：不重试，提示运维处理

## P3 体验与配置效率

- 评测工作流配置能力
  - 后台支持“输入 workflow_id 自动生成基础表单”+ 手动补齐 schema（减少配置成本）
  - 支持给每个功能维护“介绍/示例图/推荐参数”
- 资产沉淀一致性
  - 输入 URL 是否落盘 OSS：明确策略（建议：外链输入在需要长期可用时落盘；输出一律落盘）
- 成本/计费可视化
  - ability metadata pricing + 调用日志 cost 字段 → 汇总报表（按日/按能力/按节点）
