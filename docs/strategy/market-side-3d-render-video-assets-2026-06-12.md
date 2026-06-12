# 市场端 3D 渲染视频资产记录（2026-06-12）

## 结论

3D 渲染视频和 KIE/Vidu 大模型视频是两条独立能力路线：

- 大模型视频：产品图组 -> VL/LLM 脚本与分镜 -> 关键帧/首尾帧 -> KIE/Vidu 分段视频 -> 可选合成。
- 3D 渲染视频：3D 模型 -> 贴图槽/UV 验证 -> 预设场景/灯光/相机路径 -> Three.js 或 Blender 渲染 -> OSS 视频。

当前只开放 `POST /api/business/product-3d-render-video/preview` 方案预览，不触发真实渲染，不返回 MP4。该预览只确认“模型是否可用、UV 是否存在、贴图应该落在哪个材质槽、镜头/场景参数是否清晰”，不能代表已经完成贴图重合预览或视频输出。

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

判断：适合做背包正面贴图、细节扫过和慢推镜头。材质槽较多，首版不要开放复杂多面贴图，先固定 `front` 验证贴图方向和比例。

## 首版渲染方案

### 交互原则

- 用户不应该通过文字描述“想怎么生成视频”来驱动这条能力；这条路线不是大模型视频。
- 用户应该先选受控模型，再选模型固定贴图区域，再上传贴图，最后选镜头和场景预设。
- `materialSlot` 必须映射模型里的真实材质槽 / UV 区域。前端可以显示中文名称，但提交给后端的仍是固定槽位值。
- 在 Three.js 画布接入前，测评端只能说“方案预览”，不能说“生成视频”或“贴图效果已验证”。
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

1. 把试点 GLB 放入受控模型目录，建立 `modelKey -> assetPath -> materialSlots` 的配置。
2. 在测评端加入 Three.js 预览，先验证贴图方向、UV 覆盖、模型缩放和相机 framing。
3. 建立渲染 worker：Three.js headless 录制或 Blender CLI 渲染二选一；输出 MP4、首帧 PNG 和 manifest。
4. 接入统一异步业务 run：`POST /api/business/product-3d-render-video/runs` -> `runId` -> `/api/business/runs/get`。
5. 建立验收样例：1660 杯子 6 秒环绕、2551 背包 5 秒细节扫过、白底/棚拍两种场景。
