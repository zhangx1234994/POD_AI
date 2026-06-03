# 03. 文档治理机制

最后更新：2026-06-02

## 1. 文档分层

客户端文档分 5 层：

| 层级 | 目录 | 用途 |
| --- | --- | --- |
| 当前机制 | `docs/client/operating/` | 客户端主开发工作机制 |
| 当前战略 | `docs/strategy/client-agent-pack-v0.6/` | v0.6 客户端产品边界和接口边界 |
| 能力治理 | `docs/strategy/ability-governance-operating-model-v0.6.md` | 能力优先的中台/客户端共识 |
| API 文档 | `docs/api/modules/business.md` 等 | 实际接口契约 |
| 历史资料 | `docs/client/plans/`、`docs/client/tech-review-*` | 历史客户端回溯，不直接执行 |

## 2. 文档状态标签

新增客户端文档必须在开头写明状态：

| 状态 | 含义 |
| --- | --- |
| `active` | 当前执行口径 |
| `draft` | 草案，未进入执行 |
| `handover` | 交接资料 |
| `archive` | 历史资料 |
| `template` | 模板 |

本目录文档默认状态为 `active`。

## 3. 必须同步的文档

发生以下变化时必须同步文档：

| 变化 | 必须更新 |
| --- | --- |
| 页面路由变化 | `03-ui-flow.md` 或本目录机制说明 |
| API 调用变化 | `04-api-contract.md`、`docs/api/modules/business.md` |
| 错误码变化 | `docs/standards/error-catalog.md` |
| 能力边界变化 | `ability-governance-operating-model-v0.6.md` |
| 缺少中台能力 | gap log |
| 验收标准变化 | `05-acceptance-checklist.md` 或本目录回归文档 |

## 4. 资料归档规则

后续客户端讨论材料、截图、走查报告按日期归档：

```text
docs/client/runs/YYYY-MM-DD-短标题/
  README.md
  delivery-report.md
  gap-log.md
  screenshots.md
```

如果只是临时截图，可放在 `output/playwright/client-preview-YYYYMMDD/`，但交付报告必须引用关键截图路径。

## 5. 不允许的文档习惯

- 不允许只在聊天里形成决策，不落文档。
- 不允许多个文档互相冲突但不标状态。
- 不允许旧 `ready for test` 文档继续冒充当前验收口径。
- 不允许客户端文档把项目管理写成第一产品视角。
- 不允许 API 缺口只写在代码注释里，不进入 gap log。

