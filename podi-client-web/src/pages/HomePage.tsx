import {
  ArrowRight,
  BadgeCheck,
  Gift,
  Images,
  PackageCheck,
  Palette,
  ShoppingBag,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useApp, useSelectedAssets } from "../hooks/useAppState";
import { cupProducts } from "../data/cup-products";
import { inspirationWorks } from "../data/mock-data";

const categoryTiles = [
  { label: "手柄杯", image: "/demo/market/image2-tumbler-product.webp", tag: "热门", desc: "通勤、礼物、活动款" },
  { label: "马克杯", image: "/demo/market/product-mug-coral-navy.png", tag: "礼物", desc: "办公室和家庭常用" },
  { label: "保温杯", image: "/demo/market/product-tumbler-blue-botanical.png", tag: "通勤", desc: "冬季和户外场景" },
  { label: "运动水壶", image: "/demo/market/product-tumbler-blue-botanical.png", tag: "户外", desc: "社团、运动队、露营" },
  { label: "咖啡杯", image: "/demo/market/product-mug-coral-navy.png", tag: "门店", desc: "咖啡店和轻礼品" },
  { label: "杯套配件", image: "/demo/market/product-can-cooler-dark-botanical.png", tag: "套装", desc: "组合售卖和增购" },
];

const productPreviewImages = [
  "/demo/market/image2-tumbler-product.webp",
  "/demo/market/product-mug-coral-navy.png",
  "/demo/market/product-tumbler-blue-botanical.png",
  "/demo/market/product-can-cooler-dark-botanical.png",
];

const creationScenes = [
  {
    title: "只处理图片",
    desc: "批量清理、扩图、提取花纹，结果可直接下载。",
    image: "/demo/market/pattern-dark-botanical.webp",
  },
  {
    title: "先做样品",
    desc: "选一张图和一款杯子，做一件看实际效果。",
    image: "/demo/market/product-mug-coral-navy.png",
  },
  {
    title: "做活动礼品",
    desc: "同一套图案用到多款杯子，适合小批量送礼。",
    image: "/demo/market/product-can-cooler-dark-botanical.png",
  },
];

const userIntents = [
  { label: "我想批量处理图片", view: "process" as const },
  { label: "我想做一件杯子", view: "products" as const },
  { label: "我想做活动伴手礼", view: "products" as const },
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
      <section className="market-hero">
        <div className="hero-intent-row">
          {userIntents.map((intent, index) => (
            <button
              key={intent.label}
              className={index === 0 ? "active" : ""}
              onClick={() => navigate(intent.view)}
            >
              {intent.label}
            </button>
          ))}
        </div>

        <div className="market-hero-copy">
          <p className="eyebrow">AI 图片批处理 + 定制杯子</p>
          <h1>
            <span>批量处理图片</span>
            也能做成定制杯子
          </h1>
          <p>
            上传一批图，先清理、扩图、提取花纹或做裂变；喜欢的结果可以保存下载，也可以选杯型先做一件实物。
          </p>
          <div className="hero-value-line">
            <span>批量处理</span>
            <span>素材可下载</span>
            <span>1 件起做</span>
            <span>产品券试做</span>
          </div>
          <div className="market-hero-actions">
            <button className="primary" onClick={() => navigate("process")}>
              <Wand2 size={18} />
              上传图片试试
            </button>
            <button className="secondary" onClick={() => navigate("products")}>
              <ShoppingBag size={18} />
              查看可做杯型
            </button>
          </div>
        </div>

        <div className="hero-showcase" aria-label="AI 定制平台示意">
          <img className="hero-market-photo" src="/demo/market/podi-hero-products.webp" alt="AI 定制杯子和设计画布" />
          <img className="hero-pattern-card hero-pattern-card-a" src="/demo/market/pattern-garden.webp" alt="真实花纹素材" />
          <img className="hero-pattern-card hero-pattern-card-b" src="/demo/market/pattern-dark-botanical.webp" alt="真实深色花纹素材" />

          <div className="hero-proof">
            <BadgeCheck size={18} />
            <strong>先把图片处理好，再决定是否做产品</strong>
            <span>不想下单也可以只保存和下载结果图。</span>
          </div>
        </div>
      </section>

      <section className="quick-paths">
        {[
          {
            title: "批量处理图片",
            desc: "清理、扩图、提花纹、做裂变，一次处理多张图。",
            action: "上传图片",
            icon: Images,
            onClick: () => navigate("process"),
          },
          {
            title: "选杯型做样品",
            desc: "把喜欢的图片放到杯子上，先做一件看实物。",
            action: "选杯型",
            icon: Gift,
            onClick: () => navigate("products"),
          },
          {
            title: "用产品券试做",
            desc: "有券时先做样品，适合自用、送人或推广验证。",
            action: "看权益",
            icon: PackageCheck,
            onClick: () => navigate("wallet"),
          },
        ].map(({ title, desc, action, icon: Icon, onClick }) => (
          <button key={title} className="quick-path-card" onClick={onClick}>
            <Icon size={22} />
            <strong>{title}</strong>
            <span>{desc}</span>
            <em>
              {action}
              <ArrowRight size={14} />
            </em>
          </button>
        ))}
      </section>

      <section className="market-section product-market">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">AI创品杯子款式</p>
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
              ["01 选择处理方式", "清理、扩图、提花纹、做裂变，需要哪个选哪个。"],
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
                  <span>{surface?.width ? `设计尺寸 ${surface.width}×${surface.height}px` : "支持上传图片定制"}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="market-section">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">使用场景</p>
            <h2>图片怎么用，你来决定。</h2>
            <span>只处理图片、先做一件样品，或者准备一批礼品，都可以从同一张图开始。</span>
          </div>
        </div>
        <div className="scene-strip">
          {creationScenes.map((scene) => (
            <article key={scene.title}>
              <img src={scene.image} alt={scene.title} />
              <div>
                <strong>{scene.title}</strong>
                <span>{scene.desc}</span>
              </div>
            </article>
          ))}
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
        <Palette size={28} />
        <h2>先从一张图片开始。</h2>
        <p>处理图片、保存结果、选杯型试做；满意了，再考虑做更多。</p>
        <button className="primary" onClick={() => navigate("process")}>
          上传图片试试 <ArrowRight size={18} />
        </button>
      </section>
    </main>
  );
}
