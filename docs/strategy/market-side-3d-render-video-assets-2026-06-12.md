# 市场端 3D 渲染视频资产记录（2026-06-12）

## 结论

3D 渲染视频和 KIE/Vidu 大模型视频是两条独立能力路线：

- 大模型视频：产品图组 -> VL/LLM 脚本与分镜 -> 关键帧/首尾帧 -> KIE/Vidu 分段视频 -> 可选合成。
- 3D 渲染视频：3D 模型 -> 贴图槽/UV 验证 -> 预设场景/灯光/相机路径 -> Three.js 或 Blender 渲染 -> OSS 视频。

当前只开放 `POST /api/business/product-3d-render-video/preview` 方案预览，不触发服务端渲染，不返回 OSS 视频。测评端已接入客户端 Three.js 预览和浏览器本地 MP4 录制（不支持 MP4 时明确回退 WebM），可用 GLB/UV 验证贴图是否落到正确材质槽，并导出一个本地可预览视频；接口仍只确认“模型是否可用、UV 是否存在、贴图槽和镜头/场景参数是否清晰”，不能代表已经完成服务端视频输出。

2026-06-12 追加验收口径：

- 页面不能只有一个上传位。模型有多个材质槽时，交互必须允许“一个贴图点绑定一张图”，即 `textureSlots[] = [{ materialSlot, imageUrl, label }]`。
- `textureImageUrl/textureImageUrls` 只保留为兼容字段；新交互和后续渲染 worker 以 `textureSlots` 为主。
- 当前测评端已接入客户端 Three.js 预览：读取 `public/models/product-3d/1660.glb`、`public/models/product-3d/2551.glb`，并按材质名把用户贴图应用到真实模型表面。
- 所见即所得预览在客户端完成：Three.js 读取 GLB、材质槽、UV 和用户贴图，实时展示贴图位置、比例和方向；用户可拖拽旋转检查。
- 测评端先补本地 MP4 导出：用浏览器 `canvas.captureStream + MediaRecorder` 录制当前 Three.js 画面，优先生成可预览/下载的 MP4 视频样片；浏览器不支持 MP4 时明确回退 WebM；这不是服务端 MP4 worker，也不回填 OSS。
- 服务端只负责可复用渲染：异步 worker 加载同一套模型/贴图/相机/灯光配置，导出 MP4、封面帧和 manifest，并统一回填 OSS。
- 扩容判断：客户端预览主要消耗浏览器；批量导出/高质量视频会消耗服务端渲染 worker，应独立建 executor 池，不能混到 KIE/Vidu 视频队列里。

## 已检查模型

### `cup_1660`

- 来源压缩包：`3D-1660.zip`
- 推荐模型文件：`1660.glb`
- 备选：`1660.gltf`
- 生成器：Blender I/O v3.6.27，glTF 2.0
- 场景：1
- 节点：1
- Mesh：1
- 材质：7
- 贴图：2
- 图片：1
- 动画：0
- 相机：0
- UV：全部 primitive 均有 `TEXCOORD_0`
- 推荐首版贴图槽：`front`
- 材质槽：`front`、`mouth`、`cover`、`bottom`、`handshank`、`else`、`else1`

判断：适合做首版杯子 360 环绕/慢推镜头。没有内置相机和动画，渲染服务必须注入相机轨道、灯光和场景。

### `backpack_2551`

- 来源压缩包：`3D-2551.zip`
- 推荐模型文件：`2551.glb`
- 备选：`2551.gltf`
- 生成器：Blender I/O v3.6.27，glTF 2.0
- 场景：1
- 节点：1
- Mesh：1
- 材质：19
- 贴图：19
- 图片：10
- 动画：0
- 相机：0
- UV：全部 primitive 均有 `TEXCOORD_0`
- 推荐首版贴图槽：`front`
- 材质槽：`front`、`bottom`、`back`、`top`、`left`、`right`、`sideleft`、`sideright`、`qitaDZ`、`qitaBD`、`zipper`、`zipper02`、`zipperB`、`qitaSL`、`stitch`、`qitaWGBB`、`qitaWG`、`qitaWG001`、`inside`

判断：适合做背包正面贴图、细节扫过和慢推镜头。材质槽较多，建议先从 `front` 验证贴图方向和比例，再逐步扩展多槽贴图模板。

## 首版渲染方案

### 交互原则

- 用户不应该通过文字描述“想怎么生成视频”来驱动这条能力；这条路线不是大模型视频。
- 用户应该先选受控模型，再选模型固定贴图区域，再给对应贴图点上传贴图，最后选镜头和场景预设。
- `materialSlot` 必须映射模型里的真实材质槽 / UV 区域。前端可以显示中文名称，但提交给后端的仍是固定槽位值。
- 在服务端渲染 worker 接入前，测评端只能说“3D 预览 / 贴图预览 / 方案预览”，不能说“生成视频成功”。
- 真实渲染接入后，输出仍要走统一异步任务：`runId`、状态轮询、OSS 视频、封面帧和 manifest。

### 场景预设

| 预设 | 用途 |
| --- | --- |
| `clean_studio` | 干净摄影棚，默认展示场景。 |
| `marketplace_white` | 电商白底，适合上架动效。 |
| `premium_dark` | 深色质感棚，适合社媒短动效。 |

### 镜头预设

| 预设 | 用途 |
| --- | --- |
| `orbit_360` | 360 环绕，展示轮廓和贴图。 |
| `slow_push_in` | 慢速推进，适合商品主视觉动效。 |
| `detail_sweep` | 细节扫过，适合材质和印花展示。 |

## 待办

1. 把试点 GLB 放入受控模型目录，建立 `modelKey -> assetPath -> materialSlots` 的配置。（测评端已归档到 `podi-eval-web/public/models/product-3d/`）
2. 接入 Three.js 预览，读取真实 GLB/UV，先验证贴图方向、UV 覆盖、模型缩放和相机 framing。（已完成客户端 MVP）
3. 建立按材质槽绑定贴图的配置结构：`modelKey + textureSlots + cameraPreset + scenePreset + durationSeconds + aspectRatio`。（已进入接口和测评端主交互）
4. 建立渲染 worker：Three.js headless 录制或 Blender CLI 渲染二选一；输出 MP4、首帧 PNG 和 manifest。（测评端本地 MP4 仅用于快速验收镜头和贴图，不替代该 worker）
5. 接入统一异步业务 run：`POST /api/business/product-3d-render-video/runs` -> `runId` -> `/api/business/runs/get`。
6. 建立验收样例：1660 杯子 6 秒环绕、2551 背包 5 秒细节扫过、白底/棚拍两种场景。
