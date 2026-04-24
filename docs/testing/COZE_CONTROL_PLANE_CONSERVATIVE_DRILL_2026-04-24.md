# Coze 控制面保守演练记录

日期：2026-04-24  
主机：`114.55.0.56`  
范围：只部署 `backend + image-ops`，不切 toolbox，不动 `8199 / 8200`

## 结论

本轮保守演练已经完成到：

1. Coze 主机真实环境基线核查
2. `python3.11` 运行时补齐
3. `backend + image-ops` 实际部署成功
4. `bundle check` 通过
5. `backend -> image-ops` 三条图片原子能力真实链路通过

当前还没有完成的是：

- 11 条主 Coze workflow 的完整串行冒烟报告

原因不是控制面已失败，而是现有 `coze_workflow_smoke.py` 串行执行时间过长，不适合作为本轮结论阻塞项。

## 主机基线

演练前确认：

- OS：Alibaba Cloud Linux 3
- 内存：约 8G
- swap：1G
- 磁盘：49G，剩余约 24G
- 迁移目标端口：
  - `8099`
  - `8301`
  - `8199`
  - `8200`
- 当时只有 `8888` 被 Coze 使用，`8099/8301/8199/8200` 空闲

## 真实阻塞与修正

本轮演练实际暴露了 5 个问题，均已修正：

### 1. Coze 主机默认 Python 版本过低

真实情况：

- `python3 = 3.6.8`

修正：

- 安装 `python3.11`
- 所有迁移脚本增加 `PYTHON_BIN`，优先显式使用 `python3.11`

### 2. backend 缺少正式依赖声明：`pydantic-settings`

现象：

- `alembic upgrade head` 失败
- `ModuleNotFoundError: pydantic_settings`

修正：

- `backend/pyproject.toml` 补 `pydantic-settings`

### 3. backend 缺少正式依赖声明：`email-validator`

现象：

- systemd 下 `podi-backend` 反复重启
- `ImportError: email-validator is not installed`

修正：

- `backend/pyproject.toml` 补 `email-validator`

### 4. `image-ops-service` packaging 边界未收死

现象：

- `pip install -e .` 失败
- setuptools 自动发现 `app` 和 `deploy` 两个顶层包

修正：

- `image-ops-service/pyproject.toml` 显式指定：
  - `packages = ["app"]`

### 5. 演练脚本与真实接口口径不一致

现象：

- `bundle check` 把 `/api/evals/workflow-versions` 错判成 `dict`
- `bundle check` 保守模式下仍然错误检查 `8199 / 8200`
- `image-ops smoke` 从公共 `/api/abilities` 找能力，拿不到已隐藏的 3 条 PODI 原子能力

修正：

- `check_coze_control_plane_migration.py` 改成按真实 eval 接口校验 `list`
- `check_coze_control_plane_bundle.sh` 支持显式空值，保守模式可跳过前端
- `run_coze_control_plane_cutover.sh` 在 `backend-image-ops` 模式下默认跳过 `8199 / 8200`
- `smoke_image_ops_via_backend.py` 增加数据库真源回退查找

## 保守部署结果

最终在 Coze 主机上实际落起：

- `podi-backend.service`
- `image-ops.service`

对应目录：

- `/srv/pod/backend`
- `/srv/pod/image-ops-service`

对应端口：

- `8099`
- `8301`

## post-check 结果

### 1. bundle check

通过：

- `GET /health`
- `GET /api/abilities`
- `GET /api/evals/workflow-versions`
- `GET /api/coze/podi/openapi.json`
- `GET /api/coze/podi/comfyui/openapi.json`
- `GET image-ops /health`

### 2. backend -> image-ops 真链路

真实通过：

- `expand_mask_color`
- `set_dpi`
- `upscale_resize`

结果均为：

- `HTTP 200`
- `status = succeeded`
- 返回图片和资产均存在

## 当前剩余缺口

### 1. 主 Coze workflow 大烟测脚本耗时过长

现状：

- 现有 `coze_workflow_smoke.py` 串行跑 11 条 workflow
- 单次演练时间过长
- 本轮未拿它作为阻塞性结论

建议：

- 下一步把主 workflow smoke 拆成：
  - 分组运行
  - 实时输出进度
  - 每条完成就落部分结果

### 2. `smoke_image_ops_via_backend.py` 的 stdout 输出异常

现状：

- 退出码为 `0`
- 但标准输出为空

这不影响当前链路真实验证，因为已用内联请求确认结果；但脚本本身仍应补一次输出行为修正。

## 当前判断

一句话结论：

**保守演练已经证明 Coze 主机可以承载 `backend + image-ops` 控制面组合，当前剩下的不是“能不能部署”，而是把主 workflow 抽检脚本改得更适合真实迁移窗口使用。**
