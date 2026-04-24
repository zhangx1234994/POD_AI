# Coze 控制面迁移完成度摘要

日期：2026-04-24

## 结论

当前这条迁移线已经从“概念方案”推进到“可执行实施包”。

现在已经具备：

1. 文档真源
2. 部署脚本
3. 联调脚本
4. 回滚脚本
5. 回滚后验证
6. 迁移前后基线采集与对比
7. 迁移包完整性审计
8. 迁移包本地统一自检

就实施准备度而言，这版已经不是 brainstorming，而是可以进入：

- 内部评审
- 演练
- 预发布窗口规划

但还不应直接判定为“可以上线迁移”，因为仍有几项故意留在第二阶段，另有少量实施缺口没有闭完。

## 已完成

### 1. 架构边界已经定死

- Coze 与 backend 同机
- ComfyUI 只做执行
- 高清放大不允许落到 Coze 主机本机
- 自研图片原子能力开始外拆到 `image-ops`

对应真源：

- `coze-mid-platform-migration-v1.md`
- `image-ops-service-split-v1.md`

### 2. 路由约束已经落成代码

- 普通 ComfyUI 默认补：
  - `required_executor_tags=["comfyui-general"]`
- 高清放大本机禁跑开关已经落地：
  - `DISABLE_LOCAL_HEAVY_IMAGE_TASKS`
- `image_ops_registry` 已把这 3 条能力固定为 `image-ops` 管理：
  - `expand_mask_color`
  - `set_dpi`
  - `upscale_resize`

### 3. `image-ops` 服务骨架已落地

已具备：

- FastAPI 服务入口
- Bearer Token 鉴权
- 3 条内部接口
- Dockerfile
- systemd unit
- compose 模板
- 部署说明

### 4. 迁移实施材料已齐

已经有：

- inventory
- host 分批
- host 切换顺序
- Coze 主机目录与 systemd 约定
- 一页 runbook
- 一页命令清单
- 桌面端第二阶段 runbook

### 5. 脚本入口已齐

已经有：

- 保守部署脚本
- 完整部署脚本
- 总入口 cutover 脚本
- `plan` 模式
- `image-ops` 真链路 smoke
- 主 Coze workflow smoke
- 回滚模板
- 回滚后验证
- env 写入脚本

### 6. 审计与自检已落地

已经有：

- 迁移包完整性检查
- host 首轮阻塞检查
- inventory 收集脚本
- 基线采集脚本
- 基线对比脚本
- 统一自检脚本

当前自检结论：

- 迁移包完整性：`ok`
- 首轮 host 阻塞项：`0`
- 第二阶段提醒仍存在
- 自检脚本整体已跑通

## 明确保留到第二阶段

这些不是遗漏，是当前故意不在首轮做：

### 1. OSS 内网地址切换

当前只纳入方案，不跟首轮迁移绑在一起。

### 2. 桌面端 `CenterUrl` 切换

当前只做了：

- 分阶段方案
- runbook

还不属于首轮迁移范围。

### 3. `comfyui-desktop/*` 与 `docs/api/modules/agent.md` 的旧 host

这些对象当前仍保留旧 backend host。
这是第二阶段提醒，不是首轮阻塞项。

### 4. ComfyUI 执行节点搬迁

当前策略明确为：

- 控制面迁到 Coze 主机
- 执行面不动

## 还没做完的真实缺口

下面这些是后面真正要补的，不是文档问题。

### 1. 真实 Coze 主机演练还没做

当前完成的是：

- 本地脚本与文档自检
- 迁移包完整性检查

但还没做：

- 在 `114.55.0.56` 上按 runbook 跑一遍完整演练

### 2. toolbox 实际切流还没做

当前只做到：

- inventory
- host 分批
- 切换顺序

还没做：

- 真实 Coze toolbox 批量切到新 backend

### 3. `image-ops` 还没接入真实生产节点

当前只有：

- 服务骨架
- 接口契约
- 部署模板

还没做：

- 在真实服务器上长时间稳定运行验证
- 与真实图片数据的持续性能观察

### 4. 前端正式部署口径还没统一到首轮

虽然已经有：

- admin/eval 必须 build 后运行

但实际迁移时是否同批迁，还需要单独决策。

## 当前建议

下一步不该继续发散加内容，应该进入下面的顺序：

1. 先把这版迁移包定为当前候选版本
2. 用 Coze 主机做一次保守演练：
   - 只动 `backend + image-ops`
3. 演练通过后，再决定是否推到 `main`
4. 再规划首轮正式迁移窗口

## 结论摘要

一句话概括：

**这版迁移包已经足够进入演练和评审，不再缺“怎么做”的材料；当前缺的是“在真实 Coze 主机上按这套材料跑一遍”。**
