# 凭证速查

> 说明：以下内容仅供联调阶段使用，所有 Key 已记录在此文档，便于管理端或本地开发配置。上线前请按安全要求替换为正式密钥、接入 KMS/Secret Manager，并更新策略与有效期。

## 阿里云

- RAM 账号：`<ram-account>@<tenant>.onaliyun.com`
- RAM 密码：`<ram-password>`
- 账号角色：`CLTZ`
- 角色 ARN：`acs:ram::<tenant>:role/<role>`
- 信任策略：
  ```json
  {
    "Statement": [
      {
        "Action": ["sts:AssumeRole", "sts:SetSourceIdentity"],
        "Effect": "Allow",
        "Principal": { "RAM": ["acs:ram::<tenant>:root"] }
      }
    ],
    "Version": "1"
  }
  ```
- AccessKey（全局）：
  - `AccessKeyId = ${ALIYUN_ACCESS_KEY_ID}`
  - `AccessKeySecret = ${ALIYUN_ACCESS_KEY_SECRET}`

### OSS 配置

```
aliyun.oss.endpoint = oss-cn-hangzhou.aliyuncs.com
aliyun.oss.access-key-id = ${ALIYUN_OSS_KEY_ID}
aliyun.oss.access-key-secret = ${ALIYUN_OSS_KEY_SECRET}
aliyun.oss.bucket = podi
aliyun.oss.public-domain = https://podi.oss-cn-hangzhou.aliyuncs.com
aliyun.oss.root-prefix = test
```

> 后台上传全部经 OSS 统一落地，建议为前端用户下发 STS 临时凭证，并按用户/日期归档（`podi/<user>/YYYYMMDD/`）。

## 百度智能云

- API Key：`<baidu-api-key>`
- Secret Key：`<baidu-secret-key>`
- Access Key：`<baidu-access-key>`
- 平台 API Key（bce-v3）：`<baidu-platform-api-key>`
- 文档：
  - 鉴权：https://ai.baidu.com/ai-doc/REFERENCE/Lkru0zoz4
  - 图像处理：https://cloud.baidu.com/doc/IMAGEPROCESS/s/ok3bclnkg
- 已开通能力：无损放大、老照片上色、摩尔纹去除、拉伸修复、去雾增强、对比度增强、去噪等 7 大接口。

## 火山引擎（Doubao/Seedream）

- 通用 API Key：`${VOLCENGINE_API_KEY}`
- Base URL：`https://ark.cn-beijing.volces.com`
- 重点模型：
  1. `doubao-seed-1-8-251228`（Doubao Seed 1.8，支持图文多模态）
     ```bash
     curl https://ark.cn-beijing.volces.com/api/v3/chat/completions \
       -H "Content-Type: application/json" \
       -H "Authorization: Bearer ${VOLCENGINE_API_KEY}" \
       -d '{
         "model": "doubao-seed-1-8-251228",
         "messages": [{
           "role": "user",
           "content": [
             { "type": "image_url", "image_url": { "url": "https://ark-project.tos-cn-beijing.ivolces.com/images/view.jpeg" } },
             { "type": "text", "text": "图片主要讲了什么?" }
           ]
         }]
       }'
     ```
  2. `doubao-seedream-4-5-251128`（Seedream 4.5 文生图）
     ```bash
     curl -X POST https://ark.cn-beijing.volces.com/api/v3/images/generations \
       -H "Content-Type: application/json" \
       -H "Authorization: Bearer ${VOLCENGINE_API_KEY}" \
       -d '{
         "model": "doubao-seedream-4-5-251128",
         "prompt": "星际穿越…",
         "response_format": "url",
         "size": "2K",
         "stream": false,
         "watermark": true
       }'
     ```
- 文档：
  - Chat/VL：https://www.volcengine.com/docs/82379/1399008?lang=zh
  - 文生图：https://www.volcengine.com/docs/82379/1541523?lang=zh

## KIE 中转站（境外模型代理）

- API Key：`${KIE_API_KEY}`
- Base URL：`https://api.kie.ai`
- 核心模型：
  1. `nano-banana-pro`（Google Nano Banana Pro 图生图，支持 4K 与多张参考图）
  2. `flux-2/pro-image-to-image`（Flux-2 Pro 图生图，必须传 1-8 张 `input_urls`）
  3. `sora-2-pro-text-to-video`（Sora2 Pro 文生视频，支持角色 ID、去水印、10/15 帧）
- 调用说明：
  - 创建任务统一走 `POST /api/v1/jobs/createTask`，成功返回 `taskId`
  - 任务状态与结果通过 `GET /api/v1/jobs/recordInfo?taskId=xxx` 查询，`resultJson` 字段包含 `resultUrls`
  - 生产环境建议传 `callBackUrl` 以免频繁轮询
- 文档：
  - Nano Banana Pro：https://docs.kie.ai/cn/market/google/pro-image-to-image.json
  - Flux-2 Pro：https://docs.kie.ai/cn/market/flux2/pro-image-to-image.json
  - Sora2 Pro：https://docs.kie.ai/cn/market/sora2/sora-2-pro-text-to-video.json
  - 查询任务：https://docs.kie.ai/cn/market/common/get-task-detail.json

## 备注

- 所有凭证已同步到管理端“执行节点”配置中，可直接绑定到能力目录；如需刷新或替换，请同时更新本文件与系统配置。
- TODO：后续需实现火山模型列表自动同步接口，并进一步细化 RAM 信任策略与临时密钥失效流程。***
