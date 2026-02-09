# 错误码总表（Error Catalog）

> 说明：本表是**全局权威错误码目录**。新增/变更错误必须同步更新本表，并在接口文档中引用。

---

## 0. 规则

- **强约束错误**：必须使用 `ERR|<CODE>|<message>` 格式（如队列/并发限制）。
- **关键字错误**：使用大写关键字（如 `TASK_NOT_FOUND`），出现在 `detail` / `error_message` / `debugResponse`。
- `*_HTTP_*` / `*_STATUS_*` 表示带动态后缀（如 `COMFYUI_HISTORY_HTTP_502`）。

---

## 1. 队列/并发

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| Q1001 | ComfyUI 队列已满（单机 >= 10） | 强约束，写入 `taskId` |
| Q2001 | 商业模型队列已满（单机 >= 10） | 强约束，写入 `taskId` |

---

## 2. 鉴权/访问

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| AUTHORIZATION_REQUIRED | 缺少鉴权 | 401 |
| UNAUTHORIZED | 未授权（评测公共接口） | 401 |
| INVALID_TOKEN | token 无效 | 401 |
| INVALID_TOKEN_PAYLOAD | token payload 异常 | 401 |
| INVALID_CREDENTIALS | 登录凭证错误 | 401 |
| USER_NOT_FOUND | 用户不存在 | 404 |
| USER_INACTIVE | 用户被禁用 | 403 |
| ADMIN_ONLY | 仅管理员可访问 | 403 |
| INTERNAL_ONLY | 仅内网可访问 | 401 |

---

## 3. 资源/参数

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| NOT_FOUND | 通用不存在 | 404 |
| RUN_NOT_FOUND | 评测 run 不存在 | 404 |
| WORKFLOW_ID_MISSING | 缺少 workflow_id | 400 |
| WORKFLOW_VERSION_NOT_FOUND | workflow 版本不存在 | 404 |
| WORKFLOW_NOT_FOUND | workflow 不存在 | 404 |
| EXECUTOR_NOT_FOUND | 执行节点不存在 | 404 |
| EXECUTOR_BUSY | 执行节点繁忙 | 409 |
| EXECUTOR_ADAPTER_MISSING | 执行器适配缺失 | 500 |
| EXECUTOR_TYPE_NOT_BAIDU | 执行器类型不匹配（百度） | 400 |
| EXECUTOR_TYPE_NOT_COMFYUI | 执行器类型不匹配（ComfyUI） | 400 |
| EXECUTOR_TYPE_NOT_KIE | 执行器类型不匹配（KIE） | 400 |
| EXECUTOR_TYPE_NOT_VOLCENGINE | 执行器类型不匹配（火山） | 400 |
| ABILITY_NOT_FOUND | 能力不存在 | 404 |
| ABILITY_NOT_FOUND_OR_INACTIVE | 能力不存在或未激活 | 404 |
| ABILITY_INACTIVE | 能力未激活 | 403 |
| ABILITY_EXECUTOR_NOT_CONFIGURED | 能力未配置执行节点 | 400 |
| ABILITY_LOG_NOT_FOUND | 能力日志不存在 | 404 |
| ABILITY_LOG_NOT_COMFYUI | 日志非 ComfyUI | 400 |
| INVALID_WORKFLOW_OR_EXECUTOR | workflow 或 executor 无效 | 400 |

---

## 4. 评测/Coze

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| COZE_SUBMIT_FAILED | Coze 提交失败 | /v1/workflow/run |
| COZE_SUBMIT_MISSING_EXECUTE_ID | 缺少 execute_id | Coze 返回异常 |
| COZE_HISTORY_FAILED | Coze history 查询失败 | /v1/workflow/history |
| COZE_EXECUTION_FAILED | Coze 执行失败 | run_status=failed |
| COZE_FAILED | Coze 返回 code!=0 | |
| COZE_RUN_* | Coze 状态异常 | failed/canceled/timeout |
| COZE_ASYNC_TIMEOUT | 异步轮询超时 | |
| COZE_ASYNC_EMPTY | 异步轮询空响应 | |
| COZE_WORKFLOW_ERROR | workflow output 内含 error | |
| COZE_WORKFLOW_ID_MISSING | 缺少 workflow_id | |
| COZE_NOT_CONFIGURED | Coze 未配置 | |
| COZE_REQUEST_FAILED | Coze 请求失败 | |
| COZE_RESPONSE_NOT_JSON | Coze 返回非 JSON | |
| COZE_INVALID_RESPONSE | Coze 返回体异常 | |
| COZE_HTTP_* | Coze HTTP 非 200 | |
| FANOUT_EMPTY | 批量子任务全部失败 | |
| FANOUT_PARTIAL_FAILED | 批量部分失败 | |

---

## 5. Task/回调

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| TASK_ID_REQUIRED | 缺少 taskId | |
| TASK_NOT_FOUND | 任务不存在 | |
| TASK_FAILED | 任务执行失败 | |
| TASK_TIMEOUT | 任务超时 | |
| TASK_IMAGES_EMPTY | 任务无图片 | |
| CALLBACK_OUTPUT_EMPTY | 回调 task id 为空 | |
| CALLBACK_IMAGES_EMPTY | 回调解析不到图片 | |
| CALLBACK_TASK_NOT_RESOLVED | task id 无法解析/失效 | |

---

## 6. Agent/服务器管理

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| AGENT_TOKEN_REQUIRED | 缺少 Agent token | 401 |
| AGENT_TOKEN_INVALID | Agent token 无效 | 401 |
| AGENT_TOKEN_EXPIRED | Agent token 已过期 | 401 |
| AGENT_TOKEN_KID_REQUIRED | 缺少 kid（多密钥模式） | 401 |
| AGENT_TOKEN_KID_INVALID | kid 不存在 | 401 |
| AGENT_TOKEN_SCOPE_INVALID | token scope 不匹配 | 403 |
| AGENT_TOKEN_PAYLOAD_INVALID | token payload 异常 | 401 |
| AGENT_NOT_FOUND | Agent 不存在 | 404 |
| AGENT_ALREADY_EXISTS | Agent 已存在 | 409 |
| AGENT_NOT_ALLOWED | Agent 被禁用/不在白名单 | 403 |
| AGENT_BASE_URL_MISSING | Agent base_url 缺失 | 400 |
| AGENT_MANIFEST_NOT_FOUND | Manifest 不存在 | 404 |
| AGENT_MANIFEST_FORBIDDEN | Manifest 不匹配 task | 403 |
| AGENT_TASK_NOT_FOUND | Task 不存在 | 404 |
| AGENT_TASK_FORBIDDEN | Task 不属于该 Agent | 403 |
| AGENT_TASK_EXPIRED | Task 已过期 | 409 |
| AGENT_PUSH_FAILED | 任务推送失败 | 502 |

---

## 7. ComfyUI

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| COMFYUI_BASE_URL_MISSING | 缺少 ComfyUI Base URL | |
| COMFYUI_WORKFLOW_EMPTY | workflow 为空 | |
| COMFYUI_SUBMIT_ERROR | 提交失败 | /prompt |
| COMFYUI_SUBMIT_NODE_ERROR | 节点错误 | /prompt node_errors |
| COMFYUI_HISTORY_HTTP_* | history 非 200 | /history/<id> |
| COMFYUI_HISTORY_INVALID | history JSON 异常 | |
| COMFYUI_STATUS_* | status 异常 | running/error/unknown |
| COMFYUI_IMAGES_EMPTY | history 无 images | |
| COMFYUI_ASSETS_EMPTY | OSS 入库为空 | |
| COMFYUI_TIMEOUT | 轮询超时 | |
| COMFYUI_IMAGE_REQUIRED | 缺少图片 | |
| COMFYUI_OBJECT_INFO_ERROR | /object_info 异常 | |
| COMFYUI_OBJECT_INFO_INVALID | /object_info JSON 异常 | |
| COMFYUI_QUEUE_STATUS_ERROR | /queue/status 异常 | |
| COMFYUI_QUEUE_STATUS_INVALID | queue JSON 异常 | |
| COMFYUI_ADAPTER_MISSING | adapter 未注册 | |
| COMFYUI_PROMPT_ID_REQUIRED | 缺少 prompt_id | |
| COMFYUI_BASE_URL_REQUIRED | 缺少 base_url | |
| COMFYUI_ERROR | ComfyUI 执行错误 | |
| COMFYUI_EXECUTOR_NOT_MATCHED | 执行节点不匹配 | |
| COMFYUI_NOT_READY | ComfyUI 未就绪 | |
| COMFYUI_SYSTEM_STATS_ERROR | ComfyUI 系统状态异常 | |
| COMFYUI_TEST_FAILED | ComfyUI 测试失败 | |
| COMFYUI_WORKFLOW_KEY_MISSING | workflow_key 缺失 | |
| COMFYUI_VERSION_SOURCE_INVALID | ComfyUI 版本源地址无效 | |
| COMFYUI_VERSION_SYNC_FAILED | ComfyUI 版本同步失败 | |

---

## 8. 第三方/媒资

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| BAIDU_TEST_FAILED | 百度测试失败 | |
| BAIDU_API_ERROR | 百度 API 错误 | |
| BAIDU_API_KEY_MISSING | 百度 API Key 缺失 | |
| BAIDU_ENDPOINT_MISSING | 百度 endpoint 缺失 | |
| BAIDU_TOKEN_ERROR | 百度 token 异常 | |
| VOLCENGINE_REQUEST_FAILED | 火山请求失败 | |
| VOLCENGINE_API_KEY_MISSING | 火山 API Key 缺失 | |
| VOLCENGINE_HTTP_ERROR | 火山 HTTP 错误 | |
| VOLCENGINE_HTTP_* | 火山 HTTP 非 200 | |
| VOLCENGINE_API_TYPE_UNSUPPORTED | 火山 API 类型不支持 | |
| VOLCENGINE_MODEL_REQUIRED | 火山模型必填 | |
| KIE_TASK_CREATE_FAILED | KIE 创建任务失败 | |
| KIE_TASK_ID_MISSING | KIE 返回 task id 为空 | |
| KIE_API_KEY_MISSING | KIE API Key 缺失 | |
| KIE_MODEL_REQUIRED | KIE 模型必填 | |
| KIE_RESPONSE_INVALID | KIE 返回结构异常 | |
| KIE_STATUS_EMPTY | KIE 状态为空 | |
| KIE_STATUS_ERROR | KIE 状态异常 | |
| KIE_TIMEOUT | KIE 任务硬超时 | 默认 15 分钟 |
| IMAGE_DOWNLOAD_FAILED | 下载图片失败 | |
| IMAGE_BASE64_INVALID | Base64 图片无效 | |
| IMAGE_REQUIRED | 缺少图片 | |
| PODI_IMAGE_TOOLS_IMPORT_FAILED | 图像工具导入失败 | |
| PODI_UTILITY_UNSUPPORTED | 不支持的工具/能力 | |

---

## 9. 维护要求

- 新增/变更错误码：必须更新本表 + 接口文档 + 测试
- 若发现错误码缺失：**视为流程问题**，必须补齐
