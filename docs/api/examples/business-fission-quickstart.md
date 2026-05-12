# 图裂变业务接口接入 Demo

目标：业务方只接一个提交接口和一个查询接口。图裂变底层用 ComfyUI 还是 GPT Image 2 + VL，由中台版本控制。

## 1. 准备 Key

生产环境不要把真实 Key 写进文档或代码仓库。上线前在 114 后端机器执行：

```bash
cd /srv/pod/backend
python scripts/create_business_api_key.py \
  --id biz_key_fission_partner_001 \
  --name "业务方图裂变测试 Key" \
  --tenant-id partner \
  --client-id fission-api \
  --allowed-business-key fission
```

脚本会把 Key 写入中台 `api_keys` 表，并在终端输出一次完整 Key。业务方请求时放在请求头：

```http
X-PODI-API-Key: <脚本输出的 key>
```

## 2. 提交 GPT Image 2 + VL 控制版裂变

```bash
export PODI_BACKEND="http://114.55.0.56:8099"
export PODI_API_KEY="<脚本输出的 key>"

curl -X POST "$PODI_BACKEND/api/business/fission/runs" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{
    "imageUrl": "https://podi.oss-cn-hangzhou.aliyuncs.com/demo/input.png",
    "version": "gpt-image2-vl-v1",
    "variation_strength": "high",
    "quality": "preview",
    "count": 1,
    "size": "1024x1024",
    "preserve_layout": true,
    "preserve_border": "auto",
    "preserve_count_density": true,
    "style_shift": "standard",
    "prompt": "保留系列感，元素要明显变化",
    "source": "partner-api",
    "channel": "open-api",
    "traceId": "trace-fission-001",
    "requestId": "req-fission-001"
  }'
```

### 参数说明

| 参数 | 是否必填 | 推荐值 / 示例 | 说明 |
| --- | --- | --- | --- |
| `imageUrl` | 是 | `https://.../input.png` | 原图地址。必须是中台、Coze 和模型服务都能访问的图片 URL。 |
| `version` | 否 | `gpt-image2-vl-v1` | 指定裂变版本。为空时使用中台当前默认版本；明天业务接新裂变建议先固定传 `gpt-image2-vl-v1`。 |
| `prompt` | 否 | `保留系列感，元素要明显变化` | 业务补充提示词。可以不传；不传时中台仍会使用 VL 图像理解结果和内置系统提示词完成裂变。 |
| `variation_strength` | 否 | `low` / `medium` / `high` | GPT Image 2 裂变幅度。越高变化越明显；不传时使用版本默认值。 |
| `quality` | 否 | `preview` | 质量档位。业务测试建议 `preview`；正式高质量可后续切 `production` 或 `premium`。 |
| `count` | 否 | `1` | 输出张数。建议先传 `1`，多图会增加耗时和成本。 |
| `size` | 否 | `1024x1024` | 输出尺寸预设。支持 `auto`、`1024x1024`、`1536x1024`、`1024x1536`、`2048x2048`、`2048x1152`、`3840x2160`、`2160x3840`。不传时按版本默认值。 |
| `maskUrl` | 否 | `https://.../mask.png` | 蒙版图片地址。只有需要局部编辑时传；普通整图裂变不需要。 |
| `preserve_layout` | 否 | `true` | 是否尽量保留原图结构、构图关系。 |
| `preserve_border` | 否 | `auto` | 边框保留策略，支持 `auto` / `true` / `false`。 |
| `preserve_count_density` | 否 | `true` | 是否保留元素数量感和密度，适合花纹、四方连续素材。 |
| `style_shift` | 否 | `standard` | 风格变化策略，常用 `standard`；也可按版本支持传 `conservative` 或 `creative`。 |
| `source` | 否 | `partner-api` | 调用来源，用于中台统计和排查。 |
| `channel` | 否 | `open-api` | 调用渠道，例如 `open-api`、`coze-workflow`、`eval`。 |
| `traceId` | 否 | `trace-fission-001` | 跨系统链路 ID。建议业务方传自己的链路号。 |
| `requestId` | 否 | `req-fission-001` | 业务方请求 ID。建议每次请求唯一，便于排查重复提交。 |
| `callbackUrl` | 否 | `https://your-service/callback` | 终态回调地址。不传也可以，业务方用轮询接口取结果。 |
| `callbackHeaders` | 否 | `{"Authorization":"Bearer xxx"}` | 回调时附带的请求头。只有配置 `callbackUrl` 时需要。 |

最小可用请求只需要 `imageUrl` 和请求头 `X-PODI-API-Key`。如果业务要固定使用 GPT Image 2 + VL 控制版，额外传 `version: "gpt-image2-vl-v1"` 即可。

成功后会返回：

```json
{
  "runId": "业务任务ID",
  "taskId": "底层能力任务ID，可能为空或稍后生成",
  "status": "queued",
  "imageUrls": []
}
```

## 3. 查询结果

业务方推荐使用业务查询接口：

```bash
curl -X POST "$PODI_BACKEND/api/business/runs/get" \
  -H "Content-Type: application/json" \
  -H "X-PODI-API-Key: $PODI_API_KEY" \
  -d '{"runId": "上一步返回的 runId"}'
```

为兼容 Coze 旧工具箱轮询方式，中台也支持把 `runId` 填到旧字段 `taskId`：

```bash
curl -X POST "$PODI_BACKEND/api/coze/podi/tasks/get" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <SERVICE_API_TOKEN>" \
  -d '{"taskId": "上一步返回的 runId"}'
```

注意：`/api/coze/podi/tasks/get` 是 Coze/内网兼容入口，外部业务默认使用 `/api/business/runs/get`。

## 4. 结果判断

业务查询接口按 `status` 判断：

- `queued` / `running`：继续等待，建议 5-10 秒后再查。
- `succeeded`：读取 `imageUrls`。
- `failed`：读取 `error` / `errorMessage`，记录 `runId` 给中台排查。

Coze 兼容查询接口按 `taskStatus` 判断：

- `queued` / `running`：继续等待。
- `succeeded`：读取 `imageUrls`。
- `failed`：读取 `debugResponse` / `errorCode`。
