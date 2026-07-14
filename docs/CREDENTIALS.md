# 凭证配置清单

> 本文件只记录“需要哪些凭证、放在哪里、如何轮换”，不记录真实账号、密码、密钥或临时令牌。真实凭证必须放在服务器环境变量、部署平台密钥、数据库加密字段，或本地忽略文件 `docs/CREDENTIALS.local.md`。

## 1. 硬性规则

- 不允许把真实 `API Key`、`AccessKey`、账号密码、回调令牌提交到仓库。
- 示例值只能使用 `${ENV_NAME}`、`<placeholder>` 或已公开的接口域名。
- 如果线上密钥已经误入历史提交，处理顺序是：先轮换密钥，再清理当前文件，最后评估是否需要重写历史。
- 新增第三方能力时，必须同步补充本文件的环境变量清单和轮换说明。

## 2. 当前凭证来源

| 类型 | 当前推荐位置 | 说明 |
| --- | --- | --- |
| 后端运行密钥 | 服务器 `.env` 或系统环境变量 | `backend`、`vendor-api-ops`、`image-ops-service` 运行时读取 |
| 执行节点配置 | `config/executors.yaml` 或管理端执行节点 | 只允许引用环境变量，不直接写真实密钥 |
| 第三方能力密钥 | 中台加密保存或服务器环境变量 | 后续由管理端密钥页统一维护 |
| 本地联调密钥 | `docs/CREDENTIALS.local.md` | 已加入 `.gitignore`，只在个人机器存在 |

## 3. 阿里云 / OSS

### 必需配置

```bash
ALIYUN_ACCESS_KEY_ID=<required>
ALIYUN_ACCESS_KEY_SECRET=<required>
ALIYUN_OSS_KEY_ID=<required>
ALIYUN_OSS_KEY_SECRET=<required>
```

### OSS 运行参数

```bash
ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
ALIYUN_OSS_INTERNAL_ENDPOINT=oss-cn-hangzhou-internal.aliyuncs.com
ALIYUN_OSS_BUCKET=podi
ALIYUN_OSS_PUBLIC_DOMAIN=https://podi.oss-cn-hangzhou.aliyuncs.com
ALIYUN_OSS_ROOT_PREFIX=test
```

### 维护要求

- 对外返回继续使用公网稳定地址。
- 内网地址只用于中台、Coze 同机服务、执行节点之间的内部下载提速。
- STS 临时凭证必须按用户、目录、有效期限制权限。
- RAM 信任策略和临时密钥失效流程仍需单独收紧。

## 4. 百度智能云

### 必需配置

```bash
BAIDU_API_KEY=<required>
BAIDU_SECRET_KEY=<required>
BAIDU_ACCESS_KEY=<optional>
BAIDU_PLATFORM_API_KEY=<optional>
```

### 已接能力

- 无损放大
- 老照片上色
- 摩尔纹去除
- 拉伸修复
- 去雾增强
- 对比度增强
- 去噪

### 维护要求

- 能力节点在 `config/executors.yaml` 中声明，数据库执行节点只保存可追溯配置。
- 调用失败时必须区分鉴权失败、额度不足、限流和上游异常。

## 5. 火山引擎

### 必需配置

```bash
VOLCENGINE_API_KEY=<required>
VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com
```

### 已接能力

- Doubao Seed 多模态理解
- Seedream 文生图
- Seedance 图生视频
- 火山模型列表同步

### 维护要求

- 模型列表同步接口读取 `VOLCENGINE_API_KEY`，不得在前端或文档中输出真实值。
- 生图、生视频、文字/VL 能力需要在能力目录中明确区分。

## 6. KIE 中转站

### 必需配置

```bash
KIE_API_KEY=<required>
KIE_BASE_URL=https://api.kie.ai
```

### 已接能力

- Nano Banana Pro 图生图
- Flux-2 Pro 图生图
- Sora2 Pro 文生视频

### 维护要求

- KIE 余额和额度监控暂缓，但错误必须能明确提示“余额不足/额度不足/上游限流”。
- 创建任务和轮询结果必须保留 `taskId`，便于和中台任务追踪关联。

## 7. OpenAI / 兼容中转

### 必需配置

```bash
OPENAI_API_KEY=<required>
OPENAI_BASE_URL=<optional>
OPENAI_ORG_ID=<optional>
OPENAI_PROJECT_ID=<optional>
```

### 维护要求

- OpenAI、兼容中转、代理出口都归入第三方能力管理，不直接写入业务代码。
- 支持蒙版、多图、同步返回、异步轮询的模型，都必须通过能力 schema 单独描述参数。
- 对外仍统一为“提交任务 -> 查询结果”，不让业务方感知厂商差异。

## 8. 微信支付

### 必需配置

```bash
WECHAT_PAY_APP_ID=<required>
WECHAT_PAY_MCH_ID=<required>
WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH=<required>
WECHAT_PAY_MERCHANT_CERT_SERIAL=<required>
WECHAT_PAY_API_V3_KEY=<required>
WECHAT_PAY_PUBLIC_KEY_PATH=<required>
WECHAT_PAY_PUBLIC_KEY_ID=<required>
WECHAT_PAY_NOTIFY_URL=https://aichuangpin.com/api/client/v1/payments/wechat/notify
```

### 维护要求

- 商户 API 证书不能代替配套的商户 API 私钥；`APIv3 Key` 用于回调报文解密。
- 优先使用微信支付公钥与公钥 ID 验签；如采用平台证书模式，必须记录证书轮换和过期检查。
- 回调必须验签、解密、核对商户号/AppID/订单号/金额，并按支付单号幂等处理。
- 私钥、`APIv3 Key`、证书正文不得进入仓库或前端构建产物。

## 9. 支付宝

### 必需配置

```bash
ALIPAY_APP_ID=<required>
ALIPAY_APP_PRIVATE_KEY_PATH=<required>
ALIPAY_PUBLIC_KEY_PATH=<required-for-public-key-mode>
ALIPAY_ROOT_CERT_PATH=<required-for-certificate-mode>
ALIPAY_APP_CERT_PATH=<required-for-certificate-mode>
ALIPAY_PUBLIC_CERT_PATH=<required-for-certificate-mode>
ALIPAY_GATEWAY=https://openapi.alipay.com/gateway.do
ALIPAY_NOTIFY_URL=https://aichuangpin.com/api/client/v1/payments/alipay/notify
ALIPAY_RETURN_URL=https://aichuangpin.com/orders?payment=alipay
```

### 维护要求

- 普通公钥模式和证书模式二选一，不允许混用配置。
- `notify_url` 是支付异步通知地址，不是 OAuth 授权回调地址或应用网关。
- 回调必须验签、核对 `app_id/out_trade_no/total_amount/trade_status` 并按支付宝交易号幂等处理，成功时仅返回纯文本 `success`。
- 私钥一旦进入聊天、日志、工单或 Git，必须先轮换再联调。

## 10. 轮换与泄露处理

1. 立即禁用或轮换疑似泄露密钥。
2. 更新服务器环境变量或管理端密钥配置。
3. 重启相关服务并跑能力自检。
4. 检查调用日志，确认没有继续使用旧密钥。
5. 如果密钥进入 Git 历史，记录影响范围，再决定是否执行历史清理。

## 11. 文档维护规则

- 本文件变更必须和能力接入、执行节点、部署说明保持一致。
- 新增供应商时，只补充配置项、能力范围、错误分类和轮换方式。
- 真实密钥只允许进入 `docs/CREDENTIALS.local.md` 或受控密钥系统。

*最后更新: 2026-07-14*
