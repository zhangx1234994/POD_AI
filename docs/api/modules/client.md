# 普通业务端 Client API

> 状态：P0.1 已接入第一批服务端数据真源接口。该模块面向 `podi-client-web/` 和后续主题站，不暴露中台 project/run/executor/workflow 等工程概念。

## 统一约定

- 前缀：`/api/client`
- 鉴权：用户登录 Bearer Token，缺失返回 `AUTHORIZATION_REQUIRED`
- 当前实现：复用后端 `business_projects` / `business_project_assets` / `wallet_accounts` / `package_balances`
- 默认工作区：每个用户自动创建一个 `client_default_workspace`，前台称为“素材工作区”
- 产品券：P0.1 暂从套餐余额中过滤映射，后续如规则复杂再拆独立产品券表

---

## GET /api/client/me

用途：返回当前登录用户和默认素材工作区。前台启动时应先调用此接口，建立用户态和服务端数据真源。

响应：

```json
{
  "user": {
    "id": "user_1",
    "username": "designer",
    "email": "designer@example.com",
    "displayName": "设计师",
    "role": "user",
    "status": "active",
    "tenantId": "tenant-podi",
    "clientId": "podi-main"
  },
  "workspace": {
    "id": "proj_xxx",
    "name": "默认素材工作区",
    "scenario": "client_default_workspace",
    "status": "active",
    "assetCount": 0,
    "runCount": 0,
    "latestRunStatus": null,
    "createdAt": "2026-07-08T10:00:00",
    "updatedAt": "2026-07-08T10:00:00"
  }
}
```

错误：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` | 401 | 未登录 |
| `INVALID_TOKEN` / `INVALID_TOKEN_PAYLOAD` | 401 | Token 无效 |
| `USER_NOT_FOUND` | 404 | Token 对应用户不存在 |
| `USER_INACTIVE` | 403 | 用户被禁用 |

---

## GET /api/client/workspace

用途：获取当前用户默认素材工作区。接口幂等，不存在时自动创建。

响应同 `/me.workspace`。

错误同 `/me`。

---

## GET /api/client/assets

用途：列出当前用户素材。前台素材库、商品页选图、后续任务结果回填都应读这里。

查询参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `asset_type` | 否 | 资产类型，如 `input_image` / `pattern` / `product_image` |
| `selected` | 否 | 是否只看已选素材 |
| `limit` | 否 | 默认 100，最大 200 |

响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": "asset_xxx",
      "assetType": "input_image",
      "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
      "contentType": "image/png",
      "fileName": "input.png",
      "title": "上传原图",
      "sourceRunId": null,
      "sourceBusinessKey": null,
      "sourceFlowStepKey": "upload",
      "qualityGrade": null,
      "inputTags": [],
      "issueTags": [],
      "selected": false,
      "metadata": {},
      "createdAt": "2026-07-08T10:00:00",
      "updatedAt": "2026-07-08T10:00:00"
    }
  ]
}
```

错误：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` | 401 | 未登录 |
| `PROJECT_ASSET_TYPE_INVALID` | 400 | `asset_type` 不在允许枚举 |

---

## POST /api/client/assets

用途：创建用户素材记录。P0.1 接受已经上传到 OSS 或公网可访问的图片 URL；后续真实上传仍先走媒资接口，再调用本接口沉淀为用户素材。

请求：

```json
{
  "assetType": "input_image",
  "url": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
  "contentType": "image/png",
  "fileName": "input.png",
  "flowStepKey": "upload",
  "inputTags": ["原图"],
  "metadata": {
    "title": "上传原图"
  }
}
```

响应：单个素材对象，字段同 `/assets.items[]`。

错误：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` | 401 | 未登录 |
| `PROJECT_ASSET_TYPE_INVALID` | 400 | `assetType` 不在允许枚举 |
| `PROJECT_ASSET_URL_REQUIRED` | 400 | 缺少 `url` |
| `PROJECT_ASSET_URL_INVALID` | 400 | URL 不是合法 `http/https` 地址 |

---

## GET /api/client/wallet

用途：返回前台钱包视图，包括 AI 积分、冻结积分和产品券。P0.1 产品券由套餐余额映射。

响应：

```json
{
  "pointBalance": 500,
  "frozenPoints": 0,
  "currency": "CNY",
  "productCouponCount": 1,
  "productCoupons": [
    {
      "id": "pkg_balance_1",
      "packageKey": "sample_coupon_new_user",
      "name": "新人产品券",
      "businessKey": "sample_request",
      "totalUnits": 3,
      "usedUnits": 1,
      "frozenUnits": 1,
      "remainingUnits": 1,
      "unitName": "张",
      "status": "active",
      "source": "manual",
      "expiresAt": "2026-07-15T10:00:00",
      "metadata": {
        "couponType": "product"
      }
    }
  ],
  "ledger": []
}
```

错误：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `AUTHORIZATION_REQUIRED` | 401 | 未登录 |
| `USER_NOT_FOUND` | 404 | Token 对应用户不存在 |
| `USER_INACTIVE` | 403 | 用户被禁用 |

## 回归要求

- `GET /api/client/me` 连续调用必须返回同一个默认工作区。
- `POST /api/client/assets` 成功后，`GET /api/client/assets` 必须能查到。
- `/wallet.productCouponCount` 必须等于产品券剩余数量汇总，不统计普通 AI 次数包。
- 错误路径至少覆盖未登录、非法资产类型、缺少 URL、非法 URL。
