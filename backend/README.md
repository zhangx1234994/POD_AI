# PODI Backend (FastAPI)

## 启动步骤
1. 安装依赖：
   ```bash
   cd backend
   uv pip install -r <(uv pip compile pyproject.toml) # 或 poetry install
   ```
2. 配置环境变量（示例）：
   ```bash
   export OSS_BUCKET=pod-oss-private
   export OSS_REGION=oss-cn-hangzhou
   export OSS_DOWNLOAD_DOMAIN=https://oss-mock.local
   ```
3. 启动 API：
   ```bash
   uvicorn app.main:app --reload --port 8099
   ```
4. 可选：启动 Celery Worker（未来用于任务调度）。

## 路由摘要
| 路由 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/media/v1/sts` | POST | 获取 OSS 上传凭证 |
| `/api/media/v1/oss-callback` | POST | OSS 回调（占位） |
| `/api/media/v1/signed-download` | POST | 生成下载签名（占位） |
| `/api/wallet/v1/freeze` | POST | 冻结积分（占位） |
| `/api/wallet/v1/confirm` | POST | 积分确认 |
| `/api/wallet/v1/release` | POST | 积分释放 |
| `/api/wallet/v1/transactions` | GET | 流水（Mock） |
| `/api/wallet/v1/statistics` | GET | 统计（Mock） |
| `/api/tasks/v1/submit` | POST | 任务提交，占位 |
| `/api/tasks/v1/{taskId}` | GET | 任务状态占位 |
| `/api/tasks/v1/{taskId}/complete` | POST | 模拟任务完成（驱动积分确认/释放） |
| `/api/notify/v1/stream` | WebSocket | 任务/积分事件推送 |
| `/api/notify/v1/event` | POST | 推送事件（调试） |

## 前端对接
- 前端 `.env` 可将 `VITE_API_BASE_URL` 指向 `http://localhost:8099`。
- 上传：先 `POST /api/media/v1/upload-key` 获取用户级上传 Key，再 `POST /api/media/v1/sts` 获取临时凭证与 `objectKey`，随后使用 `ali-oss` 直传。
- 积分：Task 提交前先调用 `/api/wallet/v1/freeze`，任务结束后根据结果调用 confirm/release。
- 任务状态：当前返回内存数据，后端后续接入队列 + Notification。

## 后续工作
- 替换占位逻辑为真实的 STS、积分、任务调度实现。
- 增加认证、JWT 校验、数据库访问、事件推送。

## OSS 配置与上传流程
- `OSS_ENDPOINT`：阿里云 OSS endpoint，例如 `oss-cn-hangzhou.aliyuncs.com`。
- `OSS_REGION`：Region 描述，保持与 endpoint 一致（`oss-cn-hangzhou`）。
- `OSS_BUCKET`：承载图片的桶名称（例如 `podi`）。
- `OSS_AK` / `OSS_ACCESS_KEY`：上传签名所需的 AccessKeyId（建议使用具备受限权限的 RAM User）。
- `OSS_SK` / `OSS_SECRET_KEY`：与上方 AK 匹配的 Secret。
- `OSS_PUBLIC_DOMAIN`（或 `OSS_DOWNLOAD_DOMAIN`）：前端访问图片所使用的公开域名，会返回给前端拼接 OSS URL。
- `OSS_ROOT_PREFIX`：对象存储目录前缀，默认 `uploads`，可设置为 `test` 等环境隔离路径，系统会在其下追加 `userId/日期/随机串`。
- `OSS_ROLE_ARN`（可选）：若提供，将通过 STS AssumeRole 签发临时 AccessKey，自动限制到 `OSS_ROOT_PREFIX/userId`。未配置时会回退到长期 AK/SK（仅限本地联调使用）。
- `OSS_STS_DURATION`：STS 凭证有效期（秒），默认 900，最大 3600。
- `UPLOAD_TOKEN_SECRET`：签发“用户上传 Key”的服务端密钥。
- `UPLOAD_TOKEN_TTL`：上传 Key 的有效期（秒），默认 3600。

上传流程：
1. 前端调用 `POST /api/media/v1/upload-key`，传入 `userId`，获取一次性 `uploadKey`（可以拉黑用户或调整 TTL 以快速失效）。
2. 持有 `uploadKey` 后调用 `POST /api/media/v1/sts`，携带文件名/taskId 等上下文，后端基于用户生成 `objectKey` 与 STS 临时凭证。
3. 前端使用返回的 `ossCredentials`（`accessKeyId/accessKeySecret/securityToken/endpoint/rootPrefix` 等）直传 OSS，上传路径被限制在 `rootPrefix/userId/...`，即便凭证泄露也只影响特定用户。
4. 上传完成后可回调 `POST /api/media/v1/oss-callback`，后续会在这里校验签名并落库。

> TODO：当前阿里云 `ram:AssumeRole` 权限尚未完全配置，`/api/media/v1/sts` 在失败时会自动回落到长效 AK/SK（`isTemporary=false`）。待补齐 RAM 授权后更新配置，使接口稳定返回 `securityToken`。

## 数据库（任务模型）
- 在 `.env` 中配置 `DATABASE_URL`（本地/线上均需显式提供；不再内置 SQLite 默认值）。
- 当前环境统一使用阿里云 RDS（`rm-bp1r74bu12nt8ibs50o.mysql.rds.aliyuncs.com`），账号 `kanban`，密码 `Chrd5@0987`，库名 `ai_zhongtai`。示例：
  ```bash
  export DATABASE_URL='mysql+pymysql://kanban:Chrd5%400987@rm-bp1r74bu12nt8ibs50o.mysql.rds.aliyuncs.com/ai_zhongtai'
  ```
- 运行 `python scripts/create_schema.py` 会根据 `app/models/task.py` 中的 SQLAlchemy 定义创建以下核心表：
  - `task_batches`：批量任务元数据。
  - `tasks`：单任务主体。
  - `task_assets`：输入/输出资源。
  - `task_events`：状态事件流。
- 运行同一个脚本也会创建 AI 集成所需的管理表：`executors`、`workflows`、`workflow_bindings`、`api_keys`（模型位于 `app/models/integration.py`）。
- 详细字段说明见 `docs/tasks-schema.md`。

## AI 执行节点 & 工作流管理
- 新增 `/api/admin` 下的一系列接口用于管理不同厂商的算力节点与工作流：
  - `GET/POST/PUT/DELETE /api/admin/executors`：管理执行节点（如 ComfyUI、OpenAI、阿里云、火山引擎等）。
  - `GET/POST/PUT/DELETE /api/admin/workflows`：上传/版本管理工作流模版（包括 ComfyUI JSON）。
  - `GET/POST/PUT/DELETE /api/admin/workflow-bindings`：将特定 action 绑定到“工作流 + 执行节点”的组合。
  - `GET/POST/PUT/DELETE /api/admin/api-keys`：集中维护各厂商 API Key，支持状态、配额等字段。
- 后续调度器可根据这些配置将任务分发到不同节点/模型，管理端页面位于前端 `/admin/integrations`。

## Coze Studio 集成
- Coze Studio 作为外部平台接入，当前不在本仓库内维护本地源码包。
- `.env` 需要配置：
  - `COZE_BASE_URL`（例如 `https://<coze-host>`）
  - `COZE_API_TOKEN`（平台服务账号 Token）
  - `COZE_DEFAULT_TIMEOUT`（秒，默认 180）
  - `COZE_LOOP_BASE_URL` 仅作为预留配置（如未启用 Loop 可不填）
- Ability 表新增 `coze_workflow_id` 字段，管理端可在“能力目录”中为 provider=`coze` 的能力填写对应的 workflow id。调用 `/api/abilities/{id}/invoke` 时会直接命中 Coze 工作流而无需额外凭证，日志依然写入 `ability_invocation_logs`。

## ComfyUI Agent 管理（服务器同步）
- 中台对多台 ComfyUI 服务器使用 Agent 进行资源同步与任务回执。
- `.env` 可配置：
  - `AGENT_JWT_SECRETS`（逗号分隔，格式 `kid:secret`）
  - `AGENT_JWT_DEFAULT_KID`（默认 kid）
  - `AGENT_TASK_TOKEN_TTL`（秒，默认 600）
  - `AGENT_HEARTBEAT_TOKEN_TTL`（秒，默认 3600）
  - `AGENT_TASK_TIMEOUT_SECONDS`（任务超时，默认 3600）
  - `AGENT_MANIFEST_BASE_URL`（Agent 拉取 manifest 的公网/内网地址）
- 具体接口与字段见 `docs/comfyui/agent-management.md`。

可以通过 `backend/scripts/test_oss_connection.py` 快速验证是否能够访问到配置的桶：

```bash
cd backend
source .venv/bin/activate
export OSS_AK=xxx OSS_SK=xxx OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com OSS_BUCKET=podi
python scripts/test_oss_connection.py
```

成功后会打印桶名称与 Region，便于确认配置是否正确。
