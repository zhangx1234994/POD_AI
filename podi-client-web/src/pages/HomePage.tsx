import {
  ArrowRight,
  ShoppingBag,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useApp, useSelectedAssets } from "../hooks/useAppState";
import {
  listApprovedCatalogItems,
  resolveApprovedCatalogItem,
} from "../data/catalog-product-visuals";
import { inspirationWorks } from "../data/mock-data";
import type { ApprovedCatalogItem } from "../data/catalog-product-visuals";

type FeaturedProduct = ApprovedCatalogItem & {
  tag: string;
  desc: string;
};

function featuredProduct(
  templateId: string,
  sizeLabel: string,
  tag: string,
  desc: string
): FeaturedProduct | null {
  const item = resolveApprovedCatalogItem(templateId, sizeLabel);
  return item ? { ...item, tag, desc } : null;
}

const featuredProducts = [
  featuredProduct("10395", "OneSize", "热门", "通勤、礼物、活动款"),
  featuredProduct("10385", "OneSize", "轻巧", "易拉罐杯型，适合随行"),
  featuredProduct("10376", "OneSize", "手提", "大容量，17 色可选"),
  featuredProduct("10241", "18OZ", "便携", "保温太空壶，3 色可选"),
  featuredProduct("10235", "OneSize", "冰饮", "30oz 冰霸杯，支持单件试做"),
].filter((item): item is FeaturedProduct => Boolean(item));

const expressionStories = [
  {
    product: resolveApprovedCatalogItem("10395", "OneSize"),
    kicker: "通勤随行",
    title: "把喜欢的图案，做成每天都会用的手柄杯",
    desc: "20oz 带手柄和吸管不锈钢杯",
  },
  {
    product: resolveApprovedCatalogItem("10241", "18OZ"),
    kicker: "轻便出行",
    title: "把同一套表达，适配到更轻巧的随行杯型",
    desc: "18OZ 不锈钢太空壶",
  },
  {
    product: resolveApprovedCatalogItem("10376", "OneSize"),
    kicker: "活动礼赠",
    title: "先做一件看效果，再决定是否批量制作",
    desc: "30oz 手提杯",
  },
].filter((story): story is typeof story & { product: ApprovedCatalogItem } => Boolean(story.product));

function productDisplayName(item: ApprovedCatalogItem) {
  return item.product.sizes.length > 1
    ? `${item.size.label} ${item.product.name}`
    : item.product.name;
}

export default function HomePage() {
  const { navigate, state, dispatch } = useApp();
  const selectedAssets = useSelectedAssets(state);
  const approvedCatalogItems = listApprovedCatalogItems();
  const hotProducts = approvedCatalogItems.slice(0, 6);

  const openProduct = (item: ApprovedCatalogItem) => {
    dispatch({ type: "SET_SELECTED_PRODUCT", productId: item.product.id, sizeLabel: item.size.label });
    dispatch({ type: "SET_SELECTED_SURFACE", surface: item.surface.name });
    navigate("productDesign");
  };

  return (
    <main className="market-home brand-home">
      <section className="market-hero brand-home-hero">
        <img
          className="brand-home-hero-image"
          src="/brand/generated/hero-personal-expression-v2.png"
          alt="用专属产品表达个人审美的创作者生活场景"
        />
        <div className="market-hero-copy">
          <p className="eyebrow">AI创品</p>
          <h1>有品，必不同。</h1>
          <p>不将就，不凑合。把喜欢做成你的那一件。</p>
          <div className="hero-persona-line">你的审美 · 你的表达</div>
          <div className="market-hero-actions">
            <button className="primary" onClick={() => navigate("products")}>
              <Wand2 size={18} />
              开始设计
            </button>
            <button className="secondary" onClick={() => navigate("products")}>
              <ShoppingBag size={18} />
              选择杯型
            </button>
          </div>
        </div>
      </section>

      <section className="expression-story-section">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">让产品替你表达</p>
            <h2>不是换个花色，是做出你的那一款。</h2>
            <span>从日常随行到认真送礼，让每一件都带着你的表达。</span>
          </div>
        </div>
        <div className="expression-story-grid">
          {expressionStories.map((story) => (
            <button
              key={`${story.product.product.id}-${story.product.size.label}`}
              className="expression-story"
              onClick={() => openProduct(story.product)}
            >
              <img src={story.product.renderUrl} alt={`${story.title} 商品效果图`} />
              <span>
                <small>{story.kicker}</small>
                <strong>{story.title}</strong>
                <em>{story.desc}</em>
                <i>开始设计 <ArrowRight size={14} /></i>
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="market-section product-market">
        <div className="market-section-heading">
          <div>
            <p className="eyebrow">已核验杯型</p>
            <h2>选一款真实杯型，先做一件看效果。</h2>
            <span>先看效果，再决定是否做成实物。</span>
          </div>
          <button className="text-action" onClick={() => navigate("products")}>
            全部商品 <ArrowRight size={14} />
          </button>
        </div>
        <div className="category-showcase">
          {featuredProducts.map((item) => (
            <button
              key={`${item.product.id}-${item.size.label}`}
              className="category-tile"
              onClick={() => openProduct(item)}
            >
              <img src={item.renderUrl} alt={`${productDisplayName(item)} 商品效果图`} />
              <span>{item.tag}</span>
              <strong>{productDisplayName(item)}</strong>
              <small>{item.desc}</small>
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
            <span>{approvedCatalogItems.length} 款模型与设计面已核验</span>
          </div>
          <div className="compact-product-grid">
            {hotProducts.map((item) => (
              <button
                key={`${item.product.id}-${item.size.label}`}
                onClick={() => openProduct(item)}
              >
                <img src={item.renderUrl} alt={`${productDisplayName(item)} 商品效果图`} />
                <strong>{productDisplayName(item)}</strong>
                <span>{item.size.label} · 支持单件试做</span>
              </button>
            ))}
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

      {featuredProducts[2] && (
        <section className="market-final-cta">
          <img
            src={featuredProducts[2].renderUrl}
            alt={`${productDisplayName(featuredProducts[2])} 真实商品效果图`}
          />
          <div>
            <small>AI创品</small>
            <h2>有品，必不同。</h2>
            <p>从一句想法开始，让 AI 和你一起把个性做成真实产品。</p>
            <button className="primary" onClick={() => openProduct(featuredProducts[2])}>
              开始设计 <ArrowRight size={18} />
            </button>
          </div>
        </section>
      )}
    </main>
  );
}
