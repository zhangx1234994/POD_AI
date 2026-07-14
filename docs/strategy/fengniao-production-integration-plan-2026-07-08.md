# 蜂鸟生产履约接入计划（2026-07-08）

## 当前状态

已确认蜂鸟（Humcustom）使用 `POST /open/api/v1/order/placeOrder`；凭证由服务器环境变量管理，绝不写入仓库。平台订单由用户先支付给 AI创品，支付回调确认成功后自动推蜂鸟创建待确认订单；运营随后比对 AI创品与蜂鸟两边数据，并在蜂鸟后台确认生产、完成供应链付款和快递选择。本站运营端负责对账、同步和失败重试。

2026-07-12 起，中台已增加真实生产订单骨架：生产图按表格像素/DPI 生成并预检、保存 OSS 证据、支付成功自动推送、保存供应商订单号和响应中可识别的效果图。历史真实联调曾收到“商品模板不支持定制”，因此模板/工艺/颜色必须通过成功验收后才允许推单，不能依据页面展示或本地模型猜测。

## 需要向蜂鸟确认的资料

- API 文档、沙箱地址、生产地址、鉴权方式、签名规则、IP 白名单。
- 商品目录接口：类目、SPU/SKU、价格、库存/产能、起订量、工期、可印刷区域、设计稿尺寸、工艺、材质、颜色、包装。
- 文件要求：图片格式、像素、DPI、色彩模式、出血、安全区、文件命名、压缩包结构、上传方式。
- 报价接口：单件、批量、产品券/优惠是否在我们侧计算。
- 下单接口：收货信息、发票、备注、生产文件、样例确认图、幂等键。
- 状态接口或回调：接单、待生产、生产中、质检、发货、异常、取消、退款、售后。
- 物流接口：承运商、单号、轨迹、拆单、多包裹。
- 售后接口：破损、错印、漏印、质量照片、重做、退款。
- 对账接口：订单金额、生产费、物流费、退款、赔付、月结。
- 限流、超时、错误码、重试建议。

## 我们侧订单状态

| 我们侧状态 | 含义 | 蜂鸟映射 |
| --- | --- | --- |
| `draft` | 草稿，未确认产品和图片 | 不提交 |
| `sample_ready` | 样例图/生产文件已生成 | 不提交 |
| `awaiting_payment` | 等待支付或产品券确认 | 不提交 |
| `supplier_pending` | 已支付，等待平台自动提交 | 准备提交 |
| `supplier_retry` | 自动提交失败，等待平台重试 | 未成功或结果待确认 |
| `submitted_to_supplier` | 平台已推送蜂鸟，等待运营核对 | 蜂鸟待确认订单已创建 |
| `producing` | 工厂生产中 | 蜂鸟生产中 |
| `quality_check` | 质检中或等待质检结果 | 蜂鸟质检 |
| `shipped` | 已发货 | 蜂鸟物流单号回填 |
| `delivered` | 已签收 | 物流签收 |
| `aftersale_open` | 售后中 | 蜂鸟售后/重做/退款 |
| `completed` | 完结 | 完结 |
| `refunded` | 已退款 | 退款完成 |

## 证据链

正式下单前必须保存：

- 用户原图、AI 生成图、最终生产图、样例确认图。
- 产品 ID、SKU、设计面 ID、设计尺寸、可印刷区域、安全区、工艺。
- 用户确认记录：款式、数量、收货信息、定制商品确认、费用、产品券/抵扣。
- 生产文件包 manifest、文件 URL、hash、生成时间。
- 蜂鸟请求摘要、响应摘要、外部订单号、幂等键。
- 生产状态、质检图片/结果、物流单号、售后沟通。

## 接口边界

P0 建议后端新增受控服务，不让客户端直连蜂鸟：

- `POST /api/production/fengniao/quote`：报价和工期预估。
- `POST /api/production/fengniao/preflight`：生产文件和字段预检。
- `POST /api/production/fengniao/orders`：正式下单，必须带用户确认 token 和幂等键。
- `GET /api/production/fengniao/orders/{orderId}`：查询蜂鸟状态。
- `POST /api/production/fengniao/callback`：接收蜂鸟回调。
- `POST /api/production/fengniao/orders/{orderId}/aftersale`：售后发起。

## 错误契约初稿

- `FENGNIAO_AUTH_FAILED`：鉴权失败。
- `FENGNIAO_PRODUCT_NOT_FOUND`：商品或 SKU 不存在。
- `FENGNIAO_PRODUCT_UNAVAILABLE`：商品不可生产、库存/产能不足或已下架。
- `FENGNIAO_FILE_INVALID`：生产文件不符合尺寸、格式、安全区或工艺要求。
- `FENGNIAO_QUOTE_CHANGED`：报价或工期变化，需要用户重新确认。
- `FENGNIAO_ORDER_DUPLICATE`：幂等键重复，返回已有订单。
- `FENGNIAO_ORDER_REJECTED`：蜂鸟拒单。
- `FENGNIAO_TIMEOUT`：请求超时，进入可恢复查询。
- `FENGNIAO_CALLBACK_INVALID`：回调签名或字段无效。
- `FENGNIAO_AFTERSALE_REJECTED`：售后申请被拒。

这些错误码正式落地时必须同步 `docs/standards/error-catalog.md` 和接口文档。

## 下一步

1. 向蜂鸟拿 API、商品目录、文件规范、沙箱和测试账号。
2. 把当前 `podi-client-web/src/data/cup-products.ts` 的杯子模板字段映射到蜂鸟商品/版型字段。
3. 先做 `quote + preflight`，不直接下单。
4. 选 3 个杯型跑完整沙箱：生成样例、生产文件、预检、报价、下单、状态回调。
5. 再把订单页从模拟状态改成真实状态。

最后更新：2026-07-08
