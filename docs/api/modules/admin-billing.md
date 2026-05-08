# 管理端账单 / 套餐 / 月结接口

> 状态：运营骨架已接入。当前目标是让管理端能看到真实钱包、套餐、月结、发票和通知记录；真实支付网关、自动开票、外部通知推送属于后续阶段。

## 统一约定

- 前缀：`/api/admin/billing`
- 鉴权：管理员登录态或服务 token，非管理员返回 `ADMIN_ONLY`
- 金额单位：`amountCents` 为分，钱包 `points` 为点数
- 套餐单位：`units` 为可用次数，`remainingUnits = totalUnits - usedUnits - frozenUnits`
- 月份格式：`YYYY-MM`
- 通知接口当前只记录动作和草稿，不真实推送外部群机器人

## GET /api/admin/billing/overview

用途：账单页总览，聚合用户钱包、套餐余量、计费异常和套餐风险。

查询参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `month` | 否 | 账单月份，默认当前月 |
| `window_days` | 否 | 统计窗口，默认 30 |
| `tenant_id` | 否 | 业务租户过滤 |
| `client_id` | 否 | 业务方过滤 |
| `business_key` | 否 | 业务能力过滤 |
| `limit` | 否 | 用户条数，默认 100 |
| `issue_limit` | 否 | 计费问题条数 |
| `package_alert_limit` | 否 | 套餐风险条数 |

响应要点：

```json
{
  "month": "2026-05",
  "totalUsers": 1,
  "totalBalance": 500,
  "totalPackageRemainingUnits": 30,
  "issueCount": 1,
  "issues": [
    {
      "runId": "run_xxx",
      "issueType": "wallet_missing",
      "issueLabel": "成功任务未扣费"
    }
  ],
  "packageAlertCount": 1,
  "packageAlerts": [],
  "items": []
}
```

## GET /api/admin/billing/commercial-report

用途：商业化报表雏形，用于同一账期内核对“订单收入、任务成本、扣费完成度、计费风险”。当前不替代正式财务报表，只作为上线前运营复核入口。

查询参数：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `month` | 否 | 账单月份，默认当前月 |
| `tenant_id` | 否 | 业务租户过滤 |
| `client_id` | 否 | 业务方过滤 |
| `business_key` | 否 | 业务能力过滤 |
| `limit` | 否 | 纳入统计的业务任务上限，默认 1000，最大 5000 |

响应要点：

```json
{
  "month": "2026-05",
  "status": "blocked",
  "statusLabel": "需先处理风险",
  "nextAction": "先补模型成本规则，再重试扣费。",
  "runCount": 20,
  "billableRunCount": 18,
  "chargedRunCount": 16,
  "noChargeRunCount": 1,
  "unpricedRunCount": 1,
  "billingIssueCount": 2,
  "costByCurrency": [{ "currency": "USD", "amount": 1.24 }],
  "paidPackageOrderCount": 3,
  "packageOrderRevenueByCurrency": [{ "currency": "CNY", "amountCents": 59700 }],
  "businessRows": [
    {
      "businessKey": "fission",
      "runCount": 12,
      "chargedRunCount": 10,
      "noChargeRunCount": 1,
      "billingIssueCount": 1
    }
  ],
  "riskItems": []
}
```

计费口径：

- `billableRunCount` 只统计真实应收费任务；成功但标记为内部巡检、免计费或测试来源的任务进入 `noChargeRunCount`。
- `billingIssueCount` 只统计需要运营处理的问题：成功任务未扣费、扣费失败、免计费任务被误扣费、成功任务缺少定价。
- 内部巡检的典型标识为 `source=business-api-patrol`、`tenantId=podi-internal-patrol`、`metadata.patrol=true`，这些任务可记录成本和输出，但不阻断收费门禁。

错误：

| 错误码 | 场景 |
| --- | --- |
| `BILL_MONTH_INVALID` | `month` 不是 `YYYY-MM` |
| `ADMIN_ONLY` | 非管理员访问 |

### GET /api/admin/billing/commercial-report/export

用途：导出同一口径的商业化报表 CSV，便于运营、财务和上线复核留档。

查询参数同 `/commercial-report`。响应为 `text/csv; charset=utf-8`，包含三段内容：

- 报表摘要：账期、状态、下一步、收入、成本、套餐消耗、计费风险。
- 业务明细：按业务能力聚合任务数、成功数、可计费数、已扣费数、未定价数和成本。
- 风险任务：存在计费风险时列出最近风险样本，方便回到管理端处理。

错误：

| 错误码 | 场景 |
| --- | --- |
| `BILL_MONTH_INVALID` | `month` 不是 `YYYY-MM` |
| `ADMIN_ONLY` | 非管理员访问 |

## 套餐目录和定价

### GET /api/admin/billing/package-catalog

用途：查看后台可售或可发放的套餐规则。订单和人工发放只填 `packageKey` 时，会自动复用启用中的目录默认值。

查询参数：`business_key`、`status`、`limit`

响应：

```json
{
  "total": 1,
  "items": [
    {
      "packageKey": "fission-pro",
      "packageName": "图裂变正式套餐",
      "businessKey": "fission",
      "units": 300,
      "unitName": "次",
      "amountCents": 19900,
      "currency": "CNY",
      "validityDays": 30,
      "status": "active"
    }
  ]
}
```

### POST /api/admin/billing/package-catalog

用途：创建或覆盖套餐规则。

请求：

```json
{
  "packageKey": "fission-pro",
  "packageName": "图裂变正式套餐",
  "businessKey": "fission",
  "description": "图裂变主线生产套餐",
  "units": 300,
  "unitName": "次",
  "amountCents": 19900,
  "currency": "CNY",
  "validityDays": 30,
  "status": "active",
  "sortOrder": 100
}
```

### PATCH /api/admin/billing/package-catalog/{packageKey}

用途：修改已有套餐规则。停用后不再作为订单/发放默认值来源，但历史订单和余额不受影响。

错误：

| 错误码 | 场景 |
| --- | --- |
| `PACKAGE_KEY_REQUIRED` | 缺少套餐标识 |
| `PACKAGE_CATALOG_NAME_REQUIRED` | 缺少套餐名称 |
| `PACKAGE_UNITS_INVALID` | 套餐额度非法 |
| `PACKAGE_AMOUNT_INVALID` | 套餐金额小于 0 |
| `PACKAGE_VALIDITY_DAYS_INVALID` | 有效期天数小于等于 0 |
| `PACKAGE_CATALOG_STATUS_INVALID` | 状态不是 `active/inactive` |
| `PACKAGE_CATALOG_NOT_FOUND` | 修改的套餐规则不存在 |

## GET /api/admin/billing/users/{userId}

用途：查看单个用户的钱包、账单、使用量、钱包流水、套餐余量和套餐流水。

查询参数：`month`、`window_days`、`business_key`、`page_size`

响应要点：

```json
{
  "user": { "id": "user_1", "username": "client-a" },
  "balance": { "balance": 500, "frozenBalance": 0 },
  "bill": { "income": 0, "expense": 0, "net": 0 },
  "ledger": { "items": [] },
  "packageBalances": { "totalRemainingUnits": 30, "items": [] },
  "packageLedger": { "items": [] }
}
```

## POST /api/admin/billing/users/{userId}/packages/grant

用途：人工发放套餐额度。带 `traceId` 时按用户 + `traceId` 幂等，重复提交不会重复加额度。

说明：如果请求只传 `packageKey` 和 `traceId`，系统会尝试读取启用中的套餐目录，自动填充 `packageName/businessKey/units/unitName/expiresAt`。

请求：

```json
{
  "packageKey": "fission-basic",
  "packageName": "图裂变基础包",
  "businessKey": "fission",
  "units": 30,
  "unitName": "次",
  "expiresAt": "2026-06-01T00:00:00",
  "traceId": "ops-20260504-001",
  "description": "运营补发"
}
```

响应：

```json
{
  "transactionId": "pkg_txn_1",
  "packageBalanceId": "1",
  "granted": 30,
  "remainingUnits": 30,
  "idempotent": false,
  "packageBalances": {},
  "packageLedger": {}
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `PACKAGE_KEY_REQUIRED` | 缺少套餐标识 |
| `PACKAGE_UNITS_INVALID` | 发放额度小于等于 0 |
| `BILLING_DATETIME_INVALID` | `expiresAt` 时间格式非法 |

## 套餐购买订单

### GET /api/admin/billing/package-purchase-orders

查询参数：`status`、`user_id`、`business_key`、`limit`

### POST /api/admin/billing/package-purchase-orders

用途：创建线下套餐购买订单。当前不接支付网关，订单支付状态由管理员更新。

说明：如果请求只传 `userId` 和 `packageKey`，系统会尝试读取启用中的套餐目录，自动填充套餐名称、业务、额度、金额、币种和到期时间。

请求：

```json
{
  "userId": "user_1",
  "packageKey": "outpaint-basic",
  "packageName": "扩图基础包",
  "businessKey": "outpaint",
  "units": 10,
  "amountCents": 9900,
  "currency": "CNY",
  "channel": "offline"
}
```

### PATCH /api/admin/billing/package-purchase-orders/{orderId}

用途：更新订单状态。首次改为 `paid` 会自动调用套餐发放，使用 `package_order:{orderId}` 做幂等键。

请求：

```json
{
  "status": "paid",
  "paymentReference": "bank-002",
  "transactionId": "txn_001",
  "note": "线下收款确认"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `BILLING_USER_ID_REQUIRED` | 创建订单缺少用户 ID |
| `PACKAGE_KEY_REQUIRED` | 创建订单缺少套餐标识 |
| `PACKAGE_UNITS_INVALID` | 套餐额度非法 |
| `PACKAGE_PURCHASE_ORDER_NOT_FOUND` | 订单不存在 |
| `PACKAGE_PURCHASE_ORDER_STATUS_INVALID` | 状态不是 `pending/paid/cancelled/failed` |

## 月结

### GET /api/admin/billing/monthly-settlement

用途：生成月结预览，不落库。

### GET /api/admin/billing/monthly-settlements

用途：查看已出账记录。

查询参数：`month`、`status`、`limit`

### POST /api/admin/billing/monthly-settlements/issue

用途：按月份 + 租户 + 业务方 + 业务能力出账。相同范围重复出账返回 `idempotent=true`。

请求：

```json
{
  "month": "2026-05",
  "tenantId": "tenant-a",
  "clientId": "client-a",
  "businessKey": "fission",
  "windowDays": 30,
  "note": "五月图裂变月结"
}
```

### PATCH /api/admin/billing/monthly-settlements/{settlementId}

用途：更新月结记录为已回款或取消。

请求：

```json
{
  "status": "paid",
  "paymentReference": "bank-001",
  "note": "已线下收款"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `BILL_MONTH_INVALID` | 月份格式非法 |
| `MONTHLY_SETTLEMENT_NOT_FOUND` | 月结记录不存在 |
| `MONTHLY_SETTLEMENT_STATUS_INVALID` | 状态不是 `issued/paid/cancelled` |

## 发票申请

### GET /api/admin/billing/invoice-requests

查询参数：`status`、`business_key`、`user_id`、`related_order_type`、`limit`

### POST /api/admin/billing/invoice-requests

请求：

```json
{
  "relatedOrderType": "package_purchase_order",
  "relatedOrderId": "pkg_order_xxx",
  "userId": "user_1",
  "invoiceTitle": "上海测试公司",
  "amountCents": 9900,
  "currency": "CNY",
  "deliveryEmail": "finance@example.com"
}
```

### PATCH /api/admin/billing/invoice-requests/{invoiceRequestId}

请求：

```json
{
  "status": "issued",
  "invoiceNo": "INV-001",
  "note": "电子发票已发送"
}
```

错误：

| 错误码 | 场景 |
| --- | --- |
| `BILLING_INVOICE_TITLE_REQUIRED` | 创建申请缺少发票抬头 |
| `BILLING_INVOICE_REQUEST_NOT_FOUND` | 发票申请不存在 |
| `BILLING_INVOICE_STATUS_INVALID` | 状态不是 `requested/issued/cancelled` |

## 通知与催收

### GET /api/admin/billing/notification-config

用途：查看账单通知通道配置。

### PATCH /api/admin/billing/notification-config

请求：

```json
{
  "channels": [
    {
      "key": "ops-webhook",
      "enabled": true,
      "webhookUrl": "https://example.com/webhook",
      "webhookFormat": "generic"
    }
  ]
}
```

错误：`BILLING_NOTIFICATION_CONFIG_INVALID`

### POST /api/admin/billing/package-alerts/notify

用途：生成套餐低余额/临期提醒记录。

### GET /api/admin/billing/package-alert-notifications

用途：查看套餐提醒记录。

### POST /api/admin/billing/monthly-settlements/collections/notify

用途：生成月结回款提醒记录。

### GET /api/admin/billing/monthly-settlement-collection-notifications

用途：查看月结回款提醒记录。

## GET /api/admin/billing/users/{userId}/ledger/export

用途：导出用户钱包流水 CSV。当前导出钱包流水，套餐流水在用户详情中查看。

查询参数：`month`、`business_key`

错误总表：见 `docs/standards/error-catalog.md`。
