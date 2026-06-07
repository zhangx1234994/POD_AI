# 错误码 -> 页面提示映射（V1）

> 目标：前端展示统一口径，减少“只看到技术错误码，不知道怎么处理”。
> 范围：先覆盖高频 20 条，后续滚动补齐。

## 1. 高优先级映射（首批）

| 错误码 | 中文提示（面向用户） | 下一步动作（面向操作） |
| --- | --- | --- |
| AUTHORIZATION_REQUIRED | 当前请求未登录或登录已过期。 | 重新登录后再试。 |
| INVALID_TOKEN | 登录状态无效。 | 退出后重新登录。 |
| INVALID_CREDENTIALS | 账号或密码错误。 | 检查账号密码后重试。 |
| USER_INACTIVE | 当前账号已被禁用。 | 联系管理员恢复账号。 |
| ADMIN_ONLY | 当前操作仅管理员可用。 | 切换管理员账号或联系管理员。 |
| BATCH_ASSET_LIMIT_EXCEEDED | 本次上传素材超过上限。 | 减少上传数量后重试。 |
| BATCH_REVIEW_NOT_READY | 批次尚未结束，暂不可标注。 | 回到生成页等待批次结束。 |
| EXECUTOR_BUSY | 执行节点繁忙。 | 稍后重试或切换节点。 |
| EXECUTOR_NOT_FOUND | 执行节点不存在或已下线。 | 到执行节点页检查节点状态。 |
| COZE_SUBMIT_FAILED | 工作流提交失败。 | 检查工作流参数后重试。 |
| TASK_NOT_FOUND | 任务不存在或已失效。 | 核对 taskId 与调用环境。 |
| TASK_TIMEOUT | 任务执行超时。 | 保持等待或重提任务。 |
| CALLBACK_TASK_NOT_RESOLVED | 回调任务未解析成功。 | 到任务事件查看原始返回。 |
| Q1001 | ComfyUI 队列已满。 | 等待队列释放或切换服务器。 |
| Q1002 | ComfyUI 没有可用执行节点。 | 检查节点健康、能力绑定和路由配置；短时网络波动可重试一次。 |
| Q2001 | 商业模型队列已满。 | 错峰提交或降低并发。 |
| COMFYUI_EXECUTOR_UNAVAILABLE | ComfyUI 没有可用执行节点。 | 检查节点健康、能力绑定和路由配置。 |
| COMFYUI_TIMEOUT | ComfyUI 执行超时。 | 查看队列状态并继续观察。 |
| COMFYUI_SUBMIT_ERROR | ComfyUI 提交失败。 | 检查工作流节点与参数。 |
| AGENT_PUSH_FAILED | 任务下发到代理服务失败。 | 检查代理服务在线状态后重推。 |
| KIE_TIMEOUT | KIE 任务超时。 | 保持轮询，必要时重新提交。 |
| IMAGE_DOWNLOAD_FAILED | 图片下载失败。 | 检查图片 URL 是否可公网访问。 |

## 2. 前端渲染约束

1. 所有错误提示必须展示 `error_code`。  
2. 当有 `error_message` 时，展示在“详情”区域，不直接替换主提示文案。  
3. 对 `Q1001/Q2001` 必须识别为“队列限制”，不可误显示为系统故障。  
4. 对 `Q1002/COMFYUI_EXECUTOR_UNAVAILABLE` 必须识别为“执行节点不可用/无兼容节点”，不可误显示为提交成功或队列满。
5. 对 `*_TIMEOUT` 默认视为“可恢复”，避免直接引导重复提交。

## 3. 验收清单

- [ ] 管理端任务列表使用本映射文案。  
- [ ] 评测端任务详情使用本映射文案。  
- [ ] 文档示例与页面提示一致。  

*最后更新: 2026-03-04*
