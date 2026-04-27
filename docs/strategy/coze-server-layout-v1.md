# Coze 主机目录与 systemd 约定 v1

> 目标：把 Coze 主机上的目录、服务名、日志位置和启动方式固定下来。  
> 原则：迁移当天不再临时决定目录结构；所有服务都有固定名字。

## 1. 目录约定

Coze 主机统一使用：

```text
/srv/pod
```

目录建议：

```text
/srv/pod/
  backend/
  image-ops-service/
  podi-admin-web/
  podi-eval-web/
  scripts/
  logs/
  runtime/
```

说明：

- `backend/`：中台后端代码与 `.env`
- `image-ops-service/`：图片原子能力服务代码与 `.env`
- `podi-admin-web/`：管理端代码与 `dist/`
- `podi-eval-web/`：测评端代码与 `dist/`
- `scripts/`：静态代理和联调脚本
- `logs/`：手工启动或兜底脚本日志
- `runtime/`：本地缓存、临时检查产物

## 2. systemd 服务名约定

统一服务名：

- `podi-backend`
- `image-ops`
- `podi-admin-web`
- `podi-eval-web`
- `podi-eval-health-watch.timer`

对应模板：

- `deploy/systemd/podi-backend.service`
- `image-ops-service/deploy/image-ops.service`
- `deploy/systemd/podi-admin-web.service`
- `deploy/systemd/podi-eval-web.service`
- `deploy/systemd/podi-eval-health-watch.service`
- `deploy/systemd/podi-eval-health-watch.timer`

要求：

- 服务名固定，不允许一台机器一个名字
- 迁移、回滚、排障全部使用这套名字

## 3. 端口约定

固定端口：

- `8888` Coze
- `8099` backend
- `8301` image-ops
- `8199` admin
- `8200` eval

说明：

- `8301` 只允许 Coze 主机本机访问，默认监听 `127.0.0.1`，不要对公网开放
- `8199 / 8200` 只允许 build 产物 + static proxy
- 不允许长期 `vite dev`

## 4. `.env` 位置约定

### backend

```text
/srv/pod/backend/.env
```

### image-ops

```text
/srv/pod/image-ops-service/.env
```

要求：

- 不把正式环境变量散在 shell history 里
- 不在 systemd unit 里硬编码敏感值
- 统一走 `EnvironmentFile`

## 5. 日志约定

### systemd

正式运行优先看：

```bash
journalctl -u podi-backend -f
journalctl -u image-ops -f
journalctl -u podi-admin-web -f
journalctl -u podi-eval-web -f
journalctl -u podi-eval-health-watch.service -n 80 --no-pager
```

### 脚本兜底

如果临时使用仓库脚本，则日志统一落：

```text
/srv/pod/logs/
```

建议文件名：

- `backend-8099.log`
- `image_ops.log`
- `admin-8199.log`
- `eval-8200.log`

## 6. 启动顺序约定

标准顺序：

1. `podi-backend`
2. `image-ops`
3. `podi-admin-web`
4. `podi-eval-web`

说明：

- Coze 自身保持原有容器启动方式
- 本次只规范中台侧服务

## 7. 安装命令约定

### backend

```bash
cp deploy/systemd/podi-backend.service /etc/systemd/system/podi-backend.service
systemctl daemon-reload
systemctl enable podi-backend
systemctl start podi-backend
```

### image-ops

```bash
cp image-ops-service/deploy/image-ops.service /etc/systemd/system/image-ops.service
systemctl daemon-reload
systemctl enable image-ops
systemctl start image-ops
```

### admin / eval

```bash
cp deploy/systemd/podi-admin-web.service /etc/systemd/system/podi-admin-web.service
cp deploy/systemd/podi-eval-web.service /etc/systemd/system/podi-eval-web.service
systemctl daemon-reload
systemctl enable podi-admin-web podi-eval-web
systemctl start podi-admin-web podi-eval-web
```

### eval health watch（可选）

```bash
cp deploy/systemd/podi-eval-health-watch.service /etc/systemd/system/podi-eval-health-watch.service
cp deploy/systemd/podi-eval-health-watch.timer /etc/systemd/system/podi-eval-health-watch.timer
systemctl daemon-reload
systemctl enable --now podi-eval-health-watch.timer
```

说明：

- 该定时任务每 15 分钟执行一次评测链路健康检查。
- `warning` 和 `critical` 都会让单次 service 以失败状态结束，便于通过 `systemctl status` / `journalctl` 发现。
- 启用前必须先手工跑通 `backend/.venv/bin/python backend/scripts/check_eval_operations_health.py`。

## 8. 最小结论

迁移当天默认假设：

- 代码目录固定在 `/srv/pod`
- 服务名固定
- 端口固定
- 日志入口固定

这样回滚和排障才有统一口径。
