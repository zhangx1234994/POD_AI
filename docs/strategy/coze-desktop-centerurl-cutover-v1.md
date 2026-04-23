# 桌面端 CenterUrl 切换方案 v1

> 适用范围：`comfyui-desktop` 安装包、Windows 安装脚本、桌面端 Agent 协议文档。  
> 目标：把桌面端 `CenterUrl` 从旧 backend host 切到 Coze 同机 backend host，但不和首轮 Coze 控制面迁移绑成一批。

## 1. 为什么单独拆一批

桌面端 `CenterUrl` 切换涉及：

- 安装包默认值
- 已安装机器本地配置
- Agent 心跳与任务回执
- 自动更新检查
- 运维安装文档

这和 Coze toolbox 切流不是一类风险。

如果把两者绑成同一批，会出现两个问题：

1. Coze 控制面已经稳定，但桌面端还没验证完
2. 桌面端需要回滚时，会反向影响 Coze / backend 主链路

所以桌面端 `CenterUrl` 必须放在 **第二阶段**。

## 2. 当前第二阶段对象

当前已登记的第二阶段对象：

- `comfyui-desktop/installer/podi-agent.iss`
- `comfyui-desktop/installer/install_windows.ps1`
- `comfyui-desktop/installer/build_windows.ps1`
- `comfyui-desktop/installer/publish_windows_release.ps1`
- `comfyui-desktop/README.md`
- `docs/api/modules/agent.md`
- `docs/comfyui/desktop-agent.md`

当前默认旧值：

- `http://117.50.80.158:8099`

目标值：

- `http://<new-backend-host>:8099`

## 3. 切换前提

只有当以下条件全部满足时，才允许进入桌面端切换：

1. Coze + backend 同机迁移已完成
2. toolbox 与主 Coze workflow 已稳定
3. `/api/agent/*` 在新 backend 上可正常访问
4. 至少 1 台桌面端测试机器可用于灰度

## 4. 标准切换顺序

### 第一步：先改安装包默认值

统一更新：

- `podi-agent.iss`
- `install_windows.ps1`
- `build_windows.ps1`
- `publish_windows_release.ps1`

要求：

- 只改 `CenterUrl`
- 不在这一批修改桌面端协议、心跳字段、任务 contract

### 第二步：重发安装包

重新构建并发布桌面端安装包：

1. 生成新 EXE
2. 上传到中台 release 列表
3. 标记为新的目标版本

### 第三步：灰度 1 台测试机器

在 1 台 Windows 机器上验证：

1. 零配置安装是否成功
2. `auto-exchange` 是否成功
3. 心跳是否正常
4. `/tasks` 能否收到任务
5. 结果回填是否成功

### 第四步：再扩到全量机器

只有灰度通过后，才允许全量替换旧安装包或指导运维重装。

## 5. 已安装机器的处理策略

### 5.1 新安装机器

直接使用新安装包，默认 `CenterUrl` 已是新 backend host。

### 5.2 旧安装机器

分两类处理：

- 如果支持自动更新：
  - 先确认自动更新拉的是新安装包
- 如果不支持自动更新：
  - 运维手工更新本地 `config.json` 里的 `center_url`
  - 或重新安装

不建议：

- 一边保留旧 `center_url`
- 一边期待桌面端自动切流

## 6. 回滚方案

桌面端切换失败时，回滚步骤固定为：

1. 恢复安装脚本里的 `CenterUrl`
2. 重新发布旧 backend host 指向的安装包
3. 对灰度机器恢复旧 `config.json`
4. 保持 Coze / backend 主链路不动

关键原则：

- 桌面端回滚不能反向拖动 Coze 主链路
- 只回滚桌面端 `CenterUrl`

## 7. 最小结论

桌面端 `CenterUrl` 切换：

- 必须做
- 但必须放在第二阶段
- 绝不和首轮 Coze 控制面切流绑在一起
