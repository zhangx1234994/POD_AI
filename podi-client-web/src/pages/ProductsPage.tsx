import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  Heart,
  Search,
  ShieldCheck,
  Sparkles,
  Ticket,
  Truck,
  Wand2,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { mapClientProductionOrder } from "../hooks/useAppState";
import { createClientProductionOrder } from "../api";
import { cupProducts, cupTags, filterCupProducts } from "../data/cup-products";
import type { CupProduct } from "../data/cup-products";

const priceBase = [19.8, 22.6, 26.8, 29.9, 32.8, 36.6, 42.8, 49.9];
const productTextures = [
  "/demo/market/pattern-vintage-floral.webp",
  "/demo/market/pattern-garden.webp",
  "/demo/market/pattern-dense-floral.webp",
  "/demo/market/pattern-forest.webp",
  "/demo/market/pattern-dark-botanical.webp",
  "/demo/market/pattern-bloom.webp",
  "/demo/market/pattern-night-flower.webp",
  "/demo/market/pattern-dino.webp",
];
const productHeroImage = "/demo/market/image2-tumbler-product.webp";
const productPhotos = [
  productHeroImage,
  "/demo/market/product-mug-coral-navy.png",
  "/demo/market/product-tumbler-blue-botanical.png",
  "/demo/market/product-can-cooler-dark-botanical.png",
];

function productPrice(product: CupProduct, index: number) {
  const seed = Number(product.id.slice(-2)) || index;
  return `¥${(priceBase[index % priceBase.length] + (seed % 7)).toFixed(2)}起`;
}

function productShipDate(index: number) {
  return index % 3 === 0 ? "预计 3-5 天发出" : "预计 5-7 天发出";
}

function firstReadySurface(product: CupProduct) {
  return product.sizes.flatMap((size) => size.surfaces).find((surface) => surface.width && surface.height);
}

const availableCupProducts = cupProducts.filter((product) => product.status === "ready");
const availableCupTags = Array.from(new Set(availableCupProducts.flatMap((product) => product.tags))).sort();

export default function ProductsPage() {
  const { state, dispatch, navigate } = useApp();
  const [catalogMode, setCatalogMode] = useState<"list" | "design">(
    state.sameStyleWork?.kind === "产品作品" ? "design" : "list"
  );
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProductId, setSelectedProductId] = useState(availableCupProducts[0]?.id ?? "");
  const [selectedAssetId, setSelectedAssetId] = useState(state.assets[0]?.id ?? "");
  const [previewGenerated, setPreviewGenerated] = useState(false);
  const [notice, setNotice] = useState("");
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [shipping, setShipping] = useState({
    recipientName: "",
    phoneNumber: "",
    country: "CN",
    state: "",
    city: "",
    district: "",
    address: "",
    postalCode: "",
    email: "",
  });

  const filteredProducts = useMemo(
    () => filterCupProducts(tagFilter, searchQuery || null).filter((product) => product.status === "ready"),
    [tagFilter, searchQuery]
  );
  const selectedProduct = availableCupProducts.find((product) => product.id === selectedProductId) ?? availableCupProducts[0];
  const selectedProductIndex = Math.max(
    0,
    availableCupProducts.findIndex((product) => product.id === selectedProduct?.id)
  );
  const selectedProductPhoto = productPhotos[selectedProductIndex % productPhotos.length];
  const selectedAsset = state.assets.find((asset) => asset.id === selectedAssetId) ?? state.assets[0];
  const sameStyleWork = state.sameStyleWork?.kind === "产品作品" ? state.sameStyleWork : null;
  const selectedSurface = selectedProduct ? firstReadySurface(selectedProduct) ?? selectedProduct.sizes[0]?.surfaces[0] : null;
  const readyCount = availableCupProducts.length;
  const surfaceCount = availableCupProducts.flatMap((product) => product.sizes.flatMap((size) => size.surfaces)).length;
  const readySurfaceCount = availableCupProducts
    .flatMap((product) => product.sizes.flatMap((size) => size.surfaces))
    .filter((surface) => surface.width && surface.height).length;
  const supplierReady = selectedProduct?.id === "10167" && selectedProduct.sizes[0]?.label === "OneSize";
  const supplierReadyCount = availableCupProducts.filter(
    (product) => product.id === "10167" && product.sizes.some((size) => size.label === "OneSize")
  ).length;

  const showNotice = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice(""), 2600);
  };

  const selectProduct = (product: CupProduct, mode: "stay" | "open" = "stay") => {
    setSelectedProductId(product.id);
    setPreviewGenerated(false);
    dispatch({ type: "SET_SELECTED_PRODUCT", productId: product.id });
    if (mode === "open") {
      setCatalogMode("design");
      window.setTimeout(() => window.scrollTo({ top: 0, behavior: "smooth" }), 0);
    }
  };

  const generatePreview = () => {
    if (!selectedAsset) {
      showNotice("请先选择一张素材");
      return;
    }
    if (!selectedSurface?.width || !selectedSurface.height) {
      showNotice("该杯型设计面尺寸待补充，暂不能生成生产预览");
      return;
    }
    setPreviewGenerated(true);
    showNotice("已生成页面预览。提交订单时，中台会另行生成并预检真实生产文件。");
  };

  const submitSample = async () => {
    if (!selectedProduct || !selectedAsset || !selectedSurface?.width || !selectedSurface.height) return;
    if (!supplierReady) {
      showNotice("该杯型尚未完成蜂鸟参数验收，暂不能创建真实生产订单。");
      return;
    }
    const required = [shipping.recipientName, shipping.phoneNumber, shipping.state, shipping.city, shipping.address, shipping.postalCode];
    if (required.some((value) => !value.trim())) {
      showNotice("请补齐收货人、电话、省市、详细地址和邮编。");
      return;
    }
    setOrderSubmitting(true);
    try {
      const order = await createClientProductionOrder({
        clientRequestId: `client-${crypto.randomUUID()}`,
        shippingAddress: {
          recipientName: shipping.recipientName.trim(),
          phoneNumber: shipping.phoneNumber.trim(),
          country: shipping.country.trim() || "CN",
          state: shipping.state.trim(),
          city: shipping.city.trim(),
          district: shipping.district.trim() || undefined,
          address: shipping.address.trim(),
          postalCode: shipping.postalCode.trim(),
          email: shipping.email.trim() || undefined,
        },
        items: [{
          productName: selectedProduct.name,
          templateNo: selectedProduct.id,
          bodyCode: selectedProduct.bodyCode,
          sizeCode: selectedProduct.sizes[0]?.label || "OneSize",
          colorCode: "white",
          firstCraft: "17",
          secondCraft: "2",
          viewId: "1",
          surfaceName: selectedSurface.name,
          targetWidth: selectedSurface.width,
          targetHeight: selectedSurface.height,
          targetDpi: selectedSurface.dpi || 150,
          quantity: 1,
          sourceAssetUrl: selectedAsset.url,
          compositionMode: "cover",
          tiledReviewConfirmed: false,
        }],
      });
      dispatch({ type: "ADD_ORDER", order: mapClientProductionOrder(order) });
      showNotice("真实生产订单已创建并完成生产文件预检，等待支付接入。");
      window.setTimeout(() => navigate("orders"), 500);
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "创建生产订单失败");
    } finally {
      setOrderSubmitting(false);
    }
  };

  return (
    <main className="catalog-page">
      {sameStyleWork && (
        <section className="same-style-draft-banner product">
          <img src={sameStyleWork.image} alt={sameStyleWork.title} />
          <div>
            <small>同款产品草稿</small>
            <strong>{sameStyleWork.title}</strong>
            <p>来自 {sameStyleWork.author} 的公开产品作品。你可以换素材、换杯型或直接生成自己的产品预览；公开来源会用于后续站内抵扣。</p>
          </div>
          <button className="secondary" onClick={() => dispatch({ type: "SET_SAME_STYLE_WORK", work: null })}>
            清除草稿
          </button>
        </section>
      )}

      {catalogMode === "list" && (
        <>
          <section className="catalog-campaign-row" aria-label="平台活动">
            {[
              ["图片批处理", "批量洗图后直接套版", "/demo/market/podi-ai-workflow.webp"],
              ["杯子货盘", "0 库存 · 1 件起做", "/demo/market/product-tumbler-blue-botanical.png"],
              ["产品券试做", "先拿样品再批量", "/demo/market/product-mug-coral-navy.png"],
            ].map(([title, desc, image]) => (
              <button key={title} onClick={() => (title === "图片批处理" ? navigate("process") : setCatalogMode("list"))}>
                <img src={image} alt={title} />
                <span>{title}</span>
                <strong>{desc}</strong>
              </button>
            ))}
          </section>

          <section className="catalog-summary">
            <div>
              <p className="eyebrow">杯子商品</p>
              <h1>选一款杯子，做成实物。</h1>
              <p>商品款式来自固定供应链模板。选杯型和图片后，系统按设计面生成预览，再进入试做或批量制作。</p>
            </div>
            <div className="catalog-summary-stats">
              <article>
                <strong>{readyCount}</strong>
                <span>可设计杯型</span>
              </article>
              <article>
                <strong>{supplierReadyCount}</strong>
                <span>已开放试做</span>
              </article>
              <article>
                <strong>
                  {readySurfaceCount}/{surfaceCount}
                </strong>
                <span>设计面</span>
              </article>
            </div>
            <img className="catalog-summary-photo" src={selectedProductPhoto} alt="AI 生成的杯子商品样张" />
          </section>
        </>
      )}

      {notice && (
        <div className="catalog-notice" role="status">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      {catalogMode === "list" ? (
        <div className="catalog-shell catalog-shell-list">
          <aside className="catalog-sidebar">
            <strong>商品分类</strong>
            <span>当前先开放杯子类，后续扩展更多 POD 商品。</span>
            <button className={!tagFilter ? "active" : ""} onClick={() => setTagFilter(null)}>
              全部商品
            </button>
            {cupTags
              .filter((tag) => tag !== "杯子" && availableCupTags.includes(tag))
              .map((tag) => (
                <button
                  key={tag}
                  className={tagFilter === tag ? "active" : ""}
                  onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
                >
                  {tag}
                </button>
              ))}
          </aside>

          <section className="catalog-main">
            <div className="catalog-toolbar">
              <div className="catalog-search">
                <Search size={16} />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="搜索杯型或用途"
                />
              </div>
              <div className="catalog-filters">
                <button>可试做</button>
                <button>价格</button>
                <button>发货时间</button>
                <button>综合排序</button>
              </div>
            </div>

            <div className="catalog-result-line">
              <span>已找到 {filteredProducts.length} 款可做杯型</span>
              <button onClick={() => navigate("process")}>
                先处理图片 <ArrowRight size={14} />
              </button>
            </div>

            <div className="catalog-grid">
              {filteredProducts.map((product, index) => {
                const surface = firstReadySurface(product) ?? product.sizes[0]?.surfaces[0];
                const active = product.id === selectedProductId;
                const texture = productTextures[index % productTextures.length];
                const productPhoto = productPhotos[index % productPhotos.length];
                return (
                  <button
                    key={product.id}
                    className={`catalog-product-card ${active ? "active" : ""}`}
                    onClick={() => selectProduct(product, "open")}
                  >
                    <div className="catalog-product-visual">
                      <img className="catalog-product-photo" src={productPhoto} alt={product.name} />
                      <img className="catalog-card-swatch" src={texture} alt={`${product.name} 图案素材`} />
                      {surface?.width && (
                        <div className="design-area-label">
                          <strong>设计面尺寸</strong>
                          <span>
                            {surface.width}×{surface.height}px
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="catalog-product-body">
                      <strong>{product.name}</strong>
                      <span>支持上传图片定制</span>
                      <div className="catalog-product-meta">
                        <b>{productPrice(product, index)}</b>
                        <small>{productShipDate(index)}</small>
                      </div>
                      <div className="catalog-card-tags">
                        {product.tags.slice(1, 3).map((tag) => (
                          <span key={tag}>{tag}</span>
                        ))}
                      </div>
                      <em className="catalog-card-action">{product.id === "10167" ? "进入试做" : "开始设计"}</em>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      ) : (
        <section className="product-operation-page">
          <button className="product-back-link" onClick={() => setCatalogMode("list")}>
            <ArrowLeft size={16} />
            返回全部商品
          </button>

          <div className="product-operation-hero">
            <div>
              <p className="eyebrow">商品试做</p>
              <h1>{selectedProduct?.name ?? "选择一款杯子"}</h1>
              <p>先选素材查看页面预览。提交时会生成符合规格的生产文件并完成中台预检。</p>
            </div>
            <div className="designer-facts">
              <article>
                <ShieldCheck size={15} />
                <span>制作方式</span>
                <strong>按图定制</strong>
              </article>
              <article>
                <Clock size={15} />
                <span>发货</span>
                <strong>5-7 天</strong>
              </article>
              <article>
                <Truck size={15} />
                <span>履约</span>
                <strong>供应链代发</strong>
              </article>
            </div>
          </div>

          <div className="product-operation-shell">
            <section className="product-preview-panel">
              <div className="designer-preview">
                {previewGenerated ? (
                  <img className="designer-product-photo" src={selectedProductPhoto} alt="页面杯子预览" />
                ) : (
                  <div className="designer-stage-preview">
                    <img className="designer-product-photo pending" src={selectedProductPhoto} alt="待生成杯子预览" />
                    {selectedAsset && (
                      <div className="designer-material-swatch">
                        <img src={selectedAsset.thumbnailUrl} alt={selectedAsset.title} />
                        <span>待套版素材</span>
                      </div>
                    )}
                  </div>
                )}
                <span>{previewGenerated ? "页面预览已生成" : "选择素材后查看页面预览"}</span>
              </div>

              <div className="surface-summary">
                <strong>当前设计面</strong>
                <span>面：{selectedSurface?.label ?? "待选择"}</span>
                <span>
                  尺寸：
                  {selectedSurface?.width ? `${selectedSurface.width}×${selectedSurface.height}px` : "待补充"}
                </span>
                <span>DPI：{selectedSurface?.dpi ?? "待补充"}</span>
              </div>
            </section>

            <aside className="product-operation-panel">
              <div className="asset-picker">
                <div className="asset-picker-title">
                  <strong>选择素材</strong>
                  <button onClick={() => navigate("assets")}>打开素材库</button>
                </div>
                <div className="asset-picker-grid">
                  {state.assets.slice(0, 6).map((asset) => (
                    <button
                      key={asset.id}
                      className={selectedAssetId === asset.id ? "active" : ""}
                      onClick={() => {
                        setSelectedAssetId(asset.id);
                        setPreviewGenerated(false);
                      }}
                    >
                      <img src={asset.thumbnailUrl} alt={asset.title} />
                      <span>{asset.title}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="designer-actions">
                <button className="primary full" onClick={generatePreview}>
                  <Eye size={16} />
                  {previewGenerated ? "重新生成页面预览" : "生成页面预览"}
                </button>
                {previewGenerated && (
                  <>
                    <div className="product-order-form">
                      <strong>收货信息</strong>
                      <p>内测阶段会创建真实待支付订单，并生成可追溯的生产文件；不会自动推送供应链。</p>
                      <div className="product-order-form-grid">
                        {[
                          ["recipientName", "收货人"],
                          ["phoneNumber", "联系电话"],
                          ["state", "省/州"],
                          ["city", "城市"],
                          ["district", "区/县（可选）"],
                          ["postalCode", "邮编"],
                        ].map(([field, label]) => (
                          <label key={field}>
                            <span>{label}</span>
                            <input
                              value={shipping[field as keyof typeof shipping]}
                              onChange={(event) => setShipping((current) => ({ ...current, [field]: event.target.value }))}
                            />
                          </label>
                        ))}
                      </div>
                      <label>
                        <span>详细地址</span>
                        <input value={shipping.address} onChange={(event) => setShipping((current) => ({ ...current, address: event.target.value }))} />
                      </label>
                    </div>
                    <button className="secondary full" onClick={submitSample} disabled={orderSubmitting}>
                      <Ticket size={16} />
                      {orderSubmitting ? "正在创建真实订单" : supplierReady ? "创建待支付订单" : "该款暂不可下单"}
                      {state.productCouponCount > 0 && <small>支付接入后可使用 {state.productCouponCount} 张产品券</small>}
                    </button>
                    <button className="secondary full" onClick={() => showNotice("样例图已准备下载")}>
                      <Download size={16} />
                      下载预览图
                    </button>
                  </>
                )}
              </div>
            </aside>
          </div>
        </section>
      )}

      <section className="catalog-bottom-guide">
        <article>
          <Wand2 size={20} />
          <strong>只处理图片也可以</strong>
          <span>批量图处理结果会进入素材库，可直接下载，不强制做产品。</span>
        </article>
        <article>
          <Sparkles size={20} />
          <strong>素材可复用</strong>
          <span>同一张素材可以套到多个杯型，也可以继续做裂变和单图精修。</span>
        </article>
        <article>
          <Heart size={20} />
          <strong>公开前审核</strong>
          <span>私用素材不审核，公开到灵感广场后再进入审核和分成规则。</span>
        </article>
      </section>
    </main>
  );
}
