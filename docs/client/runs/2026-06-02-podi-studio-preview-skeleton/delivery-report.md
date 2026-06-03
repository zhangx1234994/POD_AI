# Delivery Report

## 本轮目标

按客户端主开发机制创建新的 PODI Studio Preview 工程，完成第一版单能力生产 MVP：工作单、花纹提取、裂变候选、候选选择、资产/任务/导出入口。

## 已实现

- 新建 `podi-studio-preview/`。
- 新建 React + Vite + TypeScript 最小工程。
- 实现顶部 API Key 配置。
- 实现 `/workbench` 工作台。
- 实现创建工作单入口。
- 实现工作单详情页。
- 实现花纹提取能力工作区。
- 实现源图 URL 登记。
- 实现花纹提取提交和 runId 轮询。
- 实现裂变候选能力工作区。
- 实现从花纹结果继续提交裂变。
- 实现裂变候选选择并写入业务选择接口。
- 实现工作单资产、任务、导出草稿页面骨架。
- 实现中文网络错误提示。
- 实现业务 API 500 的可读错误提示。

## 用户动线

```text
进入 /workbench
  -> 配置 API Key
  -> 创建工作单
  -> 进入花纹提取
  -> 登记图片 URL
  -> 提交业务能力
  -> 查看任务编号和状态
  -> 查看结果资产
  -> 从花纹结果进入裂变候选
  -> 选择候选
  -> 生成交付草稿
```

## API 调用

| API | 用途 | 状态 |
| --- | --- | --- |
| `GET /api/business/projects` | 最近工作单 | 已接入 |
| `POST /api/business/projects` | 创建工作单 | 已接入 |
| `GET /api/business/projects/{projectId}` | 工作单详情 | 已接入 |
| `POST /api/business/projects/{projectId}/assets` | 登记源图 URL | 已接入 |
| `POST /api/business/pattern-extract/runs` | 提交花纹提取 | 已接入 |
| `POST /api/business/fission/runs` | 提交裂变候选 | 已接入 |
| `POST /api/business/runs/get` | 轮询 runId | 已接入 |
| `POST /api/business/projects/{projectId}/selections` | 保存候选选择 | 已接入 |
| `POST /api/business/projects/{projectId}/exports` | 生成交付草稿 | 已接入 |

## 验证

| 项 | 结果 |
| --- | --- |
| `npm install` | 通过 |
| `npm run lint` | 通过 |
| `npm run build` | 通过 |
| 浏览器截图 | 通过，已保存截图 |
| 后端健康检查 `/health` | 通过 |
| 业务项目列表 `/api/business/projects` | 阻塞：数据库缺少 `business_projects` 表 |

## 截图证据

- `/workbench`：`output/playwright/podi-studio-preview-20260602-mvp/workbench-final.png`
- 花纹提取错误态：`output/playwright/podi-studio-preview-20260602-mvp/pattern-error.png`
- 裂变候选错误态：`output/playwright/podi-studio-preview-20260602-mvp/fission-error.png`

## Gap

- 文件直传到业务资产链路未确认。
- 花纹提取预计消耗与余额数据缺失。
- 产品图生产能力仍未开放，MVP 暂停在候选选择和交付草稿。
- 当前 RDS 缺少业务工作单表，真实联调需要先执行后端迁移。

## 剩余风险

- 后端已启动且 `/health` 正常，但 `/api/business/projects` 返回 500；日志显示 `Table 'ai_zhongtai.business_projects' doesn't exist`。
- 当前数据库为阿里云 RDS，不应在未确认环境归属前由客户端侧擅自执行 Alembic 迁移。
- 产品图和导出完整 ZIP 尚未进入真实闭环，当前只做到候选选择与交付草稿。

## 下一轮建议

1. 由后端负责人确认 RDS 环境后执行业务项目相关迁移。
2. 跑通创建工作单、登记 URL、花纹提取、轮询结果。
3. 跑通裂变候选、候选选择、交付草稿。
4. 如果成功结果未自动沉淀资产，记录中台回填 gap。
