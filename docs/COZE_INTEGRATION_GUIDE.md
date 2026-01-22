# Coze 工作流对接指南

## 1. 文档介绍

本文档详细介绍了如何对接中台项目的 Coze 工作流 API，用于集成各种 AI 能力。通过本指南，您可以了解如何调用 Coze 工作流，获取执行结果，并处理回调事件。

## 2. 对接准备

### 2.1 基础信息

| 项目 | 说明 |
|------|------|
| API 基础 URL | `https://api.example.com`（线上环境）| 
| 认证方式 | Bearer Token |
| 请求格式 | JSON |
| 响应格式 | JSON |
| 支持协议 | HTTPS |
| 超时时间 | 30秒 |

### 2.2 环境要求

- Python 3.11+
- FastAPI 0.100+
- httpx 0.24+

### 2.3 核心依赖

```python
# 安装依赖
pip install fastapi httpx
```

### 2.4 认证流程

1. 向中台管理员申请 API Token
2. 在请求头中添加 `Authorization: Bearer {token}`
3. 确保 Token 保密，定期更换

## 3. 能力列表

### 3.1 公共能力 API

#### 3.1.1 获取能力列表

- **URL**: `/api/abilities`
- **方法**: GET
- **认证**: Bearer Token
- **响应格式**: JSON

```json
{
  "items": [
    {
      "id": "ability_coze_prompt_extract",
      "displayName": "提示词提取",
      "description": "从图片中提取提示词",
      "provider": "coze",
      "capabilityKey": "prompt_extract",
      "status": "active",
      "inputSchema": {
        "fields": [
          {
            "name": "url",
            "type": "string",
            "required": true,
            "description": "图片地址"
          },
          {
            "name": "shuru",
            "type": "string",
            "required": false,
            "description": "用户输入内容"
          }
        ]
      }
    }
    // 更多能力...
  ]
}
```

#### 3.1.2 获取能力详情

- **URL**: `/api/abilities/{ability_id}`
- **方法**: GET
- **认证**: Bearer Token
- **路径参数**: `ability_id` - 能力 ID
- **响应格式**: JSON

```json
{
  "id": "ability_coze_prompt_extract",
  "displayName": "提示词提取",
  "description": "从图片中提取提示词",
  "provider": "coze",
  "capabilityKey": "prompt_extract",
  "status": "active",
  "inputSchema": {
    "fields": [
      {
        "name": "url",
        "type": "string",
        "required": true,
        "description": "图片地址"
      },
      {
        "name": "shuru",
        "type": "string",
        "required": false,
        "description": "用户输入内容"
      }
    ]
  }
}
```

### 3.2 调用能力 API

#### 3.2.1 接口信息

- **URL**: `/api/abilities/{ability_id}/invoke`
- **方法**: POST
- **认证**: Bearer Token
- **路径参数**: `ability_id` - 能力 ID

#### 3.2.2 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| executorId | string | 否 | 执行器 ID |
| inputs | object | 是 | 能力输入参数，根据不同能力的 inputSchema 定义 |
| imageUrl | string | 否 | 图片 URL，支持 HTTP/HTTPS 和 OSS URL |
| imageBase64 | string | 否 | 图片 Base64 编码，需包含完整的 Data URL 格式 |
| callbackUrl | string | 否 | 回调 URL，任务完成后系统会向该 URL 发送结果 |
| callbackHeaders | object | 否 | 回调请求头，会在回调时添加到请求中 |
| metadata | object | 否 | 元数据，可用于传递自定义信息 |

#### 3.2.3 响应格式

```json
{
  "abilityId": "ability_coze_prompt_extract",
  "provider": "coze",
  "status": "succeeded",
  "requestId": "abc123",
  "logId": 12345,
  "durationMs": 1200,
  "images": [
    {
      "ossUrl": "https://example.com/image.png",
      "sourceUrl": "https://example.com/image.png",
      "type": "image"
    }
  ],
  "videos": [],
  "texts": ["提示词内容"],
  "assets": [],
  "metadata": {
    "model": "coze",
    "state": "completed",
    "taskId": "task123"
  },
  "raw": {
    "response": {
      "code": 0,
      "msg": null,
      "data": "{\"output\": \"提示词内容\"}",
      "execute_id": "task123",
      "debug_url": "https://api.example.com/debug/task123"
    }
  }
}
```

### 3.3 查询任务状态 API

#### 3.3.1 接口信息

- **URL**: `/api/ability_tasks/{task_id}`
- **方法**: GET
- **认证**: Bearer Token
- **路径参数**: `task_id` - 任务 ID

#### 3.3.2 请求参数

无额外请求参数

#### 3.3.3 响应格式

```json
{
  "id": "task123",
  "abilityId": "ability_coze_pattern_extract",
  "status": "succeeded",
  "requestId": "abc123",
  "logId": 12345,
  "createTime": "2026-01-22T10:00:00Z",
  "updateTime": "2026-01-22T10:01:00Z",
  "resultPayload": {
    "texts": ["花纹提取完成"],
    "images": [
      {
        "ossUrl": "https://example.com/pattern.png",
        "sourceUrl": "https://example.com/pattern.png",
        "type": "image"
      }
    ]
  },
  "errorPayload": null
}
```

### 3.4 回调机制

#### 3.4.1 回调触发条件

- 异步任务完成（成功或失败）
- 任务执行超时
- 任务被取消

#### 3.4.2 回调请求格式

- **方法**: POST
- **Content-Type**: application/json
- **请求头**: 包含调用时指定的 `callbackHeaders`

#### 3.4.3 回调数据格式

```json
{
  "requestId": "abc123",
  "taskId": "task123",
  "abilityId": "ability_coze_pattern_extract",
  "status": "succeeded",
  "durationMs": 60000,
  "texts": ["花纹提取完成"],
  "images": [
    {
      "ossUrl": "https://example.com/pattern.png",
      "sourceUrl": "https://example.com/pattern.png",
      "type": "image"
    }
  ],
  "videos": [],
  "assets": [],
  "metadata": {
    "model": "coze",
    "state": "completed"
  },
  "errorMessage": null
}
```

#### 3.4.4 回调响应要求

- 回调服务需返回 HTTP 200 状态码
- 响应内容需包含 `code` 和 `message` 字段
- 响应示例：`{"code": 0, "message": "success"}`

#### 3.4.5 重试机制

- 回调失败后，系统会进行重试
- 重试间隔：10秒、30秒、1分钟、5分钟、10分钟
- 最大重试次数：5次
- 超过重试次数后，不再重试

#### 3.4.6 回调安全建议

- 使用 HTTPS 协议接收回调
- 验证回调请求的来源 IP（可联系管理员获取系统 IP 列表）
- 在 `callbackHeaders` 中添加自定义验证信息
- 对回调数据进行签名验证

### 3.5 状态码说明

| 状态码 | 说明 |
|--------|------|
| succeeded | 任务执行成功 |
| failed | 任务执行失败 |
| queued | 任务排队中 |
| running | 任务执行中 |
| canceled | 任务已取消 |
| timeout | 任务执行超时 |

## 4. 工作流列表

### 4.1 提示词工作流

- **工作流 ID**: `7597535455856295936`
- **名称**: 提示词工作流
- **描述**: 提取图片的提示词
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
  | shuru | string | 否 | 用户输入内容 |
- **出参**: `output`（输出的提示词内容）

### 4.2 花纹提取工作流

- **工作流 ID**: `7597530887256801280`
- **名称**: 花纹提取工作流
- **描述**: 提取图片花纹，返回回调 ID
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
  | height | number | 是 | 生成图片高度 |
  | width | number | 是 | 生成图片宽度 |
  | lora | string | 否 | 用到的 lora 模型 |
- **出参**: `output`（回调使用的 ID，用于查询生成结果）

### 4.3 四部急速生图

- **工作流 ID**: `7597701996124045312`
- **名称**: 四部急速生图
- **描述**: 快速生成图片
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
  | height | number | 是 | 生成图片高度 |
  | width | number | 是 | 生成图片宽度 |
  | prompt | string | 是 | 提示词 |
- **出参**: `output`（回调使用的 ID，用于查询生成结果）

### 4.4 八部急速生图

- **工作流 ID**: `7597702948247830528`
- **名称**: 八部急速生图
- **描述**: 高精度生成图片
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
  | height | number | 是 | 生成图片高度 |
  | width | number | 是 | 生成图片宽度 |
  | prompt | string | 是 | 提示词 |
- **出参**: `output`（回调使用的 ID，用于查询生成结果）

### 4.5 扩图多模型版本

- **工作流 ID**: `7597723984687267840`
- **名称**: 扩图多模型版本
- **描述**: 多模型扩图，返回图片 URL
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | Url | string | 是 | 图片地址 |
  | expand_bottom | number | 是 | 下方扩图像素 |
  | expand_left | number | 是 | 左侧扩图像素 |
  | expand_right | number | 是 | 右侧扩图像素 |
  | expand_top | number | 是 | 上方扩图像素 |
  | moxing | string | 否 | 模型类型（1:banana pro, 2:flunx2, 3:豆包4.5）| 
- **出参**: `output`（输出的图片地址）

### 4.6 8K 高清放大

- **工作流 ID**: `7597760543788630016`
- **名称**: 8K 高清放大
- **描述**: 高清放大图片
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
  | bianchang | number | 是 | 最大边长（最大 8K）| 
- **出参**: `output`（输出的图片地址）

### 4.7 小参数版本图片打标

- **工作流 ID**: `7597767702970630144`
- **名称**: 小参数版本图片打标
- **描述**: 图片打标，返回 JSON 标签
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
- **出参**: `output`（JSON 标签格式）

### 4.8 大参数版本图片打标

- **工作流 ID**: `7598080013539213312`
- **名称**: 大参数版本图片打标
- **描述**: 详细图片打标，返回 JSON 标签
- **入参**:
  | 参数名 | 类型 | 必填 | 说明 |
  |--------|------|------|------|
  | url | string | 是 | 图片地址 |
- **出参**: `output`（JSON 标签格式）

## 5. 调用示例

### 5.1 HTTP 直接调用 - 获取能力列表

```python
import httpx

# 配置
base_url = "https://api.example.com"
token = "your-bearer-token"

# 构造请求
url = f"{base_url}/api/abilities"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 发送请求
response = httpx.get(url, headers=headers)
result = response.json()
print("能力列表:")
for ability in result["items"]:
    print(f"- {ability['displayName']} (ID: {ability['id']})")
```

### 5.2 HTTP 直接调用 - 调用能力

```python
import httpx

# 配置
base_url = "https://api.example.com"
token = "your-bearer-token"

# 构造请求
ability_id = "ability_coze_prompt_extract"
url = f"{base_url}/api/abilities/{ability_id}/invoke"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

body = {
    "inputs": {
        "url": "https://example.com/image.png",
        "shuru": ""
    },
    "callbackUrl": "https://your-server.com/callback",
    "callbackHeaders": {
        "X-Custom-Header": "your-custom-value"
    }
}

# 发送请求
response = httpx.post(url, json=body, headers=headers)
result = response.json()
print(f"执行结果: {result}")
```

### 5.3 Python SDK 调用

```python
import httpx

class AbilityClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token
        self.client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    def list_abilities(self):
        """获取能力列表"""
        url = f"{self.base_url}/api/abilities"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_ability(self, ability_id):
        """获取能力详情"""
        url = f"{self.base_url}/api/abilities/{ability_id}"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()
    
    def invoke_ability(self, ability_id, inputs, image_url=None, image_base64=None, callback_url=None, callback_headers=None, metadata=None):
        """调用能力"""
        url = f"{self.base_url}/api/abilities/{ability_id}/invoke"
        body = {
            "inputs": inputs
        }
        if image_url:
            body["imageUrl"] = image_url
        if image_base64:
            body["imageBase64"] = image_base64
        if callback_url:
            body["callbackUrl"] = callback_url
        if callback_headers:
            body["callbackHeaders"] = callback_headers
        if metadata:
            body["metadata"] = metadata
        response = self.client.post(url, json=body)
        response.raise_for_status()
        return response.json()
    
    def get_task_status(self, task_id):
        """查询任务状态"""
        url = f"{self.base_url}/api/ability_tasks/{task_id}"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()

# 使用示例
client = AbilityClient(base_url="https://api.example.com", token="your-bearer-token")

# 获取能力列表
abilities = client.list_abilities()
print("可用能力:")
for ability in abilities["items"]:
    print(f"- {ability['displayName']} (ID: {ability['id']})")

# 调用能力
ability_id = "ability_coze_prompt_extract"
result = client.invoke_ability(
    ability_id=ability_id,
    inputs={
        "url": "https://example.com/image.png",
        "shuru": ""
    },
    callback_url="https://your-server.com/callback"
)
print(f"调用结果: {result}")
```

### 5.4 异步调用与回调处理

```python
# 调用异步能力
ability_id = "ability_coze_pattern_extract"
result = client.invoke_ability(
    ability_id=ability_id,
    inputs={
        "url": "https://example.com/image.png",
        "height": 512,
        "width": 512,
        "lora": ""
    },
    callback_url="https://your-server.com/callback"
)

# 处理结果
print(f"调用状态: {result['status']}")
print(f"请求 ID: {result['requestId']}")

# 提取文本结果
if result.get('texts'):
    print(f"文本结果: {result['texts'][0]}")

# 提取图片结果
if result.get('images'):
    for i, image in enumerate(result['images']):
        print(f"图片 {i+1}: {image['sourceUrl']}")

# 提取任务 ID（用于异步任务）
task_id = result['metadata'].get('taskId')
if task_id:
    print(f"异步任务 ID: {task_id}")
    
    # 查询任务状态
    task_result = client.get_task_status(task_id)
    print(f"任务状态: {task_result}")
```

### 5.5 回调接收示例

```python
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.post("/callback")
async def handle_callback(request: Request):
    """处理能力调用回调"""
    callback_data = await request.json()
    print(f"收到回调: {callback_data}")
    
    # 解析回调数据
    request_id = callback_data.get("requestId")
    task_id = callback_data.get("taskId")
    status = callback_data.get("status")
    
    if status == "succeeded":
        # 处理成功结果
        texts = callback_data.get("texts", [])
        images = callback_data.get("images", [])
        print(f"任务 {task_id} 成功完成")
        print(f"文本结果: {texts}")
        print(f"图片结果: {images}")
    else:
        # 处理失败结果
        error_message = callback_data.get("errorMessage")
        print(f"任务 {task_id} 失败: {error_message}")
    
    return {"code": 0, "message": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 6. 错误处理

### 6.1 错误码说明

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| 0 | 成功 | 正常处理结果 |
| 400 | 请求参数错误 | 检查请求参数格式和内容 |
| 401 | 认证失败 | 检查 Token 是否有效或已过期 |
| 404 | 能力不存在 | 检查 ability_id 是否正确 |
| 500 | 服务器内部错误 | 重试或联系管理员 |
| 502 | 第三方服务错误 | 检查第三方服务状态或联系管理员 |
| 720701013 | Coze 工作流执行失败 | 检查工作流配置和参数，或查看 debug_url |

### 6.2 异常处理

```python
import httpx

client = AbilityClient(base_url="http://localhost:8888", token="your-bearer-token")

try:
    result = client.invoke_ability(
        ability_id="ability_coze_prompt_extract",
        inputs={"url": "https://example.com/image.png"}
    )
    print(f"成功: {result}")
except httpx.HTTPStatusError as e:
    print(f"HTTP 错误: {e.response.status_code} - {e.response.text}")
    # 根据错误类型进行处理
    if e.response.status_code == 401:
        print("认证失败，请检查 Token 是否有效")
    elif e.response.status_code == 404:
        print("能力不存在，请检查 ability_id 是否正确")
    elif e.response.status_code == 400:
        print("请求参数错误，请检查输入参数")
    else:
        print("服务器错误，请联系管理员")
except httpx.RequestError as e:
    print(f"请求失败: {str(e)}")
    print("网络错误，请检查网络连接或稍后重试")
except Exception as e:
    print(f"其他错误: {str(e)}")
    print("请联系管理员")
```

## 7. 最佳实践

### 7.1 性能优化

- 对于耗时较长的能力，建议使用异步调用模式
- 合理设置轮询间隔，避免频繁请求导致服务器压力过大
- 缓存常用能力的执行结果，减少重复调用
- 对于批量处理，考虑使用并发调用提高效率

### 7.2 安全性

- 保护好 API Token，避免泄露给未授权人员
- 定期更换 Token，降低安全风险
- 对输入参数进行验证，防止注入攻击
- 限制能力的调用频率，防止滥用
- 使用 HTTPS 协议进行通信，保护数据传输安全

### 7.3 可靠性

- 实现重试机制，处理临时网络错误或服务器繁忙情况
- 记录详细的调用日志，便于调试和分析问题
- 监控能力的执行状态，及时发现异常情况
- 使用回调机制获取异步任务结果，避免长时间轮询
- 设计合理的超时机制，避免请求无限等待

## 8. 常见问题

### 8.1 如何获取能力 ID？

可以通过调用 `/api/abilities` 接口获取所有可用能力的列表，其中包含每个能力的 ID、名称和描述。

### 8.2 如何处理大文件？

对于大文件，建议先上传到 OSS，然后将 OSS URL 作为参数传递给能力调用接口。

### 8.3 能力执行超时怎么办？

对于耗时较长的能力，建议使用异步调用模式，并通过回调机制或定期轮询获取结果。

### 8.4 如何调试能力调用？

可以通过以下方式调试能力调用：
1. 检查请求参数是否正确
2. 查看返回结果中的 `raw` 字段，获取详细的调用信息
3. 查看返回结果中的 `debug_url`，在 Coze Studio 中查看工作流的执行详情
4. 联系管理员获取详细的日志信息

### 8.5 如何处理回调结果？

对于需要回调的能力，可以通过以下方式处理：
1. 在调用能力时提供 `callbackUrl` 参数，系统会在任务完成后自动回调该 URL
2. 或者，使用返回结果中的 `metadata.taskId` 定期查询任务状态

## 9. 附录

### 9.1 能力类型说明

| 类型 | 说明 |
|------|------|
| 提示词生成 | 从图片中提取提示词 |
| 花纹提取 | 提取图片中的花纹，生成新图片 |
| 多模型生图 | 使用不同模型生成图片 |
| 图片放大 | 高清放大图片 |
| 图片打标 | 对图片进行分类和标注 |

### 9.2 模型类型说明

| 模型编码 | 模型名称 |
|----------|----------|
| 1 | banana pro |
| 2 | flunx2 |
| 3 | 豆包4.5 |

### 9.3 联系我们

- 技术支持：tech-support@example.com
- 问题反馈：feedback@example.com
- 文档更新：docs@example.com

## 10. 版本记录

| 版本 | 日期 | 作者 | 说明 |
|------|------|------|------|
| v1.0 | 2026-01-22 | AI Assistant | 初始版本 |
| v1.1 | 2026-01-23 | AI Assistant | 新增工作流列表 |
| v1.2 | 2026-01-24 | AI Assistant | 完善调用示例 |
| v2.0 | 2026-01-25 | AI Assistant | 重构为能力调用模式，优化文档结构 |
| v2.1 | 2026-01-26 | AI Assistant | 更新为线上服务器配置，完善回调机制和任务查询 API |

---

**© 2026 中台项目团队**

本文档版权归中台项目团队所有，未经授权，不得擅自修改、复制或传播。
