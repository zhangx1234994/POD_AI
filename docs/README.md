# POD AI Studio 文档目录

## 文档索引

### 核心文档

| 文档 | 描述 | 状态 |
|------|------|------|
| [BUSINESS_MODEL.md](./BUSINESS_MODEL.md) | 业务建模文档，包含登录、存储、处理、积分等完整架构设计 | ✅ 完整 |
| [architecture.md](./architecture.md) | 技术架构与边界总览（含抽象/解耦原则） | ✅ 最新 |
| [api.md](./api.md) | API 接口概览（认证、媒资、任务、能力等模块） | ✅ 持续更新 |
| [api/abilities.md](./api/abilities.md) | 统一能力 API & 回调/并发任务规范 | ✅ 最新 |

### 开发文档

| 文档 | 描述 | 状态 |
|------|------|------|
| [development-guide.md](./development-guide.md) | 开发指南 | ✅ 完整 |
| [task-submission-flow.md](./task-submission-flow.md) | 任务提交流程 | ✅ 完整 |
| [smart-polling-mechanism.md](./smart-polling-mechanism.md) | 智能轮询机制 | ✅ 完整 |
| [async-task-monitoring.md](./async-task-monitoring.md) | 异步任务监控 | ✅ 完整 |

### 其他文档

| 文档 | 描述 | 状态 |
|------|------|------|
| [error-codes.md](./error-codes.md) | 错误码文档 | ✅ 完整 |
| [comfyui/README.md](./comfyui/README.md) | ComfyUI 工作流与服务器运维手册 | ✅ 最新 |
| [standards/abstraction-and-decoupling.md](./standards/abstraction-and-decoupling.md) | 抽象与解耦准则 | ✅ 最新 |
| [standards/issue-improvement-log.md](./standards/issue-improvement-log.md) | 问题与优化记录（滚动） | ✅ 最新 |
| [retrospectives/2026-02-03.md](./retrospectives/2026-02-03.md) | 复盘纪要（问题与准则提炼） | ✅ 最新 |

---

## 快速开始

### 1. 业务流程概览

```
用户登录 → 选择工具 → 上传图片 → 配置参数 → 积分校验 → 提交任务
                                                    ↓
任务处理 ← 图片上传 ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
                    ↓
              结果展示 → 下载保存
```

### 2. 核心模块

#### 认证系统
- **自有账号**: 用户名密码登录、手机验证码登录
- **第三方SSO**: 跨平台单点登录（加密Ticket机制）

#### 积分系统
- 积分账户管理
- 任务消耗计算（支持VIP折扣、批量折扣）
- 积分变动动画

#### 任务系统
- 任务提交与状态管理
- 智能轮询（页面可见性+用户活动检测）
- 任务队列与并发控制

### 3. 原子能力与图片处理架构

```
┌──────────────────────────────────────────────┐
│                任务调度 / 能力中台               │
├──────────────────────────────────────────────┤
│  原子能力 (Baidu / Volcengine / KIE / …)      │
│  ComfyUI 工作流（多节点，内含 LoRA/模型托管）    │
│  统一能力 API / 回调 / 并发控制 / 成本统计        │
│  能力调用日志 & 健康巡检                          │
└──────────────────────────────────────────────┘
```

> 说明：统一能力接口 `GET|POST /api/abilities`、`/api/ability-tasks`、`/api/admin/abilities/{id}/logs` 等细节见 [docs/api/abilities.md](./api/abilities.md)。ComfyUI 的 workflow 版本、LoRA 枚举、队列状态等见 [docs/comfyui/README.md](./comfyui/README.md)。

---

## 文档贡献指南

1. 新增文档请添加到对应分类
2. 更新文档时请在文件头部更新版本号和日期
3. 重大变更需要更新 `BUSINESS_MODEL.md`

---

*最后更新: 2026-02-03*
