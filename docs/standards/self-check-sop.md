# 上线前自检与回归 SOP（必执行）

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

### C. 业务回归（必须执行）
对所有**对外暴露的工作流**逐条回归：
1) **成功路径**：用标准测试图/入参跑通
2) **参数契约核对**：schema ↔ 文档 ↔ 实际调用一致
3) **异常枚举**：宽高/步数/枚举/URL/文本等边界值测试

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

## Risk & Gaps
- covered:
- uncovered:

Result: PASS/FAIL
```
