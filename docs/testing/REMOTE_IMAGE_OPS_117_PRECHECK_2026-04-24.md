# 117 Image Ops 切换前检查记录（2026-04-24）

## 目标

确认 `117.50.80.158` 复用 `8200` 承载 image-ops 前，Coze 主机和旧回滚入口处于安全状态。

## 检查命令

在 Coze 主机执行：

```bash
cd /srv/pod
/srv/pod/backend/.venv/bin/python /srv/pod/scripts/check_remote_image_ops_cutover.py --phase pre
```

## 结果

- Coze backend `http://127.0.0.1:8099/health`：通过。
- Coze backend 当前 `IMAGE_OPS_BASE_URL=http://127.0.0.1:8301`：符合预期，尚未切 117。
- `117.50.80.158:8099/health`：通过，旧 backend 回滚入口仍在。
- `117.50.80.158:8200/health`：连接拒绝，符合预期，说明 image-ops 尚未占用旧 eval 端口。

## 结论

可以进入 117 更新窗口，但更新动作仍需按顺序执行：

1. 在 117 拉取包含 `deploy_image_ops_only.sh` 的新版本。
2. 使用 `DEFAULT_IMAGE_OPS_PORT=8200` 写入 image-ops `.env`。
3. 使用 `REUSE_8200=1 bash scripts/deploy_image_ops_only.sh` 启动 image-ops。
4. 从 Coze 主机执行 `check_remote_image_ops_cutover.py --phase post-117`。
5. post-117 通过后，再切 Coze backend 的 `IMAGE_OPS_BASE_URL`。
