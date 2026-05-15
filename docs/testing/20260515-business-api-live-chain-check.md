# 2026-05-15 新业务接口线上链路排查

## 结论

- 检查窗口：2026-05-15 00:00:00 ~ 2026-05-16 00:00:00（Asia/Shanghai）。
- 业务方今天已经使用新接口：`POST /api/business/fission/runs`。
- 本次实际使用的是 `comfyui-vl-control-v2`，共 21 次提交，全部成功，每个 run 回填 1 张图。
- `gpt-image2-vl-v2` 和 `fission_evaluate` 今天窗口内未发现业务方正式调用。
- 业务 API Key 调用异常为 0；业务 run 异常为 0；测评 run 异常为 0。
- 发现 2 个需要处理的隐患：
  - 业务方轮询频率偏高，21 个 run 产生 1071 次查询，部分 run 3 分钟内轮询 70+ 次。
  - 233 ComfyUI 缺少 `String` 自定义节点，旧“四方连续裂变”工作流先打到 233 失败，再 fallback 到 158 成功。

## 业务 API 使用情况

| 指标 | 结果 |
| --- | --- |
| 业务 run 总数 | 24 |
| 新业务方裂变 run | 21 |
| 新业务方裂变成功率 | 21/21 |
| 新业务方裂变版本 | `comfyui-vl-control-v2` |
| 输出图数量 | 21 |
| 业务 Key 异常 | 0 |
| 业务 run 异常 | 0 |
| 能力 pending 残留 | 0 |

新业务方调用来源：

```text
tenant_id = business-fission-eval
client_id = delivery-demo-20260512
api_key_name = 业务方图裂变与评分交付 Key 20260512
```

## 业务链路

本次 21 个业务方裂变任务均按以下链路完成：

```text
业务方
  -> POST /api/business/fission/runs
  -> business_runs(version=comfyui-vl-control-v2)
  -> VL 图裂变颜色控制卡
  -> Doubao-Seed-2.0-lite VL
  -> ComfyUI 颜色锁定裂变
  -> OSS 回填 imageUrls[0]
  -> POST /api/business/runs/get 轮询成功
```

## 执行节点分布

| 执行节点 | 数量 | 平均耗时 |
| --- | ---: | ---: |
| ComfyUI 4090 · 233 · 117.50.216.233 | 12 | 31535.83 ms |
| ComfyUI 5090 · 158 · 117.50.80.158 | 9 | 44865.89 ms |

结论：

- 新业务接口的 ComfyUI 颜色锁定裂变已经能同时跑到 233 和 158。
- 两台机器当前队列均为空。
- 当前新业务接口没有出现单机路由问题。

## VL 前置耗时

| 能力 | 数量 | 平均耗时 | 最小耗时 | 最大耗时 |
| --- | ---: | ---: | ---: | ---: |
| Doubao-Seed-2.0-lite | 21 | 111281.38 ms | 55792 ms | 174348 ms |
| VL 图裂变控制卡 | 21 | 111481.62 ms | 55982 ms | 174552 ms |

结论：

- 当前端到端耗时主要被 VL 前置拖长，不是 ComfyUI 出图本身。
- 业务等待时间约 59~176 秒，执行出图时间约 16~76 秒。
- 后续如果业务方认为等待时间长，优先优化 VL 模型耗时、并发和缓存，而不是先动 ComfyUI。

## 轮询情况

| 路径 | 次数 | 平均耗时 | 最大耗时 |
| --- | ---: | ---: | ---: |
| `POST /api/business/fission/runs` | 21 | 265.76 ms | - |
| `POST /api/business/runs/get` | 1071 | 73.09 ms | 418 ms |

观察：

- 所有查询都是 200，无错误码。
- 轮询频率偏高，部分 run 在约 3 分钟内查询 70+ 次。
- 按交付文档建议，应每 5~10 秒轮询一次；当前看起来更接近 2~3 秒一次。

建议：

- 短期：提醒业务方按 `retryAfterSeconds` 或 5~10 秒间隔轮询。
- 中期：平台可增加 Key 级“查询频率观察”或软限速提示，避免业务高峰时无意义查询放大。
- 长期：如果业务方并发接入增多，需要给 `/api/business/runs/get` 做按 Key 的轻量缓存或频率控制。

## 查询返回体检查

抽查 run：`b52d43d4034a46b1a3e80361a3dff188`。

| 查询模式 | 返回大小 | 是否包含 steps | 是否包含 routeInfo |
| --- | ---: | --- | --- |
| 默认查询 | 1573 bytes | 否 | 否 |
| `detail=full` | 26815 bytes | 是 | 是 |

结论：

- 默认业务查询已经是轻量返回。
- 排障模式仍可拿到底层步骤和完整证据，但不应作为业务方常规轮询方式。

## 发现的非新接口隐患

08:36 左右旧“四方连续裂变”测评/Coze 工作流出现一次能力层失败：

```text
executor = ComfyUI 4090 · 233 · 117.50.216.233
capability = flux2_9b_liebian_sifang
error = Node 'String' not found. The custom node may not be installed. Node ID '#99'
```

同一能力随后 fallback 到 158 成功：

```text
executor = ComfyUI 5090 · 158 · 117.50.80.158
stored_url = https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-comfyui/20260515/020a70dd-1778776600.png
```

确认结果：

- 233 `/object_info/String` 返回 `{}`。
- 158 `/object_info/String` 返回节点信息，来源为 `custom_nodes.comfyui_bmad_nodes`。
- 这不影响今天业务方使用的新 `comfyui-vl-control-v2` 接口，但说明 233 与 158 的自定义节点仍未完全同步。

建议：

- 优先在 233 安装或同步 `comfyui_bmad_nodes`，补齐 `String` 节点。
- 在“逐功能上线检查表”中增加 workflow 级节点检查，不能只检查 `KSampler/SaveImage/LoadImage`。
- 在修复前，旧 `flux2_9b_liebian_sifang` 对 233 的失败会依赖 fallback，不应视为完全健康。

## 本次判断

今天业务方使用的新裂变接口整体可用，链路完整：

- 提交成功。
- 业务 run 成功。
- VL 前置成功。
- ComfyUI 出图成功。
- OSS 回填成功。
- 查询接口轻量返回成功。
- Key 调用记录完整。

当前需要继续处理的是“平台稳健性”问题，而不是本次新业务接口不可用：

1. 业务方轮询过密。
2. 233 与 158 的 ComfyUI 节点不完全一致。
3. 逐功能上线检查表仍未固化。
