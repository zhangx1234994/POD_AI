# PODI Business API

本服务是主站业务系统的本地闭环 API，不是 8099 中台。

## 边界

- 业务 API：登录、用户、素材、任务、产品试做订单、钱包、公开申请、多站点业务配置。
- 中台 8099：能力目录、能力路由、执行节点、ComfyUI/vendor 调用、回调、OSS 结果回填、能力日志。
- 主站前端只直连业务 API；真实图片能力由业务 API 受控调用中台。

## 本地启动

```bash
python3 podi-business-api/server.py --host 127.0.0.1 --port 8240
```

健康检查：

```bash
curl http://127.0.0.1:8240/health
```

未配置短信服务时，本地验证码仍使用 `PODI_TEST_SMS_CODE`（默认 `123456`）。配置阿里云短信后，验证码会真实发送到用户手机，不再在接口中返回测试码。本地媒体上传会写入 `podi-business-api/.data/uploads/`，只用于本机闭环测试。

手机号验证码是主站统一账号入口：用户输入验证码后，如果手机号已存在则直接登录；如果手机号不存在则自动创建账号，默认昵称按 `创品达人 + 6 位ID` 生成。当前入口不要求用户理解“注册”和“邀请码”，邀请码/渠道码后续作为活动归因单独处理。

## 手机号登录短信

真实短信通过阿里云短信 `SendSms` 接口发送。真实密钥只允许配置到服务器环境变量或本地忽略文件，不写入仓库。

```bash
ALIYUN_SMS_ACCESS_KEY_ID=<required>
ALIYUN_SMS_ACCESS_KEY_SECRET=<required>
ALIYUN_SMS_SIGN_NAME=西安郁郁芊芊科技
ALIYUN_SMS_LOGIN_TEMPLATE_CODE=SMS_500500023
ALIYUN_SMS_IMAGE_LOGIN_TEMPLATE_CODE=SMS_500595029
ALIYUN_SMS_TEMPLATE_PARAM_NAME=code
PODI_SMS_CODE_EXPIRES_SECONDS=300
PODI_SMS_RESEND_INTERVAL_SECONDS=60
PODI_SMS_DAILY_LIMIT_PER_PHONE=10
PODI_SMS_MAX_VERIFY_ATTEMPTS=5
```

上线前需要确认短信模板变量名是否为 `${code}`。如阿里云模板使用其他变量名，只改 `ALIYUN_SMS_TEMPLATE_PARAM_NAME` 即可。

## 中台代理

默认不代理中台能力，批处理会返回本地闭环结果。需要接真实中台时设置：

```bash
PODI_MIDPLATFORM_BASE_URL=http://127.0.0.1:8099 \
PODI_MIDPLATFORM_API_KEY=你的中台业务Key \
python3 podi-business-api/server.py --port 8240
```

注意：真实中台能力要求输入图片为公网可访问 OSS URL；本地 `127.0.0.1:8240/media/uploads/*` 只能用于本地闭环，不适合远程中台拉取。

## AI 设计 VL 路由

`AI 帮我设计` 的会话、上下文、规划和确认点归业务 API 管理；VL 也先由业务 API 直连模型服务。Image2、ComfyUI、连续图、OSS 回填等出图能力继续通过中台能力调用。

当前业务默认只路由到中台内已验证的 Packy Image 2 能力：`packy_gpt_image_2_generate` 和 `packy_gpt_image_2_edit`。旧官方 OpenAI GPT Image 2 与 Seedream 目录条目仅保留审计，不允许进入自动业务路由。新增中转供应商时，先在中台完成能力测试、OSS 回填和错误契约验证，再更新业务 API 的受控能力 ID；前端不得直连厂商。

默认不调用外部 VL，使用本地规则保持闭环。需要启用豆包 VL 时设置：

```bash
PODI_AGENT_VL_PROVIDER=volcengine-doubao-lite \
VOLCENGINE_ARK_API_KEY=你的火山方舟Key \
python3 podi-business-api/server.py --port 8240
```

可选模型配置：

```bash
PODI_AGENT_VL_MODEL=doubao-seed-2-0-lite-260428
PODI_AGENT_PLANNER_MODEL=doubao-seed-2-1-turbo-260628
```

路由建议：

- `volcengine-doubao-lite`：默认图片理解，成本低，适合判断图片类型、质量、是否适合提花纹/环绕。
- `volcengine-doubao-turbo`：复杂规划或低置信复核，适合多图、多贴图面和复杂需求。
- GPT 系模型先作为后续质量标尺和兜底，不作为当前默认主路由。

模型返回只作为规划证据。最终能力调用仍由业务 API 做白名单、Schema、费用估算、用户确认、幂等和队列控制。
