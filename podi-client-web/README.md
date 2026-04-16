# PODI Client Web

面向业务用户的正式客户端前台，整体产品结构与交互节奏对齐 `Style3D`，底层能力走现有 PODI 中台。

## 当前版本定位

当前不是最终商业发布版，而是：

- 一个可运行、可构建、可系统测试的 `alpha` 版本
- 非 3D 对标内容已基本补齐
- 第一批核心能力已接通真实链路
- 大量剩余功能已先接“第一版复用链路”

如果要看更详细边界，请先看：

- `docs/PLATFORM_SURFACES.md`
- `docs/client/plans/2026-03-16-style3d-client-version-boundary.md`
- `docs/client/plans/2026-03-16-style3d-client-gap-audit.md`

## 当前已接入

- 登录态
- 首页工作室
- AI研发设计第一批能力
- AI工具箱第一批能力
- AI视觉商拍第一批能力
- 任务中心
- 本地素材沉淀与再次创作
- 钱包 / 积分 / 充值订单创建
- 积分不足拦截与返回继续提交

## 当前测试入口

开始系统测试前，建议依次查看：

- `docs/client/plans/2026-03-16-style3d-client-test-scope.md`
- `docs/client/plans/2026-03-16-style3d-client-test-checklist.md`
- `docs/client/plans/2026-03-16-style3d-client-test-preflight.md`
- `docs/client/plans/2026-03-16-style3d-client-test-report-template.md`

## 开发命令

```bash
cd podi-client-web
npm install
npm run dev
npm run lint
npm run build
npm run test:ui
npm run selfcheck:local
npm run selfcheck:full
npm run selftest:remote
```

默认开发端口：

- `8210`

## 环境说明

- `VITE_API_BASE_URL`
  - 可选
  - 默认走 `/api` 代理到 `http://localhost:8099`

- `VITE_MEDIA_BASE_URL`
  - 可选
  - 默认走 `/api/media`

- `CLIENT_SELFTEST_BASE_URL`
  - 可选
  - 远端自测脚本使用，默认 `http://117.50.80.158:8099`

- `CLIENT_SELFTEST_USERNAME`
- `CLIENT_SELFTEST_PASSWORD`
- `CLIENT_SELFTEST_IMAGE`
  - 可选
  - 远端自测脚本使用
- `CLIENT_SELFTEST_MAX_ATTEMPTS`
- `CLIENT_SELFTEST_INTERVAL_MS`
  - 可选
  - 控制异步任务轮询时长

## 目录结构

```text
src/
  app/                 全局 provider / router
  components/          页面通用组件
  components/workspace 工作区子组件
  config/              工具与能力映射
  hooks/               页面状态控制
  mock/                前台演示内容
  pages/               路由页面
  services/            API / 本地状态 / 草稿 / 运行辅助
  styles/              主题变量
  types/               类型定义
  utils/               上传等工具
```

## 维护约定

- 页面壳与业务逻辑分开
- 工作区逻辑优先走 hook，不往页面里堆
- 能力接入优先修改 `src/config/toolConfigs.ts`
- 本地素材沉淀统一走 `src/services/assetLibrary.ts`
- 草稿恢复统一走 `src/services/workspaceDraft.ts`

## 说明

当前素材库仍以“前端本地沉淀”作为第一阶段闭环，后续会升级到真正的后端资产中心。

## 远端自测脚本

可直接执行：

```bash
cd podi-client-web
npm run selfcheck:local
```

作用：

- 本地类型检查
- 本地构建
- 本地 UI 自动化 smoke

完整一把跑完：

```bash
cd podi-client-web
npm run selfcheck:full
```

## 远端自测脚本

可直接执行：

```bash
cd podi-client-web
npm run selftest:remote
```

作用：

- 登录远端后端
- 上传一张测试图到 OSS
- 跑一条同步能力样本
- 跑一条异步能力样本

说明：

- 同步样本当前已跑通
- 异步样本在部分场景下可能长时间 `running`，需结合 `docs/client/plans/2026-03-16-style3d-client-live-selftest-notes.md` 一起看
