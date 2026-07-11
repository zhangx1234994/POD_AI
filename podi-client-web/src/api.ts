import OSS from "ali-oss";
import type { ApiResult, AssetItem, AssetType, UploadResult } from "./types";

const CONFIG_STORAGE_KEY = "podi-client-web.runtime-config.v1";
const defaultBaseUrl = (import.meta.env.VITE_PODI_API_BASE ?? (typeof window === "undefined" ? "http://127.0.0.1:8099" : "")).replace(/\/$/, "");
const defaultApiKey = import.meta.env.VITE_PODI_API_KEY || "";
const defaultAccessToken = import.meta.env.VITE_PODI_ACCESS_TOKEN || "";

export interface RuntimeConfig {
  apiBaseUrl: string;
  mediaBaseUrl: string;
  apiKey: string;
  accessToken: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken?: string | null;
  expiresIn: number;
  role: string;
  user?: ClientUser | null;
}

export interface ClientUser {
  id: string;
  username: string;
  email: string;
  displayName?: string | null;
  role: string;
  status: string;
  tenantId?: string | null;
  clientId?: string | null;
}

export interface ClientWorkspace {
  id: string;
  name: string;
  scenario: string;
  status: string;
  assetCount: number;
  runCount: number;
  latestRunStatus?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ClientMeResponse {
  user: ClientUser;
  workspace: ClientWorkspace;
}

export interface ClientAsset {
  id: string;
  assetType: string;
  url: string;
  contentType?: string | null;
  fileName?: string | null;
  title?: string | null;
  sourceRunId?: string | null;
  sourceBusinessKey?: string | null;
  sourceFlowStepKey?: string | null;
  qualityGrade?: string | null;
  inputTags: string[];
  issueTags: string[];
  selected: boolean;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface ClientAssetCreatePayload {
  assetType: string;
  url: string;
  contentType?: string;
  fileName?: string;
  flowStepKey?: string;
  inputTags?: string[];
  issueTags?: string[];
  metadata?: Record<string, unknown>;
}

export interface ClientAssetListResponse {
  total: number;
  items: ClientAsset[];
}

export interface ClientProductCoupon {
  id: string;
  packageKey: string;
  name: string;
  businessKey?: string | null;
  totalUnits: number;
  usedUnits: number;
  frozenUnits: number;
  remainingUnits: number;
  unitName: string;
  status: string;
  source?: string | null;
  expiresAt?: string | null;
  metadata: Record<string, unknown>;
}

export interface ClientWalletResponse {
  pointBalance: number;
  frozenPoints: number;
  currency: string;
  productCouponCount: number;
  productCoupons: ClientProductCoupon[];
  ledger: Array<{
    id: string;
    points: number;
    description?: string | null;
    createdAt?: string | null;
    traceId?: string | null;
    taskId?: string | null;
  }>;
}

export interface ClientProductionOrderItem {
  id: string;
  productName: string;
  templateNo: string;
  sizeCode: string;
  colorCode: string;
  targetWidth: number;
  targetHeight: number;
  targetDpi: number;
  quantity: number;
  sourceAssetUrl: string;
  productionAssetUrl: string;
  supplierEffectImageUrl?: string | null;
  preflight: Record<string, unknown>;
}

export interface ClientProductionOrder {
  id: string;
  orderNo: string;
  status: string;
  paymentStatus: string;
  shippingAddress: Record<string, string | null>;
  supplierOrderId?: string | null;
  supplierStatus?: string | null;
  supplierEffectImageUrls: string[];
  items: ClientProductionOrderItem[];
  createdAt: string;
  updatedAt: string;
}

export interface ClientProductionOrderCreatePayload {
  clientRequestId: string;
  shippingAddress: {
    recipientName: string;
    phoneNumber: string;
    country: string;
    state: string;
    city: string;
    district?: string;
    address: string;
    postalCode: string;
    email?: string;
  };
  items: Array<{
    productName: string;
    templateNo: string;
    bodyCode?: string;
    sizeCode: string;
    colorCode: string;
    firstCraft: string;
    secondCraft: string;
    viewId: string;
    surfaceName: string;
    targetWidth: number;
    targetHeight: number;
    targetDpi: number;
    quantity: number;
    sourceAssetUrl: string;
    compositionMode: "cover" | "tile" | "seamless";
    tiledReviewConfirmed: boolean;
  }>;
}

interface UploadKeyResponse {
  uploadKey: string;
  expiresAt: string;
  expiresIn: number;
}

interface OssCredentials {
  accessKeyId: string;
  accessKeySecret: string;
  securityToken?: string | null;
  endpoint: string;
  publicDomain: string;
  bucket: string;
  region: string;
  expiration: number;
  isTemporary: boolean;
  rootPrefix: string;
}

interface OssCredentialResponse {
  ossCredentials: OssCredentials;
  objectKey: string;
  host: string;
}

let cachedUploadKey: { token: string; expiresAt: number } | null = null;

async function fetchWithTimeout(url: string, init: RequestInit = {}, timeoutMs = 15000): Promise<Response> {
  const controller = new AbortController();
  const timer = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...init,
      signal: init.signal || controller.signal
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`请求超时 ${Math.round(timeoutMs / 1000)} 秒`);
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timer);
  }
}

function normalizeUrl(value: string, fallback: string): string {
  const trimmed = value.trim();
  return (trimmed || fallback).replace(/\/$/, "");
}

function defaultConfig(): RuntimeConfig {
  const apiBaseUrl = defaultBaseUrl;
  return {
    apiBaseUrl,
    mediaBaseUrl: normalizeUrl(import.meta.env.VITE_PODI_MEDIA_BASE || `${apiBaseUrl}/api/media`, `${apiBaseUrl}/api/media`),
    apiKey: defaultApiKey,
    accessToken: defaultAccessToken
  };
}

export function getRuntimeConfig(): RuntimeConfig {
  const fallback = defaultConfig();
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(CONFIG_STORAGE_KEY);
    const stored = raw ? (JSON.parse(raw) as Partial<RuntimeConfig>) : {};
    const apiBaseUrl = normalizeUrl(stored.apiBaseUrl || fallback.apiBaseUrl, fallback.apiBaseUrl);
    return {
      apiBaseUrl,
      mediaBaseUrl: normalizeUrl(stored.mediaBaseUrl || fallback.mediaBaseUrl || `${apiBaseUrl}/api/media`, `${apiBaseUrl}/api/media`),
      apiKey: (stored.apiKey || fallback.apiKey || "").trim(),
      accessToken: (stored.accessToken || fallback.accessToken || "").trim()
    };
  } catch {
    return fallback;
  }
}

export function saveRuntimeConfig(config: RuntimeConfig): RuntimeConfig {
  const fallback = defaultConfig();
  const apiBaseUrl = normalizeUrl(config.apiBaseUrl, fallback.apiBaseUrl);
  const next = {
    apiBaseUrl,
    mediaBaseUrl: normalizeUrl(config.mediaBaseUrl, `${apiBaseUrl}/api/media`),
    apiKey: config.apiKey.trim(),
    accessToken: config.accessToken.trim()
  };
  cachedUploadKey = null;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export async function loginClient(username: string, password: string): Promise<LoginResponse> {
  const { apiBaseUrl } = getRuntimeConfig();
  const response = await fetchWithTimeout(`${apiBaseUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username.trim(), password })
  }, 15000);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeErrorText(data?.detail || data?.message || data) || `HTTP ${response.status}`);
  }
  const token = String(data.accessToken || "").trim();
  if (!token) {
    throw new Error("登录成功但未返回访问令牌");
  }
  const current = getRuntimeConfig();
  saveRuntimeConfig({ ...current, accessToken: token });
  return data as LoginResponse;
}

export function logoutClient(): void {
  const current = getRuntimeConfig();
  saveRuntimeConfig({ ...current, accessToken: "" });
}

function headers(): HeadersInit {
  const apiKey = getRuntimeConfig().apiKey;
  const value: HeadersInit = {
    "Content-Type": "application/json"
  };
  if (apiKey) {
    value["X-PODI-API-Key"] = apiKey;
  }
  const accessToken = getRuntimeConfig().accessToken;
  if (accessToken) {
    value.Authorization = `Bearer ${accessToken}`;
  }
  return value;
}

async function clientRequest<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const { apiBaseUrl } = getRuntimeConfig();
  const response = await fetchWithTimeout(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...headers(),
      ...(init.headers || {})
    }
  }, timeoutMs);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeErrorText(data?.detail || data?.message || data) || `HTTP ${response.status}`);
  }
  return data as T;
}

function readRunId(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") return undefined;
  const body = payload as Record<string, unknown>;
  const direct = body.runId || body.id || body.taskId;
  if (typeof direct === "string") return direct;
  const nested = body.run;
  if (nested && typeof nested === "object") {
    const runId = (nested as Record<string, unknown>).runId || (nested as Record<string, unknown>).id;
    if (typeof runId === "string") return runId;
  }
  return undefined;
}

function collectUrls(value: unknown, target: string[] = []): string[] {
  if (!value) return target;
  if (typeof value === "string") {
    if (/^https?:\/\//.test(value)) target.push(value);
    return target;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectUrls(item, target));
    return target;
  }
  if (typeof value === "object") {
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      if (/image|url|asset|stored/i.test(key)) collectUrls(item, target);
      if (key === "result" || key === "resultPayload" || key === "outputs") collectUrls(item, target);
    });
  }
  return Array.from(new Set(target));
}

function readStatus(payload: unknown): string | undefined {
  if (!payload || typeof payload !== "object") return undefined;
  const body = payload as Record<string, unknown>;
  const status = body.status || body.taskStatus || body.state;
  return typeof status === "string" ? status : undefined;
}

function normalizeErrorText(value: unknown): string | undefined {
  const explain = (text: string | undefined): string | undefined => {
    if (!text) return undefined;
    const hints: Array<[string, string]> = [
      ["AUTHORIZATION_REQUIRED", "当前访问凭证无效；请联系平台客服或运营人员处理。"],
      ["BUSINESS_API_KEY_INACTIVE", "当前访问凭证已停用；请联系平台客服或运营人员处理。"],
      ["BUSINESS_API_KEY_EXPIRED", "当前访问凭证已过期；请联系平台客服或运营人员处理。"],
      ["BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED", "当前功能暂未开通；请联系平台客服或运营人员处理。"],
      ["VENDOR_API_CLIENT_FORBIDDEN", "当前服务暂时不可用；请稍后重试或联系平台客服。"],
      ["EXECUTOR_BUSY", "执行节点繁忙；请稍后重试或降低并发。"],
      ["COMFYUI_EXECUTOR_UNAVAILABLE", "ComfyUI 执行节点不可用或队列已满；请稍后重试。"]
    ];
    const matched = hints.find(([code]) => text.includes(code));
    return matched ? `${text}。${matched[1]}` : text;
  };
  if (!value) return undefined;
  if (typeof value === "object") {
    const body = value as Record<string, unknown>;
    const detail = body.detail;
    if (detail && typeof detail === "object") {
      const nested = detail as Record<string, unknown>;
      const code = nested.errorCode || nested.code;
      const message = nested.message || nested.error;
      if (code || message) return explain([code, message].filter(Boolean).join(": "));
    }
    const code = body.errorCode || body.code;
    const message = body.message || body.error || body.detail;
    if (code || message) return explain([code, message].filter(Boolean).join(": "));
  }
  const text = String(value).trim();
  const codeMatch = text.match(/['"]errorCode['"]:\s*['"]([^'"]+)['"]/);
  const messageMatch = text.match(/['"]message['"]:\s*['"]([^'"]+)['"]/);
  if (codeMatch || messageMatch) {
    return explain([codeMatch?.[1], messageMatch?.[1]].filter(Boolean).join(": "));
  }
  return explain(text || undefined);
}

async function mediaRequest<T>(path: string, payload: Record<string, unknown>): Promise<T> {
  const { mediaBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${mediaBaseUrl}${path}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    }, 20000);
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "媒体服务请求失败");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeErrorText(data?.detail || data?.message || data) || `HTTP ${response.status}`);
  }
  return data as T;
}

async function ensureUploadKey(userId = "client-web"): Promise<string> {
  const now = Date.now();
  if (cachedUploadKey && cachedUploadKey.expiresAt - now > 60 * 1000) {
    return cachedUploadKey.token;
  }
  const response = await mediaRequest<UploadKeyResponse>("/v1/upload-key", { userId });
  cachedUploadKey = {
    token: response.uploadKey,
    expiresAt: Date.parse(response.expiresAt)
  };
  return response.uploadKey;
}

function buildObjectUrl(payload: OssCredentialResponse): string {
  const domain = (payload.ossCredentials.publicDomain || payload.host || "").replace(/\/$/, "");
  const objectKey = payload.objectKey
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${domain}/${objectKey}`;
}

function createOssClient(credentials: OssCredentials) {
  const endpoint = credentials.endpoint?.trim();
  const config: {
    region: string;
    accessKeyId: string;
    accessKeySecret: string;
    bucket: string;
    secure: boolean;
    endpoint?: string;
    stsToken?: string;
  } = {
    region: credentials.region,
    accessKeyId: credentials.accessKeyId,
    accessKeySecret: credentials.accessKeySecret,
    bucket: credentials.bucket,
    secure: true
  };
  if (endpoint) {
    config.endpoint = endpoint.startsWith("http") ? endpoint : `https://${endpoint}`;
  }
  if (credentials.securityToken) {
    config.stsToken = credentials.securityToken;
  }
  return new OSS(config);
}

function normalize(payload: unknown): ApiResult {
  const body = payload as Record<string, unknown> | null;
  const imageUrls = body
    ? collectUrls(
        body.imageUrls ||
          body.resultUrls ||
          body.outputUrls ||
          body.images ||
          body.assets ||
          body.resultPayload ||
          body.result
      )
    : [];
  const videoUrls = body ? collectUrls(body.videoUrls || body.videos || body.resultPayload || body.result) : [];
  const error = body?.error || body?.errorMessage || body?.errorCode;
  return {
    ok: !error,
    runId: readRunId(payload),
    status: readStatus(payload),
    imageUrls,
    videoUrls,
    text: typeof body?.text === "string" ? body.text : undefined,
    error: normalizeErrorText(error),
    raw: payload
  };
}

export async function checkBackendHealth(): Promise<{ ok: boolean; message: string }> {
  const { apiBaseUrl } = getRuntimeConfig();
  try {
    const response = await fetchWithTimeout(`${apiBaseUrl}/health`, {}, 8000);
    if (!response.ok) {
      return { ok: false, message: `HTTP ${response.status}` };
    }
    const data = await response.json().catch(() => ({}));
    const status = data?.status ? String(data.status) : "ok";
    return { ok: status === "ok", message: status };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "后端不可达"
    };
  }
}

export async function submitBusinessRun(endpoint: string, payload: Record<string, unknown>): Promise<ApiResult> {
  const { apiBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl}${endpoint}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    }, 20000);
  } catch (error) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: error instanceof Error ? error.message : "网络请求失败"
    };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: normalizeErrorText(data?.detail || data?.message) || `HTTP ${response.status}`,
      raw: data
    };
  }
  return normalize(data);
}

export async function getBusinessRun(runId: string): Promise<ApiResult> {
  const { apiBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl}/api/business/runs/get`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ runId, detail: "full" })
    }, 15000);
  } catch (error) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: error instanceof Error ? error.message : "网络请求失败"
    };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: normalizeErrorText(data?.detail || data?.message) || `HTTP ${response.status}`,
      raw: data
    };
  }
  return normalize(data);
}

export async function previewBusinessRoute(endpoint: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { apiBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl}${endpoint}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    }, 15000);
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "路由预检请求失败");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(normalizeErrorText(data?.detail || data?.message || data) || `HTTP ${response.status}`);
  }
  return data as Record<string, unknown>;
}

export async function uploadClientImage(file: File, userId = "client-web"): Promise<UploadResult> {
  const uploadKey = await ensureUploadKey(userId);
  const credential = await mediaRequest<OssCredentialResponse>("/v1/sts", {
    uploadKey,
    taskId: `client-upload-${Date.now()}`,
    action: "client-image-upload",
    fileName: file.name,
    mimeType: file.type || "application/octet-stream",
    fileSize: file.size,
    channel: "podi-client-web"
  });
  const client = createOssClient(credential.ossCredentials);
  await client.put(credential.objectKey, file);
  return {
    url: buildObjectUrl(credential),
    objectKey: credential.objectKey,
    name: file.name,
    size: file.size
  };
}

export function fetchClientMe(): Promise<ClientMeResponse> {
  return clientRequest<ClientMeResponse>("/api/client/me");
}

export function fetchClientAssets(options: { assetType?: string; selected?: boolean; limit?: number } = {}): Promise<ClientAssetListResponse> {
  const params = new URLSearchParams();
  if (options.assetType) params.set("asset_type", options.assetType);
  if (typeof options.selected === "boolean") params.set("selected", String(options.selected));
  if (options.limit) params.set("limit", String(options.limit));
  const query = params.toString();
  return clientRequest<ClientAssetListResponse>(`/api/client/assets${query ? `?${query}` : ""}`);
}

export function createClientAsset(payload: ClientAssetCreatePayload): Promise<ClientAsset> {
  return clientRequest<ClientAsset>("/api/client/assets", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchClientWallet(): Promise<ClientWalletResponse> {
  return clientRequest<ClientWalletResponse>("/api/client/wallet");
}

export function fetchClientProductionOrders(): Promise<ClientProductionOrder[]> {
  return clientRequest<ClientProductionOrder[]>("/api/client/production-orders");
}

export function createClientProductionOrder(payload: ClientProductionOrderCreatePayload): Promise<ClientProductionOrder> {
  return clientRequest<ClientProductionOrder>("/api/client/production-orders", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 60000);
}

export function clientAssetToAssetItem(asset: ClientAsset): AssetItem {
  const type = mapClientAssetType(asset.assetType);
  return {
    id: asset.id,
    type,
    title: asset.title || asset.fileName || "未命名素材",
    url: asset.url,
    thumbnailUrl: asset.url,
    source: asset.sourceBusinessKey || asset.sourceFlowStepKey || "服务端素材",
    createdAt: asset.createdAt,
    selected: asset.selected,
    favorite: Boolean(asset.metadata?.favorite),
    visibility: "private"
  };
}

function mapClientAssetType(assetType: string): AssetType {
  if (assetType === "pattern") return "pattern";
  if (assetType === "variant") return "variation";
  if (assetType === "product_image" || assetType === "angle_image" || assetType === "model_image") return "ai_generated";
  if (assetType === "input_image") return "original";
  return "processed";
}

export function getApiBaseUrl(): string {
  return getRuntimeConfig().apiBaseUrl;
}

export function getMediaBaseUrl(): string {
  return getRuntimeConfig().mediaBaseUrl;
}

export function hasApiKey(): boolean {
  return Boolean(getRuntimeConfig().apiKey);
}

export function hasAccessToken(): boolean {
  return Boolean(getRuntimeConfig().accessToken);
}
