# ComfyUI 任务状态回归计划（提交/回调/最终）

> 目标：验证 ComfyUI 任务链路的状态口径、错误口径、回填口径一致。  
> 适用范围：`/api/admin/comfyui/tasks*`、`/api/admin/comfyui/repair-jobs*`、管理端 ComfyUI 管理页。

## 1. 测试维度

1. 提交阶段：`pending/submitting/submit_failed/submitted`
2. 回调阶段：`waiting/running/success/failed/not_configured`
3. 最终状态：`pending/running/success/failed/canceled`
4. 错误提示：错误码 + 可读文案

## 2. 必测场景

### A. 正常路径
- [ ] 创建任务 -> 提交成功 -> 回调成功 -> 最终成功
- [ ] 创建修复任务 -> 聚合状态 success

### B. 失败路径
- [ ] 代理服务离线 -> `AGENT_PUSH_FAILED`
- [ ] ComfyUI 队列满 -> `Q1001`
- [ ] ComfyUI 提交失败 -> `COMFYUI_SUBMIT_ERROR`
- [ ] 任务超时 -> `COMFYUI_TIMEOUT`

### C. 边界路径
- [ ] 回调晚到：软超时后仍能回填结果
- [ ] 重复回调：状态不乱跳，不重复覆盖终态
- [ ] 修复任务部分成功：聚合状态 `partial` 合理

## 3. 页面验收

- [ ] 任务列表列名固定：提交阶段 / 回调阶段 / 最终状态
- [ ] 失败原因展示：可读文案 + 错误码
- [ ] 同步发布步骤状态：前置未满足/待处理/进行中/已完成

## 4. 发布门槛

1. 成功/失败/边界场景全部有结果记录。  
2. 错误码与页面文案映射一致。  
3. 回归报告可追溯到 task_id、agent_id、时间窗口。  

*最后更新: 2026-03-04*
