# 上线前自检与回归 SOP（必执行）

> 114 控制面正式发布的唯一执行入口见 `docs/standards/release-sop.md`。本文只保留“上线前自检与回归”的质量门槛。

## 1. 核心观点（硬性准则）
- **功能做得好不是结束，而是开始**：交互必须顺滑、可预测，覆盖高频与极端输入场景。
- **一次报错足以毁掉信任**：上线前必须做回归测试并输出报告，明确“已覆盖的错误场景清单”和“仍未覆盖的风险”。
- **四处一致**：评测平台/管理端/文档/接口必须一致，任何参数变更必须同步。

## 2. 适用范围
所有上线、合并、回滚前的改动（后端/管理端/评测端/文档）。

## 3. 自检清单
### A. 自动化检查（必须 100% 通过）
1) 后端：`python3 -m pytest backend/tests -q`
2) 管理端：`npm run lint`（podi-admin-web）
3) 评测端：`npm run lint`（podi-eval-web）

### B. 契约一致性（必须确认）
- `/api/evals/docs/workflows` 结构化与 Markdown 内容一致
- 对外文档不暴露内部参数（如 `count/generateCount/variantCount/n`）
- 输出字段与错误码列表完整
- 业务接口交付材料包含提交请求、查询请求、提交返回、查询排队中/成功/失败 JSON 样例
- 业务接口参数表必须说明必填、默认值、类型、枚举值和业务含义
- 输出类型归类正确（`callback_task_id / image_url / json_output`）
- 模型相关枚举按模型维度完整列出（比例/分辨率/多图上限）
- 文档总索引 `docs/README.md` 已同步

### C. 业务回归（必须执行）
对所有**对外暴露的工作流**逐条回归：
1) **成功路径**：用标准测试图/入参跑通
2) **参数契约核对**：schema ↔ 文档 ↔ 实际调用一致
3) **异常枚举**：宽高/步数/枚举/URL/文本等边界值测试
4) **状态一致性**：失败必须落到 `failed`，不允许“成功但无结果”

### D. Bug 修复闭环（必须执行）
对任何接口、任务、回填、队列、计费、权限类 Bug，不能只验证“现象消失”。必须逐项确认：

1) **根因定位**：明确是契约错误、参数映射、执行节点、数据库副作用、前端展示、文档不一致还是发布流程问题。
2) **成功路径复测**：使用真实样例跑通一次完整链路，记录 `runId`、结果链接和输出类型。
3) **失败路径复测**：至少覆盖本次 Bug 对应的错误请求，例如缺参、非法枚举、依赖不可用或队列满。
4) **副作用检查**：提交前错误不能创建业务任务、处理步骤、计费记录、回调任务或 queued/running 脏数据。
5) **返回契约检查**：默认返回必须是业务方可用的轻量结构；调试版才返回步骤、请求、路由、底层响应等排障字段。
6) **用量记录检查**：业务 API Key、服务令牌或内部巡检调用都必须能在接口调用中心按 `runId/requestId/traceId` 追溯。
7) **文档同步检查**：请求、响应、错误、枚举和示例必须同步到接口文档、错误码、测评端说明和交付材料。
8) **防复发测试**：补单测、契约测试、巡检脚本或逐功能检查项；不能只靠人工记忆。

## 4. 通过标准
- 自动化检查 0 失败
- 契约一致性 0 偏差
- 回归清单 100% PASS
- 否则：**禁止上线**

## 5. 输出物（必须产出）
- `reports/self-check/YYYYMMDD-HHMM.md`
- `reports/regression/YYYYMMDD-workflow-contract.md`
- `reports/regression/YYYYMMDD-workflow-run.md`
- `reports/regression/YYYYMMDD-param-risk.md`

## 6. 记录模板（最小字段）
```
date:
scope:

## Automated
- pytest backend: PASS/FAIL
- lint admin: PASS/FAIL
- lint eval: PASS/FAIL

## Contract & Docs
- eval docs (structured/markdown): PASS/FAIL
- internal params hidden: PASS/FAIL
- error catalog updated: PASS/FAIL

## Regression
- total workflows: N
- pass: N
- fail: N

## Bug Fix Closure
- root cause:
- success runId / result:
- negative case:
- side effects checked: PASS/FAIL
- light response checked: PASS/FAIL
- debug response checked: PASS/FAIL
- usage record checked: PASS/FAIL
- regression test added:

## Risk & Gaps
- covered:
- uncovered:

Result: PASS/FAIL
```
