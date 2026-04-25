# FLUX2-Klein 扩图上线闭环

## 目标

把新版 ComfyUI workflow `flux2_klein_9b_outpaint_v1.json` 作为 **新增能力** 接入中台与 Coze，保持以下原则：

- 不替换现有 `AI扩图` 主链路
- 不破坏现有接口和业务
- 先并行接入，再灰度验证

## 已完成

### 1. 工作流结构审查

已确认这条 workflow 符合当前中台接入要求：

- 输入图节点：`76 · LoadImage.image`
- 扩边节点：`102 · ImagePadForOutpaint`
- 提示词节点：`117 · CLIPTextEncode.text`
- 随机种节点：`99 · RandomNoise.seed`
- 明确输出节点：`9 · SaveImage`

结论：

- 中台对外仍使用 `image_url`
- Coze 对外仍使用 `url`
- 后端需先把远程图片上传到 ComfyUI `input` 目录，再把返回文件名写入节点 `76.image`

### 2. 中台代码接入

已完成的代码层接入：

- Workflow 文件：
  - `/Volumes/MAC 1/pod_codex/backend/app/workflows/comfyui/flux2_klein_9b_outpaint.json`
- Workflow / Binding Seed：
  - `/Volumes/MAC 1/pod_codex/backend/app/services/workflow_seed.py`
- ComfyUI 输入适配：
  - `/Volumes/MAC 1/pod_codex/backend/app/services/executors/comfyui.py`
- Ability 定义 / Schema / Presentation：
  - `/Volumes/MAC 1/pod_codex/backend/app/constants/abilities.py`
- Coze 单功能 OpenAPI：
  - `/Volumes/MAC 1/pod_codex/backend/app/routers/coze_podi_plugin.py`

当前对外能力形态：

- ability key：`flux2_klein_9b_outpaint`
- workflow key：`flux2_klein_9b_outpaint`
- 对外展示名：`FLUX2 扩图`
- surfaces：
  - `admin=true`
  - `eval=true`
  - `coze=true`
  - `client=false`

### 3. 文档同步

已同步以下真源文档：

- `/Volumes/MAC 1/pod_codex/docs/comfyui/README.md`
- `/Volumes/MAC 1/pod_codex/docs/coze/toolbox-inventory.md`

## 已验证

### 1. 本地测试

以下测试已通过：

```bash
cd /Volumes/MAC\ 1/pod_codex/backend
python3 -m pytest \
  tests/test_comfyui_new_toolbox_inputs.py \
  tests/test_workflow_seed_new_comfyui_toolboxes.py \
  tests/test_coze_comfyui_new_toolboxes_openapi.py -q
```

结果：`13 passed`

### 2. 双机模型检查

已确认两台 ComfyUI 节点都具备该 workflow 需要的模型：

- `http://117.50.80.158:8079`
- `http://117.50.216.233:8079`

两台均存在：

- `flux-2-klein-9b-fp8.safetensors`
- `qwen_3_8b_fp8mixed.safetensors`
- `flux2-vae.safetensors`

### 3. 线上后端状态检查

已确认线上后端健康：

- `http://117.50.80.158:8099/health`

但新 OpenAPI 路由当前尚未在线上生效：

- `http://117.50.80.158:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json`

现状：`404`

这说明：

- 本地代码已接好
- 线上后端尚未发布到包含该路由的新版本

## 当前阻塞

当前唯一阻塞点是 **后端生产机发布入口缺失**。

已确认：

- `114.55.0.56` 是 Coze 服务器，可登录并维护
- `117.50.80.158:8099` 提供的是 PODI 后端服务
- 目前无法直接 SSH 到 `117.50.80.158`，因此不能独立完成后端发布

所以当前还不能执行最后两步：

1. 让线上后端暴露新版 OpenAPI
2. 在 Coze 中导入并发布该工具箱

## 拿到发布入口后的动作

一旦拿到 `117.50.80.158` 的发布方式，按这个顺序执行：

1. 发布后端代码
2. 在后端机器执行种子同步
3. 验证新 OpenAPI 路由返回 `200`
4. 使用 Coze 自动导入脚本更新插件
5. 在 Coze 中做一次真实提交和 `/tasks/get` 轮询验证

建议校验命令：

```bash
curl -fsS http://117.50.80.158:8099/api/coze/podi/comfyui/execute/flux2-klein-9b-outpaint/openapi.json
```

插件更新脚本：

```bash
cd /Volumes/MAC\ 1/pod_codex
PODI_PUBLIC_BASE_URL=http://117.50.80.158:8099 \
python3 scripts/ensure_coze_plugin_podi.py
```

## 回归点

发布后至少回归以下场景：

1. 只传 `url`
2. 左右扩图
3. 上下扩图
4. 四边同时扩图
5. 自定义 `prompt`
6. 指定 `seed`
7. 结果图是否成功沉淀 OSS
8. `tasks/get` 是否能正常轮询出 `succeeded + imageUrl/imageUrls`

## 结论

这条能力已经完成了：

- 结构审查
- 本地接入
- 双机模型校验
- OpenAPI 封装
- 文档同步

现在不属于代码问题，而属于 **发布入口问题**。拿到后端上线方式后，可以直接进入最后的 Coze 导入和线上回归阶段。
