/**
 * 灵感广场 — 公开作品流、授权和投诉入口
 */
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Bookmark,
  Eye,
  Images,
  PackagePlus,
  Search,
  ShieldAlert,
  Share2,
  Sparkles,
  WandSparkles,
  X,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { inspirationWorks } from "../data/mock-data";
import { licenseModeLabels } from "../utils/constants";
import type { AssetItem, AssetType, InspirationWork, WorkKind } from "../types";
import PageHeader from "../components/PageHeader";
import { createClientAsset, submitClientComplaint } from "../api";

type LicenseFilter = "全部" | "免费可用" | "积分授权";
type WorkViewMode = "资源墙" | "详情卡" | "大图";
const pendingProductAssetKey = "podi.pendingProductDesignAssetId";

function workLicenseLabel(work: InspirationWork) {
  if (work.rightsLabel) return work.rightsLabel;
  if (work.licenseMode === "paid_points") return `授权 ${work.pricePoints || 0} 积分`;
  return licenseModeLabels[work.licenseMode || "free_reuse"] || "免费复用";
}

function workActionLabel(work: InspirationWork) {
  if (work.kind === "产品作品") return work.licenseMode === "paid_points" ? "授权后同款试做" : "用同款试做";
  return work.licenseMode === "paid_points" ? "授权后保存素材" : "保存并使用";
}

function workEarningsLabel(work: InspirationWork) {
  const raw = work.earnings.replace("抵扣 ¥", "").replace("积分", "").trim();
  return raw ? `${raw} 积分` : "待结算积分";
}

function normalizeProductId(productId?: string | null) {
  const raw = String(productId || "").trim();
  return raw.startsWith("cup-") ? raw.slice(4) : raw;
}

function normalizeInspirationImage(image?: string | null) {
  const raw = String(image || "").trim();
  if (raw.endsWith("/demo/market/product-can-cooler.png")) {
    return raw.replace("/demo/market/product-can-cooler.png", "/demo/market/product-can-cooler-dark-botanical.png");
  }
  return raw;
}

function rememberProductDesignAsset(assetId: string) {
  try {
    window.sessionStorage.setItem(pendingProductAssetKey, assetId);
  } catch {
    // React state selection remains the fallback.
  }
  try {
    window.localStorage.setItem(pendingProductAssetKey, assetId);
  } catch {
    // Ignore storage failures.
  }
}

export default function InspirePage() {
  const { state, navigate, dispatch, activeUserId } = useApp();
  const [workKind, setWorkKind] = useState<WorkKind | "全部">("全部");
  const [licenseFilter, setLicenseFilter] = useState<LicenseFilter>("全部");
  const [sort, setSort] = useState("热门");
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<WorkViewMode>("资源墙");
  const [imageActionWork, setImageActionWork] = useState<InspirationWork | null>(null);
  const [complaintWork, setComplaintWork] = useState<InspirationWork | null>(null);
  const [complaintType, setComplaintType] = useState("版权侵权");
  const [complaintContact, setComplaintContact] = useState("");
  const [complaintEvidence, setComplaintEvidence] = useState("");
  const [complaintDetail, setComplaintDetail] = useState("");
  const [notice, setNotice] = useState("");
  const [preparingWorkId, setPreparingWorkId] = useState<string | null>(null);

  const sourceWorks = useMemo(() => {
    const merged = new Map<string, InspirationWork>();
    [...inspirationWorks, ...state.inspirationWorks].forEach((work) => {
      const existing = merged.get(work.id);
      merged.set(work.id, {
        ...(existing || {}),
        ...work,
        image: normalizeInspirationImage(work.image || existing?.image),
        productId: normalizeProductId(existing?.productId || work.productId),
      });
    });
    return Array.from(merged.values());
  }, [state.inspirationWorks]);

  const works = useMemo(() => {
    let list = workKind === "全部" ? sourceWorks : sourceWorks.filter((work) => work.kind === workKind);
    if (licenseFilter === "免费可用") list = list.filter((work) => work.licenseMode !== "paid_points");
    if (licenseFilter === "积分授权") list = list.filter((work) => work.licenseMode === "paid_points");
    if (query.trim()) {
      const keyword = query.trim().toLowerCase();
      list = list.filter((work) =>
        [
          work.title,
          work.kind,
          work.author,
          work.trend,
          workLicenseLabel(work),
          ...(work.tags || []),
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(keyword))
      );
    }
    return [...list].sort((a, b) => {
      if (sort === "最新") return a.id.localeCompare(b.id);
      if (sort === "最多收藏") return b.favorites - a.favorites;
      if (sort === "最多使用") return b.tries - a.tries;
      return b.favorites + b.tries - (a.favorites + a.tries);
    });
  }, [licenseFilter, query, sort, sourceWorks, workKind]);

  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2600);
  };

  const acquireWorkAsset = async (work: InspirationWork): Promise<string | null> => {
    if (work.licenseMode === "display_only") {
      showNotice("这个作品当前只允许展示，不能保存或同款使用。");
      return null;
    }

    const assetId = `licensed-${work.id}`;
    const sourceAsset = work.sourceAssetId ? state.assets.find((asset) => asset.id === work.sourceAssetId) : null;
    const assetUrl = sourceAsset?.url || sourceAsset?.thumbnailUrl || work.image;
    const assetTitle = sourceAsset?.title || `${work.title} · 同款素材`;
    const usableType: AssetType = sourceAsset?.type && sourceAsset.type !== "product_preview" ? sourceAsset.type : "ai_generated";
    const existing = state.assets.find((asset) => asset.id === assetId);
    if (existing) {
      if (existing.type === "product_preview" || existing.url === work.image) {
        dispatch({
          type: "UPDATE_ASSET",
          id: assetId,
          patch: {
            type: usableType,
            title: existing.title === work.title ? assetTitle : existing.title,
            url: assetUrl,
            thumbnailUrl: assetUrl,
            width: sourceAsset?.width ?? existing.width,
            height: sourceAsset?.height ?? existing.height,
            dpi: sourceAsset?.dpi ?? existing.dpi,
            metadata: {
              ...(existing.metadata || {}),
              ...(sourceAsset?.metadata || {}),
              inspirationWorkId: work.id,
              sourceAssetId: work.sourceAssetId,
              sourceWorkImage: work.image,
              sourceWorkKind: work.kind,
              rightsLabel: workLicenseLabel(work),
            },
          },
        });
      }
      dispatch({ type: "SELECT_ASSETS", ids: [assetId] });
      showNotice("这张图已经在你的素材库里。");
      return assetId;
    }

    const price = work.licenseMode === "paid_points" ? Number(work.pricePoints || 0) : 0;
    if (price > 0) {
      if (state.aiCredits < price) {
        showNotice("AI 积分不足，先去钱包充值或兑换积分。");
        return null;
      }
      dispatch({
        type: "SPEND_CREDITS",
        amount: price,
        event: `已用 ${price} AI 积分获得「${work.title}」站内授权。作者收益会以积分形式记录，不支持提现。`,
      });
    }

    const asset: AssetItem = {
      id: assetId,
      type: usableType,
      title: assetTitle,
      url: assetUrl,
      thumbnailUrl: assetUrl,
      source: work.licenseMode === "paid_points" ? "灵感广场积分授权" : "灵感广场免费复用",
      createdAt: new Date().toLocaleString("zh-CN"),
      selected: false,
      favorite: false,
      visibility: "private",
      licenseMode: work.licenseMode || "free_reuse",
      licenseSource: work.licenseMode === "paid_points" ? "purchased" : "free_reuse",
      licensePoints: price || null,
      author: work.author,
      acquiredAt: new Date().toLocaleString("zh-CN"),
      width: sourceAsset?.width,
      height: sourceAsset?.height,
      dpi: sourceAsset?.dpi,
      metadata: {
        ...(sourceAsset?.metadata || {}),
        inspirationWorkId: work.id,
        sourceAssetId: work.sourceAssetId,
        sourceWorkImage: work.image,
        sourceWorkKind: work.kind,
        rightsLabel: workLicenseLabel(work),
      },
    };
    let savedAsset = asset;
    try {
      savedAsset = await createClientAsset({ userId: activeUserId, ...asset });
    } catch {
      showNotice("素材已先保存在当前页面，业务服务恢复后会重新同步。");
    }
    dispatch({ type: "ADD_ASSETS", assets: [savedAsset] });
    dispatch({ type: "SELECT_ASSETS", ids: [savedAsset.id] });
    showNotice(price > 0 ? `已授权并加入素材库，消耗 ${price} AI 积分。` : "已加入素材库，可以继续处理或做产品。");
    return savedAsset.id;
  };

  const useWork = async (work: InspirationWork) => {
    if (preparingWorkId) return;
    setPreparingWorkId(work.id);
    try {
      dispatch({ type: "SET_SAME_STYLE_WORK", work });
      if (work.kind === "产品作品") {
        const assetId = await acquireWorkAsset(work);
        if (!assetId) return;
        rememberProductDesignAsset(assetId);
        dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: assetId });
        const productId = normalizeProductId(work.productId);
        if (productId) dispatch({ type: "SET_SELECTED_PRODUCT", productId });
        navigate("productDesign");
        return;
      }
      setImageActionWork(work);
    } finally {
      setPreparingWorkId(null);
    }
  };

  const submitComplaint = async () => {
    if (!complaintWork) return;
    if (!complaintContact.trim() || !complaintEvidence.trim()) {
      showNotice("请留下联系方式和侵权证据，方便运营联系核验。");
      return;
    }
    try {
      await submitClientComplaint({
        userId: activeUserId,
        workId: complaintWork.id,
        workTitle: complaintWork.title,
        workKind: complaintWork.kind,
        author: complaintWork.author,
        image: complaintWork.image,
        type: complaintType,
        contact: complaintContact,
        evidence: complaintEvidence,
        detail: complaintDetail,
      });
    } catch {
      showNotice("投诉已先保存在当前页面。业务服务恢复后请重新提交一次。");
    }
    setComplaintWork(null);
    setComplaintType("版权侵权");
    setComplaintContact("");
    setComplaintEvidence("");
    setComplaintDetail("");
    showNotice("投诉已提交。运营会人工核验证据，并联系双方处理。");
  };

  return (
    <main className="page-shell inspire-page">
      <PageHeader
        eyebrow="灵感广场"
        title="看见喜欢的风格，就把它做成你的表达。"
        desc="收藏灵感、使用授权素材，或从一件喜欢的作品开始创作。"
      />

      {notice && (
        <div className="assets-notice inspire-notice" role="status">
          <Sparkles size={16} />
          <span>{notice}</span>
        </div>
      )}

      <section className="inspire-top-bar refined">
        <div className="inspire-filter-head">
          <label className="search-box inspire-search">
            <Search size={16} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜花纹元素、产品、作者或标签"
            />
            {query && (
              <button type="button" onClick={() => setQuery("")} aria-label="清空搜索">
                x
              </button>
            )}
          </label>
          <button className="primary publish-work-button" onClick={() => navigate("publish")}>
            <Share2 size={16} /> 发布我的作品
          </button>
        </div>

        <div className="inspire-filter-rows">
          <div className="kind-row">
            <span className="filter-label">类型</span>
            {(["全部", "图片作品", "产品作品"] as const).map((item) => (
              <button key={item} className={workKind === item ? "active" : ""} onClick={() => setWorkKind(item)}>
                {item}
              </button>
            ))}
          </div>
          <div className="kind-row license-row">
            <span className="filter-label">使用方式</span>
            {(["全部", "免费可用", "积分授权"] as const).map((item) => (
              <button key={item} className={licenseFilter === item ? "active" : ""} onClick={() => setLicenseFilter(item)}>
                {item}
              </button>
            ))}
          </div>
          <div className="sort-row">
            <span className="filter-label">排序</span>
            {["热门", "最新"].map((item) => (
              <button key={item} className={sort === item ? "active" : ""} onClick={() => setSort(item)}>
                {item}
              </button>
            ))}
          </div>
        </div>

        <details className="inspire-rules-compact">
          <summary>广场规则</summary>
          <div className="rule-grid compact">
            <div className="rule-item">
              <strong>图片作品</strong>
              <span>先加入自己的素材库，再继续处理、做产品或收藏。</span>
            </div>
            <div className="rule-item">
              <strong>产品作品</strong>
              <span>进入同款试做，可换素材、换杯型，再放入设计篮。</span>
            </div>
            <div className="rule-item">
              <strong>积分授权</strong>
              <span>用户支付 AI 积分获得站内使用权，作者收益也是积分。</span>
            </div>
            <div className="rule-item">
              <strong>侵权投诉</strong>
              <span>提交证据和联系方式后，运营人工联系核验处理。</span>
            </div>
          </div>
        </details>
      </section>

      <section className="inspire-content refined">
        <div className="inspire-feed">
          <div className={`work-grid large refined ${viewMode === "资源墙" ? "resource-wall" : viewMode === "大图" ? "visual-wall" : "detail-cards"}`}>
            {works.length > 0 ? works.map((work) => (
              <article key={work.id} className={`work-card refined ${viewMode === "资源墙" ? "resource-wall" : viewMode === "大图" ? "visual-wall" : "detail-cards"}`}>
                <div className="work-image-wrap">
                  <img src={work.image} alt={work.title} />
                  <span className={work.kind === "产品作品" ? "type-tag product" : "type-tag"}>{work.kind}</span>
                </div>
                <div className="work-body refined">
                  <div className="work-title-line">
                    <h3>{work.title}</h3>
                    <button className="text-danger" onClick={() => setComplaintWork(work)}>
                      <ShieldAlert size={14} /> 投诉
                    </button>
                  </div>
                  <div className="creator-line">
                    <span>{work.author}</span>
                    <em>{workLicenseLabel(work)}</em>
                  </div>
                  <div className="tag-row">{work.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
                  <div className="work-stats">
                    <span><Eye size={14} /> {work.tries} 次使用</span>
                    <span><Bookmark size={14} /> {work.favorites} 收藏</span>
                    <span>{work.trend}</span>
                  </div>
                  <div className="creator-earnings">
                    <strong>作者收益：{workEarningsLabel(work)}</strong>
                    <span>只能站内抵扣，不能提现</span>
                  </div>
                  <button
                    className="primary full"
                    onClick={() => useWork(work)}
                    disabled={Boolean(preparingWorkId)}
                  >
                    {preparingWorkId === work.id ? "正在准备…" : workActionLabel(work)}
                  </button>
                </div>
              </article>
            )) : (
              <div className="assets-empty">
                <Search size={24} />
                <strong>没有找到匹配作品</strong>
                <p>换一个元素、产品或标签搜索，也可以切换作品类型和授权方式。</p>
                <button
                  className="secondary"
                  onClick={() => {
                    setQuery("");
                    setWorkKind("全部");
                    setLicenseFilter("全部");
                  }}
                >
                  清空筛选
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {imageActionWork && (
        <div className="app-modal-backdrop" role="presentation" onClick={() => setImageActionWork(null)}>
          <section className="app-modal inspire-action-modal" role="dialog" aria-modal="true" aria-label="选择图片用途" onClick={(event) => event.stopPropagation()}>
            <div className="app-modal-head">
              <div>
                <small>图片同款</small>
                <strong>先获得使用权，再选择用途</strong>
              </div>
              <button className="icon-button" onClick={() => setImageActionWork(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="inspire-action-preview">
              <img src={imageActionWork.image} alt={imageActionWork.title} />
              <div>
                <strong>{imageActionWork.title}</strong>
                <span>{imageActionWork.author} · {workLicenseLabel(imageActionWork)}</span>
                <em>获得使用权后进入“已购授权”，作者收益按站内积分记录。</em>
              </div>
            </div>
            <div className="design-guide-grid">
              <button onClick={async () => {
                const assetId = await acquireWorkAsset(imageActionWork);
                if (!assetId) return;
                dispatch({ type: "SELECT_ASSETS", ids: [assetId] });
                setImageActionWork(null);
                navigate("imageEditor");
              }}>
                <WandSparkles size={22} />
                <strong>单图精修</strong>
                <span>进入图片处理工具，可以标注位置、加参考图，再提交精确修改。</span>
              </button>
              <button onClick={async () => {
                const assetId = await acquireWorkAsset(imageActionWork);
                if (!assetId) return;
                rememberProductDesignAsset(assetId);
                dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: assetId });
                dispatch({ type: "SELECT_ASSETS", ids: [assetId] });
                setImageActionWork(null);
                navigate("products");
              }}>
                <PackagePlus size={22} />
                <strong>用它做产品</strong>
                <span>保存为素材后选择杯型，进入产品试做。</span>
              </button>
              <button onClick={async () => {
                const assetId = await acquireWorkAsset(imageActionWork);
                if (!assetId) return;
                setImageActionWork(null);
                navigate("assets");
              }}>
                <Images size={22} />
                <strong>加入素材库</strong>
                <span>先放进自己的资产库，后续再决定用途。</span>
              </button>
            </div>
          </section>
        </div>
      )}

      {complaintWork && (
        <div className="app-modal-backdrop" role="presentation" onClick={() => setComplaintWork(null)}>
          <section className="app-modal complaint-modal" role="dialog" aria-modal="true" aria-label="投诉侵权" onClick={(event) => event.stopPropagation()}>
            <div className="app-modal-head">
              <div>
                <small>投诉侵权</small>
                <strong>提交证据，运营人工联系处理</strong>
              </div>
              <button className="icon-button" onClick={() => setComplaintWork(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="complaint-target">
              <img src={complaintWork.image} alt={complaintWork.title} />
              <div>
                <strong>{complaintWork.title}</strong>
                <span>{complaintWork.author} · {complaintWork.kind}</span>
              </div>
            </div>
            <div className="complaint-fields">
              <label>
                <span>投诉类型</span>
                <select value={complaintType} onChange={(event) => setComplaintType(event.target.value)}>
                  <option>版权侵权</option>
                  <option>商标侵权</option>
                  <option>肖像侵权</option>
                  <option>其他问题</option>
                </select>
              </label>
              <label>
                <span>联系方式</span>
                <input value={complaintContact} onChange={(event) => setComplaintContact(event.target.value)} placeholder="手机号、微信或邮箱" />
              </label>
              <label>
                <span>证据链接或说明</span>
                <textarea value={complaintEvidence} onChange={(event) => setComplaintEvidence(event.target.value)} placeholder="原图链接、版权登记、商标证明、平台商品链接等" />
              </label>
              <label>
                <span>补充说明（可选）</span>
                <textarea value={complaintDetail} onChange={(event) => setComplaintDetail(event.target.value)} placeholder="说明你希望平台联系和处理的方式" />
              </label>
            </div>
            <div className="complaint-warning">
              <AlertTriangle size={16} />
              <span>平台会先记录投诉并联系双方核验。明显风险内容可先临时隐藏，最终以人工处理为准。</span>
            </div>
            <button className="primary full" onClick={submitComplaint}>提交投诉证据</button>
          </section>
        </div>
      )}
    </main>
  );
}
