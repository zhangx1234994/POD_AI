# 2026-06-02 客户端主开发机制建立

状态：active

## 背景

用户要求客户端负责人建立开发机制、文档管理和项目管理机制。此前客户端讨论已从旧页面修补转向 v0.6 的 **PODI Studio Preview**，并进一步确认当前不适合以完整项目管理闭环作为第一阶段主线，而应以能力驱动的生产工作台推进。

## 本次决策

### DECISION-20260602-01

客户端主线采用能力工作台视角：

- `/workbench` 是产品主入口。
- 用户第一视角是“选择生产动作并完成能力调用”。
- `projectId` 是后端证据容器，不作为客户端主产品视角。
- 第一阶段优先跑通单能力真实闭环。

### DECISION-20260602-02

客户端负责人每轮开发必须按固定机制推进：

- 先做用户需求推导。
- 再做范围收敛。
- 开发前说明编辑范围。
- 开发后输出验证、截图、gap 和风险。
- 重要决策和 API 缺口必须落文档。

## 本次新增文档

- `docs/client/operating/README.md`
- `docs/client/operating/01-product-reasoning.md`
- `docs/client/operating/02-development-rhythm.md`
- `docs/client/operating/03-document-governance.md`
- `docs/client/operating/04-acceptance-and-regression.md`
- `docs/client/operating/05-gap-and-decision-log.md`
- `docs/client/operating/06-delivery-report-template.md`

## 本次更新文档

- `docs/client/README.md`
- `docs/client/DOC_STATUS.md`

## 当前执行口径

```text
Workbench
  -> 创建/打开工作单
  -> 选择生产动作
  -> 上传/登记素材
  -> 提交业务能力
  -> 展示状态和 runId
  -> 结果进入资产
  -> 继续下一步或记录 gap
```

## 下一步建议

1. 检查当前仓库是否已有新客户端工程目录。
2. 如无，创建 `podi-studio-preview/`。
3. 先实现 `/workbench`、工作单详情、单能力工作区的骨架。
4. 第一条真实闭环优先选择花纹提取。
5. 补齐 gap log 和回归基线。

