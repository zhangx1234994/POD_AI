# 2026-05-15 对外业务接口交付回归记录

## 结论

- 发布版本：`d6c23053 fix: harden business fission delivery contract`
- 发布目标：114 控制面
- 结论：通过。本次对外业务接口契约硬化、交付包 v4 和 114 发布 smoke 均完成。

## 本次范围

| 范围 | 结论 |
| --- | --- |
| GPT Image 2 + VL 受控裂变 | 固定一请求一图；外部批量字段忽略；交付文档已改为 JSON 示例。 |
| ComfyUI 颜色锁定裂变 | 固定一请求一图；`bili` 继续表示重绘幅度；交付文档已补参数和枚举说明。 |
| 裂变生成图评分 | 独立业务接口；提交返回 `runId`，统一用 `/api/business/runs/get` 轮询。 |
| 业务查询返回体 | 默认轻量化；完整排障字段只在 `detail=full` 或管理端视角返回。 |
| 对外接口边界 | 业务方默认只使用 `/api/business/*`；Coze 工具箱和原子能力不混入业务交付材料。 |

## 自动化检查

| 检查项 | 结果 |
| --- | --- |
| `python3 -m pytest backend/tests/test_business_api_contract.py -q` | 17 passed |
| `python3 -m pytest backend/tests -q` | 538 passed |
| 交付包 JSON 示例格式校验 | PASS |
| `python3 scripts/audit_external_api_boundaries.py --summary` | `unclassified_count=0` |
| `git diff --check` | PASS |

## 114 发布后 smoke

| 检查项 | 结果 |
| --- | --- |
| `/health` | PASS，`{"status":"ok"}` |
| Coze OpenAPI | PASS，server=`http://172.17.0.1:8099` |
| 内部 `tasks/get` | PASS，未知任务返回 `TASK_NOT_FOUND` |
| ComfyUI 队列汇总 | PASS，servers=2，capacity=20，idle=20 |
| 公开测评目录 | PASS，26 条 |
| 内部测评目录 | PASS，33 条 |
| 花纹提取 route-preview | PASS |
| 图裂变 route-preview | PASS |
| 扩图 route-preview | PASS |

## 交付包

本次交付包：

```text
deliverables/podi_fission_business_delivery_20260514_v4.zip
```

交付包结构：

```text
01_gpt_image2_controlled_fission/
02_comfyui_colorlock_fission/
03_fission_generated_image_score/
README.md
TEST_REPORT.md
.env.example
business_api_key.env
```

说明：

- `business_api_key.env` 仅存在本地交付包中，不进 Git。
- 正式文档不再默认提供 Python Demo。
- 每个接口目录独立包含提交请求、查询请求、提交返回、排队中返回、成功返回、失败返回和参数说明。

## 已覆盖的错误路径

| 错误路径 | 覆盖方式 |
| --- | --- |
| 缺少 `imageUrl` | 业务接口契约测试 |
| 缺少 `runId` | 业务接口契约测试 |
| 查询不存在任务 | 发布 smoke 的 `TASK_NOT_FOUND` |
| 外部批量字段误传 | 业务接口契约测试确认忽略 |
| 对外接口未分类 | `audit_external_api_boundaries.py` |
| 查询返回体过重 | 轻量响应测试与交付 JSON 示例 |

## 剩余风险

- 测评端逐功能视觉回归还需要明天继续，重点是结果图浏览、批量上传、默认滑块模式和正在处理任务时的列表交互。
- ComfyUI 生成质量仍需要结合样本包和团队回执继续归因；本次只确认接口契约和参数边界，不代表生成质量已经达到最终要求。
- 业务方真实接入后，需要继续观察 Key 使用记录、轮询频率、错误处理和返回体大小。

## 下一步

1. 建立“每功能上线检查表”，把接口、参数、页面、记录、输出和错误逐项卡死。
2. 对测评端三个新业务入口跑完整页面回归。
3. 把业务方接入反馈继续回写到交付包和接口规范。
