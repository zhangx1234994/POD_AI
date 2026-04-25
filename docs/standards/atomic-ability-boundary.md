# 原子能力与执行服务边界准则

> 版本：2026-04-24
> 目的：统一“什么是原子能力、能力放在哪个服务、谁负责密钥与网络”的判断口径。

## 1. 原子能力定义

原子能力是可独立调用、输入输出稳定、可被 Coze / 中台 / 工作流复用的最小能力单元。

原子能力不等于“本地函数”，也不等于“第三方 API”。只要满足以下条件，即可视为原子能力：

- 有明确的输入 schema。
- 有明确的输出 schema。
- 可独立测试和计费。
- 可被 Coze 工具箱单独暴露。
- 失败原因可归一到平台错误契约。

## 2. 原子能力分类

| 类别 | 服务归属 | 典型能力 | 特征 |
| --- | --- | --- | --- |
| 本地图像原子能力 | `image-ops` | DPI、缩放、裁剪、遮罩扩展、格式转换 | 平台自研、轻/中等 CPU 或图像处理，不依赖第三方模型 API |
| 工作流原子能力 | ComfyUI executor | 图裂变、扩图、抠图、多图融合、四方连续 | 由外部工作流执行节点承载，可能耗 GPU/显存 |
| 第三方 API 原子能力 | `vendor-api-ops` | OpenAI、火山、百度、KIE、其他云模型 | 依赖厂商 API Key、网络出口、限流、额度、计费和错误适配 |

## 3. 服务边界

### backend

backend 是控制面，不承载重执行和特殊网络调用。

backend 负责：

- 能力目录与能力 schema。
- Coze 工具箱 OpenAPI。
- 路由、调度、并发判断。
- 任务状态、日志、评测、OSS 落盘。
- 对外统一错误契约。

backend 不负责：

- 长期执行高清放大、GPU 工作流等重任务。
- 直接承载需要特殊国际出口的厂商 API 调用。
- 长期保存和轮换所有第三方 API Key 的运行细节。

### image-ops

image-ops 是自研图像处理执行面。

image-ops 负责：

- DPI、尺寸、裁剪、遮罩、格式转换等本地图像原子能力。
- 可复用、可离线执行、不依赖第三方模型 API 的能力。

image-ops 不负责：

- OpenAI / KIE / 火山 / 百度等第三方 API 调用。
- API Key 托管、代理、国际出口、模型路由。
- Coze 工具箱契约生成。

### ComfyUI executor

ComfyUI executor 是工作流执行面。

ComfyUI executor 负责：

- 执行 ComfyUI workflow。
- 暴露队列、健康状态、模型/插件状态。
- 返回可回填到 OSS 的输出。

ComfyUI executor 不负责：

- 平台能力目录。
- Coze 工具箱 contract。
- 第三方 API Key 的平台级管理。

### vendor-api-ops

vendor-api-ops 是第三方 API 执行面。

vendor-api-ops 负责：

- OpenAI、火山、百度、KIE 等第三方 API 的运行时适配。
- API Key 托管、轮换、熔断、冷却、额度状态。
- 网络出口和代理策略。
- provider/model 级限流与并发。
- 厂商错误归一为平台可理解的错误。
- 调用耗时、用量、成本基础数据回传。

vendor-api-ops 不负责：

- Coze 工作流编排。
- 管理端/评测端页面。
- 平台能力目录的最终展示口径。
- OSS 对外返回链接策略。

## 4. Key 管理原则

目标状态：

- 第三方 API Key 的运行时托管放在 vendor-api-ops。
- backend 只保存能力目录、executor 引用和必要的 Key 引用标识。
- Coze 和前端永远不接触第三方 API Key。

过渡状态：

- 现有 backend `api_keys` / `executor_api_keys` 继续兼容火山、KIE、百度等已接能力。
- 新增需要特殊网络的厂商能力，优先接入 vendor-api-ops。
- 后续逐步把 backend 内的厂商 Key 迁移为 vendor-api-ops 托管。

硬约束：

- Key 不写入 Coze 工作流。
- Key 不写入前端构建产物。
- Key 不写入普通文档。
- Key 的查看、修改、失效必须可审计。

## 5. Coze 工具箱边界

Coze 只调用 backend 工具箱，不直接调用 image-ops、ComfyUI、vendor-api-ops。

固定调用链：

```text
Coze
  -> backend / Coze toolbox
    -> image-ops
    -> ComfyUI executor
    -> vendor-api-ops
```

原因：

- 工具箱 contract 由 backend 统一维护。
- 任务查询、错误码、OSS 回填统一。
- 后续 executor 可以替换，不影响 Coze 编排。

## 6. 新能力归属判断

接入新能力时按以下顺序判断：

1. 是否为自研图像处理，且不依赖第三方模型 API？
   - 是：放入 image-ops。
2. 是否为 ComfyUI workflow 或 GPU/显存执行任务？
   - 是：放入 ComfyUI executor。
3. 是否依赖第三方 API Key、特殊网络出口、厂商限流或余额？
   - 是：放入 vendor-api-ops。
4. 是否只是平台控制面查询、任务状态、文档、目录？
   - 是：留在 backend。

禁止为了快速上线把第三方 API 调用塞进 image-ops。

## 7. 发布前检查

新增原子能力必须检查：

- 能力归属是否符合本准则。
- 输入/输出 schema 是否稳定。
- 错误码是否进入错误契约。
- Coze 工具箱是否只指向 backend。
- 评测端是否能按输出类型正确展示。
- Key 和网络出口是否不暴露给 Coze/前端。
