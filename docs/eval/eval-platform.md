# 评测平台（podi-eval-web）功能说明

> 版本：2026-02-03  
> 定位：内部回归验证与打分，不替代生产调用。

## 1. 页面结构

评测端导航固定为 4 个业务分类 + 功能页：

- **通用类 / 花纹提取类 / 图延伸类 / 图裂变**：工具选择与试运行
- **任务**：查看最近运行记录
- **文档**：自动生成的工作流文档（结构化 + Markdown）
- **管理**：管理员维护能力名称/备注/状态（需管理员 token）

## 2. 关键行为（交互）

### 2.1 工具试运行

- 选择工具后自动加载默认参数（来自 `parameters_schema`）
- 图片输入统一字段 `url`
- 运行后写入评测 run，并在列表中轮询刷新

### 2.2 运行记录

- 运行列表每 2s 自动刷新（用于及时看到回调结果）
- 支持筛选（状态/评分/未评分）与关键词搜索

### 2.3 文档页

- 拉取 `GET /api/evals/docs/workflows`
- 支持结构化表格和 Markdown 视图切换

### 2.4 管理页

- 通过 `EVAL_ADMIN_TOKEN` 登录（本地存储）
- 支持编辑：名称、备注、状态、分类、版本

## 3. 前端请求与接口映射

`podi-eval-web/src/api.ts`：

- `GET /api/evals/me`
- `GET /api/evals/workflow-versions?status=active`
- `POST /api/evals/runs`
- `GET /api/evals/runs`
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

