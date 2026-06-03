# 图编辑组件边界

这个目录是图编辑前端能力的源码边界。目标是同一套组件同时服务：

- 测评端“图编辑”工作台
- `/image-edit` 托管组件入口
- 后续内部业务方源码集成

对话改图 ChatBot 是独立产品入口，不属于 `ImageEditWorkbench` 的内部模式。它应在组件外层通过 `/api/business/image-edit-chat/*` 管理会话、消息、建议确认，再由后端调用底层 `image_edit` 业务 run。

对话改图的线程语义是“图片 Codex”，不是单次任务表单：同一会话内继续输入时，默认基于最新一次成功输出继续改；只有新建会话、上传/粘贴新的基准图时才切换图片上下文。执行结果必须作为对应 tool/run 消息的一部分回填，不能用脱离聊天流的全局结果区替代。

## 文件职责

- `model.ts`：交互协议和枚举真源，包括改图模式、尺寸、质量、输出格式、区域标注结构、区域序列化和任务摘要。
- `ImageEditWorkbench.tsx`：可嵌入图编辑工作台。组件不直接依赖中台 API，只通过调用方注入上传函数、提交函数和当前表单值。
- `image-edit.css`：组件样式边界。源码交付时必须和组件一起复制，避免依赖测评端全局样式。

## 集成方式

调用方需要提供：

- `value`：当前主图、改图模式、编辑指令、标注、参考图、蒙版、尺寸、质量和输出格式。
- `onChange`：接收组件产生的新值。
- `onUploadImage`：上传图片并返回可访问 URL。
- `onSubmit`：提交当前任务。业务方应在这里调用 `/api/business/image-edit/runs`。

测评端的任务检查、请求预览、排障信息和业务接入文档必须在组件外层渲染，不允许塞进 `ImageEditWorkbench`。组件源码交付给业务方时，只保留图编辑操作本体。

如果业务方要做聊天式改图，不要把 ChatBot 逻辑塞进编辑器组件；应使用独立会话入口：

- `POST /api/business/image-edit-chat/sessions`
- `POST /api/business/image-edit-chat/sessions/{sessionId}/messages`
- `POST /api/business/image-edit-chat/sessions/{sessionId}/confirm`

当前源码组件依赖 `tdesign-react` 和 `tdesign-icons-react`。如果业务方页面不使用 TDesign，先按托管组件接入；源码交付时再提供同等交互的轻量样式适配层，不允许业务方自行改协议字段。

接口枚举必须和中台业务 API 保持一致：质量档位只使用 `auto / preview / production / premium`，输出格式只使用 `png / jpeg / webp`，尺寸字段支持预设值或符合后端约束的 `宽x高`。

## 配置与升级

业务方源码集成时，页面启动应先读取 `/api/business/image-edit/component-config`：

- `skills` 决定可展示的改图模式。
- `outpaint` 决定扩展画布默认值和锚点选项。
- `sizes/customSizeConstraints` 决定尺寸下拉和自定义尺寸校验。
- `qualityLevels/outputFormats` 决定质量和格式选项。
- `copy` 决定占位文案和提示说明。
- `component.componentVersion` 用于判断源码组件是否需要升级。

只改配置的更新不应要求业务方重新发版。涉及画布交互、标注协议或提交 payload 结构的变化，才需要升级源码组件。中台托管入口 `/image-edit` 始终跟随中台发版自动更新，是业务方最省维护成本的接入方式。

## 扩展画布模式

`canvas_outpaint` 是图编辑里的单图扩展画布模式，不是批量扩图业务。

- 用户可以选择四周、单边或手动输入上下左右扩展像素。
- 组件展示的是实际目标画布预览；后端会把目标尺寸按 16 的倍数向上取整。
- `instruction` 可不填；不填时默认自然补全外扩区域。
- `preserveOriginal` 默认开启；后端会先用 mask 保护原图区域，模型返回后再把原图区域贴回最终结果。
- 业务轻量结果只展示最终图；中间画布、mask、模型原始输出只用于排障。

## 标注与引用规则

图编辑器必须把“用户点了哪里、引用了哪张参考图”明确展示出来，不能只在画布上画一个点。

- `local_modify`、`reference_element_transfer`、`remove_inpaint`、`color_reference_correction` 只是后台编译提示词的“改图意图”，不要做成四个大功能入口。
- 用户主路径固定为：主图 -> 标注/蒙版 -> 参考图 -> 底部一句话说明目标 -> 提交。
- 主图、标注清单、参考图、改图目标和输出设置必须属于同一个编辑器画布；画布需要整体缩放，不要拆成页面左右两块普通表单。
- 改图指令固定放在画布下方，符合“先看图、再圈选、最后描述”的操作顺序，不允许放到主图上方抢占操作空间。
- 参考图默认折叠；当意图需要参考图或已经上传参考图时，参考图面板自动展开。
- 输出设置只能作为改图指令区里的小按钮/折叠项出现，不能作为常驻大面板占用画布空间。
- 点选、矩形、圆形、手绘都会生成一条标注记录，显示在画布下方“@ 标注区域”清单。
- 标注统一生成可引用名称：`@标注1`、`@标注2`。
- 参考图统一生成可引用名称：`#参考图1`、`#参考图2`。
- 用户在编辑指令里输入 `@` 必须弹出标注清单，输入 `#` 必须弹出参考图清单。
- 提交给后端的 `selectionHints` 必须包含 `mention` 和 `geometryText`。后端会基于这些标注自动生成一张红色编号“标注定位图”，作为额外输入图传给模型，避免只靠坐标文字定位。
- 红色编号定位图只用于让模型理解位置，不是结果图的一部分；蒙版仍然是唯一硬限制。
- 非强依赖参考图的模式只提交用户在指令中显式引用的参考图，避免无关参考图干扰模型。

## 不要在业务方项目里改的内容

- 不要复制后改 `editSkill` 枚举。
- 不要私自改 `selectionHints` 结构。
- 不要在组件里直接调用 OpenAI。
- 不要把多个蒙版作为多个字段传给后端。第一版只允许一个最终 `maskUrl`。

## 修改规则

任何交互协议变更必须同时更新：

- `model.ts`
- `docs/api/examples/image-edit-internal-handoff.md`
- `docs/standards/error-catalog.md`（如涉及错误）
- 测评端真实任务回归记录
