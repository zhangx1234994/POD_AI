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
| INVALID_TOKEN | token 无效 | 401 |
| INVALID_TOKEN_PAYLOAD | token payload 异常 | 401 |
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
| ABILITY_NOT_FOUND | 能力不存在 | 404 |
| ABILITY_NOT_FOUND_OR_INACTIVE | 能力不存在或未激活 | 404 |
| ABILITY_LOG_NOT_FOUND | 能力日志不存在 | 404 |

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

## 6. ComfyUI

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

---

## 7. 第三方/媒资

| 编号 | 含义 | 备注 |
| --- | --- | --- |
| BAIDU_TEST_FAILED | 百度测试失败 | |
| VOLCENGINE_REQUEST_FAILED | 火山请求失败 | |
| KIE_TASK_CREATE_FAILED | KIE 创建任务失败 | |
| KIE_TASK_ID_MISSING | KIE 返回 task id 为空 | |
| IMAGE_DOWNLOAD_FAILED | 下载图片失败 | |
| PODI_IMAGE_TOOLS_IMPORT_FAILED | 图像工具导入失败 | |

---

## 8. 维护要求

- 新增/变更错误码：必须更新本表 + 接口文档 + 测试
- 若发现错误码缺失：**视为流程问题**，必须补齐
