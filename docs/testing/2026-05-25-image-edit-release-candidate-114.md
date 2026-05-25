# 2026-05-25 图编辑 114 候选发布记录

## 候选范围

本次只更新 114 控制面：

- `backend/`
- `podi-admin-web/`
- `podi-eval-web/`
- `docs/`
- `scripts/`

不更新 4090/5090/ComfyUI 能力机，不调整扩图路由，不把扩图固定到 4090。

## 变更摘要

- 图编辑 `canvas_outpaint` 已纳入发布巡检脚本，覆盖四边、单边、横向、纵向四类样例。
- 图编辑业务 API 线上真实巡检 8/8 成功，证据见 `deliverables/image_edit_patrol_online_20260525/20260525_065932/summary.json`。
- 测评端图编辑工作台补交互保护：
  - 防快速重复提交。
  - 参数变更后隐藏上一条结果，避免误读。
- 管理端业务运行页降噪：
  - 内部巡检/测评任务显示为内部或测评提交，不再误报外部入口缺失。
  - OpenAI/GPT Image 2 这类无固定 executor 的任务显示为第三方模型通道。
- 图编辑业务方接入策略补齐：
  - 推荐托管组件 `/image-edit`。
  - 源码组件集成必须读取 `/api/business/image-edit/component-config`。
  - 配置接口新增 `componentVersion/configVersion/updatePolicy`，方便后续配置更新免业务方发版。

## 已覆盖验证

- `backend/.venv/bin/python -m pytest backend/tests/test_business_api_contract.py -q`
- `python3 scripts/check_doc_entry_references.py`
- `python3 scripts/check_error_catalog.py`
- `podi-admin-web npm run lint`
- `podi-admin-web npm run build`
- `podi-eval-web npm run lint`
- `podi-eval-web npm run build`
- 生产静态包浏览器检查：
  - `http://127.0.0.1:8299/#nav=business` 无 console error。
  - `http://127.0.0.1:8300/image-edit` 无 console error，并能进入图编辑工作台。
- 线上真实图编辑巡检：8/8 succeeded。
- 线上测评端手工扩展画布成功：测评 run `fe55d212c2ce40ce9e87a168387dc2a7`，中台任务 `25ce8e4757a4479fba287e8790432775`。

## 上线步骤

按唯一发布入口执行：

```bash
bash scripts/release_114_control_plane.sh
```

如果 SSH 需要密码，使用临时环境变量：

```bash
SSHPASS='<临时 SSH 密码>' bash scripts/release_114_control_plane.sh
```

本次不启用 `RUN_LIVE_PATROL=1`，因为 GPT Image 2 真实图编辑巡检已在上线前单独完成；上线后再做轻量复核和必要的单条手工提交。

## 上线后验证

1. 后端健康：

```bash
curl -fsS http://114.55.0.56:8099/health
```

2. 图编辑组件配置：

```bash
curl -fsS http://114.55.0.56:8099/api/business/openapi.json | grep -q 'image-edit/component-config'
```

3. 测评端 `/image-edit` 用户动线：

- 打开 `http://114.55.0.56:8200/image-edit`。
- 选择扩展画布。
- 粘贴主图 URL。
- 选择向右扩展。
- 提交一次，确认只创建一个 run。
- 修改参数，确认右侧不再展示上一条结果。

4. 管理端业务运行页：

- 打开 `http://114.55.0.56:8199`。
- 进入业务能力/业务运行。
- 确认内部巡检和测评端 run 不再显示误导性的“未记录入口调用”。
- 确认 GPT Image 2 图编辑任务显示第三方模型通道或等价文案。

## 回滚口径

- 失败优先回滚 114 控制面上一版目录，不做数据库 destructive 回滚。
- 如仅前端交互异常，可先回滚管理端/测评端静态产物。
- 如后端启动异常，恢复上一版 backend 目录并保留当前线上 `.env` 与 `.venv`。
- 回滚后必须跑：

```bash
curl -fsS http://127.0.0.1:8099/health
BACKEND_URL=http://127.0.0.1:8099 ADMIN_URL=http://127.0.0.1:8199 EVAL_URL=http://127.0.0.1:8200 bash scripts/deploy_preflight.sh
```

## 剩余风险

- 5090 ComfyUI 扩图 `DrawMaskOnImage.opacity` 节点差异未在本次处理，继续由节点侧修复。
- 测评端历史列表轮询仍偏重，作为后续性能/体验优化项。
- 源码组件分发尚未独立打包成 npm 包；当前对业务方优先推荐托管组件或源码目录交付。
