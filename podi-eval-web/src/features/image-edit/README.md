# 图编辑组件边界

这个目录是图编辑前端能力的源码边界。目标是同一套组件同时服务：

- 测评端“图编辑”工作台
- `/image-edit` 托管组件入口
- 后续内部业务方源码集成

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
- `payloadPreview`：可选，用于展示最终会提交给中台的请求预览。

当前源码组件依赖 `tdesign-react` 和 `tdesign-icons-react`。如果业务方页面不使用 TDesign，先按托管组件接入；源码交付时再提供同等交互的轻量样式适配层，不允许业务方自行改协议字段。

接口枚举必须和中台业务 API 保持一致：质量档位只使用 `auto / preview / production / premium`，输出格式只使用 `png / jpeg / webp`，尺寸字段支持预设值或符合后端约束的 `宽x高`。

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
