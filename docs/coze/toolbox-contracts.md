**
1) 调用能力工具 → 返回 `taskId`  
2) 调用 `POST /api/coze/podi/tasks/get` 轮询结果  

`taskId` 推荐格式：`t1.<provider>.<executorId>.<raw>`

## 6. 队列与错误

队列满时，工具返回：

```
taskId = ERR|Q1001|COMFYUI_QUEUE_FULL(...)
taskStatus = failed
```

错误码详见：`docs/standards/queue-and-error-standards.md`

## 7. 内部鉴权

默认仅允许内网调用（否则 `401 INTERNAL_ONLY`）：

- 配置 `COZE_TRUSTED_IPS`
- 或请求头 `Authorization: Bearer <SERVICE_API_TOKEN>`

## 8. 常见问题

- **schema 未更新**：删除 Coze 节点重新拖入
- **Missing required parameters**：检查 `url/width/height` 必填字段
- **TASK_NOT_FOUND**：确认 taskId 对应同一后端/数据库

