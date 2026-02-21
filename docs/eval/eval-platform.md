# 评测平台（podi-eval-web）功能说明

> 版本：2026-02-21  
> 定位：内部回归验证与打分，不替代生产调用。

## 1. 页面结构

评测端导航固定为 5 个业务分类 + 功能页：

- **通用类 / 花纹提取类 / 图延伸类 / 四方/两方连续图类 / 图裂变**：工具选择与试运行
- **LoRA 批测**：独立批量回归页（不属于上述 5 个分类），仅展示含 LoRA 字段的工作流
- **任务**：查看最近运行记录
- **文档**：自动生成的工作流文档（结构化 + Markdown）
- **管理**：管理员维护能力名称/备注/状态（使用评测端专用 `EVAL_ADMIN_TOKEN`，非管理端 JWT）

## 2. 关键行为（交互）

### 2.1 工具试运行

- 选择工具后自动加载默认参数（来自 `parameters_schema`）
- 图片输入统一字段 `url`
- 运行后写入评测 run，并在列表中轮询刷新

### 2.2 运行记录

- 运行列表每 2s 自动刷新（用于及时看到回调结果）
- 支持筛选（状态/评分/未评分）与关键词搜索

### 2.3 LoRA 批测

- 入口：顶部导航 `LoRA批测`
- 参数：
  - 工作流：仅可选“参数 schema 含 LoRA 字段且含 `url` 字段”的工作流
  - LoRA：优先读取 schema options；若未配置枚举值则允许手动输入
  - 提示词：若该工作流支持 `prompt` 字段则可填写；不支持时输入框置灰
  - 其他入参：按 workflow schema 动态展示（可选/必填），不支持的字段置灰提示
  - 测试次数：每张图重复提交次数（用于降低随机性）
  - 并发提交：批次提交并发数（建议 1~4）
  - 输出尺寸策略：
    - 原图大小：不下发尺寸字段（保持工作流默认）
    - 推荐 1K：优先下发 `resolution=1K`；若工作流只有 `width/height`，则按原图比例换算为“最长边=1024”
    - 自定义：可选画幅比例与分辨率
- 行为：
  - 任务口径：一次“上传图片 + 点击提交”定义为一个测试任务（批次）（可包含多张图）
  - 批量上传后，评测端先上传 OSS，再按“每图 * 次数”提交 `POST /api/evals/runs`
  - 单批上限 5000 条（图片数 * 测试次数），超过需分批执行
  - 提交进度卡展示：样本图片数、每图测试次数、计划执行条数、已提交执行、已完成执行、有图完成
  - 批次保留：历史批次会保留在页面中，可通过“查看批次”切换，不会因“清空图片”被删除
  - 批次列表不再跟随“当前工作流”筛选，避免切换工作流后找不到历史批次
  - 批次历史来源：页面优先从后端批次接口加载，不依赖当前浏览器内存；刷新页面后仍可查看历史批次
  - 弱网处理：批次列表/明细均提供“刷新”按钮，并显示最近一次加载失败原因
  - 批次停止：支持“停止本批次”，会把该批次未完成任务置为失败，避免继续占用服务器资源
  - 自动做必填默认值检查：缺少默认参数时阻止提交并提示补齐能力配置
  - 后端调度隔离：ComfyUI 与商业模型（KIE/火山）分开并发池执行，互不占用执行槽位
  - 页面状态分离：
    - 已提交：仅表示 run 创建成功
    - 已完成：表示 run 状态已变为 succeeded/failed
    - 有图完成：表示 succeeded 且 `result_image_urls_json` 非空
  - 对照标注：
    - 以“原图”为一行，横向平铺“原图 + 全部结果图”（不再按第几次折叠拆分）
    - 每张结果图可标注：满意 / 不满意 / 未标注，并可填写原因与备注
    - 支持导出 CSV（全部对照集 / 仅不满意样本），用于后续训练覆盖分析

### 2.4 文档页

- 拉取 `GET /api/evals/docs/workflows`
- 支持结构化表格和 Markdown 视图切换

### 2.5 管理页

- 通过 `EVAL_ADMIN_TOKEN` 登录（本地存储，Header: `X-Eval-Admin-Token` 或 URL `?admin_token=`）
- 支持编辑：名称、备注、状态、分类、版本

## 3. 前端请求与接口映射

`podi-eval-web/src/api.ts`：

- `GET /api/evals/me`
- `GET /api/evals/workflow-versions?status=active`
- `POST /api/evals/runs`
- `GET /api/evals/runs`
- `GET /api/evals/runs/batches`
- `POST /api/evals/runs/batches/{batch_id}/stop`
- `GET /api/evals/runs/{run_id}`
- `POST /api/evals/runs/{run_id}/annotations`
- `GET /api/evals/docs/workflows`
- `POST /api/evals/uploads`
- 管理接口：`/api/evals/admin/workflow-versions`

## 4. 参数契约

- 图片输入统一 `url`
- 像素参数必须为纯数字（禁止 `px`）
- 枚举参数必须传 value

## 5. 注意事项

- 如开启 `EVAL_PUBLIC_TOKEN`，前端请求需带 `X-Eval-Token` 或 URL `?token=`（当前前端未内置 header，需通过 URL 注入）。
- 管理 token 会存于 `localStorage`，需妥善保管。

## 6. 问题与优化记录

详见 `docs/standards/issue-improvement-log.md`。
