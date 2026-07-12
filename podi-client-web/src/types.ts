import type { LucideIcon } from "lucide-react";

/* ────────────────────────────────────────────
 * 路由 & 导航
 * ──────────────────────────────────────────── */

export type AppView =
  | "home"
  | "process"
  | "tasks"
  | "assets"
  | "products"
  | "productDesign"
  | "checkout"
  | "editor"
  | "imageEditor"
  | "account"
  | "orders"
  | "wallet"
  | "inspire"
  | "publish"
  | "profile";

/* ────────────────────────────────────────────
 * 素材库
 * ──────────────────────────────────────────── */

export type AssetType =
  | "original"       // 原图
  | "processed"      // AI 处理图
  | "variation"      // 裂变图
  | "pattern"        // 花纹
  | "ai_generated"   // AI 生成图
  | "product_preview"; // 产品预览图

export type AssetVisibility = "private" | "reviewing" | "public" | "removed";
export type AssetLicenseMode = "private" | "display_only" | "free_reuse" | "paid_points";
export type AssetLicenseSource = "created" | "uploaded" | "free_reuse" | "purchased" | "product_snapshot";

export interface AssetItem {
  id: string;
  type: AssetType;
  title: string;
  url: string;
  thumbnailUrl: string;
  source: string;
  createdAt: string;
  batchId?: string;
  parentId?: string;
  selected: boolean;
  favorite: boolean;
  visibility: AssetVisibility;
  licenseMode?: AssetLicenseMode;
  licenseSource?: AssetLicenseSource;
  licensePoints?: number | null;
  author?: string | null;
  acquiredAt?: string | null;
  removedAt?: string | null;
  usedInProducts?: number;
  width?: number | null;
  height?: number | null;
  dpi?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ProductSample {
  id: string;
  productId: string;
  assetIds: string[];
  previewUrl: string;
  createdAt: string;
  visibility: AssetVisibility;
}

/* ────────────────────────────────────────────
 * AI 产品设计助手
 * ──────────────────────────────────────────── */

export type ProductDesignAgentIntent =
  | "print_as_is"
  | "clean_and_print"
  | "extract_pattern"
  | "make_seamless_wrap"
  | "generate_variations"
  | "ai_recreate"
  | "compose_product_design"
  | "clarify";

export type ProductDesignAgentStepAction =
  | "vl_analyze"
  | "pattern_extract"
  | "variation"
  | "two_way_seamless"
  | "four_way_seamless"
  | "image2_recreate"
  | "postprocess_to_surface"
  | "render_product_preview"
  | "ask_user";

export interface ProductDesignAgentStep {
  stepId: string;
  type: string;
  title: string;
  targetAbility: ProductDesignAgentStepAction;
  status: "pending" | "waiting_confirmation" | "needs_user" | "queued" | "running" | "completed" | "failed";
  userStatus?: string;
  costCredits?: number;
  idempotencyKey?: string;
  failureFallback?: string;
  requiresConfirmationBefore?: boolean;
  requiresConfirmationAfter?: boolean;
  summary?: string;
  completedAt?: string | null;
}

export interface ProductDesignAgentSurfaceAssignment {
  surfaceId: string;
  surfaceLabel?: string;
  assetRef?: string | null;
  mode?: "wrap" | "fit" | "cover" | "decal" | string;
  scale?: number;
  position?: { x: number; y: number };
  fullBleed?: boolean;
  needsSeamless?: boolean;
}

export interface ProductDesignAgentPlan {
  planId: string;
  sessionId: string;
  intent: ProductDesignAgentIntent;
  confidence: number;
  needsUserConfirmation: boolean;
  status: "clarifying" | "needs_confirmation" | "preview_ready" | "completed" | "failed" | string;
  summaryForUser: string;
  questions?: string[];
  steps: ProductDesignAgentStep[];
  layoutPlan: {
    surfaceAssignments: ProductDesignAgentSurfaceAssignment[];
    postprocess?: Record<string, unknown>;
  };
  risk?: {
    level?: "low" | "medium" | "high" | string;
    reasons?: string[];
  };
  rejectedRoutes?: Array<Record<string, unknown>>;
  contextTrace?: {
    source?: string;
    baseAssetRole?: "source_asset" | "previous_result" | "accepted_asset" | "prompt_only" | string;
    assetIds?: string[];
    sourceAssetId?: string | null;
    previousIntent?: ProductDesignAgentIntent | string | null;
    isFollowup?: boolean;
  };
  qualityChecklist?: {
    intentMatched?: boolean;
    productSurfaceKnown?: boolean;
    usesWorkingMemory?: boolean;
    requiresCostConfirmation?: boolean;
    hidesSystemTerms?: boolean;
    sizePostprocessRequired?: boolean;
    hasVisionEvidence?: boolean;
  };
  visionAnalysis?: {
    provider?: string;
    model?: string;
    imageType?: string;
    qualityRisk?: string;
    recommendedIntent?: ProductDesignAgentIntent | string;
    recommendedSurfaceId?: string;
    layoutMode?: string;
    needsSeamless?: boolean;
    needsImage2?: boolean;
    confidence?: number;
    observations?: string[];
    risks?: string[];
    questions?: string[];
    skippedReason?: string | null;
    fallback?: string | null;
    modelError?: string | null;
  };
  modelRouting?: {
    vlProvider?: string;
    vlModel?: string;
    planner?: string;
    controlPlane?: string;
  };
  createdAt?: string;
}

export interface ProductDesignAgentMessage {
  messageId: string;
  role: "user" | "assistant" | "system";
  type: "text" | "plan" | "result" | "preview" | "notice" | string;
  content: string;
  assetIds?: string[];
  planId?: string | null;
  createdAt: string;
}

export interface ProductDesignAgentSession {
  sessionId: string;
  userId: string;
  productId: string;
  productName: string;
  productContext: Record<string, unknown>;
  sourceAssetIds: string[];
  sourceImageUrls?: string[];
  status: string;
  currentPlanId?: string | null;
  messages: ProductDesignAgentMessage[];
  plans: ProductDesignAgentPlan[];
  steps: ProductDesignAgentStep[];
  toolCalls?: Array<Record<string, unknown>>;
  workingMemory?: Record<string, unknown>;
  resultAssetIds: string[];
  currentPreviewAssetId?: string | null;
  createdAt: string;
  updatedAt: string;
  resultAssets?: AssetItem[];
  previewAsset?: AssetItem | null;
}

export interface ProductDesignQuickIntake {
  intakeId: string;
  source: "vl_design_intake";
  plan: ProductDesignAgentPlan;
  recommendation: {
    title: string;
    actionLabel: string;
    reason: string;
    risk?: string | null;
    suggestedMode: "wrap" | "fit" | "cover" | "decal" | null;
    requiresAgent: boolean;
  };
}

/* ────────────────────────────────────────────
 * 批量处理任务
 * ──────────────────────────────────────────── */

export type ProcessTaskType = "clean" | "extend" | "extract" | "variation" | "seamless2" | "seamless4" | "image_edit";
export type ProcessTaskStatus = "pending" | "processing" | "completed" | "failed";

export interface ProcessTask {
  id: string;
  type: ProcessTaskType;
  status: ProcessTaskStatus;
  inputAssetIds: string[];
  outputAssetIds: string[];
  createdAt: string;
  completedAt?: string;
  abilityTitle?: string;
  outputLabel?: string;
  inputCount?: number;
  resultCount?: number;
  optionLabel?: string;
  sizeLabel?: string;
  resultType?: AssetType;
  inputImages?: string[];
  resultImages?: string[];
  submitStatus?: string;
  callbackStatus?: string;
  finalStatus?: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  queueSummary?: {
    queued?: number;
    running?: number;
    completed?: number;
    failed?: number;
    maxInFlight?: number;
    dispatchPerTick?: number;
  };
  params?: Record<string, unknown>;
}

/* ────────────────────────────────────────────
 * AI 处理能力定义
 * ──────────────────────────────────────────── */

export type BatchGoalId = Exclude<ProcessTaskType, "image_edit">;

export interface AbilityDefinition {
  id: BatchGoalId;
  title: string;
  desc: string;
  icon: LucideIcon;
  cost: string;
  output: string;
}

/* ────────────────────────────────────────────
 * 灵感广场
 * ──────────────────────────────────────────── */

export type WorkKind = "图片作品" | "产品作品";

export interface InspirationWork {
  id: string;
  title: string;
  kind: WorkKind;
  image: string;
  author: string;
  tags: string[];
  tries: number;
  favorites: number;
  earnings: string;
  trend: string;
  licenseMode?: AssetLicenseMode;
  pricePoints?: number | null;
  rightsLabel?: string;
  complaintCount?: number;
  sourceAssetId?: string | null;
  productId?: string | null;
}

/* ────────────────────────────────────────────
 * 公开申请
 * ──────────────────────────────────────────── */

export interface PublishApplicationSnapshot {
  id: string;
  kind: WorkKind;
  title: string;
  tags: string;
  usage: string;
  image: string;
  licenseMode?: AssetLicenseMode;
  pricePoints?: number | null;
  submittedAt: string;
  status: "待审核" | "已通过" | "已拒绝";
  reviewNote?: string | null;
}

export interface PublishDraftSource {
  kind: WorkKind;
  title: string;
  tags: string;
  usage: string;
  image: string;
  sourceLabel: string;
  sourceAssetId?: string | null;
}

/* ────────────────────────────────────────────
 * 订单（保持现有结构不变）
 * ──────────────────────────────────────────── */

export interface ProductionOrderSnapshot {
  id: string;
  product: string;
  asset: string;
  quantity: string;
  status: "待支付" | "制作中" | "待确认" | "已发出" | "已完成" | "已取消";
  eta: string;
  image: string;
  createdAt: string;
  shippingSummary: string;
  discount: string;
  usedProductCoupon: boolean;
  supplierOrderId?: string | null;
  logisticsNo?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ClientShippingAddress {
  recipientName: string;
  phoneNumber: string;
  country: string;
  state: string;
  city: string;
  postalCode: string;
  address: string;
  email: string;
}

export interface ProductCheckoutDraft {
  productId: string;
  productName: string;
  productImage: string;
  sourceAssetId: string;
  sourceAssetTitle: string;
  sourceAssetUrl: string;
  previewAssetId: string;
  previewImageUrl: string;
  quantity: number;
  unitPriceCents: number;
  payableCents: number;
  useProductCoupon: boolean;
  designConfig: Record<string, unknown>;
}

export interface ProductOrderDraft extends ProductCheckoutDraft {
  draftId: string;
  createdAt: string;
  status: "in_design_basket";
}

export type CommerceOrderStatus =
  | "payment_pending"
  | "paid"
  | "fulfillment_review"
  | "in_production"
  | "shipped"
  | "completed"
  | "refund_requested"
  | "refunded"
  | "cancelled";

export interface CommerceOrder {
  id: string;
  deliveryId: string;
  productName: string;
  assetTitle: string;
  assetUrl: string;
  quantity: number;
  amountLabel: string;
  status: CommerceOrderStatus;
  logisticsNo?: string;
  createdAt: string;
  updatedAt: string;
  note: string;
}

/* ────────────────────────────────────────────
 * 钱包（保持现有结构不变）
 * ──────────────────────────────────────────── */

export type CouponType = "design" | "product" | "sample" | "general";
export type CouponStatus = "available" | "used" | "expired";

export interface CouponItem {
  id: string;
  type: CouponType;
  name: string;
  scope: string;
  value: string;
  status: CouponStatus;
  expiresAt: string;
  source: string;
}

export interface PointLedgerEntry {
  id: string;
  time: string;
  action: string;
  amount: number;
  note: string;
}

export interface WalletState {
  pointBalance: number;
  frozenPoints: number;
  coupons: CouponItem[];
  ledger: PointLedgerEntry[];
  redeemedCodes: string[];
}

export interface RedeemCodeItem {
  code: string;
  redeemedAt?: string;
}

export interface RedeemCodeBatch {
  id: string;
  name: string;
  channel: string;
  type: CouponType;
  count: number;
  expiresAt: string;
  createdAt: string;
  codes: RedeemCodeItem[];
}

/* ────────────────────────────────────────────
 * 交付 & 售后（保持现有结构不变）
 * ──────────────────────────────────────────── */

export type DeliveryKind = "digital_package" | "sample_request";
export type DeliveryStatus = "digital_ready" | "ops_review" | "approved" | "rejected";

export interface DeliveryOrder {
  id: string;
  kind: DeliveryKind;
  status: DeliveryStatus;
  productName: string;
  productTemplateId: string;
  spec: string;
  safeArea: string;
  assetId: string;
  assetTitle: string;
  assetUrl: string;
  createdAt: string;
  updatedAt: string;
  quantity: number;
  couponUsed?: string;
  designBrief: string;
  note: string;
  files: Array<{ label: string; url: string }>;
}

export type InvoiceStatus = "requested" | "issued" | "rejected";

export interface InvoiceRequest {
  id: string;
  orderId: string;
  orderKind: DeliveryKind;
  productName: string;
  title: string;
  taxNo: string;
  amountLabel: string;
  status: InvoiceStatus;
  createdAt: string;
  updatedAt: string;
  note: string;
}

export type SupportTicketStatus = "open" | "processing" | "resolved" | "rejected";

export interface SupportTicket {
  id: string;
  sourceType: "task" | "delivery";
  sourceId: string;
  title: string;
  reason: "task_failure" | "delivery_issue" | "invoice_issue" | "other";
  status: SupportTicketStatus;
  createdAt: string;
  updatedAt: string;
  note: string;
  resolution?: string;
}

export type RefundStatus = "requested" | "approved" | "rejected";

export interface RefundRequest {
  id: string;
  orderId: string;
  status: RefundStatus;
  reason: string;
  createdAt: string;
  updatedAt: string;
  note: string;
}

/* ────────────────────────────────────────────
 * API 相关
 * ──────────────────────────────────────────── */

export interface UploadResult {
  url: string;
  objectKey: string;
  name: string;
  size: number;
}

export interface ApiResult {
  ok: boolean;
  runId?: string;
  status?: string;
  imageUrls: string[];
  videoUrls: string[];
  text?: string;
  error?: string;
  raw?: unknown;
}
