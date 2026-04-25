# 客户端内容与图片控制表

这份文档只回答一件事：

客户端每个重要页面上的文案、案例图、占位图、入口说明，当前从哪里来，后续应该由哪里统一控制。

## 基本判断

客户端当前的“繁琐感”不只来自技术术语，还来自内容源分散：

- 一部分在页面组件内部直接写死
- 一部分在 `mock/content.ts`
- 一部分在 `clientProduct.ts`
- 一部分在 `clientVisuals.ts`

如果不先收口内容真源，后面做术语替换、品牌图替换、案例更新时，成本会越来越高。

所以当前的控制原则是：

1. 页面结构继续留在组件里
2. 页面文案与图片尽量收进 `src/config/*`
3. 所有外部占位图统一经过 `clientVisuals.ts`
4. 后续替换品牌自有 OSS 图时，只改 registry，不散改页面

## 当前控制点

### 1. 首页

- 页面结构：`podi-client-web/src/pages/HomePage.tsx`
- 产品叙事：`podi-client-web/src/config/clientProduct.ts`
- 首页局部内容卡片：`podi-client-web/src/config/clientContent.ts`
- 首页主视觉与场景图：`podi-client-web/src/config/clientVisuals.ts`
- 案例角色卡：`podi-client-web/src/mock/content.ts`

判断：

- 首页已经开始分层，但 `roleCases` 仍然在 mock 层，后续应继续往正式内容源迁移。

### 2. 工作室首页

- 页面结构：`podi-client-web/src/components/home/HomeStudio.tsx`
- 工作室文案、showcase、suggestion、创建白板入口文案：`podi-client-web/src/config/clientContent.ts`
- 工作室占位视觉：`podi-client-web/src/config/clientVisuals.ts`
- 智能体与白板卡片数据：`podi-client-web/src/mock/content.ts`

判断：

- 工作室已经可以做到“组件只负责渲染，内容从 config 层读取”。
- 但智能体列表和白板列表目前仍是 mock 数据，后续应由真实业务数据或统一内容服务承接。

### 3. 工作区

- 页面结构：`podi-client-web/src/components/workspace/*`
- 能力级展示层：中台 `/api/abilities` 返回的 `presentation`
- 工作区内容占位与示例图：`podi-client-web/src/config/clientContent.ts`
- 工作区示例视觉：`podi-client-web/src/config/clientVisuals.ts`

判断：

- 工作区“功能解释”已经开始走中台真源。
- 但空状态示例、说明语、推荐语仍属于前台内容资产，需要保留在客户端 config，而不是沉到接口层。

### 4. 钱包 / 登录 / 落地页视觉

- 当前统一来源：`podi-client-web/src/config/clientVisuals.ts`
- 当前视觉类型：`editorial placeholder`
- 当前控制方式：registry 单点替换

判断：

- 这是一个正确过渡层。
- 现阶段可接受继续使用统一 placeholder。
- 后续替换为品牌自有图、真实案例图、OSS 品牌资产时，不应改页面组件，只改 registry。

## 现阶段推荐分层

客户端内容建议固定成 4 层：

1. `clientVisuals.ts`
   控图片、案例封面、占位视觉、登录页图、钱包图

2. `clientContent.ts`
   控页面局部文案、说明卡、showcase、suggestion、空状态示例

3. `clientProduct.ts`
   控产品级叙事、首页主张、场景路线、模板资产、商业说明

4. 中台 `presentation`
   控能力对外名称、字段文案、结果预期、能力可见性

## 后续替换顺序

### 第一阶段

- 保持接口不动
- 继续把页面内硬编码文案与图片抽到 `config`
- 所有外部图都经过 `clientVisuals.ts`

### 第二阶段

- 将 `mock/content.ts` 里的案例、智能体、白板逐步迁入正式内容源
- 区分“演示内容”和“真实业务数据”

### 第三阶段

- 接入品牌自有 OSS 案例图
- 为首页、登录页、钱包、工作室建立可运营替换机制

## 一句话结论

客户端后续不该继续“页面里直接写内容”，而应该按：

`中台 presentation 管能力语言`

`clientProduct / clientContent 管页面叙事`

`clientVisuals 管图片与视觉资产`

这样做，后面改品牌、改案例、改术语、改入口，都不会再变成全站散改。
