# 2026-06-02 PODI Studio Preview 首版骨架

状态：active

## 本轮目标

创建全新的 `podi-studio-preview/` 客户端工程，按能力工作台视角实现第一版可运行骨架，不复用旧客户端代码。

## 用户动线

```text
/workbench
  -> 创建工作单
  -> 进入工作单
  -> 进入花纹提取能力工作区
  -> 登记源图 URL
  -> 提交花纹提取
  -> 轮询任务编号 runId
  -> 查看结果资产
```

## 当前页面

- `/workbench`
- `/workbench/:projectId`
- `/workbench/:projectId/abilities/pattern_extract`
- `/assets`
- `/tasks`
- `/exports/:packageId`

## 本地服务

- 目录：`podi-studio-preview/`
- 端口：`8230`
- URL：`http://localhost:8230/workbench`

## API 边界

当前只调用：

- `GET /api/business/projects`
- `POST /api/business/projects`
- `GET /api/business/projects/{projectId}`
- `POST /api/business/projects/{projectId}/assets`
- `POST /api/business/pattern-extract/runs`
- `POST /api/business/runs/get`
- `POST /api/business/projects/{projectId}/exports`
- `GET /api/business/projects/{projectId}/exports/{packageId}`

未调用 admin、eval、abilities、ability-tasks、ComfyUI、vendor 或 image-ops 内部接口。

## 验证

- `npm install`：通过
- `npm run lint`：通过
- `npm run build`：通过
- 浏览器截图：已完成

截图：

- `output/playwright/podi-studio-preview-20260602/workbench-after-error-copy.png`
- `output/playwright/podi-studio-preview-20260602/pattern-workspace.png`

## 当前风险

- 本轮走查时后端服务未连接成功，页面已改为中文可操作错误提示；真实 API 闭环需后端启动并配置业务 API Key 后继续验证。
- 文件直传没有假实现，当前只支持登记公网图片 URL。
- 计费/余额字段尚未接入，只在页面中提示为后续能力。

