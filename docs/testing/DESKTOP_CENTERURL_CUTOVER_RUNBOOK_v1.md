# 桌面端 CenterUrl 切换执行清单 v1

> 用途：第二阶段切换桌面端 `CenterUrl` 时，直接按这份清单执行。  
> 前提：首轮 Coze + backend 同机迁移已经稳定。

## 1. 本批次只做什么

只做：

- 安装包默认 `CenterUrl` 切到新 backend host
- 灰度 1 台桌面端机器
- 验证 auto-exchange / 心跳 / 任务回执

不做：

- Coze toolbox 再次切流
- backend contract 变更
- Agent 协议变更

## 2. 切换对象

必须更新：

- `comfyui-desktop/installer/podi-agent.iss`
- `comfyui-desktop/installer/install_windows.ps1`
- `comfyui-desktop/installer/build_windows.ps1`
- `comfyui-desktop/installer/publish_windows_release.ps1`
- `comfyui-desktop/README.md`
- `docs/api/modules/agent.md`
- `docs/comfyui/desktop-agent.md`

## 3. 切换前确认

必须先确认：

1. 新 backend 的 `/api/agent/*` 可用
2. `podi-backend` 已稳定运行
3. 至少有 1 台灰度 Windows 机器
4. 旧安装包仍然可回滚

## 4. 构建与发布

### A. 更新默认 CenterUrl

把默认值改到：

```text
http://<new-backend-host>:8099
```

### B. 构建安装包

```powershell
powershell -ExecutionPolicy Bypass -File installer\build_windows.ps1 `
  -CenterUrl "http://<new-backend-host>:8099" `
  -InstallKey "<install_key>"
```

### C. 发布到中台

```powershell
powershell -ExecutionPolicy Bypass -File installer\publish_windows_release.ps1 `
  -CenterUrl "http://<new-backend-host>:8099" `
  -Username "<admin_user>" `
  -Password "<admin_password>" `
  -Version "<new_version>"
```

## 5. 灰度验证

在 1 台测试机器上：

1. 安装新包
2. 观察是否成功 `auto-exchange`
3. 确认心跳上报
4. 推一条任务
5. 验证结果回填

至少确认：

- `GET /api/agent/bootstrap/releases` 正常
- `POST /api/agent/bootstrap/auto-exchange` 正常
- `POST /api/agent/tasks/{task_id}/events` 正常

## 6. 旧机器处理

### 方案 A：自动更新

前提：

- 旧机器开启自动更新
- 新 release 已标记目标版本

### 方案 B：手工更新

直接修改本地：

```text
~/.podi/comfyui-desktop/config.json
```

把：

```json
"center_url": "http://117.50.80.158:8099"
```

改成：

```json
"center_url": "http://<new-backend-host>:8099"
```

然后重启服务。

## 7. 回滚

如果灰度失败：

1. 恢复安装脚本和安装包里的旧 `CenterUrl`
2. 重新发布旧版本安装包
3. 测试机器恢复本地 `config.json`
4. 保持 Coze / backend 主链路不动

## 8. 最小结论

桌面端切换只看三件事：

1. 新包是否指向新 backend
2. 灰度机器是否正常接入
3. 回滚是否足够简单
