import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Brush,
  CheckCircle2,
  Clock,
  Images,
  LayoutGrid,
  Loader2,
  MessageCircle,
  Search,
  Send,
  ShieldCheck,
  WandSparkles,
  X,
} from "lucide-react";
import { useApp } from "../hooks/useAppState";
import { cupProducts } from "../data/cup-products";
import type { CupProduct, DesignSurface, ProductColor, ProductCraftOption } from "../data/cup-products";
import { modelUvCalibrationForSurface } from "../data/model-uv-calibrations";
import type {
  AssetItem,
  AssetType,
  ProductDesignAgentPlan,
  ProductDesignAgentSession,
  ProductDesignQuickIntake,
} from "../types";
import {
  applyProductDesignAgentPreview,
  confirmProductDesignAgentPlan,
  confirmProductDesignAgentStep,
  createClientAsset,
  createVerifiedSeamlessArtwork,
  createClientProductSample,
  createProductDesignQuickIntake,
  createProductDesignAgentSession,
  getClientProductPricing,
  getProductDesignAgentSession,
  getBusinessRun,
  getClientAssetPreviewUrl,
  sendProductDesignAgentMessage,
  submitBusinessRun,
  uploadClientImage,
} from "../api";
import { assetTypeLabels } from "../utils/constants";

const Product3DPreview = lazy(() => import("../components/Product3DPreview"));

const pendingProductAssetKey = "podi.pendingProductDesignAssetId";
const postAuthReturnKey = "podi.postAuthReturn";
const pendingAgentDraftKey = "podi.pendingAgentDesignDraft";
const resumeAgentSessionKey = "podi.resumeAgentDesignSession";

type TexturePlacementMode = "wrap" | "fit" | "cover" | "decal";

const defaultCupColorOptions: ProductColor[] = [
  { code: "white", label: "白色", value: "#f8f7f2", note: "最常用底杯" },
  { code: "beige1", label: "奶油", value: "#f2eadb", note: "柔和浅底" },
  { code: "black", label: "黑色", value: "#111827", note: "深色杯身" },
  { code: "light-blue", label: "雾蓝", value: "#d9e6f3", note: "冷色浅底" },
  { code: "light-green", label: "鼠尾草", value: "#dce8df", note: "自然绿底" },
  { code: "pink", label: "浅粉", value: "#f4d8dc", note: "礼品底色" },
];

const textureModeOptions: Array<{
  id: TexturePlacementMode;
  title: string;
  description: string;
}> = [
  { id: "decal", title: "局部贴图", description: "照片、头像或 Logo，可调大小和位置" },
  { id: "cover", title: "铺满杯身", description: "自动放大裁切，快速预览满版效果" },
  { id: "wrap", title: "AI 适配杯身", description: "生成可生产的连续图，自动适配设计面" },
];

function displayAssetTitle(title: string | null | undefined, fallback = "已选图片") {
  const value = String(title || "").trim();
  const compactId = value.replace(/[^a-f0-9]/gi, "");
  if (!value || (compactId.length >= 16 && /^[a-f0-9-]+$/i.test(value))) return fallback;
  return value.length > 22 ? `${value.slice(0, 22)}...` : value;
}

function craftOptionKey(option: ProductCraftOption): string {
  return `${option.firstCraft}:${option.secondCraft}`;
}

const agentImageStarterPrompts = [
  "参考这张图，重新设计一套同风格杯子图案",
  "提取花纹，做成杯身满版环绕",
  "裂变 4 张候选图让我挑",
  "图片质量一般，先精修再适配杯子",
];

const agentTextStarterPrompts = [
  "我想做一款西安文旅杯，先帮我拆设计方向",
  "我有孩子画想做纪念杯，告诉我该怎么准备图片",
  "我想做公司礼品杯，先帮我判断需要哪些素材",
];

function firstReadySurface(product: CupProduct) {
  return product.sizes.flatMap((size) => size.surfaces).find((surface) => surface.width && surface.height);
}

function productHasHandleSurface(product: CupProduct) {
  return product.bodyCode === "1660" || /手柄|把手|带手柄/i.test(product.name);
}

function designSurfacesForProduct(product: CupProduct | null | undefined, sizeLabel?: string | null): DesignSurface[] {
  if (!product) return [];
  const activeSize = sizeLabel ? product.sizes.find((size) => size.label === sizeLabel) : null;
  const sourceSizes = activeSize ? [activeSize] : product.sizes;
  const surfaces = sourceSizes.flatMap((size) => size.surfaces).filter((surface) => surface.width && surface.height);
  const baseSurface = surfaces[0] ?? firstReadySurface(product) ?? product.sizes[0]?.surfaces[0];
  const normalized = Array.from(
    new Map(surfaces.map((surface) => [surface.name, surface])).values()
  );
  if (productHasHandleSurface(product) && baseSurface && !normalized.some((surface) => surface.name === "handle")) {
    normalized.push({
      name: "handle",
      label: "把手",
      sizeLabel: baseSurface.sizeLabel,
      viewId: null,
      dpi: baseSurface.dpi ?? 150,
      width: baseSurface.width ? Math.max(480, Math.round(baseSurface.width * 0.28)) : null,
      height: baseSurface.height ?? null,
    });
  }
  return normalized;
}

const quantityPresets = [1, 10, 50];
const assetFilterOptions: Array<{ id: AssetType | "all"; label: string }> = [
  { id: "all", label: "全部素材" },
  { id: "pattern", label: "花纹" },
  { id: "variation", label: "裂变图" },
  { id: "processed", label: "处理图" },
  { id: "ai_generated", label: "AI 生成" },
  { id: "original", label: "原图" },
];

function formatMoney(cents: number) {
  return `${Math.round(Math.max(0, cents) / 100)} 积分`;
}

function quantityDiscountRate(quantity: number) {
  if (quantity >= 50) return 0.88;
  if (quantity >= 10) return 0.94;
  return 1;
}

function isLocalOnlyAsset(asset: AssetItem | null | undefined) {
  if (!asset) return false;
  return Boolean(asset.metadata?.localOnly) || asset.id.startsWith("local-asset-") || asset.url.startsWith("data:") || asset.url.startsWith("blob:");
}

function agentIntentLabel(intent?: string) {
  const labels: Record<string, string> = {
    print_as_is: "原图局部印刷",
    clean_and_print: "清理后印刷",
    extract_pattern: "提取花纹",
    make_seamless_wrap: "杯身连续环绕",
    generate_variations: "裂变候选",
    ai_recreate: "AI 重绘适配",
    compose_product_design: "整套产品设计",
    clarify: "需要确认方向",
  };
  return labels[intent || ""] || "产品设计建议";
}

function agentVisionEvidence(plan?: ProductDesignAgentPlan | null) {
  const vision = plan?.visionAnalysis;
  if (!vision) return null;
  const observations = Array.isArray(vision.observations) ? vision.observations.filter(Boolean).slice(0, 2) : [];
  const risks = Array.isArray(vision.risks) ? vision.risks.filter(Boolean).slice(0, 1) : [];
  const usedFallback = Boolean(vision.skippedReason || vision.fallback || vision.modelError);
  const title = usedFallback ? "当前先按需求预判" : "已理解素材和商品约束";
  const note = vision.skippedReason
    ? "图片暂时还不能被处理服务读取，我会先按你的描述给方案。"
    : vision.modelError
      ? "图片理解暂时不稳定，我会先给出保守方案，确认后再继续。"
      : observations[0] || "已结合素材内容、杯型尺寸和你的描述规划路线。";
  return {
    title,
    modelLabel: usedFallback ? "可继续补充说明" : "设计判断",
    note,
    extra: risks[0] || observations[1] || "",
  };
}

function agentStepStatusLabel(status?: string, userStatus?: string) {
  if (userStatus) return userStatus;
  const labels: Record<string, string> = {
    pending: "等待前一步完成",
    waiting_confirmation: "等待确认",
    needs_user: "需要补充",
    queued: "排队中",
    running: "生成中",
    completed: "已完成",
    failed: "失败",
  };
  return labels[status || ""] || "待处理";
}

function isAgentClarifying(plan?: ProductDesignAgentPlan | null) {
  return Boolean(
    plan?.status === "clarifying" ||
      plan?.intent === "clarify" ||
      plan?.steps?.some((step) => step.status === "needs_user" || step.targetAbility === "ask_user")
  );
}

function latestAgentPlan(session: ProductDesignAgentSession | null): ProductDesignAgentPlan | null {
  if (!session?.plans?.length) return null;
  const current = session.currentPlanId
    ? session.plans.find((plan) => plan.planId === session.currentPlanId)
    : null;
  return current || session.plans[session.plans.length - 1] || null;
}

function agentPlanForMessage(session: ProductDesignAgentSession | null, planId?: string | null) {
  if (!session || !planId) return null;
  return session.plans.find((plan) => plan.planId === planId) || null;
}

type SurfaceFitTone = "ready" | "notice" | "warning";

type SurfaceFitAssessment = {
  tone: SurfaceFitTone;
  title: string;
  detail: string;
  chips: string[];
};

function metadataNumber(asset: AssetItem | null | undefined, keys: string[]) {
  if (!asset?.metadata) return null;
  for (const key of keys) {
    const value = asset.metadata[key];
    const parsed = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return null;
}

function assetDimensions(asset: AssetItem | null | undefined) {
  const width =
    asset?.width ??
    metadataNumber(asset, ["width", "outputWidth", "targetWidth", "sourceWidth", "imageWidth"]) ??
    null;
  const height =
    asset?.height ??
    metadataNumber(asset, ["height", "outputHeight", "targetHeight", "sourceHeight", "imageHeight"]) ??
    null;
  return { width, height };
}

function assetLooksSeamless(asset: AssetItem | null | undefined) {
  if (!asset) return false;
  const metadata = asset.metadata ?? {};
  if (metadata.seamlessVerified === true) return true;
  const text = [asset.title, asset.source, asset.type, String(metadata.ability ?? ""), String(metadata.intent ?? "")]
    .join(" ")
    .toLowerCase();
  return /已校验连续|seamless verified/.test(text);
}

function assetHasSeamlessCandidate(asset: AssetItem | null | undefined) {
  if (!asset) return false;
  const metadata = asset.metadata ?? {};
  if (metadata.seamless === true || metadata.tileable === true || metadata.isSeamless === true) return true;
  const text = [asset.title, asset.source, asset.type, String(metadata.ability ?? ""), String(metadata.intent ?? "")]
    .join(" ")
    .toLowerCase();
  return /连续|无缝|闭环|环绕|seamless|tile|repeat/.test(text);
}

function assessSurfaceFit({
  asset,
  surface,
  mode,
  plan,
}: {
  asset: AssetItem | null | undefined;
  surface: DesignSurface | null | undefined;
  mode: TexturePlacementMode;
  plan?: ProductDesignAgentPlan | null;
}): SurfaceFitAssessment {
  const surfaceWidth = surface?.width ?? null;
  const surfaceHeight = surface?.height ?? null;
  const dpi = surface?.dpi ?? 150;
  const surfaceLabel = surface?.label ?? "当前设计面";
  if (!surfaceWidth || !surfaceHeight) {
    return {
      tone: "warning",
      title: "缺少生产尺寸",
      detail: "这款商品的设计面尺寸还没有补齐，不能直接进入生产图导出。",
      chips: ["先补供应链尺寸", "暂不下单"],
    };
  }

  const targetLabel = `${surfaceLabel} ${surfaceWidth}×${surfaceHeight}px · ${dpi}DPI`;
  if (!asset) {
    return {
      tone: "notice",
      title: "选图后自动适配生产尺寸",
      detail: `系统会按 ${targetLabel} 导出生产图，用户不需要手工凑像素。`,
      chips: [targetLabel, "支持轻微拉伸", "支持裁切补边"],
    };
  }

  const { width, height } = assetDimensions(asset);
  const chips = [targetLabel];
  const targetRatio = surfaceWidth / surfaceHeight;
  const assetRatio = width && height ? width / height : null;
  const ratioDelta = assetRatio ? Math.abs(assetRatio - targetRatio) / targetRatio : null;
  const needsSeamless = mode === "wrap" || Boolean(plan?.layoutPlan?.surfaceAssignments?.some((item) => item.needsSeamless));
  const isSeamless = assetLooksSeamless(asset);

  let tone: SurfaceFitTone = "ready";
  let title = "可以生成生产图";
  let detail = `会把当前素材后处理到 ${targetLabel}。`;

  if (!width || !height) {
    tone = "notice";
    title = "尺寸待识别，系统会按杯型导出";
    detail = `当前素材缺少像素信息，生成生产图时会按 ${targetLabel} 统一适配。`;
    chips.push("尺寸待识别");
  } else if (ratioDelta !== null && ratioDelta <= 0.015) {
    title = "比例接近生产面";
    detail = `素材 ${Math.round(width)}×${Math.round(height)}px，比例接近 ${targetLabel}，只需轻微归一。`;
    chips.push("轻微拉平");
  } else if (ratioDelta !== null && ratioDelta <= 0.08) {
    tone = "notice";
    title = "会自动拉平到生产尺寸";
    detail = `素材 ${Math.round(width)}×${Math.round(height)}px 与杯型差异不大，会通过轻微拉伸/补边适配。`;
    chips.push("轻微拉伸", "补边");
  } else {
    tone = mode === "fit" || mode === "decal" ? "notice" : "warning";
    title = mode === "fit" || mode === "decal" ? "更适合局部放置" : "需要重构比例后再满版";
    detail =
      mode === "fit" || mode === "decal"
        ? `素材 ${Math.round(width)}×${Math.round(height)}px 与杯型比例不同，适合保持完整后局部印刷。`
        : `素材 ${Math.round(width)}×${Math.round(height)}px 与杯型比例差异较大，满版前需要裁切、扩图或重绘。`;
    chips.push(mode === "fit" || mode === "decal" ? "局部贴图" : "裁切/扩图");
  }

  if (needsSeamless) {
    if (isSeamless) {
      chips.push("已校验连续图");
    } else if (assetHasSeamlessCandidate(asset)) {
      tone = "notice";
      title = "已生成连续图，待生产校验";
      detail = "这张图来自连续图能力，预览可以环绕；正式下单前仍要由生产图导出链路校验四边像素和最终尺寸。";
      chips.push("待边缘校验", "不可直接宣称无缝生产");
    } else {
      tone = "warning";
      title = "先做 AI 优化，再用于满版生产";
      detail = "直接把图片绕到杯身一圈，左右边缘通常会断开。请先生成四方连续图，再进入生产图校验。";
      chips.push("需要四方连续", "避免杯身接缝");
    }
  }

  return { tone, title, detail, chips };
}

function SurfaceFitCard({ assessment }: { assessment: SurfaceFitAssessment }) {
  const Icon = assessment.tone === "warning" ? AlertTriangle : ShieldCheck;
  return (
    <section className={`surface-fit-card surface-fit-card--${assessment.tone}`} aria-label="生产尺寸适配">
      <Icon className="surface-fit-card__icon" size={18} />
      <div className="surface-fit-card__body">
        <div className="surface-fit-card__title">
          <span>生产检查</span>
          <strong>{assessment.title}</strong>
        </div>
        <p>{assessment.detail}</p>
        <div className="surface-fit-card__chips">
          {assessment.chips.map((chip) => (
            <em key={chip}>{chip}</em>
          ))}
        </div>
      </div>
    </section>
  );
}

type DesignBasketCardProps = {
  mode: "manual" | "agent";
  itemCount: number;
  quantity: number;
  unitPriceCents: number;
  payableCents: number;
  priceConfigured: boolean;
  discountLabel: string;
  hasDesign: boolean;
  isSubmitting: boolean;
  alreadyAdded: boolean;
  couponCount: number;
  isAuthenticated: boolean;
  onQuantityChange: (quantity: number) => void;
  onConfirm: () => void;
  onContinue: () => void;
  onCheckout: () => void;
};

function DesignBasketCard({
  mode,
  itemCount,
  quantity,
  unitPriceCents,
  payableCents,
  priceConfigured,
  discountLabel,
  hasDesign,
  isSubmitting,
  alreadyAdded,
  couponCount,
  isAuthenticated,
  onQuantityChange,
  onConfirm,
  onContinue,
  onCheckout,
}: DesignBasketCardProps) {
  const isAgentMode = mode === "agent";
  const statusTitle = !priceConfigured
    ? "等待运营设置售价"
    : !hasDesign
    ? isAgentMode
      ? "先让 AI 产出可用方案"
      : "先完成当前设计"
    : alreadyAdded
      ? "这件已在设计篮"
      : "确认后加入设计篮";
  const statusText = !priceConfigured
    ? "当前杯型还没有设置对外售价，设计可以继续，但不能进入结算。"
    : !hasDesign
    ? isAgentMode
      ? "在对话里上传图片或描述需求，采用某个候选后再保存这一件。"
      : "选择素材、调整贴图和底色后，再保存这一件。"
    : alreadyAdded
      ? "可以继续做下一件，或去结算。"
      : itemCount > 0
        ? `设计篮已有 ${itemCount} 件，当前这件确认后一起结算。`
        : "确认当前贴图、底色和数量后，会保存到设计篮。";
  const actionLabel = !priceConfigured
    ? "售价待设置"
    : !hasDesign
    ? isAgentMode
      ? "等待采用候选"
      : "先选择素材"
    : isSubmitting
      ? "正在保存"
      : alreadyAdded
        ? "已加入设计篮"
        : "加入设计篮";

  if (!hasDesign || !priceConfigured) {
    return (
      <section className="design-basket-card design-basket-card--waiting" aria-label="设计篮">
        <div className="design-basket-card__head">
          <div>
            <span>设计篮</span>
            <strong>{statusTitle}</strong>
            <p>{statusText}</p>
          </div>
          <em>{itemCount} 件</em>
        </div>
        <p className="design-basket-note">
          <ShieldCheck size={15} />
          <span>
            {!priceConfigured
              ? "售价和每订单物流费用由运营端统一设置后，才允许进入结算。"
              : isAgentMode
              ? "AI 先在对话里给出候选图和产品预览；你点“采用”后，这里才会出现数量和结算动作。"
              : "先上传图片、从素材库选择，或进入 AI 设计；当前面有素材后再确认数量和结算。"}
          </span>
        </p>
      </section>
    );
  }

  return (
    <section className="design-basket-card" aria-label="设计篮">
      <div className="design-basket-card__head">
        <div>
          <span>设计篮</span>
          <strong>{statusTitle}</strong>
          <p>{statusText}</p>
        </div>
        <em>{itemCount} 件</em>
      </div>

      <div className="design-basket-quantity">
        <div className="design-basket-quantity__label">
          <span>制作数量</span>
          <strong>{quantity} 件</strong>
        </div>
        <div className="design-basket-quantity__options" role="list" aria-label="制作数量">
          {quantityPresets.map((item) => (
            <button
              key={item}
              type="button"
              className={quantity === item ? "active" : ""}
              onClick={() => onQuantityChange(item)}
            >
              {item === 1 ? "1 件试做" : `${item} 件`}
            </button>
          ))}
          <label>
            <span>自定义</span>
            <input
              type="number"
              min="1"
              max="10000"
              value={quantity}
              onChange={(event) => onQuantityChange(Number(event.target.value))}
            />
          </label>
        </div>
      </div>

      <div className="design-basket-price">
        <span>单价 {formatMoney(unitPriceCents)} · {discountLabel}</span>
        <strong>{formatMoney(payableCents)}</strong>
      </div>

      <button className="primary full design-basket-primary" disabled={isSubmitting || alreadyAdded || !hasDesign} onClick={onConfirm}>
        {actionLabel}
        {isAuthenticated && couponCount > 0 && <small>{couponCount} 张产品券可在结算时使用</small>}
      </button>

      {itemCount > 0 && (
        <div className="design-basket-actions">
          <button className="secondary" type="button" onClick={onContinue}>
            继续做下一件
          </button>
          <button className="primary" type="button" onClick={onCheckout}>
            去结算
          </button>
        </div>
      )}

      <p className="design-basket-note">
        <ShieldCheck size={15} />
        <span>结算页再统一校验地址、支付和订单状态。</span>
      </p>
    </section>
  );
}

export default function ProductDesignPage() {
  const { state, dispatch, navigate, activeUserId, isAuthenticated } = useApp();
  const selectedProduct =
    cupProducts.find((product) => product.id === state.selectedProductId) ?? cupProducts[0];
  const designSourceAssets = state.assets.filter((asset) => asset.type !== "product_preview");
  const initialSurfaceName = selectedProduct ? firstReadySurface(selectedProduct)?.name ?? "" : "";
  const initialCraftOption =
    selectedProduct?.craftOptions.find((option) => option.isDefault) ?? selectedProduct?.craftOptions[0] ?? null;
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [selectedSurfaceName, setSelectedSurfaceName] = useState(initialSurfaceName);
  const [surfaceAssetIds, setSurfaceAssetIds] = useState<Record<string, string>>({});
  const [textureLoadState, setTextureLoadState] = useState({ expected: 0, loaded: 0, failedSurfaceNames: [] as string[] });
  const surfaceFileInputRef = useRef<HTMLInputElement | null>(null);
  const agentFileInputRef = useRef<HTMLInputElement | null>(null);
  const agentChatThreadRef = useRef<HTMLDivElement | null>(null);
  const agentPreviousResultCountRef = useRef(0);
  const autoAppliedSelectionRef = useRef("");
  const [surfaceUploadBusy, setSurfaceUploadBusy] = useState(false);
  const [previewGenerated, setPreviewGenerated] = useState(false);
  const [storedPreviewKey, setStoredPreviewKey] = useState("");
  const [previewAssetId, setPreviewAssetId] = useState("");
  const [previewImageUrl, setPreviewImageUrl] = useState("");
  const [notice, setNotice] = useState("");
  const [previewSubmitting, setPreviewSubmitting] = useState(false);
  const [assetModalOpen, setAssetModalOpen] = useState(false);
  const [assetSearch, setAssetSearch] = useState("");
  const [assetTypeFilter, setAssetTypeFilter] = useState<AssetType | "all">("all");
  const [baseColor, setBaseColor] = useState(defaultCupColorOptions[0].value);
  const [selectedCraftKey, setSelectedCraftKey] = useState(initialCraftOption ? craftOptionKey(initialCraftOption) : "");
  const [textureMode, setTextureMode] = useState<TexturePlacementMode>("decal");
  const [textureScale, setTextureScale] = useState(1);
  const [textureOffsetX, setTextureOffsetX] = useState(0);
  const [textureOffsetY, setTextureOffsetY] = useState(0);
  const [seamlessOptimizing, setSeamlessOptimizing] = useState(false);
  const [quickDesignIntake, setQuickDesignIntake] = useState<ProductDesignQuickIntake | null>(null);
  const [quickDesignBusy, setQuickDesignBusy] = useState(false);
  const [salePricesByProduct, setSalePricesByProduct] = useState<Record<string, number>>({});
  const [quantity, setQuantity] = useState(1);
  const [designMode, setDesignMode] = useState<"manual" | "agent">("manual");
  const [agentSession, setAgentSession] = useState<ProductDesignAgentSession | null>(null);
  const [agentInput, setAgentInput] = useState("");
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentBusyText, setAgentBusyText] = useState("");
  const [agentError, setAgentError] = useState("");
  const [agentAttachmentIds, setAgentAttachmentIds] = useState<string[]>([]);
  const [agentUploadBusy, setAgentUploadBusy] = useState(false);
  const [agentInputFocused, setAgentInputFocused] = useState(false);

  useEffect(() => {
    const defaultCraft =
      selectedProduct?.craftOptions.find((option) => option.isDefault) ?? selectedProduct?.craftOptions[0] ?? null;
    const defaultKey = defaultCraft ? craftOptionKey(defaultCraft) : "";
    setSelectedCraftKey((current) =>
      selectedProduct?.craftOptions.some((option) => craftOptionKey(option) === current) ? current : defaultKey
    );
  }, [selectedProduct?.id]);

  const sameStyleWork = state.sameStyleWork?.kind === "产品作品" ? state.sameStyleWork : null;
  const selectedProductSizeLabel = state.selectedProductSizeLabel;
  const selectedSizeByRoute = selectedProductSizeLabel
    ? selectedProduct?.sizes.find((size) => size.label === selectedProductSizeLabel) ?? null
    : null;
  const readySurfaces = designSurfacesForProduct(selectedProduct, selectedProductSizeLabel);
  const fallbackSurface = selectedProduct
    ? selectedSizeByRoute?.surfaces.find((surface) => surface.width && surface.height) ??
      selectedSizeByRoute?.surfaces[0] ??
      firstReadySurface(selectedProduct) ??
      selectedProduct.sizes[0]?.surfaces[0]
    : null;
  const selectedSurface = readySurfaces.find((surface) => surface.name === selectedSurfaceName) ?? fallbackSurface ?? null;
  const selectedSize =
    selectedSizeByRoute ??
    selectedProduct?.sizes.find((size) => size.label === selectedSurface?.sizeLabel) ??
    selectedProduct?.sizes[0] ??
    null;
  const productColorOptions = selectedProduct?.colors?.length ? selectedProduct.colors : defaultCupColorOptions;
  const selectedSurfaceAssetId = selectedSurface?.name ? surfaceAssetIds[selectedSurface.name] ?? "" : "";
  const selectedAsset = selectedSurfaceAssetId ? designSourceAssets.find((asset) => asset.id === selectedSurfaceAssetId) ?? null : null;
  const assignedSurfaceCount = readySurfaces.filter((surface) => Boolean(surfaceAssetIds[surface.name])).length;
  const missingSurfaces = readySurfaces.filter((surface) => !surfaceAssetIds[surface.name]);
  const primaryAssignedEntry =
    readySurfaces
      .map((surface) => {
        const assetId = surfaceAssetIds[surface.name];
        const asset = assetId ? designSourceAssets.find((item) => item.id === assetId) ?? null : null;
        return asset ? { surface, asset } : null;
      })
      .find(Boolean) ?? null;
  const primaryAssignedAsset = primaryAssignedEntry?.asset ?? null;
  const primaryAssignedSurface = primaryAssignedEntry?.surface ?? null;
  const draftAsset = selectedAsset ?? primaryAssignedAsset;
  const draftSurface = selectedAsset ? selectedSurface : primaryAssignedSurface ?? selectedSurface;
  const product3DModelFile = selectedSize?.modelFile || selectedProduct?.modelFile || "";
  const selectedProductPhoto = product3DModelFile
    ? `/models/catalog-renders/${product3DModelFile.replace(/\.glb$/i, ".png")}`
    : "";
  const surfaceTextureAssignments = readySurfaces
    .map((surface) => {
      const assetId = surfaceAssetIds[surface.name];
      const asset = assetId ? designSourceAssets.find((item) => item.id === assetId) : null;
      if (!asset) return null;
      return {
        surfaceName: surface.name,
        surfaceLabel: surface.label,
        // The 3D engine reads an authenticated same-origin preview. Browser <img>
        // previews can use OSS directly, but WebGL texture loading cannot rely on OSS CORS.
        textureUrl: isLocalOnlyAsset(asset)
          ? asset.url || asset.thumbnailUrl
          : getClientAssetPreviewUrl(asset.id, state.currentUser?.id || ""),
        textureLabel: displayAssetTitle(asset.title),
        printWidth: surface.width,
        printHeight: surface.height,
        uvCalibration: modelUvCalibrationForSurface(product3DModelFile, surface.name),
      };
    })
    .filter(
      (item): item is {
        surfaceName: string;
        surfaceLabel: string;
        textureUrl: string;
        textureLabel: string;
        printWidth: number | null;
        printHeight: number | null;
        uvCalibration: ReturnType<typeof modelUvCalibrationForSurface>;
      } => Boolean(item)
    );
  const surfaceTextureAssignmentKey = surfaceTextureAssignments
    .map((item) => `${item.surfaceName}:${item.textureUrl}`)
    .join("|");
  const product3DModelUrl = selectedProduct?.category === "杯子" && product3DModelFile ? `/models/product-3d/${product3DModelFile}` : null;
  const selectedBaseColor = productColorOptions.find((option) => option.value === baseColor) ?? productColorOptions[0] ?? defaultCupColorOptions[0];
  const productCraftOptions = selectedProduct?.craftOptions ?? [];
  const selectedCraft =
    productCraftOptions.find((option) => craftOptionKey(option) === selectedCraftKey) ??
    productCraftOptions.find((option) => option.isDefault) ??
    productCraftOptions[0] ??
    null;
  const selectedTextureMode = textureModeOptions.find((option) => option.id === textureMode) ?? textureModeOptions[0];
  const quantityNumber = Math.max(1, Math.min(10000, Math.round(Number(quantity) || 1)));
  const unitPriceCents = selectedProduct ? salePricesByProduct[selectedProduct.id] ?? 0 : 0;
  const priceConfigured = unitPriceCents > 0;
  const subtotalCents = unitPriceCents * quantityNumber;
  const discountRate = quantityDiscountRate(quantityNumber);
  const payableCents = Math.round(subtotalCents * discountRate);
  const quantityDiscountLabel = discountRate < 1 ? `${Math.round((1 - discountRate) * 100)}% 批量优惠` : "单件试做价";
  const designKey = [
    baseColor,
    textureMode,
    textureScale.toFixed(2),
    textureOffsetX.toFixed(2),
    textureOffsetY.toFixed(2),
    selectedCraft ? craftOptionKey(selectedCraft) : "craft",
    draftSurface?.name ?? "surface",
    selectedSurfaceAssetId || primaryAssignedAsset?.id || "asset",
  ].join(":");
  const designConfig = {
    designKey,
    baseColor,
    baseColorCode: selectedBaseColor.code,
    baseColorLabel: selectedBaseColor.label,
    textureMode,
    textureModeLabel: selectedTextureMode.title,
    textureScale,
    textureOffsetX,
    textureOffsetY,
    surfaceName: draftSurface?.name ?? null,
    surfaceLabel: draftSurface?.label ?? null,
    surfaceWidth: draftSurface?.width ?? null,
    surfaceHeight: draftSurface?.height ?? null,
    surfaceDpi: draftSurface?.dpi ?? null,
    surfaceViewId: draftSurface?.viewId ?? null,
    sizeLabel: draftSurface?.sizeLabel ?? selectedSize?.label ?? null,
    surfaceAssignments: surfaceAssetIds,
    productTemplateId: selectedProduct?.id ?? null,
    productBodyCode: selectedProduct?.bodyCode ?? null,
    firstCraft: selectedCraft?.firstCraft ?? null,
    firstCraftName: selectedCraft?.firstCraftName ?? null,
    secondCraft: selectedCraft?.secondCraft ?? null,
    secondCraftName: selectedCraft?.secondCraftName ?? null,
  };
  const texturePreviewReady =
    !product3DModelUrl ||
    !surfaceTextureAssignments.length ||
    (textureLoadState.expected === surfaceTextureAssignments.length &&
      textureLoadState.loaded === surfaceTextureAssignments.length &&
      textureLoadState.failedSurfaceNames.length === 0);
  const failedTextureSurfaces = readySurfaces.filter((surface) => textureLoadState.failedSurfaceNames.includes(surface.name));
  const hasTextureLoadFailure = failedTextureSurfaces.length > 0;
  const canConfirmDesign = Boolean(selectedProduct && draftAsset && priceConfigured && texturePreviewReady);
  const currentPreviewKey = selectedProduct && draftAsset ? `${selectedProduct.id}:${draftAsset.id}:${designKey}` : "";
  const currentPreviewAlreadyGenerated = Boolean(
    currentPreviewKey && storedPreviewKey === currentPreviewKey && previewAssetId
  );
  const orderDraftCount = state.orderDrafts.length;
  const currentDesignAlreadyInBasket = state.orderDrafts.some((draft) => {
    const config = draft.designConfig;
    if (typeof config.designKey === "string") {
      return draft.productId === selectedProduct?.id && draft.quantity === quantityNumber && config.designKey === designKey;
    }
    return (
      draft.productId === selectedProduct?.id &&
      draft.sourceAssetId === draftAsset?.id &&
      draft.quantity === quantityNumber &&
      config.baseColor === baseColor &&
      config.textureMode === textureMode &&
      config.surfaceName === (draftSurface?.name ?? null) &&
      config.textureScale === textureScale &&
      config.textureOffsetX === textureOffsetX &&
      config.textureOffsetY === textureOffsetY
    );
  });
  const filteredAssets = designSourceAssets.filter((asset) => {
    const matchesType = assetTypeFilter === "all" || asset.type === assetTypeFilter;
    const keyword = assetSearch.trim().toLowerCase();
    const matchesKeyword =
      !keyword ||
      [asset.title, asset.source, asset.type, String(asset.metadata?.["productName"] ?? "")]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    return matchesType && matchesKeyword;
  });
  const quickDesignAssets = [...designSourceAssets]
    .sort((a, b) => Date.parse(b.createdAt || "") - Date.parse(a.createdAt || ""))
    .slice(0, 6);
  const productDesignManifest = {
    manifestVersion: "product-design-agent-mvp",
    productId: selectedProduct?.id ?? "",
    productName: selectedProduct?.name ?? "",
    templateNo: selectedProduct?.id ?? "",
    bodyCode: selectedProduct?.bodyCode ?? "",
    category: selectedProduct?.category ?? "杯子",
    sizeLabel: selectedSize?.label ?? "",
    material: selectedProduct?.tags.find((tag) => tag.includes("不锈钢") || tag.includes("塑料")) ?? "不锈钢",
    colors: productColorOptions.map((option) => ({ code: option.code, label: option.label, value: option.value })),
    craftOptions: productCraftOptions.map((option) => ({
      name: [option.firstCraftName, option.secondCraftName].filter(Boolean).join(" · "),
      firstCraft: option.firstCraft,
      secondCraft: option.secondCraft,
      isDefault: option.isDefault,
    })),
    surfaces: readySurfaces.map((surface) => ({
      name: surface.name,
      label: surface.label,
      sizeLabel: surface.sizeLabel,
      viewId: surface.viewId,
      width: surface.width,
      height: surface.height,
      dpi: surface.dpi,
      role: surface.name === "handle" ? "decal" : "wrap",
      supportsWrap: surface.name !== "handle",
      supportsHandleTexture: surface.name === "handle",
      safeArea: "待供应链补齐",
      bleed: "待供应链补齐",
    })),
    model: {
      modelFile: product3DModelFile,
      previewModelUrl: product3DModelUrl,
      materialSlots: selectedProduct?.materialSlots ?? [],
    },
  };
  const agentSourceAssetIds = Array.from(new Set(agentAttachmentIds));
  const agentAttachedAssets = agentAttachmentIds
    .map((assetId) => designSourceAssets.find((asset) => asset.id === assetId))
    .filter(Boolean) as AssetItem[];
  const agentResultAssets = Array.from(
    new Map(
      [
        ...(agentSession?.resultAssets ?? []),
        ...(agentSession?.resultAssetIds ?? []).map((assetId) => state.assets.find((asset) => asset.id === assetId)).filter(Boolean) as AssetItem[],
      ].map((asset) => [asset.id, asset])
    ).values()
  );
  const agentHasReferenceContext =
    agentAttachmentIds.length > 0 ||
    Boolean(agentSession?.sourceAssetIds?.length) ||
    agentResultAssets.length > 0;
  const visibleAgentStarterPrompts = agentHasReferenceContext ? agentImageStarterPrompts : agentTextStarterPrompts;
  const readySurfaceNames = readySurfaces.map((surface) => surface.name).join("|");
  const designAssetIds = designSourceAssets.map((asset) => asset.id).join("|");
  const surfaceAssignmentKey = Object.entries(surfaceAssetIds)
    .map(([surfaceName, assetId]) => `${surfaceName}:${assetId}`)
    .join("|");

  const showNotice = (msg: string) => {
    setNotice(msg);
    window.setTimeout(() => setNotice(""), 2600);
  };

  useEffect(() => {
    if (!isAuthenticated || agentSession || agentInput.trim() || !selectedProduct) return;
    try {
      const raw = window.sessionStorage.getItem(pendingAgentDraftKey);
      if (!raw) return;
      const draft = JSON.parse(raw) as { productId?: string; message?: string };
      if (draft.productId !== selectedProduct.id || !draft.message?.trim()) return;
      setDesignMode("agent");
      setAgentInput(draft.message.trim());
      window.sessionStorage.removeItem(pendingAgentDraftKey);
      showNotice("已恢复刚才的设计描述，请确认后发送。");
    } catch {
      window.sessionStorage.removeItem(pendingAgentDraftKey);
    }
  }, [agentInput, agentSession, isAuthenticated, selectedProduct]);

  const handleTextureLoadStateChange = useCallback(
    (next: { expected: number; loaded: number; failedSurfaceNames: string[] }) => {
      setTextureLoadState((current) => {
        const unchanged =
          current.expected === next.expected &&
          current.loaded === next.loaded &&
          current.failedSurfaceNames.join("|") === next.failedSurfaceNames.join("|");
        return unchanged ? current : next;
      });
    },
    []
  );

  useEffect(() => {
    setTextureLoadState({ expected: surfaceTextureAssignments.length, loaded: 0, failedSurfaceNames: [] });
  }, [surfaceTextureAssignmentKey]);

  useEffect(() => {
    let cancelled = false;
    void getClientProductPricing()
      .then((items) => {
        if (cancelled) return;
        const next: Record<string, number> = {};
        items.forEach((item) => {
          if (typeof item.salePriceCents === "number" && item.salePriceCents > 0) {
            next[item.productId] = item.salePriceCents;
          }
        });
        setSalePricesByProduct(next);
      })
      .catch(() => {
        if (!cancelled) setSalePricesByProduct({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (designMode !== "agent") return;
    const timer = window.setTimeout(() => {
      const container = agentChatThreadRef.current;
      if (!container) return;
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }, 80);
    return () => window.clearTimeout(timer);
  }, [designMode, agentSession?.messages.length, agentSession?.status, agentBusy, agentResultAssets.length]);

  useEffect(() => {
    if (designMode !== "agent") {
      agentPreviousResultCountRef.current = 0;
      return;
    }
    const resultCount = agentResultAssets.length;
    if (resultCount > agentPreviousResultCountRef.current) {
      showNotice(`AI 已生成 ${resultCount} 张候选图，结果在对话里。`);
    }
    agentPreviousResultCountRef.current = resultCount;
  }, [designMode, agentResultAssets.length]);

  const resetPreviewState = () => {
    setPreviewGenerated(false);
    setPreviewAssetId("");
    setPreviewImageUrl("");
    setStoredPreviewKey("");
  };

  useEffect(() => {
    if (!readySurfaces.length) {
      if (selectedSurfaceName) setSelectedSurfaceName("");
      return;
    }
    if (!readySurfaces.some((surface) => surface.name === selectedSurfaceName)) {
      setSelectedSurfaceName(readySurfaces[0].name);
      resetPreviewState();
    }
  }, [readySurfaceNames, selectedSurfaceName]);

  useEffect(() => {
    const availableAssetIds = new Set(designSourceAssets.map((asset) => asset.id));
    if (selectedAssetId && !availableAssetIds.has(selectedAssetId)) {
      setSelectedAssetId("");
      resetPreviewState();
    }
    setSurfaceAssetIds((current) => {
      const next = Object.fromEntries(Object.entries(current).filter(([, assetId]) => availableAssetIds.has(assetId)));
      if (Object.keys(next).length !== Object.keys(current).length) {
        resetPreviewState();
        return next;
      }
      return current;
    });
  }, [designAssetIds, selectedAssetId]);

  useEffect(() => {
    setSurfaceAssetIds({});
    setSelectedAssetId("");
    setSelectedSurfaceName(readySurfaces[0]?.name ?? "");
    setBaseColor((current) =>
      productColorOptions.some((option) => option.value === current)
        ? current
        : productColorOptions[0]?.value ?? defaultCupColorOptions[0].value
    );
    setAgentSession(null);
    setAgentInput("");
    setAgentError("");
    setAgentAttachmentIds([]);
    setQuickDesignIntake(null);
    setDesignMode("manual");
    resetPreviewState();
  }, [selectedProduct?.id]);

  useEffect(() => {
    if (!isAuthenticated || !selectedProduct) return;
    let sessionId = "";
    try {
      sessionId = window.localStorage.getItem(resumeAgentSessionKey) || "";
    } catch {
      return;
    }
    if (!sessionId) return;
    const cached = state.designAgentSessions.find((item) => item.sessionId === sessionId);
    if (cached && cached.productId !== selectedProduct.id) return;
    let cancelled = false;
    const restoreSession = async () => {
      try {
        const session = cached || await getProductDesignAgentSession({ userId: activeUserId, sessionId });
        if (cancelled || session.productId !== selectedProduct.id) return;
        setAgentSession(session);
        setDesignMode("agent");
        upsertAgentAssets(session.resultAssets);
        if (session.previewAsset) upsertAgentAssets([session.previewAsset]);
        dispatch({ type: "UPSERT_DESIGN_AGENT_SESSION", session });
        try {
          window.localStorage.removeItem(resumeAgentSessionKey);
        } catch {
          // Ignore storage failures.
        }
      } catch (error) {
        if (!cancelled) setAgentError(error instanceof Error ? error.message : "恢复 AI 设计任务失败。");
      }
    };
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [activeUserId, isAuthenticated, selectedProduct?.id, state.designAgentSessions]);

  const applyAssetToSurface = (assetId: string, surfaceName?: string) => {
    const targetSurfaceName = surfaceName || selectedSurface?.name || readySurfaces[0]?.name || "";
    setSelectedAssetId(assetId);
    if (targetSurfaceName) {
      setSelectedSurfaceName(targetSurfaceName);
      setSurfaceAssetIds((current) => ({ ...current, [targetSurfaceName]: assetId }));
    }
    setQuickDesignIntake(null);
    resetPreviewState();
  };

  const fillMissingSurfaces = () => {
    const assetId = selectedAsset?.id || primaryAssignedAsset?.id || "";
    if (!assetId || !missingSurfaces.length) return;
    setSurfaceAssetIds((current) => {
      const next = { ...current };
      missingSurfaces.forEach((surface) => {
        next[surface.name] = assetId;
      });
      return next;
    });
    setSelectedAssetId(assetId);
    setQuickDesignIntake(null);
    resetPreviewState();
    showNotice(`已按各设计面的生产尺寸补齐 ${missingSurfaces.length} 个面。`);
  };

  const selectAssetForSurface = (assetId: string) => {
    applyAssetToSurface(assetId);
  };

  const clearSelectedSurfaceAsset = () => {
    const targetSurfaceName = selectedSurface?.name;
    if (!targetSurfaceName || !surfaceAssetIds[targetSurfaceName]) return;
    setSurfaceAssetIds((current) => {
      const next = { ...current };
      delete next[targetSurfaceName];
      return next;
    });
    setSelectedAssetId("");
    setQuickDesignIntake(null);
    resetPreviewState();
    showNotice(`已移除${selectedSurface?.label ?? "当前设计面"}的图案。`);
  };

  useEffect(() => {
    // A pure-text Agent request must start from a blank product. Reapplying a
    // previous manual asset here makes the preview look like AI generated it.
    if (designMode === "agent" && !agentHasReferenceContext) return;
    if (surfaceAssignmentKey) return;
    let pendingAssetId = "";
    try {
      pendingAssetId = window.sessionStorage.getItem(pendingProductAssetKey) || "";
    } catch {
      pendingAssetId = "";
    }
    if (!pendingAssetId) {
      try {
        pendingAssetId = window.localStorage.getItem(pendingProductAssetKey) || "";
      } catch {
        pendingAssetId = "";
      }
    }
    const selectedId = [state.pendingProductDesignAssetId || "", pendingAssetId, ...state.selectedAssetIds].find((assetId) =>
      Boolean(assetId) && designSourceAssets.some((asset) => asset.id === assetId)
    );
    const targetSurfaceName = readySurfaces[0]?.name || selectedSurface?.name || "";
    if (!selectedId || !targetSurfaceName) return;
    const applyKey = `${selectedProduct?.id ?? "product"}:${targetSurfaceName}:${selectedId}`;
    if (autoAppliedSelectionRef.current === applyKey && surfaceAssignmentKey) return;
    autoAppliedSelectionRef.current = applyKey;
    setSelectedAssetId(selectedId);
    setSelectedSurfaceName(targetSurfaceName);
    setSurfaceAssetIds({ [targetSurfaceName]: selectedId });
    resetPreviewState();
    if (state.pendingProductDesignAssetId === selectedId) {
      dispatch({ type: "SET_PENDING_PRODUCT_DESIGN_ASSET", id: null });
    }
    if (pendingAssetId === selectedId) {
      try {
        window.sessionStorage.removeItem(pendingProductAssetKey);
      } catch {
        // Ignore storage failures.
      }
      try {
        window.localStorage.removeItem(pendingProductAssetKey);
      } catch {
        // Ignore storage failures.
      }
    }
  }, [state.pendingProductDesignAssetId, state.selectedAssetIds, designAssetIds, readySurfaceNames, surfaceAssignmentKey, selectedProduct?.id, selectedSurface?.name, designMode, agentHasReferenceContext]);

  const upsertAgentAssets = (assets?: AssetItem[]) => {
    if (!assets?.length) return;
    const existingIds = new Set(state.assets.map((asset) => asset.id));
    const newAssets = assets.filter((asset) => !existingIds.has(asset.id));
    if (newAssets.length) dispatch({ type: "ADD_ASSETS", assets: newAssets });
  };

  const rememberAgentSession = (session: ProductDesignAgentSession) => {
    setAgentSession(session);
    dispatch({ type: "UPSERT_DESIGN_AGENT_SESSION", session });
  };

  useEffect(() => {
    if (!agentSession || agentSession.status !== "executing") return;
    let cancelled = false;
    const refreshSession = async () => {
      try {
        const latest = await getProductDesignAgentSession({
          userId: activeUserId,
          sessionId: agentSession.sessionId,
        });
        if (cancelled) return;
        upsertAgentAssets(latest.resultAssets);
        if (latest.previewAsset) upsertAgentAssets([latest.previewAsset]);
        rememberAgentSession(latest);
        if (latest.status !== "executing") {
          setAgentBusy(false);
          setAgentBusyText("");
        }
      } catch (error) {
        if (!cancelled) {
          setAgentError(error instanceof Error ? error.message : "刷新 AI 设计结果失败。");
        }
      }
    };
    const timer = window.setInterval(() => void refreshSession(), 5000);
    void refreshSession();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [agentSession?.sessionId, agentSession?.status, activeUserId]);

  const handleAgentFilesSelected = async (files: File[]) => {
    if (!files.length || agentUploadBusy) return;
    if (!isAuthenticated) {
      showNotice("请先登录，AI 对话图片会保存到你的素材库。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    setAgentUploadBusy(true);
    setAgentError("");
    try {
      const uploads = await Promise.all(files.slice(0, 6).map((file) => uploadClientImage(file, activeUserId)));
      const createdAssets = await Promise.all(
        uploads.map((upload, index) => {
          const file = files[index];
          const safeName = file.name.replace(/\.[^.]+$/, "") || "对话图片";
          return createClientAsset({
            userId: activeUserId,
            type: "original",
            title: safeName,
            url: upload.url,
            thumbnailUrl: upload.url,
            source: "AI 设计对话上传",
            visibility: "private",
            metadata: {
              objectKey: upload.objectKey ?? null,
              originalFileName: file.name,
              uploadSource: "product-design-agent-chat",
            },
          });
        })
      );
      dispatch({ type: "ADD_ASSETS", assets: createdAssets });
      setAgentAttachmentIds((current) => Array.from(new Set([...current, ...createdAssets.map((asset) => asset.id)])));
      showNotice(`已添加 ${createdAssets.length} 张图片，可以继续描述你想要的效果。`);
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "AI 对话图片上传失败，请稍后重试";
      setAgentError(messageText);
      showNotice(messageText);
    } finally {
      setAgentUploadBusy(false);
    }
  };

  const submitAgentMessage = async (messageOverride?: string, assetIdsOverride?: string[]) => {
    if (!selectedProduct) {
      showNotice("请先选择商品。");
      return;
    }
    const sourceAssetIds = assetIdsOverride ?? agentSourceAssetIds;
    const message = (messageOverride || agentInput).trim() || (sourceAssetIds.length ? "请把我上传的图片作为参考，重新设计一套适合这款杯子的方案，不要直接把原图贴上去。" : "");
    if (!isAuthenticated) {
      if (message) {
        window.sessionStorage.setItem(
          pendingAgentDraftKey,
          JSON.stringify({ productId: selectedProduct.id, message, savedAt: new Date().toISOString() })
        );
      }
      showNotice("请先登录，AI 设计会保存你的会话和素材。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    if (!message) {
      showNotice("先告诉 AI 你想怎么设计。");
      return;
    }
    if (!agentSession && sourceAssetIds.length === 0) {
      setSelectedAssetId("");
      setSurfaceAssetIds({});
      resetPreviewState();
    }
    setAgentBusy(true);
    setAgentBusyText("AI 正在规划这款杯子的设计方案，通常需要 20-60 秒。");
    setAgentError("");
    try {
      const session = agentSession
        ? await sendProductDesignAgentMessage({
            userId: activeUserId,
            sessionId: agentSession.sessionId,
            message,
            sourceAssetIds: agentSourceAssetIds,
          })
        : await createProductDesignAgentSession({
            userId: activeUserId,
            productId: selectedProduct.id,
            productName: selectedProduct.name,
            productContext: productDesignManifest,
            sourceAssetIds,
            message,
          });
      upsertAgentAssets(session.resultAssets);
      if (session.previewAsset) upsertAgentAssets([session.previewAsset]);
      rememberAgentSession(session);
      setAgentInput("");
      setAgentAttachmentIds([]);
      setDesignMode("agent");
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "AI 设计助手暂时不可用。";
      setAgentError(messageText);
      showNotice(messageText);
    } finally {
      setAgentBusy(false);
      setAgentBusyText("");
    }
  };

  const startQuickDesign = async () => {
    if (!selectedProduct) {
      showNotice("请先选择商品。");
      return;
    }
    if (!isAuthenticated) {
      showNotice("请先登录，AI 设计建议会结合你的素材库保存。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    if (!selectedAsset) {
      setDesignMode("agent");
      setSelectedAssetId("");
      setSurfaceAssetIds({});
      resetPreviewState();
      setAgentInput("我还没有图片，想为这款杯子设计一套方案。");
      showNotice("没有图片时，直接告诉 AI 你想做什么就可以。");
      return;
    }
    if (quickDesignBusy) return;
    setQuickDesignBusy(true);
    try {
      const intake = await createProductDesignQuickIntake({
        userId: activeUserId,
        productId: selectedProduct.id,
        productName: selectedProduct.name,
        productContext: productDesignManifest,
        sourceAssetIds: [selectedAsset.id],
        message: "请先看这张图，结合当前杯型给出最适合的可生产设计方式。用户希望少做选择，优先给一个明确建议。",
      });
      setQuickDesignIntake(intake);
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "暂时无法识别图片，请稍后重试。");
    } finally {
      setQuickDesignBusy(false);
    }
  };

  const applyQuickDesignRecommendation = async () => {
    if (!quickDesignIntake || !selectedAsset) return;
    if (seamlessOptimizing || agentBusy) return;
    const { plan, recommendation } = quickDesignIntake;
    if (recommendation.suggestedMode) {
      setTextureMode(recommendation.suggestedMode);
      setTextureScale(recommendation.suggestedMode === "decal" ? 1.45 : 1);
      setTextureOffsetX(0);
      setTextureOffsetY(0);
    }
    resetPreviewState();

    if (plan.intent === "print_as_is" || plan.intent === "clean_and_print") {
      showNotice(plan.intent === "clean_and_print" ? "已按建议放入设计面，可继续微调位置后生成预览。" : "已按建议使用局部贴图，可继续微调位置后生成预览。");
      return;
    }
    if (plan.intent === "make_seamless_wrap") {
      await optimizeForSeamlessProduction();
      return;
    }

    setAgentAttachmentIds([selectedAsset.id]);
    setDesignMode("agent");
    const message = plan.intent === "clarify"
      ? "我想继续设计这张图片。请先问我一个最关键的问题，再给我可生产的方案。"
      : `请按刚才识图建议继续完成这张图的设计：${plan.summaryForUser}`;
    void submitAgentMessage(message, [selectedAsset.id]);
  };

  const handleConfirmAgentPlan = async (planId?: string | null) => {
    const plan = planId ? agentPlanForMessage(agentSession, planId) : latestAgentPlan(agentSession);
    if (!agentSession || !plan) {
      showNotice("请先生成设计方案。");
      return;
    }
    setAgentBusy(true);
    setAgentBusyText("正在生成阶段结果，完成后会直接出现在对话里。");
    setAgentError("");
    try {
      const response = await confirmProductDesignAgentPlan({
        userId: activeUserId,
        sessionId: agentSession.sessionId,
        planId: plan.planId,
      });
      if (response.wallet) {
        dispatch({ type: "SET_WALLET", wallet: response.wallet });
      }
      upsertAgentAssets(response.resultAssets);
      upsertAgentAssets(response.session.resultAssets);
      rememberAgentSession(response.session);
      if (response.status === "failed") {
        setAgentError(response.message || "执行设计方案失败。");
        showNotice(response.message || "执行设计方案失败。");
      } else if (response.status === "running" || response.session.status === "executing") {
        showNotice(response.message || "设计任务已提交，结果会继续回到对话里。");
      } else {
        showNotice("阶段结果已生成，可以采用为当前产品设计。");
      }
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "执行设计方案失败。";
      setAgentError(messageText);
      showNotice(messageText);
    } finally {
      setAgentBusy(false);
      setAgentBusyText("");
    }
  };

  const agentPlacementMode = (plan?: ProductDesignAgentPlan | null): TexturePlacementMode => {
    const assignmentMode = plan?.layoutPlan?.surfaceAssignments?.[0]?.mode;
    if (assignmentMode === "wrap" || assignmentMode === "fit" || assignmentMode === "cover" || assignmentMode === "decal") {
      return assignmentMode;
    }
    if (plan?.intent === "make_seamless_wrap" || plan?.intent === "extract_pattern" || plan?.intent === "generate_variations") return "wrap";
    if (plan?.intent === "print_as_is" || plan?.intent === "clean_and_print") return "fit";
    return textureMode;
  };

  const agentPlacementSurface = (plan?: ProductDesignAgentPlan | null) => {
    const assignmentSurfaceId = plan?.layoutPlan?.surfaceAssignments?.[0]?.surfaceId;
    if (assignmentSurfaceId) {
      const plannedSurface = readySurfaces.find((surface) => surface.name === assignmentSurfaceId);
      if (plannedSurface) return plannedSurface;
    }
    return readySurfaces.find((surface) => surface.name !== "handle") || selectedSurface || readySurfaces[0];
  };

  const currentAgentPlan = latestAgentPlan(agentSession);
  const activePlacementMode = designMode === "agent" ? agentPlacementMode(currentAgentPlan) : textureMode;
  const surfaceFitAssessment = assessSurfaceFit({
    asset: draftAsset,
    surface: draftSurface,
    mode: activePlacementMode,
    plan: currentAgentPlan,
  });

  const optimizeForSeamlessProduction = async () => {
    if (!draftAsset || !draftSurface || !selectedProduct || !draftSurface.width || !draftSurface.height) {
      showNotice("先选择一张图片和可用设计面，再进行 AI 优化。");
      return;
    }
    if (!isAuthenticated) {
      showNotice("请先登录，AI 优化结果会保存到你的素材库。");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    if (seamlessOptimizing) return;

    setSeamlessOptimizing(true);
    try {
      const submitted = await submitBusinessRun("/api/business/seamless/runs", {
        imageUrl: draftAsset.url,
        prompt: "将输入图片整理为上下左右均可无缝拼接的四方连续图。保留主要花纹、色彩和密度；不要保留拍摄背景、产品轮廓或透视。",
        width: draftSurface.width,
        height: draftSurface.height,
        inputs: {
          imageUrl: draftAsset.url,
          patternType: "seamless",
          mode: "seamless",
          width: draftSurface.width,
          height: draftSurface.height,
          productId: selectedProduct.id,
          surfaceName: draftSurface.name,
          dpi: draftSurface.dpi ?? 150,
          designIntent: "production-seamless-source",
        },
        source: "client-product-design",
        userId: activeUserId,
        clientRequestId: `seamless-${selectedProduct.id}-${Date.now()}`,
      });
      if (!submitted.ok || !submitted.runId) {
        throw new Error(submitted.error || "四方连续任务未能提交。");
      }

      showNotice("AI 优化已提交，正在生成连续图。");
      const deadline = Date.now() + 8 * 60 * 1000;
      let latest = submitted;
      while (Date.now() < deadline) {
        await new Promise((resolve) => window.setTimeout(resolve, 3500));
        latest = await getBusinessRun(submitted.runId);
        if (!latest.ok) throw new Error(latest.error || "连续图任务失败。");
        if (latest.imageUrls.length > 0) break;
        if (["failed", "cancelled"].includes(String(latest.status || "").toLowerCase())) {
          throw new Error("连续图任务未成功完成，请在任务中心查看原因。");
        }
      }
      const imageUrl = latest.imageUrls[0];
      if (!imageUrl) {
        throw new Error("连续图仍在队列中，稍后可在任务中心继续查看。");
      }
      const asset = await createVerifiedSeamlessArtwork({
        userId: activeUserId,
        sourceUrl: imageUrl,
        sourceAssetId: draftAsset.id,
        businessRunId: submitted.runId,
        title: `${draftAsset.title} · AI 四方连续`,
        width: draftSurface.width,
        height: draftSurface.height,
        dpi: draftSurface.dpi ?? 150,
      });
      dispatch({ type: "ADD_ASSETS", assets: [asset] });
      applyAssetToSurface(asset.id, draftSurface.name);
      setTextureMode("wrap");
      setTextureScale(1);
      setTextureOffsetX(0);
      setTextureOffsetY(0);
      resetPreviewState();
      showNotice("已应用 AI 连续图，并完成生产图边缘像素校验。");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "AI 优化失败，请稍后重试。");
    } finally {
      setSeamlessOptimizing(false);
    }
  };

  const handleUseAgentAsset = async (asset: AssetItem, surfaceName?: string, mode?: TexturePlacementMode) => {
    upsertAgentAssets([asset]);
    const plan = currentAgentPlan;
    const targetSurface = readySurfaces.find((surface) => surface.name === surfaceName) || agentPlacementSurface(plan);
    const targetMode = mode || agentPlacementMode(plan);
    applyAssetToSurface(asset.id, targetSurface?.name);
    setTextureMode(targetMode);
    const assignment = plan?.layoutPlan?.surfaceAssignments?.[0];
    if (typeof assignment?.scale === "number") setTextureScale(assignment.scale);
    if (assignment?.position && typeof assignment.position.x === "number") setTextureOffsetX(assignment.position.x);
    if (assignment?.position && typeof assignment.position.y === "number") setTextureOffsetY(assignment.position.y);
    if (targetMode === "wrap") {
      setTextureScale(1);
      setTextureOffsetX(0);
      setTextureOffsetY(0);
    }
    if (!agentSession || !targetSurface) return;
    try {
      const session = await confirmProductDesignAgentStep({
        userId: activeUserId,
        sessionId: agentSession.sessionId,
        stepId: latestAgentPlan(agentSession)?.steps?.find((step) => step.status === "completed")?.stepId || "s2",
        assetId: asset.id,
        surfaceId: targetSurface.name,
        surfaceLabel: targetSurface.label,
        mode: targetMode,
        fullBleed: targetMode === "wrap",
        needsSeamless: targetMode === "wrap",
        scale: textureScale,
        position: { x: textureOffsetX, y: textureOffsetY },
      });
      rememberAgentSession(session);
      showNotice("已采用为当前产品设计，左侧预览会同步更新。");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "应用 AI 结果失败。");
    }
  };

  const handleApplyAgentPreview = async () => {
    if (!agentSession) {
      showNotice("请先和 AI 生成一套设计。");
      return null;
    }
    setAgentBusy(true);
    try {
      const response = await applyProductDesignAgentPreview({
        userId: activeUserId,
        sessionId: agentSession.sessionId,
        assetId: draftAsset?.id || agentResultAssets[0]?.id || null,
        designConfig,
      });
      upsertAgentAssets([response.previewAsset]);
      if (response.session.resultAssets) upsertAgentAssets(response.session.resultAssets);
      rememberAgentSession(response.session);
      setPreviewAssetId(response.previewAsset.id);
      setPreviewImageUrl(response.previewAsset.url || response.previewAsset.thumbnailUrl || selectedProductPhoto);
      setStoredPreviewKey(currentPreviewKey || `${selectedProduct?.id}:${response.previewAsset.id}:${designKey}`);
      setPreviewGenerated(true);
      showNotice("AI 预览已生成，可以放入设计篮。");
      return response.previewAsset;
    } catch (error) {
      const messageText = error instanceof Error ? error.message : "生成 AI 产品预览失败。";
      setAgentError(messageText);
      showNotice(messageText);
      return null;
    } finally {
      setAgentBusy(false);
    }
  };

  const handleSurfaceFilesSelected = async (files: File[]) => {
    if (!files.length || surfaceUploadBusy) return;
    if (!isAuthenticated) {
      showNotice("请先登录，上传到设计面的图片会保存到你的素材库。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    setSurfaceUploadBusy(true);
    try {
      const uploads = await Promise.all(files.slice(0, 8).map((file) => uploadClientImage(file, activeUserId)));
      const createdAssets = await Promise.all(
        uploads.map((upload, index) => {
          const file = files[index];
          const safeName = file.name.replace(/\.[^.]+$/, "") || "上传图片";
          return createClientAsset({
            userId: activeUserId,
            type: "original",
            title: safeName,
            url: upload.url,
            thumbnailUrl: upload.url,
            source: "产品设计上传",
            visibility: "private",
            metadata: {
              objectKey: upload.objectKey ?? null,
              originalFileName: file.name,
              uploadSource: "product-design-surface",
            },
          });
        })
      );
      dispatch({ type: "ADD_ASSETS", assets: createdAssets });
      if (createdAssets[0]) selectAssetForSurface(createdAssets[0].id);
      showNotice(`已上传 ${createdAssets.length} 张图片到素材库，并应用到当前设计面`);
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "图片上传失败，请稍后重试");
    } finally {
      setSurfaceUploadBusy(false);
    }
  };

  const ensurePreviewAsset = async (): Promise<{ assetId: string; imageUrl: string } | null> => {
    if (!isAuthenticated) {
      showNotice("请先登录，产品预览会保存到你的素材库。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return null;
    }
    if (!selectedProduct) {
      showNotice("请先选择一款杯子");
      return null;
    }
    if (!draftAsset) {
      showNotice("请先选择一张素材");
      return null;
    }
    if (!draftSurface?.width || !draftSurface.height) {
      showNotice("该杯型设计面尺寸待补充，暂不能放入设计篮。");
      return null;
    }
    const previewKey = currentPreviewKey;
    if (storedPreviewKey === previewKey && previewAssetId) {
      setPreviewGenerated(true);
      const imageUrl = previewImageUrl || selectedProductPhoto;
      if (!previewImageUrl) setPreviewImageUrl(imageUrl);
      return { assetId: previewAssetId, imageUrl };
    }
    if (designMode === "agent" && agentSession) {
      const preview = await handleApplyAgentPreview();
      if (preview) {
        return { assetId: preview.id, imageUrl: preview.url || preview.thumbnailUrl || selectedProductPhoto };
      }
    }
    if (isLocalOnlyAsset(draftAsset)) {
      const sample: AssetItem = {
        id: `local-preview-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: "product_preview",
        title: `${selectedProduct.name} · 本地预览`,
        url: selectedProductPhoto,
        thumbnailUrl: selectedProductPhoto,
        source: "本地产品预览",
        createdAt: new Date().toISOString(),
        selected: false,
        favorite: false,
        visibility: "private",
        width: draftSurface.width,
        height: draftSurface.height,
        dpi: draftSurface.dpi ?? null,
        metadata: {
          localOnly: true,
          localFallbackReason: "source_asset_not_persisted",
          sourceAssetId: draftAsset.id,
          sourceAssetTitle: draftAsset.title,
          designConfig,
        },
      };
      dispatch({ type: "ADD_ASSETS", assets: [sample] });
      setPreviewAssetId(sample.id);
      setPreviewImageUrl(sample.url);
      setStoredPreviewKey(previewKey);
      setPreviewGenerated(true);
      return { assetId: sample.id, imageUrl: sample.url };
    }
    const sample = await createClientProductSample({
      userId: activeUserId,
      productId: selectedProduct.id,
      productName: selectedProduct.name,
      assetId: draftAsset.id,
      sourceAssetUrl: draftAsset.url,
      sourceAssetTitle: draftAsset.title,
      surfaceName: draftSurface.name,
      sizeLabel: draftSurface.sizeLabel ?? selectedSize?.label ?? null,
      designConfig,
    });
    dispatch({ type: "ADD_ASSETS", assets: [sample] });
    setPreviewAssetId(sample.id);
    setPreviewImageUrl(sample.url || sample.thumbnailUrl || selectedProductPhoto);
    setStoredPreviewKey(previewKey);
    setPreviewGenerated(true);
    return { assetId: sample.id, imageUrl: sample.url || sample.thumbnailUrl || selectedProductPhoto };
  };

  const confirmDesignToOrderPool = async () => {
    if (!selectedProduct || !draftAsset) {
      showNotice("请先选择杯型和素材");
      return;
    }
    if (!priceConfigured) {
      showNotice("该杯型售价尚未由运营设置，暂不能加入设计篮。");
      return;
    }
    if (!isAuthenticated) {
      showNotice("请先登录，确认后的设计会放进设计篮。");
      window.sessionStorage.setItem(postAuthReturnKey, "productDesign");
      window.setTimeout(() => navigate("account"), 700);
      return;
    }
    if (currentDesignAlreadyInBasket) {
      showNotice("当前设计已经在设计篮里，可以继续做下一件或去结算。");
      return;
    }
    setPreviewSubmitting(true);
    try {
      const preview = await ensurePreviewAsset();
      if (!preview) return;
      dispatch({
        type: "ADD_ORDER_DRAFT",
        draft: {
          draftId: `draft-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          createdAt: new Date().toISOString(),
          status: "in_design_basket",
          productId: selectedProduct.id,
          productName: selectedProduct.name,
          productImage: selectedProductPhoto,
          sourceAssetId: draftAsset.id,
          sourceAssetTitle: draftAsset.title,
          sourceAssetUrl: draftAsset.url,
          previewAssetId: preview.assetId,
          previewImageUrl: preview.imageUrl,
          quantity: quantityNumber,
          unitPriceCents,
          payableCents,
          useProductCoupon: state.productCouponCount > 0,
          designConfig,
        },
      });
      showNotice("已放入设计篮，可以继续做下一件或去结算。");
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "放入设计篮失败，请稍后重试");
    } finally {
      setPreviewSubmitting(false);
    }
  };

  const openDesignBasket = () => {
    if (!orderDraftCount) {
      showNotice("设计篮还是空的，先确认当前设计。");
      return;
    }
    navigate("checkout");
  };

  const continueNextDesign = () => {
    if (!orderDraftCount) {
      showNotice("先确认当前设计，再继续做下一件。");
      return;
    }
    setSurfaceAssetIds({});
    setSelectedAssetId(designSourceAssets[0]?.id ?? "");
    setSelectedSurfaceName(readySurfaces[0]?.name ?? "");
    setQuantity(1);
    resetPreviewState();
    showNotice("上一件已在设计篮，继续选择素材或杯型设计下一件。");
  };

  return (
    <main className="catalog-page product-design-page">
      {sameStyleWork && (
        <section className="same-style-draft-banner product">
          <img src={sameStyleWork.image} alt={sameStyleWork.title} />
          <div>
            <small>同款产品草稿</small>
            <strong>{sameStyleWork.title}</strong>
            <p>来自 {sameStyleWork.author} 的公开产品作品。你可以换素材、换杯型，确认后放入自己的设计篮。</p>
          </div>
          <button className="secondary" onClick={() => dispatch({ type: "SET_SAME_STYLE_WORK", work: null })}>
            清除草稿
          </button>
        </section>
      )}

      {notice && (
        <div className="catalog-notice" role="status">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
        </div>
      )}

      <section className="product-operation-page">
        <button className="product-back-link" onClick={() => navigate("products")}>
          <ArrowLeft size={16} />
          返回全部商品
        </button>

        <div className="product-operation-hero">
          <div>
            <p className="eyebrow">产品试做</p>
            <h1>{selectedProduct?.name ?? "选择一款杯子"}</h1>
            <p>把你的图案放上去，先看效果，再决定是否制作。</p>
          </div>
          <div className="designer-facts">
            <article>
              <Brush size={15} />
              <span>材质</span>
              <strong>{selectedProduct?.secondCraft.includes("非不锈钢") ? "陶瓷" : "不锈钢"}</strong>
            </article>
            <article>
              <Images size={15} />
              <span>可选颜色</span>
              <strong>{productColorOptions.length} 色</strong>
            </article>
            <article>
              <Clock size={15} />
              <span>可印位置</span>
              <strong>
                {readySurfaces.length ? `${readySurfaces.length} 处` : "待补充"}
              </strong>
            </article>
          </div>
        </div>

        <div className="product-operation-shell">
          <section className="product-preview-panel">
            <div className="designer-preview">
              {product3DModelUrl ? (
                <Suspense
                  fallback={
                    <div className="product-3d-preview product-3d-preview--empty">
                      <strong>正在加载 3D 预览</strong>
                      <span>模型和贴图只在产品试做页加载。</span>
                    </div>
                  }
                >
                  <Product3DPreview
                    productName={selectedProduct?.name ?? "杯子"}
                    modelFile={product3DModelFile}
                    modelUrl={product3DModelUrl}
                    textureUrl={null}
                    textureLabel={designMode === "agent" ? (surfaceTextureAssignments.length ? "已采用候选设计" : "等待 AI 生成候选") : displayAssetTitle(draftAsset?.title, "未选择素材")}
                    surfaceTextures={surfaceTextureAssignments}
                    expectedSurfaceCount={readySurfaces.length}
                    onTextureLoadStateChange={handleTextureLoadStateChange}
                    surfaceName={designMode === "agent" ? undefined : selectedSurface?.name}
                    surfaceLabel={designMode === "agent" ? "整套产品设计" : selectedSurface?.label ?? "正面"}
                    printWidth={selectedSurface?.width ?? null}
                    printHeight={selectedSurface?.height ?? null}
                    baseColor={baseColor}
                    textureMode={textureMode}
                    textureScale={textureScale}
                    textureOffsetX={textureOffsetX}
                    textureOffsetY={textureOffsetY}
                  />
                </Suspense>
              ) : previewGenerated ? (
                <img className="designer-product-photo" src={selectedProductPhoto} alt="AI 套版后的杯子预览" />
              ) : (
                <div className="designer-stage-preview">
                  <img className="designer-product-photo pending" src={selectedProductPhoto} alt="待生成杯子预览" />
                    {draftAsset && (
                    <div className="designer-material-swatch">
                      <img src={draftAsset.thumbnailUrl} alt={draftAsset.title} />
                      <span>待套版素材</span>
                    </div>
                  )}
                </div>
              )}
              <span>
                {product3DModelUrl
                  ? currentDesignAlreadyInBasket
                    ? "当前设计已放入设计篮"
                    : currentPreviewAlreadyGenerated || previewGenerated
                      ? "产品预览已生成，满意后放入设计篮"
                      : "3D 贴图实时预览，满意后放入设计篮"
                  : currentDesignAlreadyInBasket
                    ? "当前设计已放入设计篮"
                    : currentPreviewAlreadyGenerated || previewGenerated
                      ? "产品预览已生成，满意后放入设计篮"
                      : "选择素材后放入设计篮"}
              </span>
            </div>

            <div className="surface-summary">
              <strong>{designMode === "agent" ? "当前产品" : "当前图案位置"}</strong>
              {designMode === "agent" ? (
                <>
                    <span>AI 负责整套产品设计</span>
                    <span>商品约束已锁定</span>
                  <span>生产范围已自动适配</span>
                </>
              ) : (
                <>
                  <span>位置：{selectedSurface?.label ?? "待选择"}</span>
                  <span>{selectedSurfaceAssetId ? "已选择图案" : "等待选择图案"}</span>
                  <span>生产范围已自动适配</span>
                </>
              )}
            </div>
          </section>

          <aside className={designMode === "agent" ? "product-operation-panel product-operation-panel--agent" : "product-operation-panel"}>
            <div className="design-flow-rail" aria-label="产品试做步骤">
              <span className={selectedSurface ? "done" : "active"}>{designMode === "agent" ? "描述想法" : "选择设计面"}</span>
              <span className={draftAsset || agentSession ? "done" : "active"}>{designMode === "agent" ? "确认方案" : "选择素材"}</span>
              <span className={orderDraftCount > 0 ? "done" : "active"}>加入设计篮</span>
            </div>

            <div className="design-mode-switch" role="tablist" aria-label="设计模式">
              <button
                type="button"
                className={designMode === "manual" ? "active" : ""}
                onClick={() => setDesignMode("manual")}
              >
                手动设计
              </button>
              <button
                type="button"
                className={designMode === "agent" ? "active" : ""}
                onClick={() => setDesignMode("agent")}
              >
                <Bot size={15} />
                AI 帮我设计
              </button>
            </div>

            {designMode === "agent" ? (
              <div className="agent-designer-panel">
                <div className="agent-panel-head">
                  <div>
                    <small>AI 设计助手</small>
                    <strong>说清想做什么，我来组织设计方案</strong>
                    <span>先给方案，确认后再生成。</span>
                  </div>
                </div>

                <div ref={agentChatThreadRef} className="agent-chat-thread" aria-live="polite">
	                  {!agentSession && (
	                    <div className="agent-empty-state">
	                      <article className="agent-message assistant agent-message-intro">
	                        <MessageCircle size={16} />
	                        <p>发一张图，或直接说说你想做的杯子。</p>
	                      </article>
	                      {!agentHasReferenceContext && (
	                        <p className="agent-context-hint">
	                          添加参考图后，我可以更准确地保留颜色和风格。
	                        </p>
	                      )}
	                      <div className="agent-starter-actions">
	                        {visibleAgentStarterPrompts.map((item) => (
	                          <button key={item} type="button" disabled={agentBusy} onClick={() => void submitAgentMessage(item)}>
	                            {item}
	                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {agentSession?.messages.map((message) => {
                    const messageAssets = (message.assetIds || [])
                      .map((assetId) => state.assets.find((asset) => asset.id === assetId) || agentResultAssets.find((asset) => asset.id === assetId))
                      .filter(Boolean) as AssetItem[];
                    const messagePlan = message.type === "plan" ? agentPlanForMessage(agentSession, message.planId) : null;
                    const visionEvidence = messagePlan ? agentVisionEvidence(messagePlan) : null;
                    return (
                      <article key={message.messageId} className={`agent-message ${message.role}`}>
                        <p>{message.content}</p>
                        {messagePlan && (
                          <div className="agent-inline-plan">
                            <div className="agent-plan-title">
                              <span>{messagePlan.designBrief?.title || "这套设计方案"}</span>
                              <em>方案分析 0 积分</em>
                            </div>
                            <p className="agent-plan-summary">{messagePlan.summaryForUser}</p>
                            {messagePlan.designBrief && (
                              <div className="agent-design-brief">
                                <dl>
                                  <div><dt>为谁设计</dt><dd>{messagePlan.designBrief.audience}</dd></div>
                                  <div><dt>使用场景</dt><dd>{messagePlan.designBrief.occasion}</dd></div>
                                  <div className="wide"><dt>视觉风格</dt><dd><strong>{messagePlan.designBrief.styleName}</strong>{messagePlan.designBrief.styleRationale}</dd></div>
                                  <div className="wide"><dt>画面构图</dt><dd>{messagePlan.designBrief.composition}</dd></div>
                                  <div className="wide"><dt>材质与生产</dt><dd>{messagePlan.designBrief.materialNotes}</dd></div>
                                </dl>
                                {messagePlan.designBrief.palette?.length ? (
                                  <div className="agent-palette"><span>建议色彩</span>{messagePlan.designBrief.palette.map((color) => <em key={color}>{color}</em>)}</div>
                                ) : null}
                                {messagePlan.designBrief.productFit && (
                                  <div className="agent-product-fit">
                                    <strong>{messagePlan.designBrief.productFit.productName || selectedProduct?.name}</strong>
                                    <span>{[
                                      messagePlan.designBrief.productFit.sizeLabel,
                                      messagePlan.designBrief.productFit.material,
                                      messagePlan.designBrief.productFit.surfaceLabel,
                                      messagePlan.designBrief.productFit.width && messagePlan.designBrief.productFit.height
                                        ? `${messagePlan.designBrief.productFit.width}×${messagePlan.designBrief.productFit.height}px`
                                        : null,
                                      messagePlan.designBrief.productFit.dpi ? `${messagePlan.designBrief.productFit.dpi}DPI` : null,
                                    ].filter(Boolean).join(" · ")}</span>
                                  </div>
                                )}
                                {messagePlan.designBrief.operations?.length ? (
                                  <ol className="agent-operation-list">
                                    {messagePlan.designBrief.operations.map((operation, index) => (
                                      <li key={`${operation.title}-${index}`}><span>{index + 1}</span><div><strong>{operation.title}</strong><p>{operation.purpose}</p></div></li>
                                    ))}
                                  </ol>
                                ) : null}
                                <div className="agent-plan-cost">
                                  <span>理解需求与制定方案 <strong>0 积分</strong></span>
                                  <span>确认后生成 <strong>{messagePlan.designBrief.generationCredits || 0} 积分</strong></span>
                                </div>
                              </div>
                            )}
                            {!messagePlan.designBrief && visionEvidence && <p className="agent-plan-summary">{visionEvidence.note}</p>}
                            {messagePlan.questions?.length ? (
                              <div className="agent-questions">
                                {messagePlan.questions.map((item) => <button key={item} type="button" onClick={() => setAgentInput(item)}>{item}</button>)}
                              </div>
                            ) : null}
                            {isAgentClarifying(messagePlan) ? (
                              <span className="agent-plan-done muted">先回复上面的问题，我再继续规划。</span>
                            ) : messagePlan.needsUserConfirmation ? (
                              <button className="agent-chat-action primary" type="button" disabled={agentBusy} onClick={() => void handleConfirmAgentPlan(messagePlan.planId)}>
                                {agentBusy ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
                                确认这套方案并后台生成
                              </button>
                            ) : (
                              <span className="agent-plan-done">已进入生成或结果确认</span>
                            )}
                          </div>
                        )}
                        {messageAssets.length > 0 && (
                          <div className={`agent-message-assets ${message.type === "result" || message.type === "preview" ? "actionable" : ""}`}>
                            {messageAssets.map((asset) => (
                              <figure key={asset.id}>
                                <img src={asset.thumbnailUrl || asset.url} alt={asset.title} />
                                {(message.type === "result" || message.type === "preview") && (
                                  <figcaption>
                                    <strong>{asset.title}</strong>
                                    {message.type === "result" && (
                                      <span>
                                        <button type="button" onClick={() => void handleUseAgentAsset(asset)}>采用这套设计</button>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setAgentAttachmentIds([asset.id]);
                                            setAgentInput(`基于「${asset.title}」继续优化，保持适合这款杯子生产。`);
                                          }}
                                        >
                                          继续改
                                        </button>
                                      </span>
                                    )}
                                  </figcaption>
                                )}
                              </figure>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>

	                {agentSession && (
	                  <div className="agent-quick-actions">
	                    {visibleAgentStarterPrompts.map((item) => (
	                      <button key={item} type="button" disabled={agentBusy} onClick={() => void submitAgentMessage(item)}>
	                        {item}
                          </button>
                        ))}
                      </div>
                )}

                {agentBusy && (
                  <div className="agent-busy-note" role="status">
                    <Loader2 size={16} className="spin" />
                    <span>{agentBusyText || "AI 正在处理，请稍等。"}</span>
                  </div>
                )}

                {agentSession?.status === "executing" && (
                  <div className="agent-background-note">
                    <Clock size={16} />
                    <span>可以先去看素材库或继续选商品；这个设计会话会保留，完成后结果会回到对话里。</span>
                  </div>
                )}

                <form
                  className="agent-input-row"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitAgentMessage();
                  }}
                >
                  <div className="agent-composer">
                    {agentAttachedAssets.length > 0 && (
                      <div className="agent-attachments" aria-label="本轮对话图片">
                        {agentAttachedAssets.map((asset) => (
                          <span key={asset.id}>
                            <img src={asset.thumbnailUrl || asset.url} alt={asset.title} />
                            <em>{asset.title}</em>
                            <button
                              type="button"
                              onClick={() => setAgentAttachmentIds((current) => current.filter((item) => item !== asset.id))}
                              aria-label={`移除${asset.title}`}
                            >
                              <X size={12} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <textarea
                      value={agentInput}
                      onChange={(event) => setAgentInput(event.target.value)}
                      onFocus={() => setAgentInputFocused(true)}
                      onBlur={() => setAgentInputFocused(false)}
                      placeholder={
                        agentInputFocused
                          ? ""
                          : "像跟设计师说话一样描述：上传孩子画的照片，保留手绘感，做一个送给老师的杯子。"
                      }
                    />
                    <input
                      ref={agentFileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      hidden
                      onChange={(event) => {
                        const files = Array.from(event.target.files || []);
                        void handleAgentFilesSelected(files);
                        event.currentTarget.value = "";
                      }}
                    />
                  </div>
                  <button
                    className="secondary agent-upload-button"
                    type="button"
                    disabled={agentUploadBusy || agentBusy}
                    onClick={() => agentFileInputRef.current?.click()}
                  >
	                    {agentUploadBusy ? <Loader2 size={16} className="spin" /> : <Images size={16} />}
	                    加图片
                  </button>
                  <button className="primary" type="submit" disabled={agentBusy}>
                    {agentBusy ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
                    发送
                  </button>
                </form>
                {agentError && <p className="agent-error">{agentError}</p>}
              </div>
            ) : (
              <div className="asset-picker">
                <div className="asset-picker-title">
                  <div>
                    <strong>把图片放到杯子上</strong>
                    <span>上传一张喜欢的图，或从素材库选择已有素材。</span>
                  </div>
                  <button onClick={() => navigate("assets")}>
                    <Images size={14} />
                    管理素材
                  </button>
                </div>

                <div className="surface-tab-grid" aria-label="设计面">
                  {(readySurfaces.length ? readySurfaces : selectedSurface ? [selectedSurface] : []).map((surface) => {
                    const assignedAsset = surfaceAssetIds[surface.name]
                      ? designSourceAssets.find((asset) => asset.id === surfaceAssetIds[surface.name])
                      : null;
                    return (
                      <button
                        key={surface.name}
                        className={selectedSurface?.name === surface.name ? "active" : ""}
                        type="button"
                        onClick={() => {
                          setSelectedSurfaceName(surface.name);
                          const assignedAssetId = surfaceAssetIds[surface.name];
                          setSelectedAssetId(assignedAssetId || "");
                          resetPreviewState();
                        }}
                      >
                        <strong>{surface.label}</strong>
                        <span>{surface.width && surface.height ? "生产范围已适配" : "暂不可制作"}</span>
                        <em className={assignedAsset ? "surface-thumb has-image" : "surface-thumb"}>
                          {assignedAsset ? <img src={assignedAsset.thumbnailUrl || assignedAsset.url} alt={assignedAsset.title} /> : "未放图"}
                        </em>
                        {assignedAsset && <small>{displayAssetTitle(assignedAsset.title)}</small>}
                      </button>
                    );
                  })}
                </div>

                {readySurfaces.length > 1 && (
                  <div className={`surface-coverage-panel${missingSurfaces.length || hasTextureLoadFailure ? "" : " complete"}`}>
                    <div>
                      <strong>
                        {missingSurfaces.length
                          ? `已覆盖 ${assignedSurfaceCount}/${readySurfaces.length} 个生产面`
                          : hasTextureLoadFailure
                            ? `已选择 ${assignedSurfaceCount}/${readySurfaces.length} 个生产面，预览未完成`
                          : `整套设计已覆盖 ${readySurfaces.length} 个生产面`}
                      </strong>
                      <span>
                        {missingSurfaces.length
                          ? textureMode === "decal"
                            ? "当前为局部贴图：已选面也只显示局部图案；想做整套效果，请选“铺满杯身”或“AI 适配杯身”。"
                            : "未覆盖的面会保留产品底色；可逐面放图，也可用当前图案补齐。"
                          : hasTextureLoadFailure
                            ? "有素材未能加载，当前 3D 预览不可信，不能加入设计篮。"
                          : textureMode === "decal"
                            ? "每个面已按各自生产尺寸放置局部图案；要做整套满版效果，请选“铺满杯身”或“AI 适配杯身”。"
                            : "每个面已按各自生产尺寸适配，可继续点选单面替换图案。"}
                      </span>
                    </div>
                    {missingSurfaces.length > 0 && (selectedAsset || primaryAssignedAsset) && (
                      <button type="button" className="secondary" onClick={fillMissingSurfaces}>
                        补齐其余 {missingSurfaces.length} 面
                      </button>
                    )}
                  </div>
                )}

                {failedTextureSurfaces.length > 0 && (
                  <div className="surface-texture-error" role="alert">
                    <strong>有 {failedTextureSurfaces.length} 个设计面未能读取素材</strong>
                    <span>{failedTextureSurfaces.map((surface) => surface.label).join("、")} 的预览未加载成功。请重新选择或上传图片后再加入设计篮。</span>
                  </div>
                )}

                <div className="surface-library-head">
                  <strong>最近素材</strong>
                  <div className="surface-library-head__meta">
                    <span>{selectedSurface?.label ?? "当前面"} · {selectedSurfaceAssetId ? "已选图片" : "选择一张图片"}</span>
                    {selectedSurfaceAssetId && (
                      <button type="button" className="surface-clear-button" onClick={clearSelectedSurfaceAsset}>
                        <X size={13} />
                        移除图案
                      </button>
                    )}
                  </div>
                </div>
                <div className="asset-picker-grid">
                  {quickDesignAssets.length > 0 ? (
                    quickDesignAssets.map((asset) => (
                      <button
                        key={asset.id}
                        className={selectedSurfaceAssetId === asset.id ? "active" : ""}
                        type="button"
                        aria-label={`快速选择${selectedSurface?.label ?? "当前设计面"}素材：${asset.title}`}
                        onClick={() => selectAssetForSurface(asset.id)}
                      >
                        <img src={asset.thumbnailUrl} alt={asset.title} />
                        <span>{displayAssetTitle(asset.title)}</span>
                      </button>
                    ))
                  ) : (
                    <div className="asset-picker-empty">
                      <strong>还没有可用素材</strong>
                      <p>先上传图片做批处理，或从灵感广场同款生成一张素材，再回来试做杯子。</p>
                    </div>
                  )}
                </div>
                <div className="surface-source-actions">
                  <button type="button" className="secondary" onClick={() => setAssetModalOpen(true)}>
                    <Images size={15} />
                    从素材库选择
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={surfaceUploadBusy}
                    onClick={() => surfaceFileInputRef.current?.click()}
                  >
                    <Images size={15} />
                    {surfaceUploadBusy ? "上传中" : "上传图片"}
                  </button>
                  <button
                    type="button"
                    className="quick-design-trigger"
                    disabled={quickDesignBusy}
                    onClick={() => void startQuickDesign()}
                  >
                    {quickDesignBusy ? <Loader2 className="spin" size={15} /> : <WandSparkles size={15} />}
                    {quickDesignBusy ? "正在看图" : "去设计"}
                  </button>
                  <input
                    ref={surfaceFileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(event) => {
                      const files = Array.from(event.target.files || []);
                      void handleSurfaceFilesSelected(files);
                      event.currentTarget.value = "";
                    }}
                  />
                </div>
                {quickDesignIntake && (
                  <section className="quick-design-recommendation" aria-live="polite">
                    <div className="quick-design-recommendation__head">
                      <div>
                        <span>AI 设计建议</span>
                        <strong>{quickDesignIntake.recommendation.title}</strong>
                      </div>
                      <CheckCircle2 size={18} aria-hidden="true" />
                    </div>
                    <p>{quickDesignIntake.recommendation.reason}</p>
                    {quickDesignIntake.recommendation.risk && (
                      <small>{quickDesignIntake.recommendation.risk}</small>
                    )}
                    <div className="quick-design-recommendation__actions">
                      <button
                        type="button"
                        className="primary"
                        disabled={seamlessOptimizing || agentBusy}
                        onClick={() => void applyQuickDesignRecommendation()}
                      >
                        {seamlessOptimizing || agentBusy ? <Loader2 className="spin" size={15} /> : <WandSparkles size={15} />}
                        {seamlessOptimizing ? "正在适配杯身" : agentBusy ? "正在规划方案" : quickDesignIntake.recommendation.actionLabel}
                      </button>
                      <button type="button" className="secondary" onClick={() => setQuickDesignIntake(null)}>
                        我自己调整
                      </button>
                    </div>
                  </section>
                )}
              </div>
            )}

            {designMode === "manual" ? (
              <div className="product-design-controls">
                {selectedAsset && (
                  <div className="product-design-controls__header">
                    <div>
                      <strong>怎么放图</strong>
                      <span>选择一种呈现方式，AI 适配会生成可直接生产的杯身图。</span>
                    </div>
                    <em>{selectedTextureMode.title}</em>
                  </div>
                )}

                <div className="cup-color-panel">
                  <span>杯体底色</span>
                  <div className="cup-color-swatches" role="list" aria-label="杯体底色">
                    {productColorOptions.map((option) => (
                      <button
                        key={option.code}
                        className={baseColor === option.value ? "active" : ""}
                        type="button"
                        onClick={() => {
                          setBaseColor(option.value);
                          resetPreviewState();
                        }}
                        title={`${option.label} · ${option.note}`}
                      >
                        <i style={{ backgroundColor: option.value }} />
                        <strong>{option.label}</strong>
                      </button>
                    ))}
                  </div>
                </div>

                {productCraftOptions.length ? (
                  <div className="craft-option-panel">
                    <span>工艺</span>
                    <div className="craft-option-grid">
                      {productCraftOptions.map((option) => {
                        const key = craftOptionKey(option);
                        return (
                          <button
                            key={key}
                            className={selectedCraft && craftOptionKey(selectedCraft) === key ? "active" : ""}
                            type="button"
                            onClick={() => {
                              setSelectedCraftKey(key);
                              resetPreviewState();
                            }}
                          >
                            <strong>{option.secondCraftName}</strong>
                            <span>{option.firstCraftName}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {selectedAsset && (
                  <>
                <div className="texture-mode-panel">
                  <span>贴图方式</span>
                  <div className="texture-mode-grid">
                    {textureModeOptions.map((option) => (
                      <button
                        key={option.id}
                        className={textureMode === option.id ? "active" : ""}
                        type="button"
                        onClick={() => {
                          setTextureMode(option.id);
                          if (option.id === "wrap") {
                            setTextureScale(1);
                            setTextureOffsetX(0);
                            setTextureOffsetY(0);
                          }
                          if (option.id === "decal") setTextureScale(1.45);
                          resetPreviewState();
                        }}
                      >
                        <strong>{option.title}</strong>
                        <span>{option.description}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {textureMode === "wrap" && (
                  <div className="seamless-production-panel">
                    <div>
                      <span>AI 适配杯身</span>
                      <strong>
                        {assetLooksSeamless(selectedAsset)
                          ? "已完成边缘校验"
                          : assetHasSeamlessCandidate(selectedAsset)
                            ? "已生成连续图，待生产校验"
                            : "先让 AI 生成可生产的连续图"}
                      </strong>
                      <p>
                        {assetLooksSeamless(selectedAsset)
                          ? "四边像素与设计面尺寸已通过生产导出检查。"
                          : assetHasSeamlessCandidate(selectedAsset)
                            ? "3D 预览可环绕，生产导出仍会校验左右和上下边缘。"
                            : "AI 会处理边缘与尺寸，生成适合环绕制作的图案；这一步会消耗积分。"}
                      </p>
                    </div>
                    {!assetLooksSeamless(selectedAsset) && !assetHasSeamlessCandidate(selectedAsset) && (
                      <button
                        type="button"
                        className="primary"
                        disabled={!selectedAsset || seamlessOptimizing}
                        onClick={() => void optimizeForSeamlessProduction()}
                      >
                        {seamlessOptimizing ? <Loader2 className="spin" size={15} /> : <WandSparkles size={15} />}
                        {seamlessOptimizing ? "正在适配杯身" : "开始 AI 适配"}
                      </button>
                    )}
                  </div>
                )}

                <div className="texture-adjust-panel">
                  <div className="range-control">
                    <label htmlFor="texture-scale">图片大小</label>
                    <strong>{Math.round(textureScale * 100)}%</strong>
                    <input
                      id="texture-scale"
                      type="range"
                      min="0.45"
                      max="2.4"
                      step="0.05"
                      value={textureScale}
                      disabled={!selectedAsset || textureMode === "wrap"}
                      onChange={(event) => {
                        setTextureScale(Number(event.target.value));
                        resetPreviewState();
                      }}
                    />
                  </div>
                  <div className="range-control">
                    <label htmlFor="texture-offset-x">左右位置</label>
                    <strong>{textureOffsetX > 0 ? "+" : ""}{Math.round(textureOffsetX * 100)}%</strong>
                    <input
                      id="texture-offset-x"
                      type="range"
                      min="-0.35"
                      max="0.35"
                      step="0.01"
                      value={textureOffsetX}
                      disabled={!selectedAsset || textureMode === "wrap" || textureMode === "cover"}
                      onChange={(event) => {
                        setTextureOffsetX(Number(event.target.value));
                        resetPreviewState();
                      }}
                    />
                  </div>
                  <div className="range-control">
                    <label htmlFor="texture-offset-y">上下位置</label>
                    <strong>{textureOffsetY > 0 ? "+" : ""}{Math.round(textureOffsetY * 100)}%</strong>
                    <input
                      id="texture-offset-y"
                      type="range"
                      min="-0.35"
                      max="0.35"
                      step="0.01"
                      value={textureOffsetY}
                      disabled={!selectedAsset || textureMode === "wrap" || textureMode === "cover"}
                      onChange={(event) => {
                        setTextureOffsetY(Number(event.target.value));
                        resetPreviewState();
                      }}
                    />
                  </div>
                </div>

                  </>
                )}
              </div>
            ) : null}

            {(designMode === "agent" || (selectedAsset && textureMode === "wrap")) && <SurfaceFitCard assessment={surfaceFitAssessment} />}

            {(designMode === "agent" || selectedAsset) && (
              <DesignBasketCard
                mode={designMode}
                itemCount={orderDraftCount}
                quantity={quantityNumber}
                unitPriceCents={unitPriceCents}
                payableCents={payableCents}
                priceConfigured={priceConfigured}
                discountLabel={quantityDiscountLabel}
                hasDesign={canConfirmDesign}
                isSubmitting={previewSubmitting}
                alreadyAdded={currentDesignAlreadyInBasket}
                couponCount={state.productCouponCount}
                isAuthenticated={isAuthenticated}
                onQuantityChange={setQuantity}
                onConfirm={confirmDesignToOrderPool}
                onContinue={continueNextDesign}
                onCheckout={() => navigate("checkout")}
              />
            )}
          </aside>
        </div>
      </section>

      {orderDraftCount > 0 && (
        <button className="design-basket-float" type="button" onClick={openDesignBasket} aria-label={`设计篮已有 ${orderDraftCount} 件`}>
          <span>{orderDraftCount}</span>
          <strong>设计篮</strong>
          <em>去结算</em>
        </button>
      )}

      {assetModalOpen && (
        <div className="app-modal-backdrop" role="presentation" onClick={() => setAssetModalOpen(false)}>
          <section className="app-modal asset-select-modal" role="dialog" aria-modal="true" aria-label="从素材库选择图片" onClick={(event) => event.stopPropagation()}>
            <div className="app-modal-head">
              <div>
                <small>素材库选择</small>
                <strong>选择一张图片应用到当前设计面</strong>
              </div>
              <button className="icon-button" onClick={() => setAssetModalOpen(false)} aria-label="关闭">
                <X size={18} />
              </button>
            </div>
            <div className="asset-select-toolbar">
              <label>
                <Search size={16} />
                <input value={assetSearch} onChange={(event) => setAssetSearch(event.target.value)} placeholder="搜索素材标题、来源或类型" />
              </label>
              <div>
                {assetFilterOptions.map((option) => (
                  <button
                    key={option.id}
                    className={assetTypeFilter === option.id ? "active" : ""}
                    onClick={() => setAssetTypeFilter(option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="asset-select-grid">
              {filteredAssets.length > 0 ? (
                filteredAssets.map((asset) => (
                  <button
                    key={asset.id}
                    className={selectedSurfaceAssetId === asset.id ? "active" : ""}
                    type="button"
                    aria-label={`选择素材：${asset.title}，${assetTypeLabels[asset.type]}，应用到${selectedSurface?.label ?? "当前设计面"}`}
                    onClick={() => {
                      selectAssetForSurface(asset.id);
                      setAssetModalOpen(false);
                    }}
                  >
                    <img src={asset.thumbnailUrl} alt={asset.title} />
                    <span>{assetTypeLabels[asset.type]}</span>
                    <strong>{asset.title}</strong>
                  </button>
                ))
              ) : (
                <div className="asset-select-empty">
                  <LayoutGrid size={22} />
                  <strong>没有匹配素材</strong>
                  <p>可以换一个关键词，或先去批量处理页生成素材。</p>
                  <button className="secondary" onClick={() => {
                    setAssetModalOpen(false);
                    navigate("process");
                  }}>
                    去处理图片
                  </button>
                </div>
              )}
            </div>
            <footer className="app-modal-foot">
              <button className="secondary" onClick={() => navigate("assets")}>去素材库维护</button>
              <button className="primary" onClick={() => setAssetModalOpen(false)}>完成</button>
            </footer>
          </section>
        </div>
      )}

    </main>
  );
}
