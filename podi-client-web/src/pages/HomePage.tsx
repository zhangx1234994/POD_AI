import {
  ArrowRight,
  ShoppingBag,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useApp, useSelectedAssets } from "../hooks/useAppState";
import { cupProducts } from "../data/cup-products";
import { inspirationWorks } from "../data/mock-data";

const categoryTiles = [
  { label: "手柄杯", image: "/demo/market/image2-tumbler-product.webp", tag: "热门", desc: "通勤、礼物、活动款" },
  { label: "保温杯", image: "/demo/market/product-tumbler-blue-botanical.png", tag: "通勤", desc: "冬季和户外场景" },
  { label: "运动水壶", image: "/demo/market/product-tumbler-blue-botanical.png", tag: "户外", desc: "社团、运动队、露营" },
  { label: "冰霸杯", image: "/demo/market/product-can-cooler-dark-botanical.png", tag: "日常", desc: "大容量饮品和礼品" },
  { label: "杯套配件", image: "/demo/market/product-can-cooler-dark-botanical.png", tag: "套装", desc: "组合售卖和增购" },
];

const productPreviewImages = [
  "/demo/market/image2-tumbler-product.webp",
  "/demo/market/product-tumbler-blue-botanical.png",
  "/demo/market/product-can-cooler-dark-botanical.png",
  "/demo/market/image2-tumbler-product.webp",
];

const expressionStories = [
  {
    kicker: "给孩子和家人",
    title: "把一张画，做成只属于他的礼物",
    desc: "保留手绘的稚拙，再把颜色、构图和杯型整理到适合生产。",
    image: "/brand/generated/family-expression.jpg",
  },
  {
    kicker: "给一座城市",
    title: "把在地记忆，做成游客带得走的作品",
    desc: "从建筑、纹样和故事里提炼风格，不再是换个 Logo 的纪念品。",
    image: "/brand/generated/city-expression.jpg",
  },
  {
    kicker: "给自己的品牌",
    title: "把品牌气质，做成真正会被使用的伴手礼",
    desc: "让配色、图案、材质和包装服务同一个表达。",
    image: "/brand/generated/business-expression.jpg",
  },
];

export default function HomePage() {
  const { navigate, state } = useApp();
  const selectedAssets = useSelectedAssets(state);
  const readyProducts = cupProducts.filter((p) => p.status === "ready");
  const allSurfaces = cupProducts.flatMap((p) => p.sizes.flatMap((s) => s.surfaces));
  const readySurfaces = allSurfaces.filter((surface) => surface.width && surface.height);
  const hotProducts = readyProducts.slice(0, 8);

  return (
    <main className="market-home">
      <section className="market-hero brand-home-hero">
        <img
          className="brand-home-hero-image"
          src="/brand/generated/hero-expression.jpg"
          alt="三件使用不同个人图案定制的杯子"
        />
        <div className="market-hero-copy">
          <p className="eyebrow">AI创品 · 有品，必不同</p>
          <h1>
            <span>让你的个性</span>
            成为别人复制不了的产品
          </h1>
          <p>
            不套模板，不做同款。把你的故事、审美和态度交给 AI，做成真正能拿在手里的作品。
          </p>
          <div className="hero-persona-line">敢表达 · 不跟款 · 一件也能做</div>
          <div className="market-hero-actions">
            <button className="primary" onClick={() => navigate("process")}>
              <Wand2 size={18} />
              开始创作
            </button>
            <button className="secondary" onClick={() => navigate("products")}>
              <ShoppingBag size={18} />
              选择杯型
            </button>
          </div>
          <p className="hero-brand-proof">从一张图、一个故事，到一件只属于你的产品。</p>
        </div>
      </section>

      <section className="expression-story-section">
        <div className="market-section-heading">
          <div><p className="eyebrow">有品，必不同</p><h2>不是换个花色，是让产品替你发声。</h2><span>把你真正重视的东西，变成产品里看得见、拿得到的表达。</span></div>
        </div>
        <div className="expression-story-grid">
          {expressionStories.map((story) => (
            <button key={story.title} className="expression-story" onClick={() => navigate("products")}>
              <img src={story.image} alt={story.title} />
              <span><small>{story.kicker}</small><strong>{story.title}</strong><em>{story.desc}</em><i>开始设计 <ArrowRight size={14} /></i></span>
            </button>
          ))}
        </div>
      </section>

      <section className="market-section product-market">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">POD 杯子款式</p>
            <h2>选一款杯子，先做成实物。</h2>
            <span>当前先开放杯子类。选款式、选图案，生成预览后可以试做一件。</span>
          </div>
          <button className="text-action" onClick={() => navigate("products")}>
            全部商品 <ArrowRight size={14} />
          </button>
        </div>
        <div className="category-showcase">
          {categoryTiles.map((tile) => (
            <button key={tile.label} className="category-tile" onClick={() => navigate("products")}>
              <img src={tile.image} alt={tile.label} />
              <span>{tile.tag}</span>
              <strong>{tile.label}</strong>
              <small>{tile.desc}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="market-split-section">
        <div className="ai-workflow-panel">
          <p className="eyebrow">图片素材批量处理</p>
          <h2>一批图，一次处理好。</h2>
          <div className="workflow-list">
            {[
              ["01 选择处理方式", "扩图、提花纹、做裂变或连续图，需要哪个选哪个。"],
              ["02 上传多张图片", "一次处理一批，不用一张张重复操作。"],
              ["03 保存喜欢的结果", "可以直接下载，也可以放到杯子上看效果。"],
              ["04 先做一件实物", "拿到样品看效果，合适了再继续做更多。"],
            ].map(([title, desc]) => (
              <button key={title} onClick={() => navigate("process")}>
                <Sparkles size={16} />
                <strong>{title}</strong>
                <span>{desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="hot-products-panel">
          <div className="market-section-heading compact">
            <div>
              <p className="eyebrow">杯子款式</p>
              <h2>可试做杯型</h2>
            </div>
            <span>
              {readyProducts.length} 款可试做 · {readySurfaces.length}/{allSurfaces.length} 个图案位置
            </span>
          </div>
          <div className="compact-product-grid">
            {hotProducts.slice(0, 6).map((product, index) => {
              const surface = product.sizes[0]?.surfaces[0];
              return (
                <button key={product.id} onClick={() => navigate("products")}>
                  <img src={productPreviewImages[index % productPreviewImages.length]} alt={product.name} />
                  <strong>{product.name}</strong>
                  <span>
                    {product.sizes[0]?.label || "杯型"}
                    {surface?.width ? ` · 设计面 ${surface.width}×${surface.height}px` : ""}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="market-section">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">灵感广场</p>
            <h2>喜欢的设计，直接开做。</h2>
            <span>看到合适的图片或产品，可以同款处理、同款试做；公开作品会先审核。</span>
          </div>
          <button className="text-action" onClick={() => navigate("inspire")}>
            查看灵感 <ArrowRight size={14} />
          </button>
        </div>
        <div className="inspiration-market-grid">
          {inspirationWorks.slice(0, 4).map((work) => (
            <button key={work.id} onClick={() => navigate("inspire")}>
              <img src={work.image} alt={work.title} />
              <span>{work.kind}</span>
              <strong>{work.title}</strong>
              <small>{work.trend}</small>
            </button>
          ))}
        </div>
      </section>

      {selectedAssets.length > 0 && (
        <section className="recent-assets-band">
          <strong>最近素材</strong>
          <div>
            {selectedAssets.slice(0, 4).map((asset) => (
              <button key={asset.id} onClick={() => navigate("assets")}>
                <img src={asset.thumbnailUrl} alt={asset.title} />
                <span>{asset.title}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="market-final-cta">
        <img src="/brand/generated/business-expression.jpg" alt="为品牌定制的专属杯子和礼盒" />
        <div>
          <small>AI创品 · 有品，必不同</small>
          <h2>别找同款。做你的款。</h2>
          <p>从一句想法开始，让 AI 和你一起把个性做成产品。</p>
          <button className="primary" onClick={() => navigate("products")}>开始设计 <ArrowRight size={18} /></button>
        </div>
      </section>
    </main>
  );
}
