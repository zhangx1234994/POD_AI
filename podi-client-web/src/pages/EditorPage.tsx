/**
 * 素材详情 — 查看、复用和进入下一步
 *
 * 素材详情只承载查看和业务流转；单图精修进入独立图片处理工具。
 */
import {
  ArrowLeft,
  Download,
  ImageIcon,
  Layers3,
  RefreshCw,
  ShoppingBag,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import PageHeader from "../components/PageHeader";
import { assetTypeLabels, visibilityLabels } from "../utils/constants";

export default function EditorPage() {
  const { navigate, state, dispatch } = useApp();
  const asset = state.assets.find((item) => state.selectedAssetIds.includes(item.id)) ?? state.assets[0];

  const handleUseForProduct = () => {
    if (asset) {
      dispatch({ type: "SELECT_ASSETS", ids: [asset.id] });
    }
    navigate("productDesign");
  };

  const handleDownload = () => {
    if (!asset?.url) return;
    window.open(asset.url, "_blank", "noopener,noreferrer");
  };

  const handleEditImage = () => {
    if (asset) {
      dispatch({ type: "SELECT_ASSETS", ids: [asset.id] });
    }
    navigate("imageEditor");
  };

  if (!asset) {
    return (
      <main className="page-shell asset-detail-page">
        <PageHeader
          eyebrow="素材详情"
          title="还没有可查看的素材。"
          desc="先上传图片做一次批量处理，结果会自动进入素材库，然后可以继续做产品或公开分享。"
        />
        <section className="asset-detail-empty">
          <ImageIcon size={28} />
          <strong>素材库是空的</strong>
          <p>可以先从素材库选择一张图，或去图片批处理生成一批可复用素材。</p>
          <button className="primary" onClick={() => navigate("assets")}>
            去素材库
          </button>
        </section>
      </main>
    );
  }

  const typeLabel = assetTypeLabels[asset.type] ?? asset.type;
  const visibilityLabel = visibilityLabels[asset.visibility] ?? asset.visibility;

  return (
    <main className="page-shell asset-detail-page">
      <div className="asset-detail-topbar">
        <button className="secondary" onClick={() => navigate("assets")}>
          <ArrowLeft size={16} />
          返回素材库
        </button>
        <div className="asset-detail-actions">
          <button className="secondary" onClick={handleEditImage}>
            <WandSparkles size={15} />
            单图精修
          </button>
          <button className="secondary" onClick={handleDownload}>
            <Download size={15} />
            下载原图
          </button>
          <button className="primary" onClick={handleUseForProduct}>
            <ShoppingBag size={15} />
            用这张图做产品
          </button>
        </div>
      </div>

      <PageHeader
        eyebrow="素材详情"
        title={asset.title}
        desc="确认这张图片是否适合精修、进入杯子试做，或作为私有素材保存在素材库。"
      />

      <section className="asset-detail-layout">
        <div className="asset-detail-stage">
          <img src={asset.url || asset.thumbnailUrl} alt={asset.title} />
        </div>

        <aside className="asset-detail-panel">
          <div className="asset-detail-panel-header">
            <ImageIcon size={22} />
            <div>
              <small>当前素材</small>
              <strong>{asset.title}</strong>
            </div>
          </div>

          <dl className="asset-detail-meta">
            <div>
              <dt>类型</dt>
              <dd>{typeLabel}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{asset.source}</dd>
            </div>
            <div>
              <dt>公开状态</dt>
              <dd>{visibilityLabel}</dd>
            </div>
            <div>
              <dt>尺寸</dt>
              <dd>{asset.width && asset.height ? `${asset.width} × ${asset.height}px` : "待识别"}</dd>
            </div>
            <div>
              <dt>DPI</dt>
              <dd>{asset.dpi ? `${asset.dpi}` : "待识别"}</dd>
            </div>
            <div>
              <dt>批次</dt>
              <dd>{asset.batchId || "单张素材"}</dd>
            </div>
          </dl>

          <div className="asset-detail-next">
            <article>
              <RefreshCw size={18} />
              <div>
                <strong>批量处理</strong>
                <span>多张图一起扩图、裂变、提花或连续化。</span>
              </div>
              <button onClick={() => navigate("process")}>进入</button>
            </article>
            <article>
              <WandSparkles size={18} />
              <div>
                <strong>单图精修</strong>
                <span>标注位置、加入参考图，再提交精确修改。</span>
              </div>
              <button onClick={handleEditImage}>进入</button>
            </article>
            <article>
              <ShoppingBag size={18} />
              <div>
                <strong>做产品</strong>
                <span>带入杯子试做页，满意后放入设计篮。</span>
              </div>
              <button onClick={handleUseForProduct}>进入</button>
            </article>
            <article>
              <Sparkles size={18} />
              <div>
                <strong>公开灵感</strong>
                <span>通过审核后进入灵感广场。</span>
              </div>
              <button onClick={() => navigate("publish")}>申请</button>
            </article>
          </div>

          <div className="asset-detail-note">
            <Layers3 size={16} />
            <span>单图精修和批量处理分开：精确修改进入图片处理工具，多图商家处理进入批量处理。</span>
          </div>
        </aside>
      </section>
    </main>
  );
}
