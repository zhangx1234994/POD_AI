import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { cupTags, filterCupProducts } from "../data/cup-products";
import { isCatalogRenderApproved } from "../data/catalog-render-readiness";
import { getClientProductPricing } from "../api";
import type { CupProduct, ProductSize } from "../data/cup-products";

function productPrice(salePriceCents?: number | null) {
  return typeof salePriceCents === "number" && salePriceCents > 0
    ? `${Math.round(salePriceCents / 100)} 积分起`
    : "支持单件试做";
}

function productShipDate(index: number) {
  return index % 3 === 0 ? "预计 3-5 天发出" : "预计 5-7 天发出";
}

type ProductListItem = {
  product: CupProduct;
  size: ProductSize;
};

function listItemsForProducts(products: CupProduct[]): ProductListItem[] {
  return products.flatMap((product) =>
    product.sizes.map((size) => ({
      product,
      size,
    }))
  );
}

function firstReadySurface(size: ProductSize) {
  return size.surfaces.find((surface) => surface.width && surface.height);
}

function productDisplayName(product: CupProduct, size: ProductSize) {
  return product.sizes.length > 1 ? `${size.label} ${product.name}` : product.name;
}

function customerSizeLabel(size: ProductSize) {
  return size.label === "OneSize" ? "均码" : size.label;
}

function productMaterialLabel(product: CupProduct) {
  if (product.secondCraft.includes("非不锈钢")) return "陶瓷/其他";
  if (product.secondCraft.includes("不锈钢")) return "不锈钢";
  return product.category || product.secondCraft || "杯子";
}

function hasProductModel(product: CupProduct, size: ProductSize) {
  return Boolean(size.modelFile || product.modelFile);
}

function isOrderableProduct(product: CupProduct, size: ProductSize) {
  const modelFile = size.modelFile || product.modelFile;
  return hasProductModel(product, size) && Boolean(firstReadySurface(size)) && isCatalogRenderApproved(modelFile);
}

function productCatalogRenderUrl(product: CupProduct, size: ProductSize) {
  const modelFile = size.modelFile || product.modelFile;
  return modelFile ? `/models/catalog-renders/${modelFile.replace(/\.glb$/i, ".png")}` : null;
}

export default function ProductsPage() {
  const { state, dispatch, navigate } = useApp();
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [salePricesByProduct, setSalePricesByProduct] = useState<Record<string, number>>({});
  const filteredProducts = useMemo(
    () => filterCupProducts(tagFilter, searchQuery || null),
    [tagFilter, searchQuery]
  );
  const listItems = useMemo(
    () => listItemsForProducts(filteredProducts).filter(({ product, size }) => isOrderableProduct(product, size)),
    [filteredProducts]
  );
  const sameStyleWork = state.sameStyleWork?.kind === "产品作品" ? state.sameStyleWork : null;
  useEffect(() => {
    let cancelled = false;
    void getClientProductPricing()
      .then((items) => {
        if (cancelled) return;
        const prices: Record<string, number> = {};
        items.forEach((item) => {
          if (typeof item.salePriceCents === "number" && item.salePriceCents > 0) {
            prices[item.productId] = item.salePriceCents;
          }
        });
        setSalePricesByProduct(prices);
      })
      .catch(() => {
        if (!cancelled) setSalePricesByProduct({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openProduct = (product: CupProduct, size: ProductSize) => {
    const surface = firstReadySurface(size) ?? size.surfaces[0] ?? null;
    dispatch({ type: "SET_SELECTED_PRODUCT", productId: product.id, sizeLabel: size.label });
    dispatch({ type: "SET_SELECTED_SURFACE", surface: surface?.name ?? null });
    navigate("productDesign");
  };

  return (
    <main className="catalog-page">
      {sameStyleWork && (
        <section className="same-style-draft-banner product">
          <img src={sameStyleWork.image} alt={sameStyleWork.title} />
          <div>
            <small>同款产品草稿</small>
            <strong>{sameStyleWork.title}</strong>
            <p>来自 {sameStyleWork.author} 的公开产品作品。选择杯型后会进入独立试做页，素材和来源会继续保留。</p>
          </div>
          <button className="secondary" onClick={() => dispatch({ type: "SET_SAME_STYLE_WORK", work: null })}>
            清除草稿
          </button>
        </section>
      )}

      <div className="catalog-shell catalog-shell-list">
        <aside className="catalog-sidebar">
          <strong>商品分类</strong>
          <span>当前先开放杯子类，后续扩展更多 POD 商品。</span>
          <button className={!tagFilter ? "active" : ""} onClick={() => setTagFilter(null)}>
            全部商品
          </button>
          {cupTags
            .filter((tag) => tag !== "杯子")
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
                placeholder="搜索杯型 / 容量 / 标签"
              />
            </div>
          </div>

          <div className="catalog-result-line">
            <span>{listItems.length} 款可试做杯型</span>
            <button onClick={() => navigate("process")}>
              先处理图片 <ArrowRight size={14} />
            </button>
          </div>

          <div className="catalog-grid">
            {listItems.map(({ product, size }, index) => {
              const displayName = productDisplayName(product, size);
              const materialLabel = productMaterialLabel(product);
              const salePriceCents = salePricesByProduct[product.id];
              const renderUrl = productCatalogRenderUrl(product, size);
              return (
                <button key={`${product.id}-${size.label}`} className="catalog-product-card" onClick={() => openProduct(product, size)}>
                  <div className="catalog-product-visual">
                    {renderUrl ? (
                      <img className="catalog-product-photo" src={renderUrl} alt={`${displayName} 商品图`} />
                    ) : (
                      <span className="catalog-product-photo catalog-product-photo--unavailable">商品图待审核</span>
                    )}
                  </div>
                  <div className="catalog-product-body">
                    <strong>{displayName}</strong>
                    <span>{customerSizeLabel(size)} · {materialLabel} · {size.colorCodes.length} 色可选</span>
                    <div className="catalog-product-meta">
                      <b className={salePriceCents ? "" : "price-pending"}>{productPrice(salePriceCents)}</b>
                      <small>{productShipDate(index)}</small>
                    </div>
                    <em className="catalog-card-action">开始设计</em>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
