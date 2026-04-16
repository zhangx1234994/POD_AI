# 新客户端第一期任务清单（2026-03-16）

> 目标：把新客户端第一期拆成可执行任务，后面可以直接按清单开工。  
> 对齐目标：UI 和交互全面参考 `Style3D`，底层调用全部走我们的中台。  
> 本期范围：工作室首页 + AI研发设计 + AI工具箱 + 任务中心 + 我的素材 + 积分/充值中心。
>
> 文档状态：历史任务拆解清单。
> 本文保留第一轮开工拆分方式，不代表当前仍逐项按原顺序推进。

## 1. 先定实现路线

这里其实有 3 种做法：

### 方案 A：在 `podi-eval-web` 里继续堆页面

**优点：**

- 起步最快
- 现有依赖可复用

**缺点：**

- 会把评测端和客户端混在一起
- 代码职责越来越乱
- 后面功能一多很难维护

### 方案 B：新建 `podi-client-web`，但继续单页大组件模式

**优点：**

- 比方案 A 干净
- 开发初期也比较快

**缺点：**

- 一旦页面变多，还是会重复走 `App.tsx` 膨胀老路

### 方案 C：新建 `podi-client-web`，直接按正式产品结构做

**优点：**

- 边界最清楚
- 后面扩展最好
- 最适合做长期客户端

**缺点：**

- 前期搭骨架比前两种稍慢一点

## 结论

**推荐方案 C。**

原因很明确：  
这个客户端不是临时活动页，而是未来正式业务前台。  
所以现在多花一点点时间把结构搭对，后面会省很多维护成本。

## 2. 第一期开工顺序

建议按 7 个阶段推进。

### 阶段 0：项目初始化

**前端**

- 新建 `podi-client-web`
- 初始化 `React + TypeScript + Vite + TDesign + Tailwind`
- 接入 `React Router`
- 搭建全局主题、全局样式、基础布局

**产出**

- 可启动的空项目
- 顶部导航壳
- 页面路由壳

### 阶段 1：公共底座

**前端**

- 登录态管理
- 请求拦截器
- OSS 上传封装
- 通用图片上传组件
- 通用任务状态组件
- 通用结果面板
- 通用案例图库
- 全局积分显示位
- 充值弹窗或充值入口

**后端**

- 评估是否新增 `/api/client/*` 聚合层
- 如先不新增，也要先梳理好前端调用映射

**产出**

- 公共组件可被各页面复用

### 阶段 2：工作室首页

**前端**

- Hero 区
- 智能体入口卡片
- 推荐功能区
- 最近任务区
- 最近素材区
- 模板快捷入口
- 当前积分摘要

**后端**

- `GET /api/client/home` 或前端临时拼装多个接口

**产出**

- 第一眼就像正式平台，不像后台系统

### 阶段 3：AI 工具箱

**优先做：**

- AI 超清
- 无损放大
- AI 扩图
- 高质量缩放
- DPI 处理

**原因：**

- 这部分最稳
- 最容易快速上线
- 最适合先把页面骨架和调用链路跑通

### 阶段 4：AI 研发设计

**优先做：**

- 以文生款
- 以款生款
- 融合创款
- 图案提取
- 图案融合
- 四方连续

**原因：**

- 这是最能体现我们业务特色的一块
- 也是和你现有中台强能力最匹配的一块

### 阶段 5：任务中心 + 我的素材

**任务中心**

- 列表
- 状态过滤
- 详情抽屉
- 再来一次

**我的素材**

- 原图/结果图/视频分类
- 来源功能
- 下载
- 再次创作

### 阶段 6：积分与充值中心

- 顶栏余额展示
- 充值入口
- 钱包页
- 充值记录
- 消费账单
- 使用统计
- 点数不足拦截与回流

### 阶段 7：收尾与上线前验证

- 走查所有页面
- 接口错误提示补齐
- 空态/加载态/失败态补齐
- 移动端适配
- 构建与静态部署验证

## 3. 前端详细任务拆分

## 3.1 项目骨架

- `app/router.tsx`
- `layouts/ClientLayout.tsx`
- `layouts/WorkbenchLayout.tsx`
- `styles/client-theme.css`
- `services/http.ts`
- `stores/authStore.ts` 或同等状态层

## 3.2 公共组件

- `components/nav/TopNav.tsx`
- `components/nav/ModuleTabs.tsx`
- `components/uploader/ImageUploader.tsx`
- `components/uploader/AssetDropzone.tsx`
- `components/result/ResultPanel.tsx`
- `components/task/TaskStatusBadge.tsx`
- `components/task/TaskTimeline.tsx`
- `components/example/ExampleGallery.tsx`
- `components/form/CapabilityFormRenderer.tsx`
- `components/form/PromptEditor.tsx`
- `components/form/AdvancedOptions.tsx`
- `components/assets/AssetPicker.tsx`
- `components/wallet/BalanceChip.tsx`
- `components/wallet/RechargeDialog.tsx`
- `components/wallet/BillingTable.tsx`

## 3.3 页面任务

### 工作室首页

- 顶部欢迎区
- 快捷上传区
- 智能体入口卡片
- 最近任务列表
- 最近素材列表
- 模板入口

### AI 工具箱

- 左侧工具菜单
- 工具页通用壳
- 结果前后对比
- 下载与再次创作

### AI 研发设计

- 功能卡片导航
- 提示词模板
- 图像输入区
- 结果预览区
- 案例区“做同款”

### 任务中心

- 状态筛选
- 任务列表
- 任务详情
- 重试

### 我的素材

- 素材网格
- 来源筛选
- 再次创作

### 积分与充值中心

- 余额总览
- 套餐卡片
- 充值记录
- 消费账单
- 使用统计
- 点数不足提示页/弹窗

## 4. 后端适配任务

这一块建议尽量做薄，不动现有稳定主链路。

## 4.1 最小可用做法

前端直接组合现有接口：

- 登录：`POST /api/auth/login`
- 能力清单：`GET /api/abilities`
- 能力详情：`GET /api/abilities/{abilityId}`
- 同步执行：`POST /api/abilities/{abilityId}/invoke`
- 异步任务：`POST /api/ability-tasks`
- 任务查询：`GET /api/ability-tasks`、`GET /api/ability-tasks/{id}`
- 上传：`POST /api/media/v1/upload-key` + `POST /api/media/v1/sts`
- 钱包：`GET /api/wallet/v1/balance`
- 流水：`GET /api/wallet/v1/ledger`
- 账单：`GET /api/wallet/v1/bills`
- 使用统计：`GET /api/wallet/v1/usage-summary`
- 创建充值单：`POST /api/wallet/v1/recharge-orders`
- 查询充值单：`GET /api/wallet/v1/recharge-orders/{orderNo}`

**优点：**

- 后端改动最少

**缺点：**

- 前端需要自己做很多口径转换

## 4.2 推荐做法

增加一层客户端聚合接口：

- `GET /api/client/home`
- `GET /api/client/capabilities`
- `POST /api/client/jobs`
- `GET /api/client/jobs`
- `GET /api/client/jobs/{id}`
- `GET /api/client/assets`
- `GET /api/client/wallet/summary`
- `GET /api/client/wallet/ledger`
- `GET /api/client/wallet/bills`
- `GET /api/client/wallet/usage-summary`
- `POST /api/client/wallet/recharge-orders`

**优点：**

- 前台可以彻底说人话
- 中台内部字段不往外漏
- 后面客户端变动不需要跟着中台细节一起改

**结论：**

第一期可以先用“最小可用做法”起步，  
但我建议在阶段 3 之前补上 `/api/client/*`，这样后面不容易返工。

## 5. 第一批功能和能力映射

| 客户端功能 | 调用方式 | 现有链路 |
| --- | --- | --- |
| AI 超清 | 同步优先 | 百度无损放大 / 8K 放大 |
| 无损放大 | 同步优先 | 高质量缩放 / 百度无损放大 |
| AI 扩图 | 异步优先 | 扩图多模型版本 / ComfyUI 扩图 |
| 高质量缩放 | 同步 | `podi_high_quality_resize` |
| DPI 处理 | 同步 | `podi_set_dpi` |
| 以文生款 | 异步优先 | 多模型生图 |
| 以款生款 | 异步优先 | KIE Nano Banana / Flux2 |
| 融合创款 | 异步 | `comfyui_duotu_ronghe` |
| 图案提取 | 异步 | `comfyui_yinhua_tiqu` |
| 图案融合 | 异步 | `comfyui_duotu_ronghe` |
| 四方连续 | 异步 | `comfyui_sifang_lianxu` |

### 5.1 钱包功能映射

| 客户端功能 | 调用方式 | 现有链路 |
| --- | --- | --- |
| 当前余额 | 同步 | `/api/wallet/v1/balance` |
| 消费记录 | 同步 | `/api/wallet/v1/ledger` |
| 月账单 | 同步 | `/api/wallet/v1/bills` |
| 使用统计 | 同步 | `/api/wallet/v1/usage-summary` |
| 创建充值单 | 同步 | `/api/wallet/v1/recharge-orders` |
| 查询充值单 | 同步 | `/api/wallet/v1/recharge-orders/{orderNo}` |

## 6. 关键交互规则

客户端必须统一这些体验，不然后面会很乱。

### 6.1 提交体验

- 点“开始生成”后立即进入任务态
- 不要让用户等待接口长时间卡住
- 能走异步的尽量走异步
- 提交前先检查当前余额是否足够

### 6.2 状态文案

前台统一用业务语言：

- 排队中
- 正在处理
- 已完成
- 生成失败

不要出现：

- callback pending
- workflow dispatched
- executor selected

### 6.3 结果回填

结果成功后，要自动出现在：

- 当前页面结果区
- 任务中心
- 我的素材

### 6.4 错误提示

不要直接弹技术报错，统一翻译成用户听得懂的话：

- 图片上传失败，请重试
- 当前任务较多，请稍后再试
- 参数不完整，请检查后重新提交
- 服务繁忙，请稍后重试
- 当前积分不足，请先充值

## 7. 测试清单

## 7.1 前端页面测试

- 每个页面能正常进入
- 上传组件可用
- 加载态可见
- 失败态可见
- 结果态可见
- 移动端不炸布局
- 积分入口可用
- 充值弹窗可打开

## 7.2 功能测试

- 超清
- 放大
- 扩图
- 缩放
- DPI
- 图案提取
- 四方连续
- 多图融合
- 钱包余额
- 充值单创建与查询

## 7.3 回归重点

- OSS 上传是否正常
- 异步任务状态是否刷新及时
- 结果是否自动回到任务中心和素材库
- 同一用户的历史结果是否可再次创作
- 积分不足时是否正确拦截
- 成功/失败任务后积分是否正确变化

## 8. 我建议的实际开发顺序

如果下一步直接开做，我建议严格按下面顺序：

1. 新建 `podi-client-web`
2. 搭布局和导航
3. 先做上传组件和结果面板
4. 先接 AI 工具箱 5 个功能
5. 再接 AI 研发设计 6 个功能
6. 再接积分和充值中心
7. 最后做任务中心和素材库

这个顺序的好处是：

- 最快看到成型页面
- 最快验证调用链路
- 最快形成一个“能演示、能上线”的客户端版本

## 9. 当前结论

到这一步，第一期已经不是“一个想法”，而是一张可以执行的任务表。

下一步只剩两件事：

1. 开新项目骨架
2. 按任务表进入开发
