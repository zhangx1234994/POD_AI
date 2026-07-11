# 生产订单与蜂鸟供应链

## 边界

生产订单属于中台受控业务。客户端只创建订单并查看自己的生产文件与状态；支付确认来自支付回调；只有运营端在平台订单与生产文件核对后，才能推送蜂鸟。客户端不得持有蜂鸟密钥或直连蜂鸟。

当前可推送门禁：

1. 生产图按产品表的像素尺寸、DPI 合成并通过预检。
2. 平台支付状态为 `paid`。
3. 订单进入 `ops_review`。
4. 模板、尺码、颜色、工艺已在中台验证。当前仅 `10167 / OneSize / white / 17+2` 作为受控真实联调配置；其余模板在录入蜂鸟工艺与成功验收前会返回 `FENGNIAO_TEMPLATE_NOT_VERIFIED`。

`firstCraft=17`、`secondCraft=2` 是当前默认光油配置。5D 不在首版工艺范围内。

## POST /api/client/production-orders

创建订单时，中台会执行生产画布合成与印刷预检，并将最终生产 PNG 落 OSS。`compositionMode=seamless` 必须携带 `tiledReviewConfirmed=true`。

请求：

```json
{
  "clientRequestId": "web-checkout-001",
  "shippingAddress": {
    "recipientName": "张三",
    "phoneNumber": "13800138000",
    "country": "CN",
    "state": "江苏省",
    "city": "南京市",
    "district": "浦口区",
    "address": "天润城十六街区北区",
    "postalCode": "210000"
  },
  "items": [{
    "productName": "12oz啤酒保温杯",
    "templateNo": "10167",
    "sizeCode": "OneSize",
    "colorCode": "white",
    "firstCraft": "17",
    "secondCraft": "2",
    "viewId": "1",
    "surfaceName": "front",
    "targetWidth": 2717,
    "targetHeight": 1772,
    "targetDpi": 150,
    "quantity": 1,
    "sourceAssetUrl": "https://.../source.png",
    "compositionMode": "tile"
  }]
}
```

响应返回订单、每个生产文件 OSS URL、预检证据和状态 `awaiting_payment`。

## 订单状态

`awaiting_payment` -> `ops_review` -> `submitted_to_supplier` -> 后续蜂鸟状态同步。

- 平台支付给 AI创品，不会直接支付蜂鸟。
- `ops_review` 是运营核对订单、生产文件、平台支付和蜂鸟可定制规格的队列。
- 推送成功后保存蜂鸟订单号、平台订单号、响应摘要；若响应含效果图 URL，中台立即下载并保存到 OSS。

## 运营接口

- `GET /api/admin/production-orders`：运营表格查询。
- `POST /api/admin/production-orders/{id}/mark-paid`：仅当前支付尚未接入时的受控测试动作；正式支付上线后由支付回调调用同一服务，不开放给普通用户。
- `POST /api/admin/production-orders/{id}/submit-fengniao`：必须传 `{ "confirmProduction": true }`。成功才会调用蜂鸟 `placeOrder`。
- `POST /api/admin/production-orders/{id}/sync-fengniao`：查询蜂鸟订单状态；响应中的效果图 URL 会立即入库 OSS，再回填订单项。

## 错误

完整错误码见 `docs/standards/error-catalog.md`。重点包括：生产图尺寸/DPI 不匹配、连续图未复核、订单未支付、模板未验证、蜂鸟授权/超时/拒单。
