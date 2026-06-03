# 客户端主开发机制

最后更新：2026-06-02

## 1. 当前定位

客户端当前重新启动为 **PODI Studio Preview**，产品形态是：

> 能力驱动的业务生产工作台。

它不是营销落地页，不是项目管理系统，不是能力管理后台，也不是直接调用 ComfyUI、vendor、atomic ability 的壳。

当前阶段的核心判断：

- 中台的第一对象是能力。
- 客户端的第一对象是用户要完成的生产动作。
- `projectId` 是后端证据容器，不是客户端的主产品视角。
- 客户端主线以 `/workbench` 能力工作台推进，不以 `/projects` 项目管理推进。

## 2. 机制目标

建立一套固定工作机制，避免客户端开发再次变成：

- 页面先行，需求滞后。
- 视觉先行，动线不清。
- 功能堆叠，用户不知道下一步。
- 文档分散，技术负责人无法判断当前口径。
- 接口缺口被客户端绕过，长期边界失控。

## 3. 工作机制总览

| 机制 | 文档 | 用途 |
| --- | --- | --- |
| 产品推导机制 | `01-product-reasoning.md` | 从用户、任务、动线、成本和复用推导需求 |
| 开发节奏机制 | `02-development-rhythm.md` | 固定每轮开发的输入、输出、检查点 |
| 文档治理机制 | `03-document-governance.md` | 固定文档目录、状态、更新规则 |
| 验收回归机制 | `04-acceptance-and-regression.md` | 固定验收标准、测试和视觉走查 |
| Gap 与决策机制 | `05-gap-and-decision-log.md` | 记录 API 缺口、产品决策和临时降级 |
| 交付模板 | `06-delivery-report-template.md` | 每轮交付汇报固定格式 |

## 4. 当前有效输入

当前客户端主线优先读取：

1. `docs/strategy/ability-governance-operating-model-v0.6.md`
2. `docs/strategy/client-agent-pack-v0.6/README.md`
3. `docs/strategy/client-agent-pack-v0.6/01-agent-brief.md`
4. `docs/strategy/client-agent-pack-v0.6/02-product-mvp.md`
5. `docs/strategy/client-agent-pack-v0.6/03-ui-flow.md`
6. `docs/strategy/client-agent-pack-v0.6/04-api-contract.md`
7. `docs/strategy/client-agent-pack-v0.6/05-acceptance-checklist.md`
8. `docs/strategy/client-agent-pack-v0.6/06-gap-log-template.md`
9. 本目录下的客户端主开发机制文档

历史 `docs/client/plans/2026-03-*`、`2026-04-*` 文档只作为回溯资料，不直接作为当前执行口径。

## 5. 第一阶段执行原则

第一阶段按“单能力真实闭环优先”执行：

```text
Workbench
  -> 创建/打开工作单
  -> 选择生产动作
  -> 上传/登记素材
  -> 提交一个真实业务能力
  -> 展示 queued/running/succeeded/failed 和 runId
  -> 结果沉淀为资产
  -> 从结果继续下一步或记录 gap
```

优先能力顺序：

1. 花纹提取
2. 裂变候选
3. 选择候选
4. 导出草稿
5. 产品图/组图/模特图/视频作为后续能力或 gap

## 6. 我的客户端负责人职责

作为客户端主开发负责人，我后续每轮必须完成：

- 先从用户视角说明本轮为什么做。
- 明确本轮影响的用户动线和页面。
- 明确调用的业务 API 和禁止触碰的内部 API。
- 修改代码前先同步本轮编辑范围。
- 完成后跑 lint/build/必要 UI 测试。
- 做浏览器视觉走查。
- 输出交付报告、剩余风险和下一轮建议。

