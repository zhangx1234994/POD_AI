# 新客户端实施方案（2026-03-16）

> 目标：把 `Style3D` 的前台产品结构，落到我们自己的新客户端项目里。  
> 项目建议名：`podi-client-web`  
> 产品定位：给业务用户、设计师、运营同学使用的正式客户端，不是管理端，也不是评测端。
>
> 文档状态：历史实施方案。
> 本文主要保留第一轮立项和项目拆分思路，不代表当前代码结构、路由和页面骨架仍完全按原文执行。
> 当前有效骨架请看 `docs/plans/2026-03-19-style3d-client-rearchitecture-design.md`。

## 0. UI 对齐原则（已确认）

用户已明确：**新客户端的 UI 设计要完全参照 Style3D 网站。**

这里我把它翻译成可执行约束：

- 页面骨架对齐 `Style3D`
  - 顶部导航结构
  - 工作室首页结构
  - 左侧功能菜单 + 中间操作区 + 右侧案例/结果区
  - 卡片式入口和案例瀑布流
- 视觉语言对齐 `Style3D`
  - 干净、轻盈、偏专业工具平台
  - 大留白、浅色背景、圆角卡片、弱分割线
  - 首页强调“推荐入口 + 最近工作 + 案例感”
- 交互节奏对齐 `Style3D`
  - 先选功能，再填参数，再出结果
  - 示例图和“做同款”入口要明显
  - 不暴露底层技术名词

但有 3 个边界也要固定：

1. **不做 3D 精准设计模块**
2. **不直接复用对方品牌素材**
   - 不照搬 logo
   - 不直接复制对方图片资产
   - 不直接复制品牌文案
3. **能力内容换成我们的中台能力**
   - 外观与交互参照对方
   - 实际功能调用全部走我们自己的后端

## 1. 先定技术边界

为了降低维护成本，前端建议继续沿用现有技术栈：

- `React 18`
- `TypeScript`
- `Vite`
- `TDesign`
- `Tailwind`

但项目结构**不要**继续走“一个超大 `App.tsx`”的方式，建议直接做成标准多页面壳：

- `React Router`
- `layout + routes + modules + services`

原因很简单：

- 新客户端比评测端复杂得多
- 会有首页、分类页、任务中心、素材库、项目页
- 如果继续把所有状态都堆进一个页面，后续会很难维护

## 2. 项目目录建议

建议新项目从一开始就拆清楚：

```text
podi-client-web/
  src/
    app/
      router.tsx
      providers.tsx
    layouts/
      ClientLayout.tsx
      WorkbenchLayout.tsx
    pages/
      HomePage.tsx
      DesignPage.tsx
      ShootPage.tsx
      ToolboxPage.tsx
      TasksPage.tsx
      AssetsPage.tsx
      ProjectDetailPage.tsx
    modules/
      home/
      design/
      shoot/
      toolbox/
      tasks/
      assets/
      project/
      auth/
    components/
      capability/
      uploader/
      result-panel/
      task-status/
      example-gallery/
      prompt/
      asset-picker/
    services/
      clientApi.ts
      authApi.ts
      uploadApi.ts
      taskApi.ts
    hooks/
    utils/
    styles/
```

## 3. 页面树

第一期建议就按这个路由树来：

```text
/
├── /home                 工作室首页
├── /design               AI研发设计
│   ├── /design/text-to-style
│   ├── /design/style-to-style
│   ├── /design/fusion
│   ├── /design/pattern-extract
│   ├── /design/pattern-fusion
│   └── /design/seamless
├── /toolbox              AI工具箱
│   ├── /toolbox/upscale
│   ├── /toolbox/lossless-zoom
│   ├── /toolbox/outpaint
│   ├── /toolbox/resize
│   └── /toolbox/dpi
├── /shoot                AI视觉商拍（一期先只放入口和灰度能力）
│   ├── /shoot/marketing-variants
│   ├── /shoot/image-to-video
│   └── /shoot/detail-enhance
├── /tasks                任务中心
├── /assets               我的素材
├── /wallet               积分与充值中心
└── /projects/:id         项目详情
```

说明：

- `AI视觉商拍` 一期可以先留出结构，但只上线我们能稳定做的功能
- 这样后面补“服装上身”时，不需要重做导航和信息架构

## 4. 每个页面该长什么样

### 4.1 工作室首页

**目标：** 让人一进来就知道“我能做什么”。

**页面模块：**

- Hero 区：一句话介绍 + 上传入口 + 快捷开始
- 智能体卡片区：设计、图案、营销、工具
- 最近任务区：最近 10 条
- 最近素材区：最近上传/最近产出
- 常用模板区：常用场景模板
- 推荐功能区：根据业务重点推荐

### 4.2 AI 研发设计页

**统一布局：**

- 左侧：功能菜单
- 中间：参数表单
- 右侧：案例区 / 结果区 / 历史结果

**每个功能页共用组件：**

- 上传组件
- 提示词输入组件
- 模板选择器
- 高级参数折叠区
- 提交按钮
- 状态提示条
- 结果面板

### 4.3 AI 工具箱页

这页比研发设计更偏“工具感”：

- 左侧功能菜单可以更紧凑
- 中间以上传 + 参数 + 操作为主
- 右边强调前后对比和下载

### 4.4 任务中心页

**必须做成长期可用页，不是弹窗。**

建议分 4 个 Tab：

- 全部
- 处理中
- 已完成
- 失败

每条任务显示：

- 功能名称
- 缩略图
- 提交时间
- 当前状态
- 结果入口
- 失败原因
- 再做一次

### 4.5 我的素材页

建议把“用户资产”统一沉淀到这里：

- 原图
- 结果图
- 视频
- 收藏
- 标签
- 来源功能

### 4.6 积分与充值中心

如果要和你给的网站前台体验尽量一致，这页必须在架构里预留，并且建议一期就上基础版。

建议包含：

- 当前积分余额
- 冻结中积分
- 充值套餐区
- 充值记录
- 消费账单
- 使用统计

同时这部分不能只做独立页面，还要在全局顶栏长期展示：

- 当前余额
- 充值按钮
- 活动/赠送提示

## 5. 组件树建议

客户端如果想后续做快，必须把“能力页的公共部分”抽出来。

### 5.1 核心共用组件

- `CapabilitySidebar`
  - 左侧功能菜单
- `CapabilityHeader`
  - 标题、副标题、说明
- `ImageUploader`
  - 支持上传、拖拽、粘贴、历史素材选择
- `PromptEditor`
  - 主提示词、优化提示词、模板插入
- `CapabilityFormRenderer`
  - 根据能力 schema 渲染表单
- `ExampleGallery`
  - 示例图和“做同款”
- `ResultPanel`
  - 结果预览、下载、再次创作
- `TaskStatusBadge`
  - 统一展示任务状态
- `AssetPicker`
  - 从素材库选图
- `RerunButton`
  - 基于历史记录再执行

### 5.2 为什么要这样拆

因为“以文生款”“图案提取”“扩图”“超清”虽然业务名字不同，但页面骨架其实很像。  
抽掉公共层之后，新增一个新功能页，主要只需要补：

- 配置
- 表单字段
- 结果展示逻辑
- 文案和案例

## 6. 前后端接口分层建议

我建议不要让新客户端直接复用管理端/评测端的接口口径，而是加一层更稳定的客户端接口。

## 6.1 客户端接口建议

### 首页

- `GET /api/client/home`
  - 返回推荐功能、最近任务、最近素材、模板卡片、积分摘要

### 功能目录

- `GET /api/client/capabilities`
  - 返回前台可用功能列表
  - 字段要是业务词，不要带执行节点、binding 这些内部字段

### 提交任务

- `POST /api/client/jobs`
  - 前端统一提交
  - 后端决定走同步还是异步

### 查询任务

- `GET /api/client/jobs`
- `GET /api/client/jobs/{id}`

### 素材

- `GET /api/client/assets`
- `POST /api/client/assets/upload`
- `POST /api/client/assets/{id}/rerun`

### 模板

- `GET /api/client/templates`

### 钱包 / 积分

- `GET /api/client/wallet/summary`
- `GET /api/client/wallet/ledger`
- `GET /api/client/wallet/bills`
- `GET /api/client/wallet/usage-summary`
- `POST /api/client/wallet/recharge-orders`
- `GET /api/client/wallet/recharge-orders/{orderNo}`

## 6.2 客户端接口和中台接口的映射关系

```text
客户端页面
   ↓
/api/client/*
   ↓
能力路由 / AbilityTask / OSS / 日志服务
   ↓
ComfyUI / KIE / 百度 / 火山
```

好处是：

- 客户端更稳定
- 后台以后怎么调度，不影响前台
- 前台永远用业务词

## 7. 第一期开发表

建议按 4 个阶段推进。

### 阶段 A：项目骨架

- 新建 `podi-client-web`
- 搭好路由、布局、主题、请求层
- 搭好登录态和上传组件

### 阶段 B：先做工作室 + 工具箱

- 工作室首页
- AI 超清
- 无损放大
- AI 扩图
- 高质量缩放
- DPI

这是最容易最稳的第一波。

### 阶段 C：补研发设计主能力

- 以文生款
- 以款生款
- 融合创款
- 图案提取
- 图案融合
- 四方连续

### 阶段 D：补任务中心和素材中心

- 任务列表
- 任务详情
- 我的素材
- 再次创作

### 阶段 E：补积分和充值中心

- 顶栏余额展示
- 钱包页
- 充值入口
- 充值记录
- 账单记录
- 点数不足拦截

## 8. 第一批能力映射建议

为了后面实现快，我先把一期功能和现有能力做一版映射：

| 前台功能名 | 建议走的现有能力/链路 |
| --- | --- |
| AI 超清 | 百度无损放大 / 8K 高清放大 |
| 无损放大 | PODI 高质量缩放 / 百度无损放大 |
| AI 扩图 | 扩图多模型版本 / ComfyUI 扩图 |
| 高质量缩放 | `podi_high_quality_resize` |
| DPI 处理 | `podi_set_dpi` |
| 以文生款 | 多模型生图工作流 + 模板封装 |
| 以款生款 | KIE Nano Banana / Flux2 / 多模型生图 |
| 融合创款 | `comfyui_duotu_ronghe` |
| 图案提取 | `comfyui_yinhua_tiqu` |
| 图案融合 | `comfyui_duotu_ronghe` |
| 四方连续 | `comfyui_sifang_lianxu` |
| 裂变套图 | 图裂变工作流 |
| 图生视频 | KIE / 火山视频能力 |

### 8.1 账户功能映射

| 前台功能名 | 建议走的现有链路 |
| --- | --- |
| 当前余额 | `/api/wallet/v1/balance` |
| 消费记录 | `/api/wallet/v1/ledger` |
| 月账单 | `/api/wallet/v1/bills` |
| 使用统计 | `/api/wallet/v1/usage-summary` |
| 创建充值单 | `/api/wallet/v1/recharge-orders` |
| 查询充值单 | `/api/wallet/v1/recharge-orders/{orderNo}` |

## 9. 第一版 UI 风格建议

既然是对标 Style3D，就不建议做成纯后台风格。

建议视觉方向：

- 白底为主，但不要死白
- 大面积留白 + 柔和灰蓝中性色
- 卡片圆角偏大
- 重点按钮用较亮但不过分艳的品牌色
- 页面中多用“案例图卡片”
- 每个功能页都给出“生成前/生成后”

前台关键词应该是：

- 专业
- 轻盈
- 易懂
- 不像后台

另外右上角建议长期保留：

- 当前积分
- 充值入口
- 活动提示

## 10. 这份方案的实际意义

做到这里后，后面就不是“想做一个像 Style3D 的东西”，而是已经明确成：

- 项目名
- 技术栈
- 页面树
- 组件树
- 接口层
- 第一期开发表
- 能力映射表

也就是说，下一步已经可以直接进入“创建项目骨架”了。
