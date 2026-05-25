# 图编辑业务交付包

本目录面向业务方交付 `image_edit` 图编辑业务接口。图编辑是“组件工作台 + 中台业务 API + GPT Image 2 编辑能力”的组合业务，业务方不直接调用 OpenAI，也不需要理解底层提示词编译。

权威口径：

- 参数和枚举：`docs/standards/business-api-enums.md`
- 错误码：`docs/standards/error-catalog.md`
- 统一查询：`POST /api/business/runs/get`

## 交付接口

| 目录 | 能力 | 提交接口 | 查询接口 |
| --- | --- | --- | --- |
| `01_gpt_image2_editor` | 图编辑 · GPT Image 2 通用改图 | `POST /api/business/image-edit/runs` | `POST /api/business/runs/get` |

## 通用约定

- 所有请求使用 `X-PODI-API-Key` 鉴权。
- 提交接口返回 `runId` 和 `status`；业务方按 `retryAfterSeconds` 轮询 `/api/business/runs/get`。
- 终态 `status` 为 `succeeded` 或 `failed`。
- 成功时读取 `imageUrls`，失败时读取 `errorCode/errorMessage`。
- 图编辑默认一次生成 1 张图；需要多张结果时提交多次，每次保存独立 `runId`。

## 错误码

常见错误码在子目录 README 中列出；完整错误码以 `docs/standards/error-catalog.md` 为准。
