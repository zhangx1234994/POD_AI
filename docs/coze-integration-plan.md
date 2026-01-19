# Coze Studio / Coze Loop 集成方案（裸机部署 + 替换 n8n）

本文档汇总了在当前仓库内本地拉取的 `coze-studio` 与 `coze-loop` 项目，如何在我们平台中以“裸机部署 + 平台统一账号”方式落地，并逐步取代 n8n 的编排、日志能力。

---

## 一、Coze Studio 本地部署

### 依赖组件
- **语言/工具链**：Go >= 1.25.5（`brew install go@1.25 --build-from-source`；`echo 'export PATH="/opt/homebrew/opt/go/libexec/bin:$PATH"' >> ~/.zshrc` 确保系统使用新版 Go）、Node.js >= 21、PNPM 8.15.8、Rush 5.147.1、Nginx。
- **基础服务**：MySQL 8.4.5、Redis 8.0、Elasticsearch 8.18（需要 smartcn 插件）、OSS/MinIO（图片上传）。
- **数据库连接**：沿用现有 `DATABASE_URL`（线上 MySQL），Studio/Loop/Backend 全部指向同一 DSN，避免多套数据源。
- **模型配置**：通过 `backend/conf/model/` & 管理端 `/admin/#model-management` 配置 OpenAI、火山方舟等模型。

### 裸机部署步骤
1. **数据库**：依据 `docker/docker-compose.yml` 中的 entrypoint，将 `init.sql`、Atlas 迁移流程转成系统脚本；初始化 `opencoze` 库。
2. **Redis/Elasticsearch**：按 compose 中的配置启动，Elasticsearch 需先安装 smartcn 插件并导入 `volumes/elasticsearch/es_index_schema`。
3. **后端**：`cd coze-studio/backend && go build ./cmd/...`；配置 `.env`（数据库、Redis、OSS、模型等），以 systemd 方式运行。
4. **前端**：`rush install && rush build`；将 `frontend/apps/coze-studio/dist` 部署到我们统一的前端容器。
5. **首次启动**：访问 `http://localhost:8888/sign` 注册平台管理员 → `/admin/#model-management` 录入模型 → 各类插件/基础组件按 README 配置。
6. **安全建议**：若开放公网，需要在网关禁用对外注册、限制 Python 执行节点、修改监听端口，并加 WAF/SSRF 防护。

---

## 二、Coze Loop 本地部署

### 依赖组件
- **服务链**：MySQL、Redis、ClickHouse、MinIO、RocketMQ（namesrv + broker）、Python FaaS、JS FaaS。
- **配置**：`release/deployment/docker-compose/conf/model_config.yaml` 指定模型 API key 和 endpoint；`model_runtime_config.yaml`、`observability.yaml` 等用于 prompt/eval/trace。

### 裸机部署步骤
1. 根据 `release/deployment/docker-compose/bootstrap/*` 中的脚本，为 MySQL、Redis、ClickHouse、MinIO、RocketMQ 等编写系统服务。
2. 初始化数据库、对象存储、消息队列（参考 bootstrap 下的 `*-init/entrypoint.sh`、`init-sql`）。
3. 启动 `coze-loop-app` 服务（Go 后端 + 前端 UI），确保环境变量指向上面配置的基础服务。
4. 访问 `http://localhost:8082` 验证 Prompt/Evaluation/Trace 模块。

---

## 三、平台集成策略

### 统一服务账号
- 我们的后端已有 `SERVICE_API_TOKEN` 支持。Coze Studio/Loop 中创建一个“平台服务账号”，由平台配置中心统一管理。
- 调用 Coze API 时，Credential 的默认 Access Token 设置为该值，避免普通用户逐个配置。
- `.env` 中新增 `COZE_BASE_URL`/`COZE_LOOP_BASE_URL`/`COZE_API_TOKEN`/`COZE_DEFAULT_TIMEOUT`，FastAPI 通过 `coze_client` 统一调用 `/v1/workflow/run`，管理端可跳转到 Studio/Loop。

### 能力映射
- Ability 表新增 `coze_workflow_id`（或 agent_id），记录 Coze Studio 工作流。
- `/api/abilities/{id}/invoke` 逻辑：根据 ability metadata → 构建 Coze Workflow API 请求 → 调用 Coze → 把结果写入 `ability_invocation_logs` 并同步到 Coze Loop（Trace）。
- 前端仍用我们的动态表单，内部把字段映射到 Coze Workflow 所需的 JSON，用户无感知。

### 日志与监控
- 调用成功后，使用 Coze Loop SDK 上报执行 Trace，保持 Loop 中的可观测能力。
- 保留现有 `ability_invocation_logs` 接口，管理端可继续查看历史记录，Loop 作为更深的观测工具。

### 迁移流程
1. 按上文部署并运行 Coze Studio & Loop。
2. 在 Studio 中为所有“原子能力”创建工作流模板，记录 workflow ID。
3. Ability 表写入新映射，更新 `ability_invocation_service`。
4. 工程完成后，逐步删掉 n8n 相关代码、配置、文档，保留必要的迁移说明。

---

## 四、替换 n8n 的后续动作
1. **部署脚本**：将 Coze Studio/Loop 的服务部署脚本（systemd、配置模板）纳入仓库的 `scripts/` 目录，以便 CI/CD 使用。
2. **调用代码**：在后台 ability 服务中新增 Coze Workflow 调用模块，并集成 Loop Trace SDK。
3. **前端改造**：保持现有动态表单，内部新增 ability metadata → Coze payload 的映射层。
4. **清理 n8n**：确认 Coze 路径稳定后，删除 `vendor/n8n`、`vendor/n8n-custom-nodes`、脚本、文档，以及相关环境变量。
