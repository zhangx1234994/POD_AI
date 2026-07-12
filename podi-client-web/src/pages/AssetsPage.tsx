/**
 * 素材库 — 用户可复用资产中心
 */
import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Download,
  Eye,
  Heart,
  RefreshCw,
  Search,
  Share2,
  ShoppingBag,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { useApp, useSelectedAssets } from "../hooks/useAppState";
import { assetTypeLabels, licenseModeLabels, licenseSourceLabels, visibilityLabels } from "../utils/constants";
import type { AssetItem, AssetType, WorkKind } from "../types";
import PageHeader from "../components/PageHeader";

type AssetTab = "images" | "licensed" | "products" | "public";

const imageTypes: AssetType[] = ["original", "processed", "variation", "pattern", "ai_generated"];
const pendingProductAssetKey = "podi.pendingProductDesignAssetId";
const typeFilters: Array<{ id: AssetType | "all"; label: string }> = [
  { id: "all", label: "全部图片" },
  { id: "original", label: "原图" },
  { id: "processed", label: "处理图" },
  { id: "variation", label: "裂变图" },
  { id: "pattern", label: "花纹" },
  { id: "ai_generated", label: "AI 生成" },
];

function assetDateLabel(asset: AssetItem) {
  if (asset.acquiredAt) return `授权 ${asset.acquiredAt}`;
  return `创建 ${asset.createdAt}`;
}

function assetSizeLabel(asset: AssetItem) {
  if (asset.width && asset.height) return `${asset.width}x${asset.height}`;
  if (asset.dpi) return `${asset.dpi} DPI`;
  return "尺寸待识别";
}

function assetDisplayTitle(asset: AssetItem) {
  const rawTitle = asset.title.trim();
  const looksLikeSystemName = /^[a-f0-9]{16,}$/i.test(rawTitle) || /^\d+(?:-\d+)?$/.test(rawTitle);
  if (!looksLikeSystemName && rawTitle.length <= 24) return rawTitle;

  const typeLabel = assetTypeLabels[asset.type] ?? "素材";
  const date = (asset.acquiredAt || asset.createdAt).slice(0, 10);
  if (asset.type === "product_preview") return `${asset.metadata?.productName || "产品预览"} · ${date}`;
  if (asset.type === "ai_generated") return `AI 设计图 · ${date}`;
  if (asset.type === "variation") return `裂变结果 · ${date}`;
  if (asset.type === "pattern") return `花纹素材 · ${date}`;
  if (asset.type === "processed") return `处理结果 · ${date}`;
  return `${typeLabel} · ${date}`;
}

function workKindFromAsset(asset: AssetItem): WorkKind {
  return asset.type === "product_preview" ? "产品作品" : "图片作品";
}

function rememberProductDesignAsset(assetId: string) {
  try {
    window.sessionStorage.setItem(pendingProductAssetKey, assetId);
  } catch {
    // Selection in React state remains a fallback when session storage is unavailable.
  }
  try {
    window.localStorage.setItem(pendingProductAssetKey, assetId);
  } catch {
    // Ignore storage failures.
  }
}

export default function AssetsPage() {
  const { state, dispatch, navigate } = useApp();
  const selectedAssets = useSelectedAssets(state);
  const [activeTab, setActiveTab] = useState<AssetTab>("images");
  const [typeFilter, setTypeFilter] = useState<AssetType | "all">("all");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");
  const [previewAsset, setPreviewAsset] = useState<AssetItem | null>(null);

  useEffect(() => {
    dispatch({ type: "CLEAR_SELECTION" });
  }, [dispatch]);

  const visibleAssets = state.assets.filter((asset) => asset.visibility !== "removed");
  const tabs: Array<{ id: AssetTab; label: string; desc: string; count: number }> = [
    {
      id: "images",
      label: "图片素材",
      desc: "原图、处理图、花纹和 AI 图",
      count: visibleAssets.filter((asset) => imageTypes.includes(asset.type)).length,
    },
    {
      id: "licensed",
      label: "已购授权",
      desc: "从灵感广场获得的使用权",
      count: visibleAssets.filter((asset) => asset.licenseSource === "purchased" || asset.licenseSource === "free_reuse").length,
    },
    {
      id: "products",
      label: "产品预览",
      desc: "试做过程中沉淀的产品图",
      count: visibleAssets.filter((asset) => asset.type === "product_preview").length,
    },
    {
      id: "public",
      label: "公开作品",
      desc: "已进入灵感广场或审核中的作品",
      count: visibleAssets.filter((asset) => asset.visibility === "public" || asset.visibility === "reviewing").length,
    },
  ];

  const filteredAssets = useMemo(() => {
    let assets = visibleAssets;
    if (activeTab === "images") assets = assets.filter((asset) => imageTypes.includes(asset.type));
    if (activeTab === "licensed") assets = assets.filter((asset) => asset.licenseSource === "purchased" || asset.licenseSource === "free_reuse");
    if (activeTab === "products") assets = assets.filter((asset) => asset.type === "product_preview");
    if (activeTab === "public") assets = assets.filter((asset) => asset.visibility === "public" || asset.visibility === "reviewing");
    if (typeFilter !== "all") assets = assets.filter((asset) => asset.type === typeFilter);
    if (search.trim()) {
      const keyword = search.trim().toLowerCase();
      assets = assets.filter((asset) =>
        [asset.title, asset.source, asset.author, asset.batchId, assetTypeLabels[asset.type]]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword))
      );
    }
    return [...assets].sort((a, b) => Date.parse(b.acquiredAt || b.createdAt) - Date.parse(a.acquiredAt || a.createdAt));
  }, [activeTab, search, typeFilter, visibleAssets]);

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2400);
  };

  const removeAsset = (asset: AssetItem) => {
    dispatch({ type: "DELETE_ASSET", id: asset.id });
    showNotice(`已删除「${asset.title}」`);
  };

  const publishAsset = (asset: AssetItem) => {
    dispatch({
      type: "SET_PUBLISH_DRAFT",
      kind: workKindFromAsset(asset),
      source: {
        kind: workKindFromAsset(asset),
        title: asset.title,
        tags: [assetTypeLabels[asset.type], asset.source].filter(Boolean).join(" / "),
        usage: asset.type === "product_preview" ? "别人可以用同款试做，也可以保存灵感。" : "别人可以保存为素材、继续处理或用于产品试做。",
        image: asset.thumbnailUrl || asset.url,
        sourceLabel: "素材库",
        sourceAssetId: asset.id,
      },
    });
    navigate("publish");
  };

  const handleBatchDownload = () => {
    if (selectedAssets.length === 0) return;
    showNotice(`已准备 ${selectedAssets.length} 张图片下载`);
  };

  return (
    <main className="page-shell assets-page">
      <PageHeader
        eyebrow="素材库"
        title="图片、授权和产品预览分开管。"
        desc="这里保存可继续复用的图片、授权素材和产品预览；按类型、来源和时间快速找到下一步要用的图。"
      />

      <div className="asset-library-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? "active" : ""}
            onClick={() => {
              setActiveTab(tab.id);
              setTypeFilter("all");
              setSearch("");
            }}
          >
            <strong>{tab.label}</strong>
            <span>{tab.desc}</span>
            <em>{tab.count}</em>
          </button>
        ))}
      </div>

      <div className="assets-toolbar">
        <label className="search-box">
          <Search size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜标题、来源、作者或任务"
          />
          {search && (
            <button type="button" onClick={() => setSearch("")} aria-label="清空搜索">
              x
            </button>
          )}
        </label>

        {activeTab === "images" && (
          <div className="type-filters">
            {typeFilters.map((filter) => (
              <button
                key={filter.id}
                className={typeFilter === filter.id ? "active" : ""}
                onClick={() => setTypeFilter(filter.id)}
              >
                {filter.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {notice && (
        <div className="assets-notice" role="status">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      <div className="asset-grid refined">
        {filteredAssets.length > 0 ? (
          filteredAssets.map((asset) => {
            const isSelected = state.selectedAssetIds.includes(asset.id);
            const typeLabel = assetTypeLabels[asset.type] ?? asset.type;
            const visibilityLabel = visibilityLabels[asset.visibility] ?? asset.visibility;
            const licenseLabel = licenseModeLabels[asset.licenseMode || "private"] ?? "仅自己可用";
            const sourceLabel = licenseSourceLabels[asset.licenseSource || "created"] ?? asset.source;
            const displayTitle = assetDisplayTitle(asset);

            return (
              <article key={asset.id} className={`asset-card refined ${isSelected ? "selected" : ""}`}>
                <button
                  className="asset-select-btn"
                  onClick={() => dispatch({ type: "TOGGLE_ASSET", id: asset.id })}
                  aria-label={isSelected ? "取消选择" : "选择素材"}
                >
                  {isSelected ? <CheckCircle2 size={14} /> : null}
                </button>

                <button
                  className={`asset-fav-btn ${asset.favorite ? "favorited" : ""}`}
                  onClick={() => dispatch({ type: "UPDATE_ASSET", id: asset.id, patch: { favorite: !asset.favorite } })}
                  aria-label={asset.favorite ? "取消收藏" : "收藏素材"}
                >
                  <Heart size={14} />
                </button>

                <button
                  type="button"
                  className="asset-image-button"
                  onClick={() => setPreviewAsset(asset)}
                  aria-label={`查看 ${displayTitle}`}
                >
                  <img src={asset.thumbnailUrl || asset.url} alt={displayTitle} />
                </button>

                <div className="asset-info refined">
                  <div className="asset-tags">
                    <span className="asset-type-tag">{typeLabel}</span>
                    <span className="asset-vis-tag">{visibilityLabel}</span>
                    <span>{licenseLabel}</span>
                  </div>
                  <strong>{displayTitle}</strong>
                  <p>{asset.source} · {sourceLabel}</p>
                  <div className="asset-meta-grid">
                    <span>{assetDateLabel(asset)}</span>
                    <span>{assetSizeLabel(asset)}</span>
                    <span>{asset.usedInProducts ? `已用于 ${asset.usedInProducts} 个产品` : "未用于产品"}</span>
                    {asset.author ? <span>作者 {asset.author}</span> : <span>归属自己</span>}
                  </div>
                  {asset.licensePoints ? (
                    <em className="asset-license-note">授权记录：{asset.licensePoints} 积分，不支持提现，只能站内抵扣。</em>
                  ) : null}
                </div>

                <div className="asset-card-actions refined">
                  <button
                    onClick={() => {
                      setPreviewAsset(asset);
                    }}
                  >
                    <Eye size={14} /> 查看
                  </button>
                  <button
                    onClick={() => {
                      rememberProductDesignAsset(asset.id);
                      dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: asset.id });
                      dispatch({ type: "SELECT_ASSETS", ids: [asset.id] });
                      navigate("products");
                    }}
                  >
                    <ShoppingBag size={14} /> 做产品
                  </button>
                </div>
                <div className="asset-card-mini-actions">
                  <button onClick={() => showNotice(`已准备「${displayTitle}」下载`)}>
                    <Download size={13} /> 下载
                  </button>
                  <button
                    onClick={() => {
                      dispatch({ type: "SELECT_ASSETS", ids: [asset.id] });
                      navigate("imageEditor");
                    }}
                  >
                    <WandSparkles size={13} /> 精修
                  </button>
                  <button onClick={() => publishAsset(asset)}>
                    <Share2 size={13} /> 公开
                  </button>
                  <button className="danger-soft" onClick={() => removeAsset(asset)}>
                    <Trash2 size={13} /> 删除
                  </button>
                </div>
              </article>
            );
          })
        ) : (
          <div className="assets-empty">
            <Search size={24} />
            <strong>没有匹配的素材</strong>
            <p>换一个筛选条件，或先去图片批处理生成一批可复用素材。</p>
            <button
              className="secondary"
              onClick={() => {
                setSearch("");
                setTypeFilter("all");
              }}
            >
              清空筛选
            </button>
          </div>
        )}
      </div>

      {selectedAssets.length > 0 && (
        <div className="assets-batch-bar">
          <span>已选 {selectedAssets.length} 张</span>
          <div className="batch-actions">
            <button className="secondary" onClick={handleBatchDownload}>
              <Download size={14} /> 下载
            </button>
            <button
              className="secondary"
              onClick={() => navigate(selectedAssets.length === 1 ? "imageEditor" : "process")}
            >
              {selectedAssets.length === 1 ? <WandSparkles size={14} /> : <RefreshCw size={14} />}
              {selectedAssets.length === 1 ? "单图精修" : "继续批处理"}
            </button>
            <button
              className="primary"
              onClick={() => {
                if (selectedAssets[0]) rememberProductDesignAsset(selectedAssets[0].id);
                if (selectedAssets[0]) dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: selectedAssets[0].id });
                navigate("products");
              }}
            >
              <ShoppingBag size={14} /> 做产品
            </button>
            <button className="secondary" onClick={() => publishAsset(selectedAssets[0])}>
              <Share2 size={14} /> 公开
            </button>
          </div>
        </div>
      )}

      {previewAsset && (
        <div className="modal-backdrop asset-preview-backdrop" role="presentation" onClick={() => setPreviewAsset(null)}>
          <section
            className="asset-preview-modal"
            role="dialog"
            aria-modal="true"
            aria-label="素材预览"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="asset-preview-stage">
              <img src={previewAsset.url} alt={assetDisplayTitle(previewAsset)} />
            </div>
            <aside className="asset-preview-side">
              <button className="modal-close" type="button" onClick={() => setPreviewAsset(null)} aria-label="关闭预览">
                ×
              </button>
              <span>{assetTypeLabels[previewAsset.type] ?? "素材"}</span>
              <h2>{assetDisplayTitle(previewAsset)}</h2>
              <p>{previewAsset.source} · {assetDateLabel(previewAsset)}</p>
              <dl>
                <div>
                  <dt>尺寸</dt>
                  <dd>{assetSizeLabel(previewAsset)}</dd>
                </div>
                <div>
                  <dt>权限</dt>
                  <dd>{licenseModeLabels[previewAsset.licenseMode || "private"] ?? "仅自己可用"}</dd>
                </div>
                <div>
                  <dt>使用</dt>
                  <dd>{previewAsset.usedInProducts ? `已用于 ${previewAsset.usedInProducts} 个产品` : "还没有用于产品"}</dd>
                </div>
              </dl>
              <div className="asset-preview-actions">
                <button
                  className="primary"
                  type="button"
                  onClick={() => {
                    rememberProductDesignAsset(previewAsset.id);
                    dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: previewAsset.id });
                    dispatch({ type: "SELECT_ASSETS", ids: [previewAsset.id] });
                    setPreviewAsset(null);
                    navigate("products");
                  }}
                >
                  <ShoppingBag size={15} /> 做产品
                </button>
                <button
                  className="secondary"
                  type="button"
                  onClick={() => {
                    dispatch({ type: "SELECT_ASSETS", ids: [previewAsset.id] });
                    setPreviewAsset(null);
                    navigate("imageEditor");
                  }}
                >
                  <WandSparkles size={15} /> 单图精修
                </button>
                <button className="secondary" type="button" onClick={() => showNotice(`已准备「${assetDisplayTitle(previewAsset)}」下载`)}>
                  <Download size={15} /> 下载
                </button>
                <button className="secondary" type="button" onClick={() => publishAsset(previewAsset)}>
                  <Share2 size={15} /> 公开
                </button>
              </div>
            </aside>
          </section>
        </div>
      )}
    </main>
  );
}
