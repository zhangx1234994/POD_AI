# 管理端前端整理计划 Phase 1

## 1. 背景

管理端已经承载业务能力、模型弹药库、能力目录、ComfyUI 纳管、账号权限、账单雏形、发布门禁等多个模块。当前主要问题不是缺功能，而是页面概念密度高、入口多、首屏包体偏大，非技术用户很难快速判断“我现在该看哪里、下一步该做什么”。

本阶段不做整体视觉重写，不改业务接口，不引入新的设计体系。目标是先把结构风险降下来，为后续完整前端整改打基础。

## 2. 设计原则

- 先总后分：总览页先给上线结论、业务状态和下一步动作，详情页再展开执行节点、模型、工作流等底层内容。
- 业务语言优先：主标题、按钮和错误提示尽量使用“业务方能理解”的描述，技术字段放在详情或高级区。
- 高级配置降权：执行器、工作流绑定、ComfyUI 资源、密钥历史仓库默认作为平台维护入口，不抢占业务主路径。
- 首屏轻量：管理端入口只加载当前页面必要内容，非首屏面板按需加载。
- 不破坏已上线链路：第一阶段只做结构和加载边界调整，避免混入接口、状态流转和权限逻辑改动。

## 3. 第一阶段已落地范围

- `IntegrationDashboard` 保留总览首屏直接加载。
- 账单框架、账号权限、运行监控、运行线路、高级编排、路由策略、历史密钥、系统配置、调度事件改为按需加载。
- ComfyUI 管理下的 LoRA、资源、服务器、轻 Agent、桌面接入、清单、任务、告警、模板等子面板改为按需加载。
- 业务能力、能力评测、模型弹药库沿用已有按需加载边界。
- 管理端生产构建已验证，`IntegrationDashboard` 主块从约 `544 kB` 降到约 `326 kB`。
- 懒加载面板声明已抽离到 `podi-admin-web/src/features/admin/integration/lazyPanels.tsx`，`IntegrationDashboard` 不再直接维护模块注册表。
- 导航解析、页签、默认表单、分页大小、默认定价等纯配置已抽离到 `podi-admin-web/src/features/admin/integration/integrationDashboardConfig.ts`。
- 业务能力页的灰度读取、视觉辅助读取、业务/版本筛选、版本对比派生状态、编辑表单映射和保存载荷构建已抽离到 `podi-admin-web/src/features/admin/integration/businessDashboardState.ts`，主页面继续收口为页面编排层。
- 业务能力页的默认版本申请、审批、启停、对比、回滚、运行记录刷新、导出和回调重试已抽离到 `podi-admin-web/src/features/admin/integration/businessDashboardActions.ts`，主页面不再直接维护业务请求动作。
- ComfyUI 管理页签、分区、同步发布步骤文案和轻 Agent 动作文案已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiDashboardConfig.ts`；可见节点过滤、隐藏计数、任务运行统计和同步步骤派生状态已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiDashboardState.ts`。
- ComfyUI 模型、版本、插件资源目录的刷新、保存、删除与版本同步动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiResourceCatalogActions.ts`，主页面只负责接线，不再直接维护这组资源请求动作。
- ComfyUI 任务下发、任务推送、任务事件、运行监控汇总与队列汇总动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiTaskActions.ts`，队列衔接相关请求从主页面移出。
- ComfyUI 轻 Agent 的注册、刷新、保存、删除、主节点设置与令牌签发动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiAgentActions.ts`，节点接入基础动作不再堆在主页面。
- ComfyUI 清单发布、回滚、差异检测和修复任务创建动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiManifestActions.ts`，资源一致性闭环从主页面移出。
- ComfyUI 桌面端注册码、安装包版本刷新、保存和启停动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiDesktopActions.ts`，桌面接入维护动作不再堆在主页面。
- ComfyUI 服务器刷新、新增、告警列表、差异日志和对齐快照保存动作已抽离到 `podi-admin-web/src/features/admin/integration/comfyuiServerActions.ts`，服务器纳管动作层基本完成。

## 4. 仍未处理的问题

- `IntegrationDashboard.tsx` 仍然过大，ComfyUI LoRA、模板、模型弹药库状态和其他管理域请求动作还集中在一个文件中；下一步应继续拆 LoRA/模板动作或模型弹药库状态域。
- 导航信息架构还需要继续压缩，尤其是能力目录、ComfyUI 管理、模型弹药库之间的边界说明。
- TDesign 和本地存储相关 vendor 包仍偏大，需要在后续阶段评估组件级引入、路由级拆包或替代方案。
- 视觉层还没有整体重做，当前只是降低加载和结构风险。
- 测评端和客户端尚未进入本阶段整改范围。

## 5. 下一阶段建议

1. 拆分 `IntegrationDashboard` 状态层，把业务能力、ComfyUI、模型弹药库、账号权限、账单分别抽成 hooks 或独立页面容器。
2. 重做管理端一级导航，固定为“总览 / 业务能力 / 能力弹药库 / 运行保障 / 商业化 / 系统维护”这类业务聚类，再把底层模块放入二级页。
3. 对业务能力页优先做交互整理，让用户能直接看到核心三类业务：花纹提取、图裂变、扩图。
4. 对 ComfyUI 管理保留“轻纳管”定位，重点展示节点在线、队列利用率、资源一致性、任务下发和回填异常，不把 ComfyUI 编辑器功能搬进中台。
5. 管理端结构稳定后，再集中处理测评端卡片辨识度、功能分组、发布时间和工作流角色展示。

## 6. 验收口径

- 管理端构建通过，无新增大包体警告。
- 用户从总览页能在 10 秒内判断是否可上线、哪里有风险、下一步点哪里。
- 业务能力、模型弹药库、ComfyUI 管理三条主路径互不抢概念。
- 非技术用户可根据页面文案完成查看版本、查看失败原因、查看运行线路三类操作。
- 高级配置仍可找到，但不作为默认阅读路径。

*最后更新: 2026-05-01*
