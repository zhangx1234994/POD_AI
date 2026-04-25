# PODI 对外接口总文档（助理 / Skills 生成专用）

> 版本：2026-03-06
> 适用对象：需要为另一个助理工具、Agent、Skills 系统生成可直接调用接口的开发者。
> 目标：给出一份单文档，覆盖地址、鉴权、核心接口、参数约定、错误语义与推荐调用方式。

## 1. 服务地址

线上环境：

- 后端 API：`http://117.50.80.158:8099`
- 管理端：`http://117.50.80.158:8199`
- 评测端：`http://117.50.80.158:8200`

统一 API 前缀：

- `/api/*`

推荐给助理 / Skills 的调用顺序：

1. 先登录拿 `accessToken`
2. 查询能力清单或 Coze 工具箱 OpenAPI
3. 执行能力 / 创建任务
4. 轮询异步结果

---

## 2. 鉴权方式

### 2.1 用户 / 管理员 JWT

登录接口：`POST /api/auth/login`

请求体：

```json
{
  "username": "admin",
  "password": "<your_password>"
}
```

响应体：

```json
{
  "accessToken": "<jwt>",
  "tokenType": "bearer",
  "expiresIn": 3600,
  "refreshToken": "<jwt>",
  "role": "admin"
}
```

后续请求头：

```http
Authorization: Bearer <accessToken>
```

### 2.2 Coze / 内部服务 Token

适用于 `/api/coze/podi/*`：

- 内网 IP 白名单（`COZE_TRUSTED_IPS`）
- 或 `Authorization: Bearer <SERVICE_API_TOKEN>`

### 2.3 评测端 Token

仅评测端公开接口使用：

- `X-Eval-Token: <EVAL_PUBLIC_TOKEN>`
- 或 URL `?token=<token>`

---

## 3. 核心推荐接口（给助理最重要）

如果你是给另一个助理生成 skills，优先接这 5 类：

1. `POST /api/auth/login`
2. `GET /api/abilities`
3. `POST /api/abilities/{abilityId}/invoke`
4. `POST /api/ability-tasks`
5. `GET /api/ability-tasks/{taskId}`

如果你是给 Coze / 工作流类助理接入，则再加：

6. `GET /api/coze/podi/*.json`（OpenAPI）
7. `POST /api/coze/podi/tasks/get`
8. `GET /api/evals/workflow-versions`
9. `POST /api/evals/runs`
10. `GET /api/evals/runs/{runId}`

---

## 4. 能力接口（推荐主入口）

### 4.1 查询能力列表

`GET /api/abilities`

用途：

- 获取当前所有激活能力
- 适合助理动态生成工具列表、表单、技能卡片

关键字段：

- `id`：调用能力时使用，如 `comfyui_jisu_chuli`
- `provider`：`comfyui / kie / baidu / volcengine / podi`
- `capabilityKey`
- `displayName`
- `defaultParams`
- `inputSchema`
- `metadata`
- `requiresImage`

示例：

```bash
curl http://117.50.80.158:8099/api/abilities   -H "Authorization: Bearer <accessToken>"
```

### 4.2 调用能力（同步）

`POST /api/abilities/{abilityId}/invoke`

通用请求体：

```json
{
  "executorId": null,
  "inputs": {
    "prompt": "保持主体不变，优化画面质感"
  },
  "imageUrl": "https://example.com/input.png",
  "imageBase64": null,
  "images": null,
  "metadata": {
    "requestFrom": "assistant-skill"
  }
}
```

响应体：

```json
{
  "abilityId": "comfyui_jisu_chuli",
  "provider": "comfyui",
  "status": "succeeded",
  "requestId": "...",
  "logId": 12345,
  "durationMs": 842,
  "images": [
    {
      "ossUrl": "https://.../output.png",
      "sourceUrl": "https://.../output.png",
      "type": "image"
    }
  ],
  "assets": [],
  "metadata": {},
  "raw": {}
}
```

### 4.3 创建异步能力任务

`POST /api/ability-tasks`

用途：

- 大批量任务
- 长耗时任务
- 需要回调或轮询的场景

请求体：

```json
{
  "abilityId": "comfyui_jisu_chuli",
  "inputs": {
    "prompt": "保持主体不变，优化画面质感"
  },
  "imageUrl": "https://example.com/input.png",
  "callbackUrl": "https://your-domain.com/webhook"
}
```

### 4.4 查询异步任务

`GET /api/ability-tasks/{taskId}`

状态值：

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

---

## 5. 评测工作流接口（适合批量回归 / 工作流验收）

### 5.1 查询激活工作流

`GET /api/evals/workflow-versions?status=active`

用途：

- 获取当前可用的 Coze 工作流版本
- 返回 `workflow_id`、参数 schema、输出 schema、分类、备注

### 5.2 创建评测 run

`POST /api/evals/runs`

**注意：这个接口的真实入参不是 `inputs`，而是：**

- `input_oss_urls_json`
- `parameters_json`

正确示例：

```json
{
  "workflow_version_id": "<workflow_version_id>",
  "input_oss_urls_json": [
    "https://example.com/input.png"
  ],
  "parameters_json": {
    "prompt": "test prompt",
    "width": "1024",
    "height": "1024"
  }
}
```

### 5.3 查询评测 run

`GET /api/evals/runs/{runId}`

关键状态字段：

- `status`：原始评测状态
- `submit_status`：提交阶段
- `callback_status`：回调阶段
- `final_status`：最终阶段
- `error_code`
- `error_message`

状态语义：

- `submit_status`：`pending / submitting / submit_failed / submitted`
- `callback_status`：`waiting / running / success / failed / not_configured`
- `final_status`：`pending / running / success / failed / canceled`

### 5.4 获取工作流文档

`GET /api/evals/docs/workflows`

用途：

- 返回当前线上工作流的统一 Markdown 文档
- 适合让助理读取后自动生成解释、技能描述、参数表单

---

## 6. Coze 工具箱接口（适合直接导入 OpenAPI）

### 6.1 总工具箱

- `GET /api/coze/podi/openapi.json`

### 6.2 ComfyUI LoRA 查询工具箱

- `GET /api/coze/podi/comfyui/lora/openapi.json`
- 推荐工具：`POST /api/coze/podi/comfyui/lora-catalog/default`

返回兼容字段：

- `loraNames`
- `lora_names`
- `untrackedNames`
- `untracked_names`

### 6.3 KIE 模型查询工具箱

- `GET /api/coze/podi/kie/catalog/openapi.json`
- 推荐工具：`POST /api/coze/podi/kie/models/list/default`

返回兼容字段：

- `modelKeys`
- `model_keys`
- `mediaTypes`
- `media_types`

### 6.4 单模型执行工具箱

示例：

- `GET /api/coze/podi/kie/execute/nano-banana-2-image-to-image/openapi.json`

### 6.5 任务轮询

`POST /api/coze/podi/tasks/get`

请求体：

```json
{
  "taskId": "t1.kie.executor_xxx.abcdef123456"
}
```

返回字段：

- `taskStatus`：`queued / running / succeeded / failed`
- `imageUrl`
- `imageUrls`
- `executorId`
- `executorName`
- `logId`
- `requestId`

---

## 7. 媒资上传接口

### 7.1 获取上传密钥

`POST /api/media/v1/upload-key`

### 7.2 获取 OSS STS

`POST /api/media/v1/sts`

### 7.3 评测端兼容上传

`POST /api/evals/uploads`

用途：

- 直接上传图片到 OSS 并返回 URL
- 最适合脚本、助理、批测工具快速接入

返回：

```json
{
  "url": "https://...",
  "objectKey": "..."
}
```

---

## 8. 关键参数约定（非常重要）

### 8.1 图片参数

统一优先使用：

- `url`
- `imageUrl`
- `image_urls`
- `input_oss_urls_json`

不同接口字段不同，不能混用。

### 8.2 展示文案 ≠ 真实传值

这是这次回归里踩过的坑，必须明确：

- `原图比例（默认）`
- `跟随原图（默认）`

这些是 **UI 展示文案**，不是模型真实枚举值。

真实调用时应该：

- 传空字符串 `""`
- 或者直接不传该字段
- 或传真实值，如 `1:1 / auto / 1K / 2K / 4K`

**绝对不要把中文展示文案直接传给模型。**

### 8.3 评测 run 的入参结构

评测接口必须使用：

- `input_oss_urls_json`
- `parameters_json`

不能用旧式 `inputs` 结构去猜测。

---

## 9. 推荐给助理的最小 Skills 组合

如果另一个助理工具要“直接能调用”，建议先生成这组 skills：

### Skill A：认证

- `POST /api/auth/login`
- `POST /api/auth/refresh`

### Skill B：能力查询与调用

- `GET /api/abilities`
- `GET /api/abilities/{abilityId}`
- `POST /api/abilities/{abilityId}/invoke`

### Skill C：异步任务

- `POST /api/ability-tasks`
- `GET /api/ability-tasks/{taskId}`
- `GET /api/ability-tasks`

### Skill D：评测工作流

- `GET /api/evals/workflow-versions`
- `POST /api/evals/runs`
- `GET /api/evals/runs/{runId}`
- `GET /api/evals/docs/workflows`
- `POST /api/evals/uploads`

### Skill E：Coze 工具箱

- `GET /api/coze/podi/openapi.json`
- `GET /api/coze/podi/comfyui/lora/openapi.json`
- `GET /api/coze/podi/kie/catalog/openapi.json`
- `POST /api/coze/podi/tasks/get`

---

## 10. 常见错误码（助理必须识别）

优先识别这些：

- `INVALID_CREDENTIALS`
- `INVALID_TOKEN`
- `ABILITY_NOT_FOUND`
- `ABILITY_EXECUTOR_NOT_CONFIGURED`
- `IMAGE_DOWNLOAD_FAILED`
- `EXPAND_MASK_RENDER_FAILED`
- `EXPAND_MASK_UPLOAD_FAILED`
- `TASK_NOT_FOUND`
- `TASK_FAILED`
- `TASK_TIMEOUT`
- `COZE_FAILED`
- `COZE_SUBMIT_FAILED`
- `Q1001`
- `Q2001`

完整错误码总表：

- `docs/standards/error-catalog.md`

---

## 11. 对接建议

- 如果是“直接调用能力”，优先走 `/api/abilities/*`
- 如果是“回归工作流 / 批量验收”，走 `/api/evals/*`
- 如果是“Coze 工具箱自动导入”，走 `/api/coze/podi/*.json`
- 如果是“另一个助理生成 skills”，优先从本文件抽取：
  - 服务地址
  - 鉴权方式
  - 核心接口
  - 参数约定
  - 错误码

---

## 12. 关联文档

- 总览：`docs/api.md`
- 模块索引：`docs/api/INDEX.md`
- 能力接口：`docs/api/abilities.md`
- 评测接口：`docs/api/modules/eval.md`
- Coze 接口：`docs/api/modules/coze.md`
- 认证接口：`docs/api/modules/auth.md`
- 上传接口：`docs/api/modules/media.md`
- 错误码：`docs/standards/error-catalog.md`
- 接口一致性：`docs/standards/interface-consistency.md`
