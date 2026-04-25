# 客户端内容源拆分说明

这份文档记录客户端前台内容源刚完成的第一轮拆分。

目标不是“删掉 mock”，而是先把下面三类东西分开：

1. 产品目录与入口配置
2. 演示态占位数据
3. 兼容旧代码的过渡层

## 当前拆分结果

### 1. `podi-client-web/src/config/clientCatalog.ts`

负责：

- 导航入口
- 设计/商拍/工具箱目录
- 快捷入口
- 智能体列表
- 角色案例

这层代表“产品目录”和“入口编排”，不是业务实时数据。

### 2. `podi-client-web/src/config/clientDemoData.ts`

负责：

- 演示任务
- 演示素材
- 演示钱包套餐
- 演示账单
- 演示白板项目

这层代表“未登录或体验态的占位数据”，本质上是 demo 数据，不应再和目录配置混放。

### 3. `podi-client-web/src/mock/content.ts`

当前已降级为 compatibility shim。

它的职责只剩：

- 给还没迁移完的代码提供兼容出口
- 明确提示新代码不要继续从这里取数据

原则上，新代码应直接从：

- `clientCatalog.ts`
- `clientDemoData.ts`
- `clientContent.ts`
- `clientProduct.ts`
- `clientVisuals.ts`

读取内容，而不是继续把数据堆回 `mock/content.ts`

## 为什么这样拆

如果目录、演示数据、页面文案、图片控制都继续混在一个文件里，会带来 4 个问题：

1. 无法判断某条数据是不是“真业务”
2. 页面升级时容易误改别的场景
3. 后续接真实接口时替换成本很高
4. 技术负责人无法快速看清控制边界

所以当前客户端前台的推荐内容层级是：

- `presentation`：能力语言
- `clientCatalog`：产品目录与入口
- `clientDemoData`：演示态占位数据
- `clientContent`：页面局部文案
- `clientProduct`：产品叙事与路线
- `clientVisuals`：视觉与图片控制

## 下一步

下一轮应继续做两件事：

1. 逐步减少对 `clientDemoData` 的依赖，把能接真实数据的页面切到真实接口
2. 把剩余仍属于“演示内容”的案例、白板、模板进一步区分为“运营内容”还是“真实业务数据”

## 一句话结论

客户端现在已经不再把“产品目录”和“演示假数据”混成一个 `mock/content.ts` 真源。

这一步不会改变业务逻辑，但会明显降低后续接真实数据和做运营替换的成本。
