# PODI × Coze：能力插件接入（本地单机）

## 目标
- 把 PODI 的所有“原子能力”在 Coze Studio 里作为 **Tools（插件工具）** 可选、可拖拽、可配置。
- 不需要用户手工填大段 JSON；表单字段由 PODI `Ability.input_schema` 自动生成。

## 运行前提
- PODI 后端在本机运行：`http://127.0.0.1:8099`
- Coze Studio 已在 Docker/Lima 里运行：`http://127.0.0.1:8888`

## 插件 OpenAPI 地址
Coze 需要导入一个 OpenAPI 文档，我们由 PODI 后端动态生成：

`http://host.docker.internal:8099/api/coze/podi/openapi.json`

说明：
- `host.docker.internal` 是 **Coze 容器访问宿主机** 的固定域名。
- PODI 后端需要绑定 `0.0.0.0:8099`（已在 `scripts/dev_restart_backend.sh` 里做了）。

## Coze Studio 导入步骤
1. 打开 Coze Studio：`http://127.0.0.1:8888`
2. 进入插件管理（Plugin / Tools 管理页面）
3. 选择“导入 OpenAPI / Import OpenAPI”
4. 粘贴 OpenAPI 地址：`http://host.docker.internal:8099/api/coze/podi/openapi.json`
5. 导入后，工具列表将出现 `PODI Abilities` 下的各个能力（一个能力一个 tool）

## 调用说明
- 每个 Tool 的字段来自 `Ability.input_schema.fields`，并在请求体中以同名字段传入。
- PODI 后端会将这些字段封装为 `AbilityInvokeRequest.inputs` 并执行能力。
- 字段描述会尽量包含「用途 + 默认值」，用户不填时会走能力的 `default_params`（若有）。

参数契约（务必统一）：
- 图片输入统一为 `url`（字符串）。
- 像素类字段必须为纯数字（禁用 `px`）。

更完整的 Coze 工具箱契约说明见：
- `docs/coze/toolbox-contracts.md`

### 调试输出（强烈推荐）
Coze 只会展示 OpenAPI response schema 里声明过的字段。PODI 插件统一提供：
- `debugRequest`：PODI 实际发送给厂商的请求 payload（截断）
- `debugResponse`：厂商原始响应 payload（截断）

当你感觉“参数没传过去 / 图片没生效”时，优先看 `debugRequest` 是否包含你填的字段（例如 `reference_image_urls`）。

## ComfyUI 异步执行（推荐）
由于 ComfyUI 可能排队、并且 Coze 单节点有超时上限，因此 ComfyUI 工具默认采用“两段式”：
1) 调用 ComfyUI 工具（例如 `comfyui/yinhua_tiqu`）时，会立即返回 `taskId/taskStatus`（提交成功即可继续后续节点）
2) 用 `PODI · 查询任务状态/结果`（对应 OpenAPI 路径：`POST /api/coze/podi/tasks/get`）轮询拿结果

建议工作流写法：
`ComfyUI 提交节点` → `任务查询节点(循环/重试)` → `后续处理节点`

提示：
- 插件更新发布后，Coze 工作流里旧节点可能缓存旧 schema；如发现字段/输出不对，请删除节点后重新拖入。
- 多台 ComfyUI 执行节点：`/tasks/get` 会优先根据 `executorId` 从数据库读取该节点的 `baseUrl` 再拉取 `/history/{promptId}`，
  避免因为 `baseUrl` 写错导致“已生成但不刷新”。
- 若轮询一直拿不到结果，展开 `debugResponse`（或查看 `ability_tasks.error_message`）可看到最近一次失败原因
  （例如 `COMFYUI_HISTORY_HTTP_502` / `connect timeout` 等）。

## 多图输出规则（统一）
部分能力会返回多张图片（例如火山图像生成、KIE 多参考输出、ComfyUI 批量）。我们统一约定：
- `imageUrls`：所有输出图片的 URL（优先返回 OSS URL，顺序与厂商返回一致）
- `imageUrl`：`imageUrls` 的第一张（用于最常见的“单图继续处理”场景）

## 火山 Seedream 参考图说明
Seedream 图像生成使用 Ark `/api/v3/images/generations`，图生图/参考图字段为 `reference_image_urls`。
在 Coze 表单里你填的 `image_urls/image_url`，PODI 会同步写入 `reference_image_urls`，以减少“参考图被忽略”的情况。

## 内部鉴权（可选）
默认做法是“内部网络放行”（单机内网部署）。如果你希望更严格：
- 在 `backend/.env` 设置 `SERVICE_API_TOKEN=...`
- Coze 侧在请求头里统一加 `Authorization: Bearer <SERVICE_API_TOKEN>`

（当前代码也支持 `Authorization: Bearer <SERVICE_API_TOKEN>`；未设置时会按内网来源放行。）

## 跳板账号（PODI 后端）
PODI 后端没有注册入口，可通过脚本创建一个固定 admin 用户：

```bash
export BRIDGE_ADMIN_USERNAME=bridge_admin
export BRIDGE_ADMIN_EMAIL=bridge@podi.local
export BRIDGE_ADMIN_PASSWORD='请设置一个强密码'
bash scripts/ensure_bridge_admin.sh
```

## 跳板账号（统一：PODI + Coze Studio + Coze Loop）
为了“一个平台账号贯穿多个系统”，我们提供了一键脚本（不会打印密码）：

1) 在 `backend/.env` 写入（或用环境变量注入）：

```bash
BRIDGE_USERNAME=your_username
BRIDGE_EMAIL=you@example.com
BRIDGE_PASSWORD=your_password
COZE_BASE_URL=http://127.0.0.1:8888
COZE_LOOP_BASE_URL=http://127.0.0.1:8082
```

2) 执行：

```bash
bash scripts/ensure_bridge_all.sh
```

## 问题与优化记录

- 详见 `docs/standards/issue-improvement-log.md`（滚动维护）。

说明：
- Coze Studio 支持通过 `/api/user/update_profile` 设置 `user_unique_name`（若冲突会跳过更新）。
- Coze Loop 通过 `/api/foundation/v1/users/session` 获取 user_id 后再调用 `/users/:user_id/update_profile` 设置 `name`（作为唯一名）。
