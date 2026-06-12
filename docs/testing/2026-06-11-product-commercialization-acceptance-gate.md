# 产品商业化能力验收门禁（2026-06-11）

## 目标

产品商业化能力当前不再按“接口能跑通”判定完成，而按“商家是否能理解、运营是否能复核、工程师是否能追踪、接入方是否能稳定调用”判定。

本门禁覆盖两个独立能力：

- 产品文案内容包：产品图 + 可选产品导出字段 -> 大模型商品理解、海外文案、配图建议、可选 GPT Image 2 配图、下载图文包。
- 产品视频素材包：产品图 + 可选产品导出字段 -> 模型画像约束下的脚本、分镜、首尾帧/关键帧、KIE/Vidu 分段视频任务、可选合成、OSS 回填。

## 验收前提

- 文案与视频是两个能力入口，不共享前端隐藏状态。
- 产品图是最高优先级视觉事实源，导出 JSON 是可选说明材料；没有 JSON 不阻断主流程。
- 预览不偷偷触发成本动作；配图和视频必须显式点击。
- 配图默认走 `openai_gpt_image_2_edit` / GPT Image 2，除非用户或策略显式要求低成本、批量或特定模型。
- 视频时长由模型画像决定，不允许把某一个模型的 8 秒限制写成全局规则。
- 视频最终合成片不是唯一交付物；脚本、分镜、首尾帧、分段视频都要作为可复用素材验收。
- 视频脚本 / 分镜是 AI 中间稿，不是只读调试文本；用户编辑或参数变更后必须重新确认，未确认不得触发视频成本动作。

## P0 门禁

| ID | 项目 | 验收动作 | 通过标准 | 当前状态 |
| --- | --- | --- | --- | --- |
| PCG-01 | 视觉与主路径 | 桌面端、移动端打开产品文案和产品视频 | 首屏没有内部版本词；接口信息默认不抢占主路径；无横向溢出；输入区和输出区主次清楚 | 本地通过，待线上复测 |
| PCG-02 | 文案真实生成 | 用真实产品图和正常 JSON 生成文案内容包 | `copyGeneration.fallback=false` 或明确标记 fallback；结果含标题、五点描述、详情介绍、广告短文案、关键词、配图 brief | 待线上真实复测 |
| PCG-03 | 无 JSON 主流程 | 只传产品图，不传 `productFields`，生成文案和视频规划 | 不阻断；结果含 `resolvedProductFacts`、缺失字段/推断来源和置信度；不要求用户必须补 JSON | 114 预览巡检通过 |
| PCG-04 | 图片/JSON 错配 | 用明显不匹配的产品图和 JSON 生成文案 | 结果区展示冲突；`resolvedProductFacts` 以产品图为准；配图/视频提示需要人工确认风险 | 114 预览巡检通过；兜底冲突提示已补 |
| PCG-05 | 配图闭环 | 文案结果后点击单张配图和全部组图 | 走 `action=visual_generate`；默认能力为 GPT Image 2；页面展示 runId、状态、OSS 图和错误原因 | 114 真实单张 GPT Image 2 已通过，组图质量待业务样例复测 |
| PCG-06 | 视频规划 | 分别选择 KIE 和 Vidu，生成 8 秒、13/15 秒规划 | 页面和接口返回所选模型画像；KIE 按 8 秒片段，Vidu 按 3/5/8 秒片段；Vidu 必须返回 `aspectPolicy=input_image_ratio`，不伪装成直接支持固定比例；规划结果含 `videoAssetPackagePlan.script/storyboard/keyframeNeeds/compositionPlan`；脚本可编辑，编辑后确认状态失效 | 后端测试通过，页面阶段展示和确认门已补，待真实页面复测 |
| PCG-07 | 视频素材包执行 | 提交 KIE 单段、Vidu 单段、多段素材包任务 | 未确认脚本/分镜时不能提交；确认后提交成功返回统一 runId；查询口径仍是 `/api/business/runs/get`；成功后 `resultPayload.videoAssetPackage` 展示脚本、关键帧、分段视频、可选合成片；Vidu 出片比例按首帧策略验收 | 114 Vidu 8 秒单段真实 runId 通过；KIE/多段仍待复测 |
| PCG-08 | 合成失败保留素材 | 模拟或构造合成失败，但分段视频已成功 | 顶层状态按模式判断；`composition.status=failed`，已成功 `segmentVideos` 仍可下载、可复用、可追踪 | 后端结构已补，待构造线上故障复测 |
| PCG-09 | 状态与失败 | 模拟缺产品图、非法 JSON、旧结果过期、上游失败 | 按错误码返回；按钮禁用或提示原因明确；不暴露异常栈和密钥；可重新提交 | 部分通过，待专项复测 |
| PCG-10 | 文档一致 | 检查业务 API、错误码、测试用例、TODO | 参数、错误码、模型口径、默认配图路线、视频素材包口径四处一致 | 本轮已修旧口径，持续检查 |

## 视觉走查记录

本地 Playwright 已覆盖：

- `产品文案` 桌面端：无横向溢出，首屏移除内部版本词，配图标签明确为 GPT Image 2。
- `产品视频` 桌面端：无横向溢出，接口口径折叠，视频模型说明不再抢占主路径。
- `产品文案` 移动端：无横向溢出，流程说明保留，接口详情折叠。
- `产品视频` 移动端：无横向溢出，输入区可继续向下滚动。

截图目录：

- `output/visual-audit-after/copy-desktop.png`
- `output/visual-audit-after/video-desktop.png`
- `output/visual-audit-after/copy-mobile.png`
- `output/visual-audit-after/video-mobile.png`

## 真实业务复测顺序

1. 文案 preview：正常商品图 + 正常 JSON。
2. 文案 preview：只有商品图，没有 JSON。
3. 文案 preview：商品图与 JSON 明显不一致。
4. 配图：单张社媒封面，确认 GPT Image 2 路由和 OSS 回填。
5. 配图：全部组图，记录每张图的可用性和问题标签。
6. 视频规划：确认返回脚本、分镜、首尾帧/关键帧需求和可选合成策略；修改脚本后确认状态应变为待确认。
7. 视频：确认脚本和分镜后，提交 KIE 8 秒单段素材包。
8. 视频：Vidu 3/5/8 秒单段素材包各一条，确认参数不同；若输入图不是目标比例，验收时按“比例随首帧”判断，不把 `aspectRatio` 当成 Vidu 直接执行参数。
9. 视频：Vidu 13 秒或 KIE 15 秒多段素材包；合成只作为后续可选动作。
10. 错误路径：缺产品图、非法 JSON、旧结果过期、上游失败、分段失败、合成失败或超时。

## 自动化门禁脚本

新增专项脚本：

```bash
python3 backend/scripts/patrol_product_commercialization.py \
  --base-url http://127.0.0.1:8099 \
  --request-timeout 180 \
  --compact-json \
  --report output/product-commercialization-patrol.json
```

默认只跑非成本预览校验，覆盖：

- 正常产品图 + 正常字段。
- 仅产品图、无导出 JSON。
- 产品图与导出字段明显不一致。
- 结构字段：`resolvedProductFacts`、`contentPackage/copyPackage`、`visualAssetPlan`、`videoAssetPackagePlan.script/storyboard/keyframeNeeds/compositionPlan`。

线上允许付费复测时再显式打开成本动作：

```bash
python3 backend/scripts/patrol_product_commercialization.py \
  --base-url http://127.0.0.1:8099 \
  --include-live-visual \
  --include-live-video \
  --video-executor executor_kie_market_default \
  --target-duration 8 \
  --timeout 1200 \
  --report output/product-commercialization-live-patrol.json
```

如通过公网业务接口执行，必须使用受控业务 Key 或服务令牌，不把真实 Key 写进命令、文档或报告；优先使用环境变量 `PODI_BUSINESS_API_KEY` / `SERVICE_API_TOKEN`。

## 本地走查记录

- 2026-06-11：启动本地后端 `127.0.0.1:8099` 后，测评端 `127.0.0.1:8299` 产品文案 / 产品视频页面均不再出现“测评功能列表加载失败”；桌面和 390px 移动宽度无横向溢出。
- 2026-06-11：产品导出字段 JSON 默认空对象，页面提示“未填写，按产品图推断”，并提供“填入示例字段 / 清空字段，仅用产品图”；符合产品图优先、JSON 可选口径。
- 2026-06-11：产品视频页面按钮与阶段展示已从“分镜合成视频 / 多段合成”改为“单段视频素材 / 分段视频素材包”，并展示脚本、分镜、关键帧、分段视频、合成片五个阶段。
- 2026-06-11：补充 `backend/scripts/patrol_product_commercialization.py`，后续封版前必须至少跑默认预览门禁；线上验收窗口再打开 `--include-live-visual/--include-live-video` 做真实成本链路。
- 2026-06-11：本机执行默认预览巡检生成 `output/product-commercialization-patrol-local.json`，3 个用例均未通过。直接原因是本地请求超时；后端日志显示上游商品理解链路访问 vendor-api-ops 被拒绝：`VENDOR_API_CLIENT_FORBIDDEN`。该结果不能作为能力失败结论，只能说明当前本机不具备完整 vendor-api allowlist 条件；真实门禁必须在 114 或已加白的后端环境重跑。

## 114 线上复测记录

- 2026-06-11：发布 `c59fa6f4+workspace-product-commercialization-20260611` 到 114 控制面，`podi-backend`、`podi-admin-web`、`podi-eval-web` 均为 active，`/health` 返回 `{"status":"ok"}`，`scripts/deploy_preflight.sh` 结果 `PASS=5 FAIL=0`。
- 2026-06-11：首次 114 产品商业化真实巡检发现一个真实缺口：模型/VL 兜底时，产品图与导出字段未完成视觉核验，但模板包把 `fieldConflicts` 置空，导致错配场景没有稳定显示人工复核风险。已修复为：只要存在产品图和导出字段，但商品理解链路兜底或不可用，就保守输出 `PRODUCT_IMAGE_FIELD_CONFLICT`，并要求人工确认后再触发付费配图/视频动作；只有产品图、无导出字段时不误报冲突。
- 2026-06-11：修复后 114 默认预览巡检报告 `/srv/pod/reports/product-commercialization-preview-patrol-20260611-fixed2.json` 通过：`total=3 passed=3 failed=0`。覆盖正常产品图 + 字段、仅产品图无 JSON、产品图与字段明显不一致三类场景。
- 2026-06-11：114 真实 GPT Image 2 配图链路已通过，runId `83f4dd35a8e44d02b946e8a090ae49fd`，结果已回填 OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/system/20260611/96d9da72-1781154570.png`。
- 2026-06-11：114 真实 Vidu 单段视频素材包链路已通过，runId `24858339ccd94e588866018ab2c49963`，结果已回填 OSS：`https://podiaidesign.oss-cn-hangzhou.aliyuncs.com/test/abilities/admin-vidu/20260611/750a0574-1781154747.mp4`，`videoAssetPackage.deliveryStatus=assets_ready`。
- 2026-06-11：测评端产品文案 / 产品视频交互改为 AI 摄影棚式渐进工作台：`上传产品图 -> 确认商品事实 -> 设置文案/视频策略 -> 审核内容包/脚本分镜 -> 配图与下载/视频素材包结果`。旧左右堆叠表单已隐藏，产品图常驻右侧摘要；视频执行前必须在第 4 步确认脚本和分镜。线上 114 截图已留存：`output/product-commercialization-progressive-ui/copy-online-114-desktop.png`。

## 暂不封版项

- 未完成真实线上 GPT Image 2 配图质量复测。
- 本地真实复测发现 Vidu 5 秒任务成功并回填 OSS，但输入图为方图时实际输出 960x960；这符合 Vidu 单参考图生视频“比例随首帧”的能力边界。上线前必须确认页面、接口文档和 `videoPlan.aspectPolicy` 已明确该约束。
- 未完成真实线上统一 runId 视频素材包任务复测。
- 视频素材包结构化回填已进入本地实现：`script/storyboard/keyframes/segmentVideos/composition`；仍需线上真实链路确认。
- 未形成平台/语气/场景的 golden case 质量基线。
- 未形成产品组图 `product_image_set` 的独立能力契约。
