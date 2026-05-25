# PODI 版本记录

## v0.4.0 - 2026-05-25

基线 commit：`8033c843`

Git tag：`v0.4.0`

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。
- `docs/`、`scripts/` 发布与巡检材料。

未更新范围：

- 不更新 4090/5090/ComfyUI 能力机。
- 不调整扩图路由，不把扩图固定到 4090。

主要变更：

- 业务编排工作台产品化版本完成阶段封版：业务命名与版本族、编排图证据、接口调用中心、runId 排障、控制点去重继续收敛。
- 图编辑组件型业务能力完成 114 版本封版验证，`canvas_outpaint` 纳入真实巡检与交付包。
- 发布门禁修正历史失败判断：封版阻断使用未恢复失败，不再因后续已成功覆盖的历史失败误阻断。
- ComfyUI 158 扩图节点完成线上兼容复核，当前按节点侧修复结果继续参与中台路由。

验证结果：

- 封版验证时已确认发布基线与 `origin/main` 一致：`8033c843`。
- 线上真实业务巡检通过：花纹提取、图裂变、扩图均 `succeeded`。
- 图编辑真实样例通过：`canvas_outpaint_all_sides`，runId `759f0310c01c4eaf9787aaec4ff93f95`。
- 158 扩图指定节点验证通过：`flux2_klein_9b_outpaint`，logId `46261`。
- ComfyUI 兼容检查通过：`total=17 ok=17 warnings=0 failed=0 servers=2`。
- 发布 smoke 通过：队列容量 `20`、业务使用中心 `unresolved=0`、评测运维健康。
- systemd 真实巡检重新执行成功：`podi-business-live-patrol.service` 最近一次执行成功，6 个生产评测工作流全部成功。
- 管理端主要页面走查通过：业务能力、ComfyUI 资源、API 暴露、能力评测无浏览器侧 4xx/5xx 或明显运行时报错。

证据记录：

- `docs/testing/2026-05-25-v0.4.0-114-seal-validation.md`
- `docs/testing/2026-05-25-image-edit-release-candidate-114.md`
- 线上报告：`/srv/pod/deliverables/release_patrol/core_business_8033c843.json`
- 线上报告：`/srv/pod/deliverables/image_edit_patrol_seal/`
- 线上报告：`/srv/pod/reports/health-watch/eval_production_20260525T123505Z.json`

已知保留风险：

- 商业报表历史账单问题当前仍按 observed-only 观察，不作为本版本阻断。
- `legacy-seamless-fission` 仍为历史 attention 项，不影响本轮核心业务封版。
- 权限治理类风险后续继续按 auth/billing 路线处理，本版本未扩大鉴权面。

下个版本方向：

- 发布后 30-60 分钟观察接口错误率、业务运行失败率、ComfyUI 队列和 OSS 回填。
- 继续推进页面文案与视觉降噪、业务方组件更新方式、第三方能力治理和计费治理。

## v0.4.0 - 规划记录

目标：业务编排工作台产品化。

当前规划：

- 业务命名与版本族：按业务入口组织版本、继承关系、发布时间、更新时间和更新说明。
- 编排图交互闭环：节点可查看、默认版本只读、草稿版本可编辑受控字段。
- 接口调用中心与 runId 排障：一次业务调用聚合入口、版本、处理步骤、子能力、回填、回调和计费。
- 控制点继续去重：字段、枚举、默认值、状态词优先从后端业务版本和组件目录派生。
- 页面文案与视觉降噪：减少说明型大段文案，主提示使用业务语言。

方案：`docs/strategy/business-orchestration-workbench-v0.4-plan.md`

## v0.3.0 - 本地完成，待上线窗口

目标：业务编排工作台与控制点去重。

当前状态：

- 业务组件目录已落地。
- 受控编排草稿已落地。
- 草稿校验、发布门禁和切默认已落地。
- runId 父子步骤排障视图已落地。
- 后端测试、管理端类型检查和构建已通过；等待后续统一上线窗口。

方案：`docs/strategy/business-orchestration-workbench-v0.3-plan.md`

## v0.2.0 - 待发布

目标：业务控制面收敛。

当前状态：

- 本地开发和验证已完成，等待统一上线窗口。
- 业务配方、版本族、接口调用中心、测评端关键问题和逐功能上线门禁已收敛。
- 发布前仍需按 SOP 跑 114 控制面更新、线上 smoke、业务接口、Coze 工具箱和测评端回归。

方案：`docs/strategy/business-control-plane-v0.2-plan.md`

## v0.1.0 - 2026-05-16

基线 commit：`904f9a2a`

Git tag：`v0.1.0`

发布范围：

- 114 控制面 backend。
- 管理端静态站点。
- 测评端静态站点。

验证结果：

- 发布源检查通过：`PASS=6 WARN=0 FAIL=0`。
- 后端发布测试通过：`86 passed`。
- 管理端、测评端类型检查和构建通过。
- 远端健康检查通过。
- 发布 smoke 通过。
- ComfyUI 工作流兼容检查通过：`total=16 ok=16 warnings=0 failed=0 servers=2`。
- 158/233 双节点健康检查通过，队列总容量 20。

主要能力：

- 中台控制面稳定部署。
- 业务 API、Coze 工具箱、管理端、测评端基础闭环可用。
- ComfyUI 158/233 双节点路由恢复。
- 业务运行、能力调用、接口调用中心具备基础可观测能力。

已知保留问题：

- 业务链路仍存在多个控制单元重复管理的问题。
- 业务编排目前主要是 JSON/recipe，缺少可视化只读图和草稿编辑。
- 测评端和管理端仍需继续做业务化表达和视觉降噪。
- 账单、套餐、正式收费仍处于后续阶段。

下个版本方向：

- `v0.2.0`：控制权收敛、业务编排可视化、runId 全链路排障。
