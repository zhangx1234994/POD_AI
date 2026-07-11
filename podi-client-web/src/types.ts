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
  | "editor"
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
  | "ai_generated";  // AI 生成图

export type AssetVisibility = "private" | "reviewing" | "public";

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
 * 批量处理任务
 * ──────────────────────────────────────────── */

export type ProcessTaskType = "clean" | "extend" | "extract" | "variation" | "seamless2" | "seamless4";
export type ProcessTaskStatus = "pending" | "processing" | "completed" | "failed";

export interface ProcessTask {
  id: string;
  runIds?: string[];
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
  errorMessage?: string;
  executionMode?: "business";
}

/* ────────────────────────────────────────────
 * AI 处理能力定义
 * ──────────────────────────────────────────── */

export type BatchGoalId = ProcessTaskType;

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
  submittedAt: string;
  status: "待审核";
}

export interface PublishDraftSource {
  kind: WorkKind;
  title: string;
  tags: string;
  usage: string;
  image: string;
  sourceLabel: string;
}

/* ────────────────────────────────────────────
 * 订单（保持现有结构不变）
 * ──────────────────────────────────────────── */

export interface ProductionOrderSnapshot {
  id: string;
  product: string;
  asset: string;
  quantity: string;
  status: "待支付" | "运营核对" | "已推送供应商" | "制作中" | "已发货" | "已完成" | "待确认";
  eta: string;
  image: string;
  createdAt: string;
  shippingSummary: string;
  discount: string;
  usedProductCoupon: boolean;
  orderNo?: string;
  paymentStatus?: string;
  supplierStatus?: string | null;
  productionAssetUrl?: string;
  supplierEffectImageUrl?: string | null;
  preflightPassed?: boolean;
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
