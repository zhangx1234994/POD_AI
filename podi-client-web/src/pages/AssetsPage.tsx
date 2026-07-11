/**
 * 素材库 — 分层展示 + 大图网格 + 批量操作
 * 三个 Tab：我的图片 / 我的作品 / 公开作品
 */
import { useState, useMemo } from "react";
import {
  Search,
  Download,
  RefreshCw,
  ShoppingBag,
  Share2,
  CheckCircle2,
  Heart,
  Edit3,
} from "lucide-react";
import { useApp, useSelectedAssets } from "../hooks/useAppState";
import { assetTypeLabels, visibilityLabels } from "../utils/constants";
import type { AssetType, AssetVisibility } from "../types";
import PageHeader from "../components/PageHeader";

type AssetTab = "my-images" | "my-works" | "public";

const imageTypes: AssetType[] = ["original", "processed", "variation", "pattern", "ai_generated"];
const typeFilters: Array<{ id: AssetType | "all"; label: string }> = [
  { id: "all", label: "全部" },
  { id: "original", label: "原图" },
  { id: "processed", label: "处理图" },
  { id: "variation", label: "裂变图" },
  { id: "pattern", label: "花纹" },
  { id: "ai_generated", label: "AI 生成" },
];

export default function AssetsPage() {
  const { state, dispatch, navigate } = useApp();
  const selectedAssets = useSelectedAssets(state);

  const [activeTab, setActiveTab] = useState<AssetTab>("my-images");
  const [typeFilter, setTypeFilter] = useState<AssetType | "all">("all");
  const [search, setSearch] = useState("");
  const [downloadNotice, setDownloadNotice] = useState("");

  // 按 Tab 筛选素材
  const filteredAssets = useMemo(() => {
    let assets = state.assets;

    // Tab 过滤
    if (activeTab === "my-images") {
      assets = assets.filter((a) => imageTypes.includes(a.type));
    } else if (activeTab === "my-works") {
      // 目前 mock 没有产品样例类型，先显示全部
      assets = assets.filter((a) => a.visibility === "private" && !imageTypes.includes(a.type));
    } else {
      assets = assets.filter((a) => a.visibility === "public");
    }

    // 类型过滤
    if (typeFilter !== "all") {
      assets = assets.filter((a) => a.type === typeFilter);
    }

    // 搜索
    if (search.trim()) {
      const q = search.toLowerCase();
      assets = assets.filter(
        (a) =>
          a.title.toLowerCase().includes(q) ||
          a.source.toLowerCase().includes(q)
      );
    }

    return assets;
  }, [state.assets, activeTab, typeFilter, search]);

  const showNotice = (msg: string) => {
    setDownloadNotice(msg);
    setTimeout(() => setDownloadNotice(""), 2600);
  };

  const handleBatchDownload = () => {
    if (selectedAssets.length === 0) return;
    showNotice(`已准备 ${selectedAssets.length} 张图片下载`);
  };

  const handleSingleDownload = (id: string, title: string) => {
    showNotice(`已准备「${title}」下载`);
  };

  const tabs: Array<{ id: AssetTab; label: string; count: number }> = [
    {
      id: "my-images",
      label: "我的图片",
      count: state.assets.filter((a) => imageTypes.includes(a.type)).length,
    },
    {
      id: "my-works",
      label: "我的作品",
      count: state.assets.filter((a) => !imageTypes.includes(a.type) && a.visibility === "private").length,
    },
    {
      id: "public",
      label: "公开作品",
      count: state.assets.filter((a) => a.visibility === "public").length,
    },
  ];

  return (
    <main className="page-shell assets-page">
      <PageHeader
        eyebrow="素材库"
        title="处理好的图片，都在这里。"
        desc="管理原图、处理图、花纹和裂变结果，可下载、继续处理或拿去做产品。"
      />

      {/* ── Tab 切换 ── */}
      <div className="assets-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`assets-tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => {
              setActiveTab(tab.id);
              setTypeFilter("all");
              setSearch("");
            }}
          >
            {tab.label}
            <span className="tab-count">{tab.count}</span>
          </button>
        ))}
      </div>

      {/* ── 搜索 + 筛选 ── */}
      <div className="assets-toolbar">
        <label className="search-box">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索素材…"
          />
          {search && (
            <button type="button" onClick={() => setSearch("")}>×</button>
          )}
        </label>

        {activeTab === "my-images" && (
          <div className="type-filters">
            {typeFilters.map((f) => (
              <button
                key={f.id}
                className={typeFilter === f.id ? "active" : ""}
                onClick={() => setTypeFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── 下载通知 ── */}
      {downloadNotice && (
        <div className="assets-notice" role="status">
          <CheckCircle2 size={16} />
          <span>{downloadNotice}</span>
        </div>
      )}

      {/* ── 图片网格 ── */}
      <div className="assets-grid">
        {filteredAssets.length > 0 ? (
          filteredAssets.map((asset) => {
            const isSelected = state.selectedAssetIds.includes(asset.id);
            const typeLabel = assetTypeLabels[asset.type] ?? asset.type;
            const visLabel = visibilityLabels[asset.visibility] ?? asset.visibility;

            return (
              <div
                key={asset.id}
                className={`asset-card ${isSelected ? "selected" : ""}`}
              >
                {/* 选择按钮 */}
                <button
                  className="asset-select-btn"
                  onClick={() => dispatch({ type: "TOGGLE_ASSET", id: asset.id })}
                >
                  {isSelected && <CheckCircle2 size={14} />}
                </button>

                {/* 收藏 */}
                <button
                  className={`asset-fav-btn ${asset.favorite ? "favorited" : ""}`}
                  onClick={() =>
                    dispatch({
                      type: "UPDATE_ASSET",
                      id: asset.id,
                      patch: { favorite: !asset.favorite },
                    })
                  }
                >
                  <Heart size={14} />
                </button>

                {/* 图片 */}
                <img src={asset.thumbnailUrl} alt={asset.title} />

                {/* 信息 */}
                <div className="asset-card-info">
                  <div className="asset-tags">
                    <span className="asset-type-tag">{typeLabel}</span>
                    <span className="asset-vis-tag">{visLabel}</span>
                  </div>
                  <strong>{asset.title}</strong>
                  <span className="asset-source">{asset.source}</span>
                </div>

                {/* hover 操作 */}
                <div className="asset-card-actions">
                  <button
                    title="下载"
                    onClick={() => handleSingleDownload(asset.id, asset.title)}
                  >
                    <Download size={14} />
                  </button>
                  <button
                    title="编辑"
                    onClick={() => navigate("editor")}
                  >
                    <Edit3 size={14} />
                  </button>
                  <button
                    title="继续处理"
                    onClick={() => navigate("process")}
                  >
                    <RefreshCw size={14} />
                  </button>
                  <button
                    title="做产品"
                    onClick={() => navigate("products")}
                  >
                    <ShoppingBag size={14} />
                  </button>
                  <button
                    title="公开"
                    onClick={() => navigate("publish")}
                  >
                    <Share2 size={14} />
                  </button>
                </div>
              </div>
            );
          })
        ) : (
          <div className="assets-empty">
            <Search size={24} />
            <strong>没有找到匹配的素材</strong>
            <p>换一个关键词，或清空搜索重新浏览</p>
            <button
              className="secondary"
              onClick={() => {
                setSearch("");
                setTypeFilter("all");
              }}
            >
              清空搜索
            </button>
          </div>
        )}
      </div>

      {/* ── 浮动批量操作栏 ── */}
      {selectedAssets.length > 0 && (
        <div className="assets-batch-bar">
          <span>已选 {selectedAssets.length} 张</span>
          <div className="batch-actions">
            <button className="secondary" onClick={handleBatchDownload}>
              <Download size={14} /> 下载
            </button>
            <button className="secondary" onClick={() => navigate("process")}>
              <RefreshCw size={14} /> 继续处理
            </button>
            <button className="primary" onClick={() => navigate("products")}>
              <ShoppingBag size={14} /> 做产品
            </button>
            <button className="secondary" onClick={() => navigate("publish")}>
              <Share2 size={14} /> 公开
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
