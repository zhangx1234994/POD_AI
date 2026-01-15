
# POD AI Studio - 智能图像处理平台

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![React](https://img.shields.io/badge/React-18.3.1-blue.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.3.5-646CFF.svg)](https://vitejs.dev/)

## 项目简介

POD AI Studio 是一个专业的图像处理平台，专为POD(Print On Demand)业务设计。该平台提供多种AI驱动的图像处理工具，帮助用户轻松创建、编辑和优化设计素材，满足个性化定制需求。

原始设计稿可在 [Figma](https://www.figma.com/design/jieu5bqYwvrCWXgVpAymGe/POD%E4%B8%9A%E5%8A%A1UI%E8%AE%BE%E8%AE%A1) 中查看。

## ✨ 核心功能

### 🎨 AI图像处理工具

- **无损放大** - 提高图像分辨率，保持细节清晰
- **印花提取** - 从复杂背景中精确提取图案元素
- **图生图** - 基于参考图像生成新的设计变体
- **四方连续** - 创建无缝拼接的四方连续图案
- **两方连续** - 生成适合边框装饰的两方连续图案
- **扩展图** - 智能扩展图像边界，保持风格一致
- **图片融合** - 将多张图像无缝融合成新设计

### 👥 用户管理

- 用户注册与登录
- 个人资料管理
- 任务历史记录
- 下载权限控制

### 📊 仪表板

- 任务状态监控
- 实时进度跟踪
- 数据统计分析
- 快速操作入口

## 🛠️ 技术栈

- **前端框架**: React 18.3.1 + TypeScript
- **构建工具**: Vite 6.3.5
- **UI组件**: Radix UI + Tailwind CSS
- **状态管理**: React Context + Hooks
- **HTTP客户端**: 自定义HTTP工具类
- **图标库**: Lucide React
- **表单处理**: React Hook Form

## 🚀 快速开始

### 环境要求

- Node.js >= 16.0.0
- npm >= 8.0.0

### 安装依赖

```bash
npm install
```

### 启动开发服务器

```bash
npm run dev
```

应用将在 `http://localhost:8080` 启动。

### 构建生产版本

```bash
npm run build
```

构建文件将输出到 `build` 目录。

## 📁 项目结构

```
src/                       # 源代码（主要开发目录）
├── App.tsx
├── main.tsx
├── index.css
├── assets/                # 静态资源（images, icons）
├── components/            # 复用组件与 UI 组件
│   └── ui/                # 基础 UI 组件集合（Button, Card, Dialog 等）
├── pages/                 # 页面级组件（按功能组织）
│   ├── AIImageEditor/            # AI 编辑器页面
│   │   └── AIImageEditorPage.tsx
│   ├── AIProcessorTools/         # 各类 AI 工具与处理器（Upscale, Seamless, Pattern 等）
│   │   ├── LosslessUpscaleProcessor.tsx
│   │   ├── PatternExtractProcessor.tsx
│   │   └── SeamlessProcessor.tsx
│   ├── AIToolsPage/              # AI 工具入口页面
│   │   └── AIToolsPage.tsx
│   ├── AIToolsLayout/            # AI 工具布局容器
│   │   └── AIToolsLayout.tsx
│   ├── BatchTaskDashboard/       # 批量任务仪表盘（重命名/增强后的 Dashboard）
│   │   ├── BatchTaskDashboardPage.tsx
│   │   ├── BatchTaskCard.tsx
│   │   └── BatchTaskFilterBar.tsx
│   ├── Header/                   # 头部与全局小组件
│   │   └── Header.tsx
│   ├── Login/                    # 登录页面
│   │   └── LoginPage.tsx
│   ├── PersonalCenter/           # 个人中心
│   │   └── PersonalCenterPage.tsx
│   ├── PersonalGallery/          # 个人图库（网格/列表/预览/批量操作）
│   │   ├── PersonalGalleryPage.tsx
│   │   ├── GalleryToolbar.tsx
│   │   └── ImageCard.tsx
│   ├── PointsHistory/            # 积分/余额相关页面
│   │   └── PointsHistoryPage.tsx
│   ├── Register/                 # 注册页面
│   │   └── RegisterPage.tsx
│   ├── Sidebar/                  # 侧边栏与导航
│   │   └── Sidebar.tsx
│   ├── SSO/                      # 单点登录处理
│   │   └── SSOHandler.tsx
│   └── TaskDetail/               # 任务详情与结果查看
│       └── TaskDetailPage.tsx
├── contexts/              # React Context 提供者（Auth, Notifications, Points 等）
├── hooks/                 # 自定义 Hooks（useGalleryData, useTaskPolling 等）
├── services/              # 后端 API 封装（http.ts, ImageProcessingService, userAPI 等）
├── constants/             # 常量集合（gallery, task, image, sidebar 等）
├── styles/                # 全局样式文件（globals.css）
├── utils/                 # 工具函数（downloadUtils, debounce, http helpers 等）
└── config/                # 应用配置（appConfig.ts）
```

## 🔧 配置说明

### 环境变量

项目使用以下环境变量（如需要，请在项目根目录创建`.env`文件）：

```env
# API服务器地址
VITE_API_BASE_URL=http://localhost:8099

# 认证服务器地址
VITE_AUTH_BASE_URL=http://localhost:8090
```

### 代理配置

开发环境已配置API代理：

- 认证相关API: `/api/os/v1/auth` → `http://localhost:8090`
- 设计服务API: `/api/op/v1` → `http://localhost:8099`

## 📖 功能模块详解

### AI工具模块

每个AI工具都是独立组件，支持：

- 图片上传与预览
- 参数调整与配置
- 任务提交与监控
- 结果展示与下载

#### AI工具依赖组件架构

所有AI图像处理工具都基于以下核心组件构建：

1. **AIProcessorWithTasks** - 通用AI处理组件
   - 提供标准化的任务提交流程
   - 集成任务状态监控
   - 统一的用户界面和交互
   - 支持多种工具类型的配置

2. **DashboardTaskList** - 任务列表组件
   - 显示用户提交的所有任务
   - 实时更新任务状态
   - 提供任务操作（下载、删除等）
   - 支持任务筛选和排序

3. **EnhancedImageUpload** - 增强图片上传组件
   - 支持拖拽上传
   - 图片预览和验证
   - 多文件上传支持
   - 上传进度显示

4. **DualImageUpload** - 双图片上传组件（图生图工具专用）
   - 支持主图和参考图同时上传
   - 独立的预览和管理
   - 图片交换功能

#### AI工具任务提交流程

所有AI工具遵循统一的任务提交流程：

1. **参数收集** - 收集用户上传的图片和配置的参数
2. **数据验证** - 验证输入数据的有效性
3. **任务构建** - 构建符合API规范的任务参数
4. **任务提交** - 调用`submitTask`API提交任务
5. **状态监控** - 通过任务监控系统跟踪任务状态
6. **结果展示** - 任务完成后展示结果并提供下载

**详细的任务提交及交互事件说明**：请参考 [任务提交流程文档](docs/task-submission-flow.md)，其中包含完整的任务提交逻辑、状态管理、用户交互处理和代码实现细节。

### 参数封装规范

所有图像处理组件的任务提交参数遵循统一的封装规范，确保系统一致性和可维护性。

#### 必须参数（所有组件共有）

| 参数名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| action | string | 任务类型标识符 | "hires", "pattern-extract", "seamless", "twoway-seamless", "img2img", "extend", "merge" |
| taskId | string | 任务唯一ID | "task_123456789" |
| userId | string | 用户ID | "user_abc123" |

#### 各组件的可变参数

| 组件名称 | 组件路径 | 工具类型 | 可变参数 | 默认值 | 说明 |
|----------|----------|----------|----------|--------|------|
| 无损放大 | `src/components/UpscaleProcessor.tsx` | "hires" | scale, quality | scale: 2, quality: 95 | scale: 放大倍数(2/4/8/16); quality: 图片质量(0-100) |
| 印花提取 | `src/components/PatternExtractor.tsx` | "pattern-extract" | prompt, imageList | prompt: "" | prompt: 处理描述; imageList: 图片列表(主图+参考图) |
| 四方连续 | `src/components/SeamlessProcessor.tsx` | "seamless" | prompt, imageList | prompt: "" | prompt: 处理描述; imageList: 图片列表 |
| 两方连续 | `src/components/TwoWaySeamlessProcessor.tsx` | "twoway" | prompt, imageList | prompt: "" | prompt: 处理描述; imageList: 图片列表 |
| 图生图 | `src/components/Img2ImgProcessor.tsx` | "img2img" | prompt, imageList, aux_imageList, model, artStyle, count | model: "", artStyle: "", count: 1 | prompt: 处理描述; imageList: 主图片列表; aux_imageList: 辅助图片列表; model: 模型; artStyle: 艺术风格; count: 生成数量 |
| 扩展图 | `src/components/ImageExtensionProcessor.tsx` | "extend" | prompt, imageList, top, bottom, left, right | top/bottom/left/right: 10 | prompt: 处理描述; imageList: 图片列表; top/bottom/left/right: 扩展尺寸(像素) |
| 图片融合 | `src/components/ImageMergeProcessor.tsx` | "merge" | prompt, imageList, aux_imageList, mergeMode, alpha, outputRatio | mergeMode: "blend", alpha: 0.5, outputRatio: 1 | prompt: 处理描述; imageList: 主图片列表; aux_imageList: 辅助图片列表; 

#### 参数封装示例

```typescript
// 无损放大参数示例
const hiresParams = {
  action: "hires",
  taskId: "task_123456789",
  userId: "user_abc123",
  scale: 4,
  quality: 95,
  imageList: ["data:image/jpeg;base64,..."]
};

// 印花提取参数示例
const patternParams = {
  action: "pattern-extract",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "提取印花图案",
  imageList: ["data:image/jpeg;base64,..."] // 主图+参考图
};

// 四方连续参数示例
const seamlessParams = {
  action: "seamless",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "创建四方连续图案",
  imageList: ["data:image/jpeg;base64,..."]
};

// 两方连续参数示例
const twowayParams = {
  action: "twoway",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "创建两方连续图案",
  imageList: ["data:image/jpeg;base64,..."]
};

// 图生图参数示例
const img2imgParams = {
  action: "img2img",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "将图片转换为艺术风格",
  imageList: ["data:image/jpeg;base64,..."], // 主图片
  aux_imageList: ["data:image/jpeg;base64,..."], // 辅助图片
  model: "realistic",
  artStyle: "oil_painting",
  count: 1
};

// 扩展图参数示例
const extendParams = {
  action: "extend",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "",
  imageList: ["data:image/jpeg;base64,..."],
  top: 10,
  bottom: 10,
  left: 10,
  right: 10
};

// 图片融合参数示例
const mergeParams = {
  action: "merge",
  taskId: "task_123456789",
  userId: "user_abc123",
  prompt: "将两张图片融合",
  imageList: ["data:image/jpeg;base64,..."], // 主图片
  aux_imageList: ["data:image/jpeg;base64,..."], // 辅助图片
  mergeMode: "blend",
  alpha: 0.5,
  outputRatio: 1
};
```

#### 任务提交流程

所有组件遵循统一的任务提交流程：

1. **收集输入**：收集用户输入的参数（图片、文本描述、设置选项等）
2. **参数验证**：验证必填参数和参数格式
3. **构建任务对象**：按照规范构建包含必须参数和可变参数的任务对象
4. **调用接口**：通过统一的`submitTask`函数提交任务
5. **处理结果**：处理提交结果，更新UI状态和任务列表

这种统一的参数封装规范确保了系统的一致性和可维护性，使得添加新组件或修改现有组件变得更加容易。

#### 各AI工具实现详情

1. **无损放大 (UpscaleProcessor)**
   - 组件路径: `src/components/UpscaleProcessor.tsx`
   - 工具类型: `hires`
   - 特殊参数: 放大倍数 (2x, 4x, 8x, 16x)、图片质量 (0-100)
   - 依赖组件: AIProcessorWithTasks + useTaskSubmission Hook
   - 实现方式: 通过 AIProcessorWithTasks 组件渲染上传与提交界面，并把放大倍数(scale)作为自定义设置传入；底层提交统一走 useTaskSubmission，在其中对 `hires` 做特殊处理（调用 `processHiresUpscale`）
   - 任务提交流程:
     1. 用户通过EnhancedImageUpload上传图片并选择放大倍数
     2. 表单验证检查图片上传和放大倍数选择
     3. 生成任务ID并处理图片为base64格式
     4. 构建hiresParams对象，包含action("hires")、userId、taskId、imageList、scale及quality参数
     5. 通过processHiresUpscale(imageData, {scale, quality})提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success 后异步打开成功对话框（由 useTaskSubmission 的 showSuccessDialog 回调触发）
     2) 需要立即刷新任务列表：useTaskSubmission 内部调用 triggerRefreshTaskListDebounced(taskId, {userId, action, page, size})，DashboardTaskList 监听 refreshTaskList 事件并重新加载
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId(taskId) 并调用 taskMonitoringEventSystem.triggerImmediateCheck()

2. **印花提取 (PatternExtractor)**
   - 组件路径: `src/components/PatternExtractor.tsx`
   - 工具类型: `pattern-extract`
   - 特殊参数: 支持多图上传（最多3张：1张主图+2张参考图）、prompt（可选）
   - 依赖组件: useTaskSubmission Hook
   - 实现方式: 直接使用 useTaskSubmission Hook 提交任务，通过自定义UI实现图片上传和参数设置
   - 任务提交流程:
     1. 用户通过自定义UI上传主图和参考图（可选）
     2. 表单验证检查主图上传（必选）和参考图上传（可选）
     3. 生成任务ID并处理图片为base64格式
     4. 构建patternParams对象，包含action("pattern-extract")、userId、taskId、prompt和imageList
    5. 通过submitTask('pattern-extract', patternParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success 后通过 showSuccessDialog 弹出成功对话框
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId + taskMonitoringEventSystem.triggerImmediateCheck()

3. **四方连续 (SeamlessProcessor)**
   - 组件路径: `src/components/SeamlessProcessor.tsx`
   - 工具类型: `seamless`
   - 特殊参数: 无（仅支持单图上传和可选描述）
   - 依赖组件: AIProcessorWithTasks
   - 实现方式: 通过AIProcessorWithTasks组件实现，配置action为"seamless"
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片
     2. 表单验证检查图片上传
     3. 生成任务ID并处理图片为base64格式
     4. 构建seamlessParams对象，包含action("seamless")、userId、taskId、prompt和imageList
    5. 通过submitTask('seamless', seamlessParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：useTaskSubmission 触发成功提示
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId + taskMonitoringEventSystem.triggerImmediateCheck()

4. **两方连续 (TwoWaySeamlessProcessor)**
   - 组件路径: `src/components/TwoWaySeamlessProcessor.tsx`
   - 工具类型: `twoway`
   - 特殊参数: 无（仅支持单图上传和可选描述）
   - 依赖组件: AIProcessorWithTasks
   - 实现方式: 通过AIProcessorWithTasks组件实现，配置action为"twoway"
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片
     2. 表单验证检查图片上传
     3. 生成任务ID并处理图片为base64格式
     4. 构建twowayParams对象，包含action("twoway")、userId、taskId、prompt和imageList
    5. 通过submitTask('twoway', twowayParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：useTaskSubmission 触发成功提示
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId + taskMonitoringEventSystem.triggerImmediateCheck()

5. **图生图 (Img2ImgProcessor)**
   - 组件路径: `src/components/Img2ImgProcessor.tsx`
   - 工具类型: `img2img`
   - 特殊参数: model（模型）、artStyle（艺术风格）、count（生成数量）
   - 依赖组件: useTaskSubmission Hook
   - 实现方式: 直接使用 useTaskSubmission Hook 提交任务，通过自定义UI实现图片上传和参数设置
   - 任务提交流程:
     1. 用户通过自定义UI上传主图和参考图（可选）
     2. 表单验证检查主图上传（必选）和描述文本（必选）
     3. 生成任务ID并处理图片为base64格式
     4. 构建img2imgParams对象，包含action("img2img")、userId、taskId、prompt、imageList、aux_imageList、model、artStyle、count等参数
    5. 通过submitTask('img2img', img2imgParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success 后通过 showSuccessDialog 弹出成功对话框
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId + taskMonitoringEventSystem.triggerImmediateCheck()

6. **扩展图 (ImageExtensionProcessor)**
   - 组件路径: `src/components/ImageExtensionProcessor.tsx`
   - 工具类型: `extend`
   - 特殊参数: top、bottom、left、right（扩展尺寸，像素）
   - 依赖组件: useTaskSubmission Hook
   - 实现方式: 直接使用 useTaskSubmission Hook 提交任务，通过自定义UI实现图片上传和参数设置
   - 任务提交流程:
     1. 用户通过自定义UI上传图片
     2. 表单验证检查图片上传（必选）
     3. 生成任务ID并处理图片为base64格式
     4. 构建extendParams对象，包含action("extend")、userId、taskId、prompt、imageList、top、bottom、left、right等参数
    5. 通过submitTask('extend', extendParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success 后通过 showSuccessDialog 弹出成功对话框
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId + taskMonitoringEventSystem.triggerImmediateCheck()

7. **图片融合 (ImageMergeProcessor)**
   - 组件路径: `src/components/ImageMergeProcessor.tsx`
   - 工具类型: `merge`
   - 特殊参数: mergeMode（融合模式）、alpha（透明度）、outputRatio（输出比例）
   - 依赖组件: useTaskSubmission Hook
   - 实现方式: 直接使用 useTaskSubmission Hook 提交任务，通过自定义UI实现图片上传和参数设置
   - 任务提交流程:
     1. 用户通过自定义UI上传主图和辅图
     2. 表单验证检查主图和辅图上传（必选）和描述文本（必选）
     3. 生成任务ID并处理图片为base64格式
     4. 构建mergeParams对象，包含action("merge")、userId、taskId、prompt、imageList、aux_imageList、mergeMode、alpha、outputRatio等参数
    5. 通过submitTask('merge', mergeParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success 后通过 showSuccessDialog 弹出成功对话框
     2) 需要立即刷新任务列表：useTaskSubmission 内部触发 refreshTaskList 事件，DashboardTaskList 响应刷新
#### 实现方式分类

根据实现方式，图像处理组件可以分为两类：

1. **基于AIProcessorWithTasks的组件**
   - 特点：使用通用组件AIProcessorWithTasks，通过配置不同参数实现不同功能
   - 组件：UpscaleProcessor、SeamlessProcessor、TwoWaySeamlessProcessor
   - 优势：代码复用性高，UI一致性，维护成本低
   - 实现：通过action、toolName、requireDescription等配置参数区分不同工具

2. **基于useTaskSubmission Hook的组件**
   - 特点：直接使用useTaskSubmission Hook，自定义UI实现特定功能
   - 组件：PatternExtractor、Img2ImgProcessor、ImageExtensionProcessor、ImageMergeProcessor
   - 优势：灵活性高，可以实现复杂UI和特殊交互
  - 实现：自定义表单、参数验证和UI布局，通过submitTask提交任务

#### 任务提交流程

所有组件遵循统一的任务提交流程：

1. **收集输入**：收集用户输入的参数（图片、文本描述、设置选项等）
2. **参数验证**：验证必填参数和参数格式
3. **构建任务对象**：按照规范构建包含必须参数和可变参数的任务对象
4. **调用接口**：通过统一的`submitImageProcessing`函数提交任务
5. **处理结果**：处理提交结果，更新UI状态和任务列表

#### 任务提交流程

所有组件遵循统一的任务提交流程：

1. **参数收集** - 收集用户上传的图片和配置的参数
2. **数据验证** - 验证输入数据的有效性
3. **任务构建** - 构建符合API规范的任务参数
4. **任务提交** - 调用`submitTask`API提交任务
5. **状态监控** - 通过任务监控系统跟踪任务状态
6. **结果展示** - 任务完成后展示结果并提供下载

所有组件共享同一个任务监控系统：

1. **taskDynamicCollectionManager**：管理活跃任务ID集合，自动添加和移除任务ID
2. **taskMonitoringEventSystem**：监控任务状态变化，触发相应回调更新UI
3. **实时更新**：任务状态变化时自动更新本地任务状态和UI，无需手动刷新
4. **防抖处理**：使用debounce技术避免频繁更新，提升性能

这种统一的参数封装规范和任务处理流程确保了系统的一致性和可维护性，使得添加新组件或修改现有组件变得更加容易。

### 智能轮询机制

项目实现了高效的智能轮询机制，用于监控异步任务状态，同时优化资源使用和用户体验。该机制由三个核心组件构成：

1. **智能轮询管理器 (SmartPollingManager)**
   - 动态调整轮询间隔（5-30秒）
   - 基于高优先级任务和失败次数自动优化频率
   - 页面可见性和用户活动检测，减少无效请求

2. **任务管理器 (TaskManager)**
   - 维护活跃任务集合
   - 提供轮询配置管理
   - 处理不同页面类型的轮询需求

3. **任务动态集合管理器 (TaskDynamicCollectionManager)**
   - 固定间隔监控任务状态（15秒）
   - 与智能轮询管理器协同工作
   - 页面可见性监听和资源管理

**详细文档**：请参考 [智能轮询机制文档](docs/smart-polling-mechanism.md)，了解完整的实现原理、组件集成方式和最佳实践。
   - 具体实现逻辑:
     - 使用AIProcessorWithTasks组件实现四方连续功能
     - 在AIProcessorWithTasks中配置toolType为"seamless"
     - 配置toolName为"四方连续"
     - 配置toolIcon为Grid3X3组件
     - 设置requireDescription为false，表示不需要描述
     - 设置placeholderText为"上传图片后，系统将自动生成四方连续图案"
     - 设置maxImages为1，限制只能上传一张图片
     - 添加extraInfo说明"生成四方连续无缝平铺图案，适用于背景和纹理设计"
     - 任务提交和处理逻辑完全由AIProcessorWithTasks组件处理
   - 任务列表加载逻辑:
     - 初始化加载：通过useEffect在组件挂载时调用fetchTasks函数获取初始任务数据
     - 分页加载：使用usePaginationState管理分页状态，支持页面大小和页码变化
     - 参数构建：通过buildTaskListParams函数构建请求参数，包含userId、action、page、size和tooltype
     - API调用：调用/workflow-task/recent接口获取任务数据，支持items数组格式
     - 数据映射：使用createTaskFromData函数将API返回数据转换为Task对象，包含状态映射和时间格式化
   - 数据交互机制:
     - 状态管理：使用useReducer管理任务数据和版本号，支持SET_TASKS和UPDATE_TASKS操作
     - 实时更新：通过taskMonitoringEventSystem监控任务状态变化，自动更新本地状态
     - 错误处理：API调用失败时静默处理错误，保持当前状态不变
     - 缓存机制：任务数据在组件内部缓存，通过refreshParams存储刷新参数
   - 任务监控事件系统:
     - 系统初始化：通过taskMonitoringEventSystem.initialize初始化监控系统，设置userId、action、page、size参数
     - 回调设置：设置任务列表更新回调和任务状态变化回调，处理状态变化和UI更新
     - 监控启动：当有活跃任务时自动启动监控，无活跃任务时停止监控
     - 页面可见性：监听页面可见性变化，页面不可见时暂停监控，可见时恢复
     - 状态检测：定期检查任务状态变化，将数字状态转换为字符串状态，更新任务进度和图片
   - 动态管理机制:
     - 活跃任务集合：使用taskDynamicCollectionManager管理状态为pending(0)和processing(1)的任务ID集合
     - 任务添加：新任务提交时通过taskDynamicCollectionManager.addTaskId添加到监控集合
     - 任务移除：任务完成(2)、失败(3)或取消(4)时自动从监控集合移除
     - 集合清理：页面卸载时通过taskDynamicCollectionManager.clear清理监控集合
     - 监控控制：根据集合大小自动启停监控，无活跃任务时通过taskMonitoringEventSystem.stopMonitoring停止监控
   - 数据无感更新:
     - 状态同步：监控系统检测到状态变化时自动更新本地任务状态，保持UI与数据同步
     - 图片更新：任务完成时自动获取并更新缩略图和预览图，支持多字段URL获取
     - 进度显示：处理中任务显示进度条，完成时显示100%，失败时显示错误状态
     - UI刷新：使用React状态管理触发UI自动更新，通过dispatch触发状态变更
     - 防抖处理：使用debounce技术避免频繁更新，通过triggerRefreshTaskListDebounced优化刷新频率

4. **两方连续 (TwoWaySeamlessProcessor)**
   - 组件路径: `src/components/TwoWaySeamlessProcessor.tsx`
   - 工具类型: `twoway`
   - 特殊参数: 无
   - 依赖组件: AIProcessorWithTasks
   - 实现方式: 通过AIProcessorWithTasks组件实现
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片
     2. 表单验证检查图片上传
     3. 生成任务ID并处理图片为base64格式
     4. 构建twowayParams对象，包含action("twoway")、userId、taskId、prompt和imageList
    5. 通过submitTask('twoway', twowayParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：useTaskSubmission 触发成功提示；AIProcessorWithTasks 对 twoway 亦有显式的成功对话框调用（与 Hook 行为重复）
     2) 需要立即刷新任务列表：Hook 内部触发 refreshTaskList；AIProcessorWithTasks 对 twoway 再次显式调用 triggerRefreshTaskListDebounced（重复但防抖安全）
     3) 添加任务ID到动态活跃任务集合、触发任务：Hook 内部已添加并触发；AIProcessorWithTasks 对 twoway 也显式调用 addTaskId 与 triggerImmediateCheck（重复但集合去重）
   - 具体实现逻辑:
     1. **任务列表加载逻辑**
        - 初始化加载：组件挂载时通过useEffect钩子调用fetchTasks函数获取初始任务列表
        - 分页加载：使用usePaginationState Hook管理分页状态，支持页码和每页数量变化
        - 参数构建：通过buildTaskListParams函数构建请求参数，包含userId、action("twoway")、page和size
        - API调用：调用`/workflow-task/recent`接口获取任务数据
        - 数据映射：使用createTaskFromData函数将API返回数据转换为前端Task对象格式

     2. **数据交互机制**
        - 状态管理：使用useReducer管理任务数据状态，支持SET_TASKS、UPDATE_TASKS等操作
        - 实时更新：通过taskMonitoringEventSystem实现任务状态的实时监控和更新
        - 错误处理：API调用失败时进行静默错误处理，不影响用户体验
        - 数据缓存：通过refreshParams存储当前请求参数，支持使用存储参数刷新列表

     3. **任务监控事件系统**
        - 初始化：在页面可见时初始化taskMonitoringEventSystem和taskDynamicCollectionManager
        - 回调设置：设置监控回调、任务列表更新回调和任务状态变化回调
        - 监控启停：根据活跃任务数量自动启动或停止监控系统
        - 页面可见性处理：仅在页面可见时执行监控，优化性能
        - 状态检测：定期检查任务状态变化，触发相应的UI更新

     4. **动态管理机制**
        - 活跃任务集合管理：使用taskDynamicCollectionManager管理状态为pending和processing的任务ID
        - 任务添加：新提交的任务通过taskDynamicCollectionManager.addTaskId添加到监控集合
        - 任务移除：状态变为completed、failed或canceled的任务自动从监控集合中移除
        - 监控控制：根据活跃任务数量自动控制监控系统的启动和停止

     5. **数据无感更新**
        - 状态同步：通过taskStatusChangeCallback实现任务状态的实时同步
        - 图片更新：已完成任务的缩略图和预览图通过多字段获取策略确保显示正确
        - 进度显示：处理中的任务显示进度条和百分比
        - UI刷新：使用防抖机制控制UI刷新频率，避免频繁渲染
        - 防抖处理：使用triggerRefreshTaskListDebounced函数防止频繁的任务列表刷新请求

     6. **组件配置**
        - 使用AIProcessorWithTasks组件实现两方连续功能
        - 在AIProcessorWithTasks中配置toolType为"twoway"
        - 配置toolName为"两方连续"
        - 配置toolIcon为Columns组件
        - 设置requireDescription为false，表示不需要描述
        - 设置placeholderText为"上传图片后，系统将自动生成两方连续图案"
        - 设置maxImages为1，限制只能上传一张图片
        - 添加extraInfo说明"生成单方向无缝平铺图案，支持水平/垂直方向选择"
        - 任务提交和处理逻辑完全由AIProcessorWithTasks组件处理

5. **图生图 (Img2ImgProcessor)**
   - 组件路径: `src/components/Img2ImgProcessor.tsx`
   - 工具类型: `img2img`
   - 特殊参数: 效果描述（必填、≤500字）、参考图片（可选），内部生成 prompt；支持主图与参考图的 `imageList`/`aux_imageList`
   - 依赖组件: DualImageUpload, DashboardTaskList + useTaskSubmission Hook
   - 加载方式:
     - 在 `AIToolsPageV2` 中通过工具映射切换到 `Img2ImgProcessor`，页面类型设置为 `DRAWING_TOOL`，并注入刷新参数（userId、page、size、action/tooltype）到 `taskManager`
   - 任务提交交互:
     - 双图片上传（主图必选、参考图可选）+ 文本描述必填，点击“开始处理”按钮触发 `handleSubmitTask`
     - 生成 `taskId`，主/辅图转为 base64，拼装 `img2imgParams` 后调用 `useTaskSubmission.submitTask`
   - 提交后处理逻辑:
     1) 提示框：`toast.success('任务提交成功')`，随后通过 `showSuccessDialog` 异步弹出成功对话框
     2) 立即刷新任务列表：本地 `triggerRefreshTaskListDebounced(taskId)` 更新 `refreshTrigger`；另外 Hook 内部也会调用全局的 `triggerRefreshTaskListDebounced(taskId, {userId, action, page, size})`
     3) 动态集合与触发：`taskDynamicCollectionManager.addTaskId(taskId)` 添加到活跃集合，`taskMonitoringEventSystem.triggerImmediateCheck()` 触发监控
   - 实现方式: 自定义实现，不使用AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过DualImageUpload上传原始图片和参考图片（可选）
     2. 表单验证检查原始图片上传和效果描述（必填）
     3. 生成任务ID并处理图片为base64格式
     4. 构建img2imgParams对象，包含action("img2img")、userId、taskId、imageList(主图)、aux_imageList(参考图)、prompt、model、artStyle和count参数
    5. 通过submitTask('img2img', img2imgParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 具体实现逻辑:
     - 使用useState管理图片上传状态、描述文本、处理状态等17个状态变量
     - 实现handleImageChange函数处理图片上传并获取真实尺寸
     - 实现handleSubmitTask函数处理任务提交，包含表单验证和API调用
     - 使用taskDynamicCollectionManager管理任务ID集合
     - 使用taskMonitoringEventSystem监控任务状态变化
     - 使用debounce优化任务列表刷新频率
     - 支持双图片上传，包括主图和参考图
     - 实现handleDownloadTask和handleRegenerateTask函数处理任务下载和重新生成
     - 使用useEffect设置页面类型、刷新参数和初始化任务监控系统
   - 任务列表加载逻辑:
     - 初始化加载：组件挂载时通过useEffect钩子调用fetchTasks函数获取初始任务列表
     - 参数传递：通过DashboardTaskList组件的action和refreshTrigger属性控制任务列表加载
     - API调用：使用getTasks(action)函数调用/workflow-task/recent接口获取任务数据
     - 数据存储：获取的任务数据存储在tasks状态变量中
     - 刷新触发：通过refreshTrigger状态变化触发DashboardTaskList组件重新加载任务列表
   - 数据交互机制:
     - 状态管理：使用useState管理任务列表状态，支持任务添加、更新和删除
     - 实时更新：通过DashboardTaskList组件实现任务状态的实时监控和更新
     - 错误处理：API调用失败时在控制台输出错误信息，不影响用户体验
     - 事件通信：使用refreshTrigger和CustomEvent实现组件间通信
   - 任务监控事件系统:
     - 系统初始化：通过taskManager.setCurrentPageType设置页面类型为DRAWING_TOOL
     - 参数设置：使用taskManager.setRefreshParams设置刷新参数，包含userId、page、size、action和tooltype
     - 任务添加：任务提交成功后通过taskDynamicCollectionManager.addTaskId添加到监控集合
     - 立即检查：通过taskMonitoringEventSystem.triggerImmediateCheck触发立即状态检查
     - 事件触发：通过window.dispatchEvent触发refreshTaskList事件，传递taskId和相关参数
   - 动态管理机制:
     - 活跃任务集合：使用taskDynamicCollectionManager管理活跃任务ID集合
     - 任务添加：新提交任务通过taskDynamicCollectionManager.addTaskId添加到监控集合
     - 任务监控：通过taskMonitoringEventSystem实现任务状态的定期检查
     - 集合清理：页面卸载时自动清理监控集合，停止监控
   - 数据无感更新:
     - 防抖刷新：使用triggerRefreshTaskListDebounced函数实现防抖的任务列表刷新
     - 状态同步：通过DashboardTaskList组件实现任务状态的自动同步
     - 进度显示：处理中任务显示进度条和百分比
     - 结果展示：任务完成后通过对话框展示处理结果
     - 交互反馈：提供下载、继续处理等操作按钮，增强用户体验

6. **扩展图 (ImageExtensionProcessor)**
   - 组件路径: `src/components/ImageExtensionProcessor.tsx`
   - 工具类型: `extend`
   - 特殊参数: 扩展方向(left/top/right/bottom)、prompt（可选）
   - 依赖组件: EnhancedImageUpload, DashboardTaskList, ExtensionVisualizerV3
   - 实现方式: 自定义实现，不使用AIProcessorWithTasks
   - 任务提交流程:
     1. 用户上传图片并通过ExtensionVisualizerV3设置扩展参数
     2. 表单验证检查图片上传和扩展参数设置
     3. 生成任务ID并处理图片为base64格式
     4. 构建extendParams对象，包含action("extend")、userId、taskId、imageList、prompt及扩展参数
    5. 通过submitTask('extend', extendParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 具体实现逻辑:
     - 任务列表加载逻辑:
       - 初始化时通过useEffect设置页面类型为作图工具页面(taskManager.setCurrentPageType)
       - 设置taskManager刷新参数(userId、page=0、size=5、action="extend"、tooltype="extend")
       - 使用refreshTrigger状态触发DashboardTaskList组件重新渲染
       - 通过triggerRefreshTaskListDebounced防抖函数优化刷新频率，避免频繁API调用
       - 任务提交成功后立即触发任务列表刷新，确保新任务及时显示
     - 数据交互机制:
       - 使用useState管理图片上传状态(images)、扩展设置(extensionSettings)、描述(description)、处理状态(processing)等17个状态变量
       - 实现handleSubmitTask函数处理任务提交，包含表单验证和API调用
      - 图片上传后通过fileToBase64函数转换为base64格式，构建imageList
       - 使用try-catch处理任务提交过程中的错误，提供用户友好的错误提示
       - 任务提交成功后通过事件系统通知其他组件更新状态
     - 任务监控事件系统:
       - 初始化时调用taskMonitoringEventSystem.initialize设置监控参数
       - 任务提交成功后调用taskDynamicCollectionManager.addTaskId添加任务ID到活跃集合
       - 调用taskMonitoringEventSystem.triggerImmediateCheck()立即检查任务状态
       - 通过ENABLE_ASYNC_TASK_MONITORING配置控制是否启用异步任务监控
       - 组件卸载时调用taskMonitoringEventSystem.cleanup清理资源
     - 动态管理机制:
       - 使用taskDynamicCollectionManager管理活跃任务ID集合
       - 任务提交成功后自动添加到动态集合，开始监控任务状态
       - 实现handleRegenerateTask函数处理任务重新生成，支持基于原任务参数创建新任务
       - 重新生成任务时同样添加到动态集合并触发监控检查
       - 提供handleDownloadTask函数处理任务结果下载
     - 列表数据无感更新:
       - 使用防抖函数triggerRefreshTaskListDebounced控制刷新频率，避免频繁更新
       - 通过refreshTrigger状态变化触发DashboardTaskList组件重新渲染
       - 任务状态变化时自动更新列表显示，无需用户手动刷新
       - 实现任务提交成功对话框，提供查看任务列表和继续提交新任务的选项
       - 通过window.dispatchEvent(new Event('refreshTaskList'))全局事件刷新任务列表
       - 支持任务完成后自动下载和继续提交新任务的无缝切换
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success + 成功对话框（本组件通过 setShowSuccessDialog，同时 useTaskSubmission 也会触发）
     2) 需要立即刷新任务列表：本组件局部 refreshTrigger 更新 + Hook 内部全局 triggerRefreshTaskListDebounced 事件，两路并存
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId 与 taskMonitoringEventSystem.triggerImmediateCheck（与 Hook 行为重复但安全）

7. **图片融合 (ImageMergeProcessor)**
   - 组件路径: `src/components/ImageMergeProcessor.tsx`
   - 工具类型: `merge`
   - 特殊参数: prompt（必选）
   - 依赖组件: DualImageUpload, DashboardTaskList
   - 实现方式: 自定义实现，不使用AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过DualImageUpload上传主图和辅图，设置融合参数
     2. 表单验证检查主图、辅图上传和融合效果描述
     3. 生成任务ID并处理图片为base64格式
     4. 构建mergeParams对象，包含action("merge")、userId、taskId、imageList(主图)、aux_imageList(辅图)、prompt及融合参数
    5. 通过submitTask('merge', mergeParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表
   - 具体实现逻辑:
     - 任务列表加载逻辑:
       - 初始化时通过useEffect设置页面类型为作图工具页面(taskManager.setCurrentPageType)
       - 设置taskManager刷新参数(userId、page=0、size=5、action="merge"、tooltype="merge")
       - 使用refreshTrigger状态触发DashboardTaskList组件重新渲染
       - 通过triggerRefreshTaskListDebounced防抖函数优化刷新频率，避免频繁API调用
       - 任务提交成功后立即触发任务列表刷新，确保新任务及时显示
     - 数据交互机制:
       - 使用useState管理主图(mainImage)、辅图(secondaryImage)、描述(description)、融合模式(mergeMode)等状态
       - 实现handleSubmitTask函数处理任务提交，包含表单验证和API调用
      - 图片上传后通过fileToBase64函数转换为base64格式，构建imageList和aux_imageList
       - 使用try-catch处理任务提交过程中的错误，提供用户友好的错误提示
       - 任务提交成功后通过事件系统通知其他组件更新状态
     - 任务监控事件系统:
       - 初始化时调用taskMonitoringEventSystem.initialize设置监控参数
       - 任务提交成功后调用taskDynamicCollectionManager.addTaskId添加任务ID到活跃集合
       - 调用taskMonitoringEventSystem.triggerImmediateCheck()立即检查任务状态
       - 通过ENABLE_ASYNC_TASK_MONITORING配置控制是否启用异步任务监控
       - 组件卸载时调用taskMonitoringEventSystem.cleanup清理资源
     - 动态管理机制:
       - 使用taskDynamicCollectionManager管理活跃任务ID集合
       - 任务提交成功后自动添加到动态集合，开始监控任务状态
       - 实现handleRegenerateTask函数处理任务重新生成，支持基于原任务参数创建新任务
       - 重新生成任务时同样添加到动态集合并触发监控检查
       - 提供handleDownloadTask函数处理任务结果下载
     - 列表数据无感更新:
       - 使用防抖函数triggerRefreshTaskListDebounced控制刷新频率，避免频繁更新
       - 通过refreshTrigger状态变化触发DashboardTaskList组件重新渲染
       - 任务状态变化时自动更新列表显示，无需用户手动刷新
       - 实现任务提交成功对话框，提供查看任务列表和继续提交新任务的选项
       - 通过window.dispatchEvent(new Event('refreshTaskList'))全局事件刷新任务列表
       - 支持任务完成后自动下载和继续提交新任务的无缝切换
   - 提交后处理逻辑:
     1) 任务提交成功提示框弹出：toast.success + 成功对话框（组件与 Hook 双路触发）
     2) 需要立即刷新任务列表：局部 refreshTrigger + 全局 triggerRefreshTaskListDebounced 事件
     3) 添加任务ID到动态活跃任务集合、触发任务：taskDynamicCollectionManager.addTaskId 与 taskMonitoringEventSystem.triggerImmediateCheck（与 Hook 行为重复，集合去重）

### 处理器加载方式、提交交互与提交后处理 — 共同点与差异

以下对无损放大、印花提取、四方连续、两方连续、图生图、扩展图、图片融合七个处理器的加载方式、任务提交交互方式，以及提交后的处理逻辑进行归纳对比：

一、共同点
- 页面载入与监控初始化：
  - 在 AIToolsPageV2 中根据 Sidebar 的 activeTool 加载对应处理器组件
  - 所有处理器都会设置当前页面类型为绘图工具（taskManager.setCurrentPageType('DRAWING_TOOL') 或由上层页面统一设置）
  - 统一通过 taskManager.setRefreshParams 注入 userId、action/tooltype、page、size，供任务列表刷新使用
  - 初始化任务监控：taskMonitoringEventSystem.initialize，设置更新回调并监听页面可见性
- 任务提交链路：
  - 图片转 base64、生成 taskId、组装参数，走 useTaskSubmission.submitTask 统一接口（AIProcessorWithTasks 内部或各自组件显式调用）
  - useTaskSubmission 在 onSuccess 中统一执行：toast 成功提示、showSuccessDialog 弹窗、添加任务ID到 taskDynamicCollectionManager、触发 taskMonitoringEventSystem.triggerImmediateCheck、调度 triggerRefreshTaskListDebounced 刷新任务列表
- 任务列表刷新与展示：
  - DashboardTaskList 统一展示任务，监听 refreshTaskList 自定义事件或局部 refreshTrigger 状态，进行分页和状态映射
  - 刷新采用防抖触发（debounce.ts 中的 triggerRefreshTaskListDebounced）以避免高频请求

二、差异点
- 组件加载与页面结构：
  - 使用 AIProcessorWithTasks 的处理器：UpscaleProcessor、PatternExtractorV2、SeamlessProcessor、TwoWaySeamlessProcessor（统一 UI 与提交链路，扩展少量自定义配置）
  - 自定义页面的处理器：Img2ImgProcessor、ImageExtensionProcessor、ImageMergeProcessor（自定义表单/控件，仍复用 useTaskSubmission、DashboardTaskList 与监控体系）
- 提交参数差异：
  - hires（无损放大）：需要 scale 倍数；useTaskSubmission 内对 hires 有特殊分支，使用 processHiresUpscale 计算尺寸与质量
  - pattern-extract（印花提取）：支持多图（最多 3 张），prompt 可选
  - seamless/twoway（连续平铺）：单图输入，prompt 可选；AIProcessorWithTasks 对这两类在 onSuccess 中还做了显式的重复动作（添加任务ID、触发监控、刷新），与 Hook 行为重复但安全
  - img2img（图生图）：主图 imageList + 参考图 aux_imageList，描述必填，内部生成 prompt；支持模型与风格参数
  - extend（扩展图）：扩展方向/范围参数（left/top/right/bottom），prompt 可选；与可视化控件 ExtensionVisualizerV3 联动
  - merge（图片融合）：主图 + 辅图，alpha 强度、输出比例等融合参数，prompt 必填
- 提交后处理的触发路径：
  - 绝大多数组件依赖 useTaskSubmission 的统一 onSuccess 逻辑
  - Img2Img/Extend/Merge 还会在组件内手动执行（setShowSuccessDialog、addTaskId、triggerImmediateCheck、triggerRefreshTaskListDebounced），与 Hook 行为双路并存，因防抖与集合去重而不会造成问题
  - Seamless/TwoWay 在 AIProcessorWithTasks 中有显式重复触发，行为与 Hook 一致

三、可维护性建议
- 保留 useTaskSubmission 的统一后置逻辑，逐步减少各组件内的重复触发（成功弹窗、刷新、动态集合与检查）以避免多处维护
- 在 DashboardTaskList 的刷新参数中显式带上 action/tooltype，确保服务端过滤正确
- 如需扩展新的处理器，优先复用 AIProcessorWithTasks（若 UI 需求高度定制，则复用 useTaskSubmission + DashboardTaskList + 监控三件套）
<!--  暂时无需关注的工具菜单
8. **智能抠图 (CutoutProcessor)**
   - 组件路径: `src/components/CutoutProcessor.tsx`
   - 工具类型: `cutout`
   - 特殊参数: 无
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片
     2. 表单验证检查图片上传
     3. 生成任务ID并处理图片为base64格式
     4. 构建cutoutParams对象，包含action("cutout")、userId、taskId、prompt和imageList
    5. 通过submitTask('cutout', cutoutParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表

9. **文生图 (Txt2ImgProcessor)**
   - 组件路径: `src/components/Txt2ImgProcessor.tsx`
   - 工具类型: `txt2img`
   - 特殊参数: 无需上传图片，仅需文字描述
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks输入文字描述
     2. 表单验证检查文字描述输入
     3. 生成任务ID
     4. 构建txt2imgParams对象，包含action("txt2img")、userId、taskId和prompt
    5. 通过submitTask('txt2img', txt2imgParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表



10. **风格转换 (StyleTransferProcessor)**
   - 组件路径: `src/components/StyleTransferProcessor.tsx`
   - 工具类型: `style-transfer`
   - 特殊参数: 风格类型
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片并选择风格类型
     2. 表单验证检查图片上传和风格类型选择
     3. 生成任务ID并处理图片为base64格式
     4. 构建styleTransferParams对象，包含action("style-transfer")、userId、taskId、prompt、imageList和风格参数
    5. 通过submitTask('style-transfer', styleTransferParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表

11. **局部替换 (ObjectReplaceProcessor)**
   - 组件路径: `src/components/ObjectReplaceProcessor.tsx`
   - 工具类型: `object-replace`
   - 特殊参数: 替换区域描述、替换内容描述
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片并描述替换区域和内容
     2. 表单验证检查图片上传和替换描述输入
     3. 生成任务ID并处理图片为base64格式
     4. 构建objectReplaceParams对象，包含action("object-replace")、userId、taskId、prompt、imageList和替换参数
    5. 通过submitTask('object-replace', objectReplaceParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表

12. **智能擦除 (ObjectRemoverProcessor)**
   - 组件路径: `src/components/ObjectRemoverProcessor.tsx`
   - 工具类型: `object-remove`
   - 特殊参数: 擦除区域描述
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片并描述擦除区域
     2. 表单验证检查图片上传和擦除描述输入
     3. 生成任务ID并处理图片为base64格式
     4. 构建objectRemoveParams对象，包含action("object-remove")、userId、taskId、prompt、imageList和擦除参数
    5. 通过submitTask('object-remove', objectRemoveParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表

13. **图案裁剪 (PatternCutterProcessor)**
   - 组件路径: `src/components/PatternCutterProcessor.tsx`
   - 工具类型: `pattern-cut`
   - 特殊参数: 裁剪区域、裁剪形状
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片并设置裁剪参数
     2. 表单验证检查图片上传和裁剪参数设置
     3. 生成任务ID并处理图片为base64格式
     4. 构建patternCutParams对象，包含action("pattern-cut")、userId、taskId、prompt、imageList和裁剪参数
    5. 通过submitTask('pattern-cut', patternCutParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表

14. **印花模板 (PatternTemplateProcessor)**
   - 组件路径: `src/components/PatternTemplateProcessor.tsx`
   - 工具类型: `pattern-template`
   - 特殊参数: 模板类型、应用区域
   - 依赖组件: AIProcessorWithTasks
   - 任务提交流程:
     1. 用户通过AIProcessorWithTasks上传图片并选择模板类型
     2. 表单验证检查图片上传和模板类型选择
     3. 生成任务ID并处理图片为base64格式
     4. 构建patternTemplateParams对象，包含action("pattern-template")、userId、taskId、prompt、imageList和模板参数
    5. 通过submitTask('pattern-template', patternTemplateParams)提交任务
     6. 成功后添加任务ID到动态集合、触发监控检查、刷新任务列表 -->

#### 后端接口交互

所有AI工具通过统一的`submitTask`函数与后端交互：

```typescript
// 接口路径: /image-processing?Action={action}
// 请求方法: POST
// 请求参数: 
{
  action: string,        // 工具类型，如"hires", "pattern-extract"等
  userId: string,        // 用户ID
  taskId: string,        // 任务ID
  imageList: Array,      // 主图列表，包含filename和base64
  aux_imageList?: Array, // 辅图列表（可选），包含filename和base64
  prompt?: string,       // 描述文本（可选）
  ...其他特定参数        // 各工具的特定参数
}
```

任务提交后，系统通过任务监控系统跟踪任务状态，完成后通过任务列表展示结果。



### 任务管理系统

项目实现了完整的任务管理系统：

- 任务状态实时监控
- 任务队列管理
- 进度更新通知
- 异常处理机制

#### 任务监控核心组件

1. **taskMonitoringEventSystem** - 任务监控事件系统
   - 提供任务状态变化的实时监控
   - 支持事件订阅和发布
   - 自动轮询任务状态
   - 页面可见性检测，优化性能
   - 任务数据格式转换和状态变化检测
   - 支持手动刷新任务列表

2. **taskDynamicCollectionManager** - 任务动态集合管理器
   - 管理活跃任务的ID集合（PENDING/RUNNING状态）
   - 提供任务添加和移除接口
   - 支持任务状态查询
   - 自动清理非活跃任务
   - 提供任务数量统计
   - 根据活跃任务数量自动控制监控启停

3. **debounce** - 防抖工具
   - 防止频繁的API调用
   - 优化任务列表刷新性能

#### DashboardTaskList组件实现

DashboardTaskList组件是仪表板任务列表的核心实现，负责展示和管理所有AI工具的任务状态。

1. **任务列表加载逻辑**
   - 初始化加载：组件挂载时通过useEffect钩子调用refreshData函数获取初始任务列表
   - 分页加载：使用自定义usePaginationState Hook管理分页状态，支持页码和每页数量配置
   - 参数构建：通过buildTaskListParams函数构建请求参数，包含用户ID、工具类型、页码和数量
   - API调用：调用/workflow-task/recent接口获取任务数据，支持按工具类型过滤
   - 数据映射：使用createTaskFromData函数将API返回数据映射为内部Task格式

2. **数据交互机制**
   - 状态管理：使用useReducer管理任务列表状态，支持SET_TASKS、UPDATE_TASKS等操作
   - 实时更新：通过任务监控系统实时更新任务状态，无需手动刷新
   - 错误处理：API调用失败时显示错误提示，保持当前状态不变
   - 缓存机制：任务数据在组件内部缓存，避免重复请求
   - 缩略图处理：通过getTaskThumbnail函数获取任务缩略图，支持多种图片字段解析
   - 图片URL转换：使用imageBlobUrlFromUrl将图片URL转换为blob URL，提高加载性能

3. **任务监控事件系统**
   - 系统初始化：通过taskMonitoringEventSystem.initialize设置监控参数和回调函数
   - 监控回调：实现监控回调函数，定期检查活跃任务状态变化
   - 状态检测：比较前后任务状态，识别状态变化并触发相应处理
   - 监控控制：根据活跃任务数量自动启动或停止监控
   - 事件触发：支持手动触发立即检查，无需等待定时器
   - 任务状态转换：将API返回的状态字符串转换为内部TaskData格式
   - 缩略图保留策略：已完成任务保留原有的缩略图和预览图，避免闪烁

4. **动态管理机制**
   - 活跃任务管理：使用taskDynamicCollectionManager管理活跃任务ID集合
   - 任务添加：新提交任务自动添加到监控集合，开始状态跟踪
   - 任务移除：任务完成或失败后自动从监控集合移除
   - 集合清理：页面卸载时自动清理监控集合，释放资源
   - 状态同步：监控集合与任务列表状态保持同步
   - 监控间隔：每10秒执行一次监控检查，根据页面可见性和活跃任务数量控制启停

5. **列表数据无感更新**
   - 优雅更新：通过updateTasksGracefully函数实现任务列表的无感更新
   - 变化检测：比较新旧任务数据，只更新有变化的任务
   - 状态保留：已完成任务保留原有的缩略图和预览图，避免闪烁
   - UI刷新：使用setTimeout确保状态更新后再刷新UI
   - 防抖处理：使用防抖函数控制刷新频率，避免频繁更新
   - 活跃任务处理：新任务添加到活跃集合，完成/失败任务从集合移除

6. **任务操作功能**
   - 任务点击：支持点击已完成任务查看预览图
   - 下载功能：支持Blob URL和直接URL两种下载方式
   - 重绘功能：基于原任务参数创建新任务，支持重新生成
   - 刷新按钮：手动触发任务列表刷新
   - 分页控制：支持页码和每页数量调整

7. **UI展示与交互**
   - 状态显示：使用不同颜色和图标表示任务状态
   - 进度条：处理中任务显示进度条和百分比
   - 缩略图：已完成任务显示结果缩略图
   - 操作按钮：提供下载、重绘等操作按钮
   - 分页组件：使用StablePagination组件实现分页功能

#### Dashboard.tsx与DashboardTaskList.tsx的关系

Dashboard.tsx是仪表板页面的主组件，与DashboardTaskList.tsx组件协同工作，实现任务列表的展示和管理。

1. **组件关系**
   - Dashboard.tsx作为父组件，负责整体布局和状态管理
   - DashboardTaskList.tsx作为子组件，专门负责任务列表的展示和交互
   - 两者通过props传递数据和回调函数，实现组件间通信

2. **数据流向**
   - Dashboard.tsx通过fetchRecentTasks函数获取任务数据
   - 任务数据经过处理后传递给DashboardTaskList.tsx组件
   - DashboardTaskList.tsx组件内部维护任务列表状态，并支持实时更新
   - 用户操作通过回调函数返回给Dashboard.tsx处理

3. **状态管理**
   - Dashboard.tsx使用useState管理recentTasks、loading、hasMore等状态
   - DashboardTaskList.tsx使用useReducer管理任务列表状态，支持复杂状态更新
   - 两者通过props和回调函数保持状态同步

4. **任务监控集成**
   - Dashboard.tsx初始化任务监控系统，设置监控参数和回调
   - DashboardTaskList.tsx集成任务监控系统，实现任务状态的实时更新
   - 两者共享taskMonitoringEventSystem和taskDynamicCollectionManager实例

5. **功能分工**
   - Dashboard.tsx负责页面布局、统计卡片、快速操作等整体UI
   - DashboardTaskList.tsx负责任务列表的展示、分页、操作等功能
   - 任务相关的操作（如下载、重绘）在Dashboard.tsx中实现，通过回调传递给DashboardTaskList.tsx

6. **事件处理**
   - Dashboard.tsx处理页面级别的生命周期事件（如页面可见性变化）
   - DashboardTaskList.tsx处理任务列表相关的交互事件（如任务点击、分页变化）
   - 全局事件（如refreshTaskList）在Dashboard.tsx中监听，通过状态更新影响DashboardTaskList.tsx

7. **性能优化**
   - Dashboard.tsx使用useCallback优化回调函数，避免不必要的重渲染
   - DashboardTaskList.tsx使用防抖机制控制刷新频率，减少API调用
   - 两者协同实现优雅的任务列表更新机制，确保用户体验流畅

#### AI工具任务列表实现详情

每个AI工具的右侧任务列表都基于统一的任务监控系统实现，但根据工具特性有细微差异：

1. **无损放大 (UpscaleProcessor)**
   - 组件路径: `src/components/UpscaleProcessor.tsx`
   - 工具类型: `hires`
   - 特殊参数: 放大倍数(2x/4x)、放大模式
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"hires"
     - 参数传递：构建taskListParams对象，包含userId、type("hires")、分页参数
     - API调用：调用/workflow-task/recent接口获取放大任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('hires', params)提交放大任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示放大后的高分辨率图像
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

2. **印花提取 (PatternExtractorV2)**
   - 组件路径: `src/components/PatternExtractorV2.tsx`
   - 工具类型: `pattern-extract`
   - 特殊参数: 提取模式、边缘羽化程度
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"pattern-extract"
     - 参数传递：构建taskListParams对象，包含userId、type("pattern-extract")、分页参数
     - API调用：调用/workflow-task/recent接口获取印花提取任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('pattern-extract', params)提交印花提取任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示提取的印花图案
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

3. **四方连续 (SeamlessProcessor)**
   - 组件路径: `src/components/SeamlessProcessor.tsx`
   - 工具类型: `seamless`
   - 特殊参数: 混合强度、边缘融合程度
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"seamless"
     - 参数传递：构建taskListParams对象，包含userId、type("seamless")、分页参数
     - API调用：调用/workflow-task/recent接口获取四方连续任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('seamless', params)提交四方连续任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示四方连续图案
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

4. **两方连续 (TwoWaySeamlessProcessor)**
   - 组件路径: `src/components/TwoWaySeamlessProcessor.tsx`
   - 工具类型: `twoway-seamless`
   - 特殊参数: 连续方向、混合模式
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"twoway-seamless"
     - 参数传递：构建taskListParams对象，包含userId、type("twoway-seamless")、分页参数
     - API调用：调用/workflow-task/recent接口获取两方连续任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('twoway-seamless', params)提交两方连续任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示两方连续图案
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

5. **图生图 (Img2ImgProcessor)**
   - 组件路径: `src/components/Img2ImgProcessor.tsx`
   - 工具类型: `img2img`
   - 特殊参数: 提示词、强度、风格
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"img2img"
     - 参数传递：构建taskListParams对象，包含userId、type("img2img")、分页参数
     - API调用：调用/workflow-task/recent接口获取图生图任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('img2img', params)提交图生图任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示生成的图像
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

6. **扩展图 (ImageExtensionProcessor)**
   - 组件路径: `src/components/ImageExtensionProcessor.tsx`
   - 工具类型: `img-ext`
   - 特殊参数: 扩展方向、扩展比例
   - 依赖组件: 自定义任务展示，集成ExtensionVisualizerV3可视化组件
   - 任务列表加载逻辑:
     - 初始化设置：组件内部初始化任务列表，设置工具类型为"img-ext"
     - 参数传递：构建taskListParams对象，包含userId、type("img-ext")、分页参数
     - API调用：调用/workflow-task/recent接口获取扩展图任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('img-ext', params)提交扩展图任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后使用ExtensionVisualizerV3组件展示扩展结果
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

7. **图片融合 (ImageMergeProcessor)**
   - 组件路径: `src/components/ImageMergeProcessor.tsx`
   - 工具类型: `img-merge`
   - 特殊参数: 融合模式、融合强度
   - 依赖组件: AIProcessorWithTasks
   - 任务列表加载逻辑:
     - 初始化设置：通过AIProcessorWithTasks组件初始化任务列表，设置工具类型为"img-merge"
     - 参数传递：构建taskListParams对象，包含userId、type("img-merge")、分页参数
     - API调用：调用/workflow-task/recent接口获取图片融合任务列表
     - 数据存储：使用useState管理tasks状态，支持分页加载
     - 刷新触发：通过refreshTaskList函数手动刷新任务列表
   - 数据交互机制:
    - 任务提交：通过submitTask('img-merge', params)提交图片融合任务
     - 状态同步：使用taskMonitoringEventSystem监控任务状态变化
     - 结果展示：完成后显示融合后的图像
     - 缩略图处理：通过getTaskThumbnail获取任务缩略图
   - 任务监控事件系统:
     - 初始化：组件挂载时初始化taskMonitoringEventSystem
     - 监控回调：实现监控回调函数，定期检查任务状态
     - 状态更新：通过taskStatusChangeCallback更新任务状态
     - 自动刷新：任务状态变化时自动刷新任务列表
   - 动态管理机制:
     - 活跃任务：使用taskDynamicCollectionManager管理活跃任务ID
     - 任务添加：新提交任务添加到监控集合
     - 任务移除：完成/失败任务自动从监控集合移除
     - 集合清理：组件卸载时清理监控集合
   - 数据无感更新:
     - 优雅更新：通过updateTasksGracefully实现无感更新
     - 状态保留：保留已完成任务的缩略图和预览图
     - 防抖处理：使用防抖函数控制刷新频率
     - 进度显示：处理中任务显示进度条和百分比

#### 任务状态与展示

各AI工具的任务数据展示具有以下特点：

1. **统一任务状态管理**
   - 所有工具共享相同的任务状态定义：PENDING(等待中)、RUNNING(处理中)、SUCCESS(成功)、FAILED(失败)
   - 通过taskMonitoringEventSystem统一监控状态变化
   - 使用taskDynamicCollectionManager管理活跃任务集合

2. **任务数据结构**
   ```typescript
   interface Task {
     id: string;           // 任务唯一标识
     status: string;       // 任务状态
     type: string;         // 工具类型，如"hires", "pattern-extract"等
     prompt?: string;      // 描述文本
     images?: string[];    // 输入图片URL数组
     result?: string;      // 处理结果URL
     progress?: number;    // 处理进度(0-100)
     error?: string;       // 错误信息
     createdAt: string;    // 创建时间
     updatedAt: string;    // 更新时间
   }
   ```

3. **任务列表展示差异**
   - **DashboardTaskList组件**：统一展示所有工具的任务列表
   - **智能扩图(ImageExtensionProcessor)**：使用自定义任务展示，集成ExtensionVisualizerV3可视化组件
   - **其他工具**：通过AIProcessorWithTasks组件使用DashboardTaskList展示任务

4. **任务提交流程**
  - 所有工具通过统一的`submitTask`函数提交任务
   - 任务提交成功后自动添加到taskDynamicCollectionManager
   - 触发taskMonitoringEventSystem立即检查任务状态
   - 通过事件系统更新UI显示

5. **状态监控机制**
   - 10秒定时轮询检查活跃任务状态
   - 页面可见性检测，隐藏时暂停轮询
   - 任务完成后自动从活跃集合中移除
   - 支持手动触发立即检查

### 任务监控系统深度分析

#### 核心架构设计

任务监控系统采用了分层架构设计，包含以下几个核心层次：

1. **事件驱动层**
   - `taskMonitoringEventSystem`：全局任务监控事件系统，负责管理任务状态的监听和通知
   - `taskDynamicCollectionManager`：动态任务集合管理器，负责管理活跃任务的集合
   - `refreshTaskList`：全局任务列表刷新事件，用于通知各组件更新任务列表

2. **状态管理层**
   - `useState`：React状态管理，用于管理组件内部状态
   - `useEffect`：React生命周期钩子，用于处理副作用和事件监听
   - `useCallback`：React记忆化钩子，用于优化函数性能

3. **数据交互层**
   - API接口：`/workflow-task/recent`，用于获取任务列表数据
   - 数据映射：`createTaskFromData`函数，用于将后端数据映射为前端任务对象
   - 状态同步：通过事件系统实现前后端状态同步

#### 监控系统实现机制

1. **双重监控机制**
   - **全局监控**：通过`taskMonitoringEventSystem`实现全局任务状态监控
   - **局部监控**：各组件内部实现独立的任务状态监控逻辑
   - **智能控制**：通过`ENABLE_ASYNC_TASK_MONITORING`配置控制监控系统的启用

2. **动态任务集合管理**
   ```typescript
   // 任务添加到监控集合
   taskDynamicCollectionManager.addTaskId(newTaskId);
   
   // 监控系统状态检查与启动控制
   if (!isMonitoringActive) {
     startMonitoring();
   }
   
   // 立即触发监控检查
   triggerImmediateCheck();
   ```

3. **页面可见性感知**
   ```typescript
   // 页面可见性变化处理
   const handleVisibilityChange = useCallback(() => {
     if (document.hidden) {
       // 页面隐藏时暂停监控
       pauseMonitoring();
     } else {
       // 页面显示时恢复监控
       resumeMonitoring();
     }
   }, []);
   ```

#### 数据更新机制

1. **多源数据获取**
   - **存储参数**：支持从存储参数中获取任务数据
   - **API接口**：通过`/workflow-task/recent`接口获取最新任务数据
   - **事件触发**：通过`refreshTaskList`事件触发数据更新

2. **状态同步策略**
   ```typescript
   // 使用存储参数时的任务列表更新逻辑
   if (useStorageParams) {
     const mappedTasks = tasks.map(createTaskFromData);
     const hasMore = tasks.length >= pageSize;
     dispatch({ type: 'SET_TASKS', payload: { tasks: mappedTasks, hasMore } });
     return;
   }
   
   // 不使用存储参数时的参数构建及API调用
   const params = {
     user_id: userId,
     action: type,
     page,
     size: pageSize
   };
   const response = await api.get('/workflow-task/recent', { params });
   ```

3. **无感更新实现**
   ```typescript
   // 优雅更新任务列表
   const updateTasksGracefully = (newTasks: Task[]) => {
     setTasks(prevTasks => {
       // 保留已完成任务的缩略图和预览图
       const updatedTasks = newTasks.map(newTask => {
         const existingTask = prevTasks.find(t => t.id === newTask.id);
         return existingTask ? { ...newTask, thumbnail: existingTask.thumbnail } : newTask;
       });
       return updatedTasks;
     });
   };
   ```

#### 用户体验优化

1. **实时状态反馈**
   - 任务状态变化时自动更新UI显示
   - 处理中任务显示进度条和百分比
   - 完成任务显示缩略图和预览图

2. **响应式交互设计**
   - 任务卡片支持点击查看详情
   - 支持任务重绘和下载操作
   - 分页加载优化大数据量展示

3. **错误处理与容错**
   - 静默处理API错误，避免影响用户体验
   - 提供重试机制和错误提示
   - 支持手动刷新任务列表

#### 性能优化策略

1. **防抖处理**
   ```typescript
   // 使用防抖函数控制刷新频率
   const debouncedRefresh = debounce(refreshData, 300);
   ```

2. **记忆化优化**
   ```typescript
   // 使用useCallback优化函数性能
   const handleRefresh = useCallback(() => {
     refreshData();
   }, [refreshData]);
   ```

3. **条件渲染**
   ```typescript
   // 条件渲染优化性能
    {tasks.map(task => (
      <TaskCard key={task.id} task={task} />
    ))}
    ```

### 数据更新机制深度解析

#### 数据流架构

数据更新机制采用了单向数据流架构，确保数据的一致性和可预测性：

1. **数据源层**
   - 后端API：`/workflow-task/recent`接口提供原始任务数据
   - 本地存储：通过`useStorageParams`控制是否使用存储参数
   - 事件系统：`refreshTaskList`事件触发数据更新

2. **数据转换层**
   - `createTaskFromData`：将后端数据转换为前端任务对象
   - `mappedTasks`：映射后的任务数据数组
   - `hasMore`：分页加载状态标识

3. **状态管理层**
   - `useReducer`：使用reducer模式管理复杂状态
   - `dispatch`：状态更新动作分发器
   - `SET_TASKS`：设置任务列表的动作类型

#### 数据获取策略

1. **多源数据适配**
   ```typescript
   // 存储参数优先策略
   if (useStorageParams) {
     const mappedTasks = tasks.map(createTaskFromData);
     const hasMore = tasks.length >= pageSize;
     dispatch({ type: 'SET_TASKS', payload: { tasks: mappedTasks, hasMore } });
     return;
   }
   
   // API数据获取策略
   const params = {
     user_id: userId,
     action: type,
     page,
     size: pageSize
   };
   const response = await api.get('/workflow-task/recent', { params });
   ```

2. **响应数据适配**
   ```typescript
   // 多种响应格式适配
   const data = Array.isArray(response.data) ? response.data : response.data.items || [];
   const mappedTasks = await Promise.all(
     data.map(item => createTaskFromData(item, userId))
   );
   ```

3. **错误处理机制**
   ```typescript
   // 静默错误处理
   try {
     // 数据获取逻辑
   } catch (error) {
     console.error('Failed to refresh task list:', error);
     // 静默处理错误，不中断用户体验
   }
   ```

#### 状态同步机制

1. **任务状态映射**
   ```typescript
   // 任务状态映射函数
   const createTaskFromData = async (item: any, userId: string): Promise<Task> => {
     return {
       id: item.id,
       status: item.status,
       type: item.action,
       prompt: item.prompt,
       images: item.images,
       result: item.result,
       progress: item.progress,
       error: item.error,
       createdAt: item.created_at,
       updatedAt: item.updated_at,
       userId
     };
   };
   ```

2. **状态更新触发**
   ```typescript
   // 任务状态变化回调
   const taskStatusChangeCallback = useCallback(async (updatedTask: Task) => {
     setTasks(prevTasks => 
       prevTasks.map(task => 
         task.id === updatedTask.id ? { ...task, ...updatedTask } : task
       )
     );
   }, []);
   ```

3. **批量状态更新**
   ```typescript
   // 批量更新任务状态
   const updateTasksStatus = useCallback((taskUpdates: Array<{id: string, status: string}>) => {
     setTasks(prevTasks => 
       prevTasks.map(task => {
         const update = taskUpdates.find(u => u.id === task.id);
         return update ? { ...task, status: update.status } : task;
       })
     );
   }, []);
   ```

#### 数据持久化策略

1. **本地存储机制**
   ```typescript
   // 任务数据本地存储
   const saveTasksToStorage = useCallback((tasks: Task[]) => {
     try {
       localStorage.setItem('tasks', JSON.stringify(tasks));
     } catch (error) {
       console.error('Failed to save tasks to storage:', error);
     }
   }, []);
   
   // 从本地存储加载任务
   const loadTasksFromStorage = useCallback((): Task[] => {
     try {
       const storedTasks = localStorage.getItem('tasks');
       return storedTasks ? JSON.parse(storedTasks) : [];
     } catch (error) {
       console.error('Failed to load tasks from storage:', error);
       return [];
     }
   }, []);
   ```

2. **缓存策略**
   ```typescript
   // 任务数据缓存
   const taskCache = useRef(new Map<string, Task>());
   
   // 缓存任务数据
   const cacheTask = useCallback((task: Task) => {
     taskCache.current.set(task.id, task);
   }, []);
   
   // 获取缓存任务
   const getCachedTask = useCallback((taskId: string): Task | undefined => {
     return taskCache.current.get(taskId);
   }, []);
   ```

#### 数据更新优化

1. **增量更新**
   ```typescript
   // 增量更新任务列表
   const updateTasksIncrementally = useCallback((newTasks: Task[]) => {
     setTasks(prevTasks => {
       const taskMap = new Map(prevTasks.map(task => [task.id, task]));
       newTasks.forEach(task => taskMap.set(task.id, task));
       return Array.from(taskMap.values());
     });
   }, []);
   ```

2. **智能合并**
   ```typescript
   // 智能合并任务数据
   const mergeTasksIntelligently = useCallback((newTasks: Task[]) => {
     setTasks(prevTasks => {
       return prevTasks.map(prevTask => {
         const newTask = newTasks.find(t => t.id === prevTask.id);
         if (!newTask) return prevTask;
         
         // 保留重要字段，更新其他字段
         return {
           ...prevTask,
           ...newTask,
           thumbnail: newTask.thumbnail || prevTask.thumbnail,
           preview: newTask.preview || prevTask.preview
         };
       });
     });
   }, []);
   ```

3. **防抖更新**
   ```typescript
   // 防抖更新任务列表
   const debouncedUpdateTasks = useCallback(
     debounce((updateFn: () => void) => {
       updateFn();
     }, 300),
     []
   );
   ```

#### 数据一致性保障

1. **乐观更新**
   ```typescript
   // 乐观更新任务状态
   const optimisticUpdate = useCallback((taskId: string, updates: Partial<Task>) => {
     setTasks(prevTasks => 
       prevTasks.map(task => 
         task.id === taskId ? { ...task, ...updates } : task
       )
     );
     
     // 异步提交更新到服务器
     submitTaskUpdate(taskId, updates).catch(error => {
       // 回滚更新
       setTasks(prevTasks => 
         prevTasks.map(task => 
           task.id === taskId ? { ...task, status: 'failed' } : task
         )
       );
     });
   }, []);
   ```

2. **冲突解决**
   ```typescript
   // 解决数据冲突
    const resolveDataConflict = useCallback((localTasks: Task[], remoteTasks: Task[]) => {
      return remoteTasks.map(remoteTask => {
        const localTask = localTasks.find(t => t.id === remoteTask.id);
        if (!localTask) return remoteTask;
        
        // 以最新更新时间为准
        return new Date(remoteTask.updatedAt) > new Date(localTask.updatedAt) 
          ? remoteTask 
          : localTask;
      });
    }, []);
    ```

### 性能优化方案

#### 渲染性能优化

1. **虚拟列表实现**
   ```typescript
   // 使用react-window实现虚拟列表
   import { FixedSizeList as List } from 'react-window';
   
   const TaskVirtualList = ({ tasks }: { tasks: Task[] }) => {
     const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
       <div style={style}>
         <TaskCard task={tasks[index]} />
       </div>
     );
     
     return (
       <List
         height={600}
         itemCount={tasks.length}
         itemSize={120}
         width="100%"
       >
         {Row}
       </List>
     );
   };
   ```

2. **组件记忆化**
   ```typescript
   // 使用React.memo优化任务卡片组件
   const TaskCard = React.memo(({ task }: { task: Task }) => {
     // 组件实现
   }, (prevProps, nextProps) => {
     // 自定义比较函数
     return prevProps.task.id === nextProps.task.id &&
            prevProps.task.status === nextProps.task.status &&
            prevProps.task.progress === nextProps.task.progress;
   });
   ```

3. **条件渲染优化**
   ```typescript
   // 使用条件渲染减少不必要的组件渲染
   const TaskList = ({ tasks }: { tasks: Task[] }) => {
     if (!tasks.length) {
       return <EmptyState />;
     }
     
     return (
       <div>
         {tasks.map(task => (
           <TaskCard key={task.id} task={task} />
         ))}
       </div>
     );
   };
   ```

#### 数据加载优化

1. **分页加载策略**
   ```typescript
   // 实现无限滚动分页
   const useInfiniteScroll = (loadMore: () => void) => {
     const [isFetching, setIsFetching] = useState(false);
     
     useEffect(() => {
       const handleScroll = () => {
         if (
           window.innerHeight + document.documentElement.scrollTop 
           >= document.documentElement.offsetHeight - 500 &&
           !isFetching
         ) {
           setIsFetching(true);
           loadMore();
         }
       };
       
       window.addEventListener('scroll', handleScroll);
       return () => window.removeEventListener('scroll', handleScroll);
       // eslint-disable-next-line react-hooks/exhaustive-deps
     }, [isFetching]);
       
     return [isFetching, setIsFetching] as const;
   };
   ```

2. **预加载策略**
   ```typescript
   // 实现数据预加载
   const useDataPreload = (currentPage: number, totalPages: number) => {
     useEffect(() => {
       // 预加载下一页数据
       if (currentPage < totalPages) {
         const preloadTimer = setTimeout(() => {
           preloadTasksData(currentPage + 1);
         }, 2000);
         
         return () => clearTimeout(preloadTimer);
       }
     }, [currentPage, totalPages]);
   };
   ```

3. **请求缓存**
   ```typescript
   // 实现API请求缓存
   const requestCache = new Map<string, { data: any; timestamp: number }>();
   const CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存
   
   const cachedFetch = async (url: string, params: any) => {
     const cacheKey = `${url}?${JSON.stringify(params)}`;
     const cached = requestCache.get(cacheKey);
     
     if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
       return cached.data;
     }
     
     const response = await api.get(url, { params });
     requestCache.set(cacheKey, { data: response.data, timestamp: Date.now() });
     
     return response.data;
   };
   ```

#### 状态管理优化

1. **状态拆分**
   ```typescript
   // 将复杂状态拆分为多个独立状态
   const useTaskState = () => {
     const [tasks, setTasks] = useState<Task[]>([]);
     const [loading, setLoading] = useState(false);
     const [error, setError] = useState<string | null>(null);
     const [pagination, setPagination] = useState({ page: 1, hasMore: true });
     
     return {
       tasks,
       setTasks,
       loading,
       setLoading,
       error,
       setError,
       pagination,
       setPagination
     };
   };
   ```

2. **状态更新优化**
   ```typescript
   // 使用useReducer优化复杂状态更新
   const taskReducer = (state: TaskState, action: TaskAction) => {
     switch (action.type) {
       case 'SET_TASKS':
         return {
           ...state,
           tasks: action.payload.tasks,
           pagination: {
             ...state.pagination,
             hasMore: action.payload.hasMore
           }
         };
       case 'UPDATE_TASK':
         return {
           ...state,
           tasks: state.tasks.map(task =>
             task.id === action.payload.taskId
               ? { ...task, ...action.payload.updates }
               : task
           )
         };
       default:
         return state;
     }
   };
   ```

3. **选择性订阅**
   ```typescript
   // 使用Context实现选择性订阅
   const TaskContext = createContext<TaskContextType>({
     tasks: [],
     updateTask: () => {},
     addTask: () => {}
   });
   
   const useTaskSelector = <T,>(selector: (tasks: Task[]) => T): T => {
     const { tasks } = useContext(TaskContext);
     return useMemo(() => selector(tasks), [tasks, selector]);
   };
   ```

#### 内存优化

1. **图片懒加载**
   ```typescript
   // 实现图片懒加载
   const LazyImage = ({ src, alt, className }: { src: string; alt: string; className?: string }) => {
     const [isLoaded, setIsLoaded] = useState(false);
     const [isInView, setIsInView] = useState(false);
     const imgRef = useRef<HTMLImageElement>(null);
     
     useEffect(() => {
       const observer = new IntersectionObserver(
         ([entry]) => {
           if (entry.isIntersecting) {
             setIsInView(true);
             observer.disconnect();
           }
         },
         { threshold: 0.1 }
       );
       
       if (imgRef.current) {
         observer.observe(imgRef.current);
       }
       
       return () => observer.disconnect();
     }, []);
     
     return (
       <div ref={imgRef} className={className}>
         {isInView && (
           <img
             src={src}
             alt={alt}
             onLoad={() => setIsLoaded(true)}
             style={{ opacity: isLoaded ? 1 : 0 }}
           />
         )}
       </div>
     );
   };
   ```

2. **内存清理**
   ```typescript
   // 实现组件卸载时的内存清理
   const useMemoryCleanup = () => {
     useEffect(() => {
       return () => {
         // 清理定时器
         clearInterval(monitoringInterval);
         
         // 清理事件监听器
         window.removeEventListener('visibilitychange', handleVisibilityChange);
         
         // 清理缓存
         requestCache.clear();
         
         // 清理Blob URL
         blobUrls.forEach(url => URL.revokeObjectURL(url));
       };
     }, []);
   };
   ```

3. **对象池技术**
   ```typescript
   // 实现对象池减少GC压力
   class TaskPool {
     private pool: Task[] = [];
     private maxSize = 50;
     
     acquire(): Task {
       return this.pool.pop() || {
         id: '',
         status: '',
         type: '',
         prompt: '',
         images: [],
         result: '',
         progress: 0,
         error: '',
         createdAt: '',
         updatedAt: '',
         userId: ''
       };
     }
     
     release(task: Task) {
       if (this.pool.length < this.maxSize) {
         // 重置对象状态
         task.id = '';
         task.status = '';
         // ...重置其他字段
         this.pool.push(task);
       }
     }
   }
   ```

#### 网络优化

1. **请求合并**
   ```typescript
   // 实现批量请求合并
   class BatchRequestManager {
     private pendingRequests = new Map<string, any[]>();
     private flushTimers = new Map<string, NodeJS.Timeout>();
     
     addRequest(key: string, params: any, resolve: Function) {
       if (!this.pendingRequests.has(key)) {
         this.pendingRequests.set(key, []);
       }
       
       this.pendingRequests.get(key)!.push({ params, resolve });
       
       // 设置批量刷新定时器
       if (!this.flushTimers.has(key)) {
         const timer = setTimeout(() => this.flushRequests(key), 100);
         this.flushTimers.set(key, timer);
       }
     }
     
     private async flushRequests(key: string) {
       const requests = this.pendingRequests.get(key) || [];
       this.pendingRequests.delete(key);
       this.flushTimers.delete(key);
       
       if (requests.length === 0) return;
       
       // 合并请求参数
       const batchParams = requests.map(req => req.params);
       
       try {
         // 发送批量请求
         const results = await api.post('/batch-tasks', { tasks: batchParams });
         
         // 分发结果
         requests.forEach((req, index) => {
           req.resolve(results.data[index]);
         });
       } catch (error) {
         // 处理错误
         requests.forEach(req => {
           req.resolve(Promise.reject(error));
         });
       }
     }
   }
   ```

2. **请求重试机制**
   ```typescript
   // 实现指数退避重试
   const fetchWithRetry = async (
     url: string,
     options: RequestOptions,
     maxRetries = 3,
     delay = 1000
   ) => {
     let lastError;
     
     for (let i = 0; i <= maxRetries; i++) {
       try {
         const response = await fetch(url, options);
         
         if (!response.ok) {
           throw new Error(`HTTP error! status: ${response.status}`);
         }
         
         return response.json();
       } catch (error) {
         lastError = error;
         
         if (i === maxRetries) break;
         
         // 指数退避延迟
         await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)));
       }
     }
     
     throw lastError;
   };
   ```

3. **数据压缩**
   ```typescript
   // 实现请求/响应数据压缩
   const compressedFetch = async (url: string, options: RequestOptions) => {
     // 压缩请求数据
     if (options.body && typeof options.body === 'string') {
       const compressed = await compressString(options.body);
       options.body = compressed;
       options.headers = {
         ...options.headers,
         'Content-Encoding': 'gzip'
       };
     }
     
     const response = await fetch(url, options);
     
     // 检查响应是否压缩
     const isCompressed = response.headers.get('Content-Encoding') === 'gzip';
     
     if (isCompressed) {
       const compressedData = await response.arrayBuffer();
       const decompressed = await decompressArrayBuffer(compressedData);
       return JSON.parse(decompressed);
     }
     
     return response.json();
   };
   ```

### 用户认证系统

基于JWT的用户认证：

- 用户注册与登录
- Token自动刷新
- 权限控制
- 会话管理

## 🎯 使用指南

### 1. 登录系统

首次使用需要注册账号并登录。

### 2. 选择AI工具

从侧边栏选择需要的AI图像处理工具。

### 3. 上传图片

点击上传区域或拖拽图片到指定区域。

### 4. 调整参数

根据工具特性调整相关参数。

### 5. 提交任务

点击"开始处理"提交任务到队列。

### 6. 等待完成

系统会自动处理并更新任务状态。

### 7. 下载结果

任务完成后可预览并下载处理结果。

## 🔍 开发指南

### 添加新的AI工具

1. 在`src/components/`目录创建新组件
2. 实现标准的处理接口
3. 在`Sidebar.tsx`中添加导航项
4. 在`App.tsx`中添加路由

### 代码规范

- 使用TypeScript进行类型检查
- 遵循React Hooks最佳实践
- 组件采用函数式写法
- 使用Tailwind CSS进行样式开发

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 更新日志

### v0.1.0 (2024-01-XX)

- 初始版本发布
- 实现基础AI图像处理功能
- 完成用户认证系统
- 添加任务管理功能

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 联系我们

如有问题或建议，请通过以下方式联系：

- 邮箱: support@podi-studio.com
- 问题反馈: [GitHub Issues](https://github.com/your-repo/podi-design-web/issues)

## 🙏 致谢

感谢所有为这个项目做出贡献的开发者和设计师。

---

**POD AI Studio** - 让创意设计更简单 🎨
  
6. **扩展图 (ImageExtensionProcessor)**
   - 组件路径: `src/components/ImageExtensionProcessor.tsx`
   - 工具类型: `extend`
   - 特殊参数: 扩展设置（left、top、right、bottom），自动识别原图尺寸并驱动可视化扩展控件
   - 依赖组件: EnhancedImageUpload, ExtensionVisualizerV3, DashboardTaskList + useTaskSubmission Hook
   - 加载方式:
     - 在 `AIToolsPageV2` 中通过工具映射切换到扩图处理器，页面类型设置与刷新参数由 `taskManager` 管理
   - 任务提交交互:
     - 单图上传 + 扩展设置 + 可选描述，点击“提交任务”后将图片转 base64，构建 `{toolType:'extend', imageList, prompt, left, top, right, bottom}`，调用 `useTaskSubmission.submitTask`
   - 提交后处理逻辑:
     1) 提示框：成功后由 Hook 异步调用 `showSuccessDialog` 弹窗；组件本身也维护 `showSuccessDialog` 状态
     2) 立即刷新任务列表：设置本地 `refreshTrigger({ taskId, timestamp })`，同时 Hook 内部触发全局刷新事件
     3) 动态集合与触发：`taskDynamicCollectionManager.addTaskId(taskId)` 并 `taskMonitoringEventSystem.triggerImmediateCheck()`

7. **图片融合 (ImageMergeProcessor)**
   - 组件路径: `src/components/ImageMergeProcessor.tsx`
   - 工具类型: `merge`
   - 特殊参数: 融合模式 `mergeMode`（如 blend）、融合强度 `mergeStrength`（百分比，内部转 `alpha` 0–1）、输出比例 `outputRatio`；主/辅图分别进入 `imageList` 与 `aux_imageList`
   - 依赖组件: DualImageUpload, DashboardTaskList + useTaskSubmission Hook
   - 加载方式:
     - 在 `AIToolsPageV2` 中通过工具映射切换到融合处理器，页面类型设置为 `DRAWING_TOOL` 并注入刷新参数到 `taskManager`
   - 任务提交交互:
     - 主/辅图上传 + 必填文本描述，点击“开始处理”后把两张图分别转 base64，组装 `mergeParams`，调用 `useTaskSubmission.submitTask`
   - 提交后处理逻辑:
     1) 提示框：成功由 Hook 异步触发成功弹窗（组件维护 `showSuccessDialog`）
     2) 立即刷新任务列表：更新本地 `refreshTrigger`；同时 Hook 内部执行全局刷新事件
     3) 动态集合与触发：`taskDynamicCollectionManager.addTaskId(taskId)` 并 `taskMonitoringEventSystem.triggerImmediateCheck()`

---

### 处理器加载方式、提交交互与提交后处理对比（共性与差异）

1) 加载方式（共性）
   - 都通过 `AIToolsPageV2` 的工具映射进行加载与切换：给定 `id`（如 `hires`/`pattern-extract`/`seamless`/`twoway`/`extend`/`merge`/`img2img`）后，返回对应的处理器组件。
   - 切换时会设置页面类型为 `DRAWING_TOOL`，并通过 `taskManager.setRefreshParams({ userId, page, size, action, tooltype })` 注入统一的任务刷新参数。

2) 提交交互（共性）
   - 统一采用 `useTaskSubmission` Hook 进行任务提交（`AIProcessorWithTasks` 内部也使用该 Hook）。
   - 所有处理器在提交前都会将图片转为 base64，构建标准的提交参数对象；需要描述的工具会进行必填校验与长度限制。
   - 任务成功后都会回调 `showSuccessDialog` 以弹出成功对话框（由组件传入，Hook内部异步触发）。

3) 提交后处理（三点要求的统一实现）
   - 任务提交成功提示框弹出：`useTaskSubmission` 在 `handleTaskSubmissionSuccess` 中统一 `toast.success`，并异步调用 `showSuccessDialog`。
   - 立即刷新任务列表：统一通过 `triggerRefreshTaskListDebounced(taskId, { userId, action, page:0, size:5 })` 触发。部分处理器在组件内也维护 `refreshTrigger` 以驱动 `DashboardTaskList` 局部刷新。
   - 添加任务ID到动态活跃任务集合并触发：统一调用 `taskDynamicCollectionManager.addTaskId(taskId)`，并 `taskMonitoringEventSystem.triggerImmediateCheck()`。

4) 主要差异点
   - 数据准备与参数结构：
     - 无损放大（hires）：除图片列表外，还需要 `scale`，并在提交时计算 `width`/`height` 与传入 `quality`（Hook内部走 `processHiresUpscale` 特殊通道）。
     - 印花提取（pattern-extract）：支持最多3张图（主图必选，参考图可选），允许空描述（自动识别主体）。
     - 四方连续/两方连续（seamless/twoway）：单图、无需描述；`AIProcessorWithTasks` 内部也有额外的成功后处理（再添加任务ID并触发刷新），与 Hook 的统一逻辑一致。
     - 图生图（img2img）：主图必选、参考图可选、描述必填（≤500字），内部生成 prompt；使用 `imageList` + `aux_imageList`。
     - 扩展图（extend）：单图 + 扩展设置（left/top/right/bottom），会先识别图片尺寸并驱动扩展可视化控件。
     - 图片融合（merge）：主/辅图分别入主/辅列表，融合强度转为 `alpha`，支持输出比例配置。
   - 刷新触发的实现细节：
     - 有的处理器通过局部 `refreshTrigger` 驱动 `DashboardTaskList` 的刷新（如 `Img2ImgProcessor`/`ImageExtensionProcessor`/`ImageMergeProcessor`）。
     - `useTaskSubmission` 会统一触发全局的 `triggerRefreshTaskListDebounced`，与页面上的 `DashboardTaskList` 事件监听配合，确保即时刷新。
   - UI层差异：
     - `AIProcessorWithTasks` 提供统一的图片上传/描述/提交按钮与成功弹窗；而 `Img2ImgProcessor`、`ImageExtensionProcessor`、`ImageMergeProcessor` 有更定制化的表单与说明区。

通过以上梳理，七个菜单项在“加载方式、提交交互、提交后处理”三方面均遵循统一的核心机制（使用 `AIToolsPageV2` 加载、`useTaskSubmission` 提交与统一后处理、`taskDynamicCollectionManager` + `taskMonitoringEventSystem` 监控），同时在“数据准备与参数结构、局部刷新驱动、UI形态”上体现各自特色。
  