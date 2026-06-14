# 市场端 3D 渲染视频资产记录（2026-06-12）

## 结论

3D 渲染视频和 KIE/Vidu 大模型视频是两条独立能力路线：

- 大模型视频：产品图组 -> VL/LLM 脚本与分镜 -> 关键帧/首尾帧 -> KIE/Vidu 分段视频 -> 可选合成。
- 3D 渲染视频：3D 模型 -> 贴图槽/UV 验证 -> 预设场景/灯光/镜头运动 -> Three.js 或 Blender 渲染 -> OSS 视频。

当前开放 `GET /api/business/product-3d-render-video/catalog` 能力目录、`POST /api/business/product-3d-render-video/preview` 方案预览、`POST /api/business/product-3d-render-video/runs` 服务端渲染任务入口。`/catalog` 返回模型、材质槽、场景资产、镜头和远近档位；`/preview` 不触发服务端渲染，不返回 OSS 视频；`/runs` 走统一 `BusinessRun`，当前接入 `lightweight_scene_renderer_v1` 生成 MP4、封面帧和 manifest 并回填 OSS。测评端已接入客户端 Three.js 预览和浏览器本地 MP4/WebM 录制，可用 GLB/UV 验证贴图是否落到正确材质槽；服务端轻量渲染可作为接口闭环和交付样片，高保真 Blender/headless Three.js worker 后续替换。

2026-06-12 追加验收口径：

- 页面不能只有一个上传位。模型有多个材质槽时，交互必须允许“一个贴图点绑定一张图”，即 `textureSlots[] = [{ materialSlot, imageUrl, label }]`。
- `textureImageUrl/textureImageUrls` 只保留为兼容字段；新交互和后续渲染 worker 以 `textureSlots` 为主。
- 当前测评端已接入客户端 Three.js 预览：读取 `public/models/product-3d/1660.glb`、`public/models/product-3d/2551.glb`，并按材质名把用户贴图应用到真实模型表面。
- 所见即所得预览在客户端完成：Three.js 读取 GLB、材质槽、UV 和用户贴图，实时展示贴图位置、比例和方向；用户可拖拽旋转检查。
- 普通用户不应被要求理解或绘制镜头路径。默认交互必须是“选择推荐镜头模板 -> 播放镜头确认 -> 导出视频”；自定义只作为明确入口，用户在真实 3D 画面中拖动视角并保存开始镜头、结束镜头。
- 运动路径预览必须叠加在真实模型画面上，直接表达“商品固定、相机运动”的概念，显示起点、目标点、终点和安全取景区；禁止用右侧小地图作为主要轨迹交互，因为它无法让用户判断当前模型取景是否合理。
- 测评端保留本地 MP4/WebM 导出：用浏览器 `canvas.captureStream + MediaRecorder` 录制当前 Three.js 画面，作为快速预览，不作为接口交付。
- 服务端负责可复用渲染：当前轻量渲染器加载同一套模型/贴图/相机/灯光配置的业务参数，导出 MP4、封面帧和 manifest，并统一回填 OSS；后续替换为 Blender/headless Three.js 高保真 worker。
- 镜头必须有完整入画门禁：前端 Three.js 预览按模型包围盒、画幅和镜头远近计算安全距离；服务端 `lightweight_scene_renderer_v1` 按 `fit_product_safe_bounds` 把商品和运动路径限制在安全边界内，避免近景或路径移动导致主体裁切。
- 2026-06-13 进一步补强：杯子这类带把手结构的模型，不能只让杯身主体矩形进入安全边界，把手也必须落在拟合后的商品外框内。后端已调整 `cup_1660` 轻量绘制逻辑，并新增像素级回归：`close + detail_sweep + 极端 motionPath` 下，杯子和背包的主体/轮廓像素都必须离画布边缘保留最小安全边距。
- 扩容判断：客户端预览主要消耗浏览器；批量导出/高质量视频会消耗服务端渲染 worker，应独立建 executor 池，不能混到 KIE/Vidu 视频队列里。
- 贴图预览必须以颜色保真优先：有贴图的材质槽不应被强光照、金属度、粗糙度或“选中槽位”高亮染色；选中态只能帮助定位，不能改变贴图颜色判断。
- 如果贴图本身带底色或不透明背景，模型材质槽会显示该底色。这属于贴图内容/UV 映射问题，不应误判为渲染光照偏色；后续应补透明 PNG、自动去底色、贴图区域遮罩和 UV 区域检查能力。

2026-06-13 追加验收口径：

- 场景不能只作为 UI 文案存在。后端已建立 `SCENE_ASSET_LIBRARY`，每个 `scenePreset` 必须映射到一个可追溯场景资产包。
- `renderPlan.scene.asset` 必须包含 `assetId/assetType/assetStatus/renderFidelity/source/license/geometry/materialPolicy/highFidelityTarget`。
- `renderPlan.scene.renderElements` 与 `/runs` manifest 的 `sceneElements` 必须沉淀背景、台面、道具、层级和遮挡策略，供轻量渲染器、客户端预览和后续高保真 worker 共用。
- `/runs` 输出的 manifest 必须沉淀 `sceneAsset`，保证 OSS 视频可以追溯使用了哪个场景资产和授权策略。
- `/runs` 输出的 `renderAssetPackage` 和 manifest 必须同时沉淀 `textureApplication`，包含 `activeMaterialSlot/textureSlotCount/textureSlots/primaryTextureUrl/preserveUv`；轻量渲染器即使只用主贴图生成样片，也不能丢失其它贴图点绑定，方便后续高保真 worker 复用。
- 当前资产状态是 `mvp_procedural`：可用于流程闭环和交互验证；商用级视频仍需要替换为 Blender/headless Three.js 高保真 worker 或经过授权的外部场景资产。
- 外部资产候选只进入 `externalCandidates`，不能直接作为生产资产。`retail_shelf` 这类容易引入品牌/货架标签的场景必须额外走授权与内容风险复核。
- 2026-06-13 进一步明确：`/preview` 的 `renderWorkerReady=true` 只代表 `lightweight_scene_renderer_v1` 可执行；`highFidelityWorkerReady=false` 代表商用品质 worker 仍待替换。场景候选来源已进入 `renderPlan.scene.asset.externalCandidates` 和 `/runs` manifest，便于后续高保真资产入库。
- 2026-06-13 追加：`/catalog` 已结构化返回 `sceneAssetSources`，集中暴露 Poly Haven、ambientCG、内部/CC0 候选来源的授权口径、商用可用性、当前入库状态和入库门禁。业务执行仍只允许传 `scenePreset`，不能让业务方直接传任意第三方场景 URL。
- 2026-06-13 追加：`sceneAssetSources[].candidateAssets` 和 `scenePresets[].asset.externalCandidates` 已升级为资产级入库候选，包含 `ingestStage/assetVersion/downloadDate/fileHash/downloadRequired/workerReadiness/licenseReview/requiredValidation`。这些字段用于后续真实 HDRI/PBR/场景模型入库和 worker 验收，不代表当前渲染会远程下载第三方资产。
- 2026-06-13 追加：服务端像素级回归已覆盖轻量渲染器的场景差异。`desktop_lifestyle`、`marketplace_white`、`retail_shelf` 在同一商品/贴图/镜头下必须产生不同背景/台面/货架像素，同时商品贴图像素仍需保留安全边距，证明场景元素没有遮挡或裁切商品主体。
- 2026-06-13 追加：`retail_shelf` 不再只登记内部待核验货架，已补入 Poly Haven `wooden_display_shelves_01` 和 ambientCG `Metal037` 作为 CC0 候选。它们只进入 `candidateAssets/externalCandidates`，后续仍需下载 hash、视觉验收、浏览器/worker 导入测试和无品牌/无文字风险复核后才能晋级生产资产。
- 2026-06-13 追加：新增 staging 工具 `backend/scripts/stage_product_3d_scene_assets.py`。它从 `/catalog` 的候选资产生成受控 manifest，默认不下载大文件；可用 Poly Haven 官方 API 补充 `info/files`、作者、polycount、下载项、size 和 md5；只有显式 `--download` 才落主文件并记录 sha256，显式 `--download-includes` 才同时下载 GLTF 依赖的 `.bin` 和贴图。该工具服务资产入库，不是业务执行入口。下载后会写入 `packageValidation`，校验 GLTF 引用文件是否存在、hash 是否记录；缺依赖会标记 `failed`。

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
- 用户应该先选受控模型，再选模型固定贴图区域，再给对应贴图点上传贴图；场景、镜头远近、镜头模板、画面内轨迹调整、播放确认和导出动作都应集中在所见即所得预览棚中完成。
- 镜头运动对业务用户必须模板化。`orbit_360/hero_turntable/slow_push_in/detail_sweep` 等推荐镜头是主入口；高级调整也必须在 3D 模型画面上拖拽镜头点完成，不再用抽象小地图承载主操作。
- `materialSlot` 必须映射模型里的真实材质槽 / UV 区域。前端可以显示中文名称，但提交给后端的仍是固定槽位值。
- `/preview` 只能说“3D 预览 / 贴图预览 / 方案预览”，不能暗示已产生交付视频。
- `/runs` 已接入轻量服务端渲染，允许返回 `runId`，输出仍要走统一异步任务：状态轮询、OSS 视频、封面帧和 manifest。当前视频可作为接口闭环和交付样片，高保真画质需等 Blender/headless Three.js worker。
- 贴图颜色验收要区分两类问题：渲染器不应额外染色；但贴图图片自带底色、透明通道缺失或 UV 区域不匹配，需要按素材问题处理。

### 场景资产引入规则

- 首版测评端使用程序化场景模型，不直接下载第三方场景文件，避免授权和体积风险。
- 后续如果引入真实场景模型或 HDRI，优先选择授权清晰的 CC0 来源，例如 [Poly Haven](https://polyhaven.com/license) 和 [ambientCG](https://docs.ambientcg.com/license/)。
- 2026-06-13 复核官方授权信息：Poly Haven 官网说明其 HDRI、贴图和 3D 模型资产均按 CC0 发布，可用于商业用途；ambientCG 文档说明其材质、模型和其它资产均为 Creative Commons CC0 1.0 Universal。二者适合作为高保真 HDRI/PBR 材质候选来源，但具体下载资产仍需逐项登记 `sourceUrl/licenseUrl/assetVersion/downloadDate`。
- BlenderKit 等素材库可作为调研来源，但属于混合授权体系；每个资产入库前必须记录 license、作者、来源 URL、是否允许商用和是否需要署名。
- 外部资产不能直接进入生产目录。应先进入 `staging` 清单，经过视觉验收、性能验收、授权确认后，再映射为 `scenePreset`。
- 场景模型的职责是提升融合感，不允许遮挡贴图区域、制造虚假品牌/包装信息、引入文字、水印或可读价格标签。

### 外部候选来源

| 来源 | 当前候选用途 | 授权口径 | 入库状态 |
| --- | --- | --- | --- |
| [Poly Haven HDRI / Models](https://polyhaven.com) | 摄影棚、白底棚、桌面生活场景的环境光、柔光、桌面/办公桌/货架场景模型替换 | [CC0](https://polyhaven.com/license) | `externalCandidates`，待下载资产级记录 |
| [ambientCG Materials](https://ambientcg.com/list?type=Material) | 桌面、纸板、深色棚拍台、背景表面的 PBR 材质替换 | [CC0](https://docs.ambientcg.com/license/) | `externalCandidates`，待视觉/性能验收 |
| 内部/CC0 货架模型 | `retail_shelf` 的非品牌陈列架替换 | 待逐资产核验 | `needs_license_review`，不得直接上线 |

### 资产级候选清单

已通过公开 catalog/API 做首轮搜索，当前只登记为候选，不下载大文件进主仓库。后续入库必须补齐下载日期、文件 hash、分辨率/贴图通道、缩略图、性能测试记录和视觉验收截图。

资产级 candidate 的最小验收字段：

- `ingestStage`：`staging_candidate`、`license_review` 或 `ready_scene_asset`。
- `assetVersion/downloadDate/fileHash`：下载版本、下载日期和文件校验，未下载时必须显式写 `to_be_recorded` 或 `not_downloaded`。
- `workerReadiness`：分别记录浏览器预览、轻量服务端渲染和高保真 worker 的导入/渲染测试状态。
- `licenseReview`：记录是否需要授权复核、是否允许商业用途、授权链接。
- `requiredValidation`：至少覆盖授权、无文字/水印/品牌道具、融合不遮挡、近景安全取景、浏览器性能、服务端 worker smoke test。

| assetId | 来源 | 候选用途 | 目标场景 | 当前处理 |
| --- | --- | --- | --- | --- |
| `blocky_photo_studio` | [Poly Haven](https://polyhaven.com/a/blocky_photo_studio) | 棚拍 HDRI，替换程序化柔光棚 | `clean_studio`、`marketplace_white` | catalog `sceneAssetSources[].candidateAssets` + 场景 `externalCandidates` |
| `blue_photo_studio` | [Poly Haven](https://polyhaven.com/a/blue_photo_studio) | 室内棚拍 HDRI，增加桌面生活场景纵深 | `desktop_lifestyle` | catalog + manifest 候选 |
| `brown_photostudio_01` | [Poly Haven](https://polyhaven.com/a/brown_photostudio_01) | 暖调摄影棚 HDRI | `gift_table`、`premium_dark` | catalog 候选 |
| `metal_office_desk` | [Poly Haven](https://polyhaven.com/a/metal_office_desk) | 真实桌面/办公桌场景模型候选 | `desktop_lifestyle` | catalog + manifest 候选，待缩放/遮挡/性能验证 |
| `industrial_coffee_table` | [Poly Haven](https://polyhaven.com/a/industrial_coffee_table) | 真实桌面/礼品桌面场景模型候选，用于商品落点、接触阴影和 360/推拉镜头测试 | `desktop_lifestyle`、`gift_table` | catalog + manifest 候选，待缩放/接触阴影/遮挡/性能验证 |
| `SchoolDesk_01` | [Poly Haven](https://polyhaven.com/a/SchoolDesk_01) | 简洁桌面模型候选，用于桌面和前排陈列测试 | `desktop_lifestyle`、`retail_shelf` | catalog 候选，待授权/视觉/性能验收 |
| `wooden_display_shelves_01` | [Poly Haven](https://polyhaven.com/a/wooden_display_shelves_01) | 非品牌格架/展示架模型候选，用于货架陈列和桌面生活场景测试 | `retail_shelf`、`desktop_lifestyle` | catalog + manifest 候选，待缩放/遮挡/无文字品牌风险/性能验证 |
| `steel_frame_shelves_01` | [Poly Haven](https://polyhaven.com/a/steel_frame_shelves_01) | 钢架货架模型候选，用于更接近零售陈列的场景融合和商品尺度验证 | `retail_shelf` | catalog + manifest 候选，待缩放/遮挡/无文字品牌风险/近景安全取景/性能验证 |
| `Wood095` | [ambientCG](https://ambientcg.com/a/Wood095) | 浅色木质桌面 PBR 材质 | `desktop_lifestyle` | catalog + manifest 候选 |
| `Paper006` | [ambientCG](https://ambientcg.com/a/Paper006) | 中性纸张/背景材质 | `gift_table`、`marketplace_white` | catalog 候选 |
| `Cardboard002` | [ambientCG](https://ambientcg.com/a/Cardboard002) | 无文字礼盒/纸板材质 | `gift_table` | catalog 候选 |
| `Concrete036` | [ambientCG](https://ambientcg.com/a/Concrete036) | 深灰台面或棚拍台 PBR 材质 | `premium_dark`、`clean_studio` | catalog + manifest 候选 |
| `Fabric079` | [ambientCG](https://ambientcg.com/a/Fabric079) | 深色非反光软表面 | `premium_dark` | catalog 候选 |
| `Metal037` | [ambientCG](https://ambientcg.com/a/Metal037) | 中性金属货架/桌架 PBR 材质 | `retail_shelf`、`desktop_lifestyle` | catalog + manifest 候选，待尺度/反光/遮挡验证 |

入库必须记录 `sourceUrl/licenseUrl/authorOrProvider/assetVersion/downloadDate`。第三方大文件不进入主仓库；应放到受控资产存储或独立模型资产包，再由 `scenePreset -> assetId -> assetPath` 映射。

### 资产 staging 工具

脚本：

```bash
cd backend
python3 scripts/stage_product_3d_scene_assets.py --scene-preset retail_shelf --output-dir /tmp/podi-3d-scene-assets/retail-shelf --json
```

安全边界：

- 默认只生成 `manifest.json`，不会下载第三方大文件。
- 默认会尝试对 Poly Haven 候选调用官方 `info/files` API，记录作者、分类、标签、polycount、下载选项、size 和 md5；如网络波动或供应商 API 失败，manifest 会记录 `providerApi.status=failed`，不影响本地 catalog。
- ambientCG 当前先按 catalog 候选记录，下载/元信息补齐作为后续增强，避免供应商 API 网络波动阻断整条资产治理链路。
- 显式加 `--download` 才下载候选主文件；显式再加 `--download-includes` 才下载依赖文件，例如 GLTF 的 `.bin` 和贴图，避免误把大体积贴图包写入主仓库。
- 显式加 `--import-smoke` 后，工具会调用 `podi-eval-web` 里的 Three.js `GLTFLoader` 导入已下载的 `.gltf`，并记录 `sceneChildren/nodeCount/meshCount/materialCount/textureCount/animationCount`。该检查用于证明资产包能被前端渲染依赖解析，不替代视觉构图和服务端渲染验收。
- 生产晋级仍需满足 ready gate：授权可商用、下载 hash、Three.js GLTF 导入、无文字/水印/品牌道具、融合不遮挡、近景安全取景、浏览器性能和服务端 worker smoke test。
- 本地验证记录：`metal_office_desk` 1k GLTF 可通过 Poly Haven 官方 API 下载完整包到 `/tmp`，包含主 `.gltf`、`.bin` 和 3 张贴图，总大小约 1.6MB，manifest 记录每个文件 sha256；`packageValidation.status=passed`，GLTF 期望 4 个引用，缺失 0；`importSmoke.status=passed`，Three.js `GLTFLoader` 解析出 9 个 mesh、1 个 material、3 个 texture。该验证证明工具可拿到结构上可导入的资产包；是否晋级生产仍需视觉和 worker 渲染测试。
- 2026-06-13 新增候选验证记录：`industrial_coffee_table` 与 `steel_frame_shelves_01` 已通过 staging 工具生成 manifest-only 记录到 `/tmp/podi-3d-scene-assets/new-scene-candidates/manifest.json`，未下载第三方大文件。Poly Haven API 元信息返回正常：`industrial_coffee_table` polycount 41300、4 组下载选项，目标场景 `desktop_lifestyle/gift_table`；`steel_frame_shelves_01` polycount 4348、4 组下载选项，目标场景 `retail_shelf`。二者仍为 `staging_candidate`，晋级前必须补下载 hash、Three.js 导入、无文字/水印/品牌道具、无遮挡、近景安全取景和服务端 worker smoke。

示例：

```bash
# 只生成 manifest，适合评审候选资产
python3 scripts/stage_product_3d_scene_assets.py \
  --asset-id wooden_display_shelves_01 \
  --output-dir /tmp/podi-3d-scene-assets/wooden_display_shelves_01

# 下载主文件前必须显式打开 --download，并设置大小上限
python3 scripts/stage_product_3d_scene_assets.py \
  --asset-id metal_office_desk \
  --download \
  --download-includes \
  --import-smoke \
  --preferred-resolution 1k \
  --max-download-bytes 31457280 \
  --output-dir /tmp/podi-3d-scene-assets/metal_office_desk
```

### 场景预设

| 预设 | assetId | 当前层级 | 用途 |
| --- | --- | --- | --- |
| `clean_studio` | `podi.scene.procedural.clean_studio.v1` | `mvp_procedural` | 干净摄影棚，默认展示场景。 |
| `marketplace_white` | `podi.scene.procedural.marketplace_white.v1` | `mvp_procedural` | 电商白底，适合上架动效。 |
| `premium_dark` | `podi.scene.procedural.premium_dark.v1` | `mvp_procedural` | 深色质感棚，适合社媒短动效。 |
| `desktop_lifestyle` | `podi.scene.procedural.desktop_lifestyle.v1` | `mvp_procedural` | 桌面生活场景，适合杯子、办公用品等商品展示。 |
| `gift_table` | `podi.scene.procedural.gift_table.v1` | `mvp_procedural` | 礼品桌面场景，适合节日/礼品感素材。 |
| `retail_shelf` | `podi.scene.procedural.retail_shelf.v1` | `mvp_procedural` | 货架陈列场景，适合市场端陈列动效，不出现可读货架标签。 |

### 镜头预设

| 预设 | 用途 |
| --- | --- |
| `orbit_360` | 360 环绕，展示轮廓和贴图。 |
| `slow_push_in` | 慢速推进，适合商品主视觉动效。 |
| `detail_sweep` | 细节扫过，适合材质和印花展示。 |
| `hero_turntable` | 主视觉转台，更适合商品页首屏动效。 |
| `top_reveal` | 俯拍揭示，从顶部结构过渡到正面主体。 |
| `social_arc` | 社媒弧线，节奏更快但仍保持商品不变形。 |

## 待办

1. 把试点 GLB 放入受控模型目录，建立 `modelKey -> assetPath -> materialSlots` 的配置。（测评端已归档到 `podi-eval-web/public/models/product-3d/`）
2. 接入 Three.js 预览，读取真实 GLB/UV，先验证贴图方向、UV 覆盖、模型缩放和相机 framing。（已完成客户端 MVP）
3. 建立按材质槽绑定贴图的配置结构：`modelKey + textureSlots + cameraPreset + scenePreset + durationSeconds + aspectRatio`。（已进入接口和测评端主交互）
4. 建立渲染 worker：当前已接入 `lightweight_scene_renderer_v1`，可输出 MP4、首帧 PNG 和 manifest 并回填 OSS；下一步替换为 Three.js headless 或 Blender CLI 高保真渲染。
5. 接入统一异步业务 run worker：已完成，`POST /api/business/product-3d-render-video/runs` 返回 `runId`，通过 `/api/business/runs/get` 查询 `videoUrls/imageUrls/resultPayload.renderAssetPackage`。
6. 建立验收样例：1660 杯子 6 秒环绕、2551 背包 5 秒细节扫过、白底/棚拍两种场景。
