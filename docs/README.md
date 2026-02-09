# POD AI Studio 文档索引与目录说明

本文件是文档总索引与目录用途说明，新增/更新文档请先补充这里，保证能快速定位。

## 目录说明

| 目录 | 用途 | 主要内容 |
| --- | --- | --- |
| `docs/` | 全局文档入口 | 架构/规划/流程/运维/规范等跨模块文档 |
| `docs/admin/` | 管理端说明 | 管理端页面与功能说明 |
| `docs/api/` | API 规范 | API 详细说明与示例 |
| `docs/api/INDEX.md` | 接口总索引 | 全量接口按模块分类汇总 |
| `docs/comfyui/` | ComfyUI 维护 | 工作流、节点映射、运维说明 |
| `docs/coze/` | Coze 集成 | 插件/工具箱/工作流规范 |
| `docs/eval/` | 评测平台 | 评测站点功能说明 |
| `docs/retrospectives/` | 复盘记录 | 复盘纪要与行动项 |
| `docs/standards/` | 工程规范 | 错误契约、SOP、架构准则 |
| `docs/testing/` | 测试计划 | 测试计划与用例规范 |
| `docs/wip/` | 草案/临时稿 | 未定稿内容（发布前需转正） |

## 文档树（两层）

```
docs/
├── ABILITY_EVALUATION.md
├── BUSINESS_MODEL.md
├── COMPONENT_INTERACTIONS.md
├── COZE_INTEGRATION_GUIDE.md
├── COZE_WORKFLOWS.md
├── CREDENTIALS.md
├── DEPLOYMENT.md
├── README.md
├── TODO_PLATFORM.md
├── TROUBLESHOOTING.md
├── UI_STANDARD.md
├── admin
│   └── integration-dashboard.md
├── admin-system-plan.md
├── ai-capability-roadmap.md
├── ai-integration-management.md
├── api
│   ├── INDEX.md
│   ├── modules
│   │   ├── overview.md
│   │   ├── auth.md
│   │   ├── media.md
│   │   ├── abilities.md
│   │   ├── coze.md
│   │   ├── comfyui-admin.md
│   │   ├── agent.md
│   │   ├── eval.md
│   │   ├── admin-core.md
│   │   ├── tasks.md
│   │   └── notify-wallet.md
│   └── abilities.md
├── api.md
├── architecture.md
├── async-task-monitoring.md
├── auth-plan.md
├── backlog.md
├── comfyui
│   ├── agent-management.md
│   └── README.md
├── comfyui-routing-business.md
├── comfyui-routing-technical.md
├── coze
│   ├── toolbox-contracts.md
│   └── workflows.md
├── coze-integration.md
├── coze-plugin-podi.md
├── deploy-checklist.md
├── deploy-podi.md
├── development-guide.md
├── error-codes.md
├── eval
│   ├── ai-editor.md
│   └── eval-platform.md
├── release-preflight.md
├── retrospectives
│   └── 2026-02-03.md
├── smart-polling-mechanism.md
├── standards
│   ├── abstraction-and-decoupling.md
│   ├── error-catalog.md
│   ├── error-contract.md
│   ├── issue-improvement-log.md
│   ├── queue-and-error-standards.md
│   └── self-check-sop.md
├── task-submission-flow.md
├── testing
│   └── COZE_WORKFLOW_TEST_PLAN.md
├── wip
│   └── admin-ia-draft.md
└── workflow-platform-requirements.md
```

## 索引（按主题）

### 入门与运维
- `docs/development-guide.md`：开发指南
- `docs/deploy-podi.md`：PODI 后端/管理端部署流程
- `docs/DEPLOYMENT.md`：部署规范与结构
- `docs/deploy-checklist.md`：部署检查清单
- `docs/release-preflight.md`：发布前检查
- `docs/TROUBLESHOOTING.md`：常见问题排查
- `docs/CREDENTIALS.md`：凭证与密钥管理说明

### 架构与业务
- `docs/BUSINESS_MODEL.md`：业务建模文档
- `docs/architecture.md`：技术架构与边界总览
- `docs/COMPONENT_INTERACTIONS.md`：模块交互与依赖关系
- `docs/workflow-platform-requirements.md`：工作流平台需求
- `docs/ai-capability-roadmap.md`：能力演进路线图（规划）
- `docs/ai-integration-management.md`：能力接入与管理策略
- `docs/admin-system-plan.md`：管理端系统规划
- `docs/auth-plan.md`：鉴权/权限规划
- `docs/backlog.md`：需求/问题清单
- `docs/TODO_PLATFORM.md`：平台待办与阶段目标

### API 与规范
- `docs/api.md`：API 总览
- `docs/api/INDEX.md`：接口总索引（按模块分类）
- `docs/api/abilities.md`：统一能力 API 说明
- `docs/error-codes.md`：错误码文档（历史草案，现行见 `docs/standards/error-catalog.md`）
- `docs/standards/error-catalog.md`：错误码总表
- `docs/standards/error-contract.md`：错误契约规范
- `docs/standards/queue-and-error-standards.md`：队列与错误处理规范
- `docs/standards/abstraction-and-decoupling.md`：抽象与解耦准则
- `docs/standards/self-check-sop.md`：自检流程规范
- `docs/standards/issue-improvement-log.md`：问题与优化记录

### 任务流转与调度
- `docs/task-submission-flow.md`：任务提交流程
- `docs/smart-polling-mechanism.md`：智能轮询机制
- `docs/async-task-monitoring.md`：异步任务监控

### 能力、评测与 ComfyUI
- `docs/ABILITY_EVALUATION.md`：能力评测概览
- `docs/eval/ai-editor.md`：AI 图片编辑器（标注与提示词重组方法）
- `docs/eval/eval-platform.md`：评测平台说明
- `docs/comfyui/README.md`：ComfyUI 工作流与运维
- `docs/comfyui/agent-management.md`：ComfyUI 服务器管理（中台↔Agent 协议）
- `docs/comfyui-routing-business.md`：ComfyUI 业务路由说明
- `docs/comfyui-routing-technical.md`：ComfyUI 技术路由说明

### Coze 集成
- `docs/COZE_INTEGRATION_GUIDE.md`：Coze 集成指南
- `docs/coze-integration.md`：Coze 集成说明（现行）
- `docs/coze-plugin-podi.md`：PODI × Coze 插件接入
- `docs/COZE_WORKFLOWS.md`：Coze 工作流说明
- `docs/coze/toolbox-contracts.md`：工具箱契约说明
- `docs/coze/workflows.md`：Coze 工作流配置示例

### 管理端与 UI
- `docs/admin/integration-dashboard.md`：管理端能力管理页说明
- `docs/UI_STANDARD.md`：UI 规范

### 测试、复盘与草案
- `docs/testing/COZE_WORKFLOW_TEST_PLAN.md`：Coze 工作流测试计划
- `docs/retrospectives/2026-02-03.md`：复盘纪要
- `docs/wip/admin-ia-draft.md`：管理端信息架构草案

## 维护约定
1. 新增文档必须补充到本索引。
2. 规划/草案类文档请放入 `docs/wip/` 或在标题标明“计划”。
3. 重大变更请同步更新 `docs/BUSINESS_MODEL.md` 与 `docs/architecture.md`。

*最后更新: 2026-02-09*
