import OSS from "ali-oss";
import type {
  ApiResult,
  AssetLicenseMode,
  AssetItem,
  InspirationWork,
  ProcessTask,
  ProcessTaskType,
  ProductDesignQuickIntake,
  ProductDesignAgentSession,
  ProductionOrderSnapshot,
  PublishApplicationSnapshot,
  UploadResult,
  WorkKind,
} from "./types";

const CONFIG_STORAGE_KEY = "podi-client-web.runtime-config.v1";
const browserOrigin = typeof window !== "undefined" ? window.location.origin : "";
const defaultApiOrigin = import.meta.env.DEV ? "http://127.0.0.1:8240" : `${browserOrigin}/client-api`;
const defaultBaseUrl = (import.meta.env.VITE_PODI_API_BASE || defaultApiOrigin).replace(/\/$/, "");
const defaultApiKey = import.meta.env.VITE_PODI_API_KEY || "";

export interface RuntimeConfig {
  apiBaseUrl: string;
  mediaBaseUrl: string;
  businessBaseUrl: string;
  apiKey: string;
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

export interface ClientBootstrap {
  userId: string;
  assets: AssetItem[];
  processTasks: ProcessTask[];
  designAgentSessions: ProductDesignAgentSession[];
  orders: ProductionOrderSnapshot[];
  wallet: {
    userId: string;
    aiCredits: number;
    productCouponCount: number;
    shareBalance: number;
    latestWalletEvent?: string | null;
    coupons?: ClientCoupon[];
  };
  inspirationWorks: InspirationWork[];
  publishApplications: PublishApplicationSnapshot[];
}

export interface ClientCoupon {
  id: string;
  name: string;
  scope: string;
  valuePoints: number;
  value?: string;
  status: string;
  expiresAt?: string | null;
  source?: string;
}

export interface ClientCommerceConfig {
  shippingFeeCents: number;
  shippingConfigured: boolean;
  shippingOptions: Array<{ id: "zto" | "sf"; label: string; feeCents: number }>;
  currency: string;
}

export interface ClientProductPricing {
  productId: string;
  productName: string;
  salePriceCents?: number | null;
}

export interface ClientAuthUser {
  id: string;
  username: string;
  email: string;
  phone?: string | null;
  role: string;
  status: string;
  displayName?: string | null;
  tenantId?: string | null;
  clientId?: string | null;
  createdAt?: string | null;
  lastLoginAt?: string | null;
}

export interface ClientAuthSession {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
  refreshToken?: string | null;
  role: string;
  user: ClientAuthUser;
}

export interface ClientLoginPayload {
  usernameOrEmail: string;
  password: string;
}

export interface ClientRegisterPayload {
  email: string;
  username: string;
  password: string;
  displayName?: string;
  inviteCode?: string;
}

export interface ClientPhoneCodePayload {
  phone: string;
}

export interface ClientPhoneLoginPayload {
  phone: string;
  code: string;
  mode?: "login" | "register";
  displayName?: string;
  inviteCode?: string;
}

export interface SmsCodeResponse {
  ok: boolean;
  expiresIn: number;
  resendAfter?: number;
  testCode?: string | null;
}

export interface CreateProcessTaskPayload {
  userId?: string;
  type: ProcessTaskType;
  abilityTitle?: string;
  outputLabel?: string;
  inputAssetIds?: string[];
  inputImages?: string[];
  optionLabel?: string;
  sizeLabel?: string;
  outputCount?: number;
  params?: Record<string, unknown>;
}

export interface UpdateProcessTaskPayload {
  userId?: string;
  taskId: string;
  patch: Partial<ProcessTask>;
}

export interface AdvanceProcessTaskPayload {
  userId?: string;
  taskId: string;
}

let cachedUploadKey: { token: string; expiresAt: number } | null = null;

type RequestContext = "client" | "account" | "media" | "business" | "health" | "route" | "upload";

const contextFallback: Record<RequestContext, string> = {
  client: "操作没有成功，请稍后再试。",
  account: "账号服务暂时不可用，请稍后再试。",
  media: "图片上传服务暂时不可用，请稍后再试。",
  business: "能力服务暂时不可用，请稍后再试。",
  health: "暂时连接不上服务，请稍后再试。",
  route: "预检服务暂时不可用，请稍后再试。",
  upload: "图片上传失败，请稍后再试。",
};

const codeMessages: Record<string, string> = {
  AUTHORIZATION_REQUIRED: "当前访问凭证无效，请重新登录后再试。",
  INVALID_TOKEN: "登录状态已失效，请重新登录。",
  INVALID_TOKEN_PAYLOAD: "登录状态已失效，请重新登录。",
  INVALID_REFRESH_TOKEN: "登录状态已失效，请重新登录。",
  SESSION_NOT_FOUND: "登录会话不存在，请重新登录。",
  SESSION_REVOKED: "登录会话已失效，请重新登录。",
  SESSION_EXPIRED: "登录已过期，请重新登录。",
  LOGIN_IDENTIFIER_REQUIRED: "请先填写手机号。",
  INVALID_CREDENTIALS: "账号或密码不正确，请检查后重试。",
  USER_INACTIVE: "当前账号已停用，请联系平台处理。",
  PHONE_INVALID: "请输入正确的 11 位手机号。",
  PHONE_NOT_REGISTERED: "这个手机号还没有注册，请先创建账号。",
  PHONE_ALREADY_REGISTERED: "这个手机号已经注册，请直接登录。",
  SMS_CODE_REQUIRED: "请填写短信验证码。",
  SMS_CODE_INVALID: "验证码不正确或已失效，请检查短信后重新输入。",
  USERNAME_REQUIRED: "请填写用户名。",
  PASSWORD_TOO_SHORT: "密码长度不够，请至少填写 8 位。",
  USER_ALREADY_EXISTS: "该用户名或邮箱已经注册，可以直接登录。",
  LOGIN_RATE_LIMITED: "登录尝试过于频繁，请稍等几分钟后再试。",
  INVITE_CODE_INVALID: "邀请码格式不正确，请检查后重新输入。",
  INVITE_CODE_NOT_FOUND: "邀请码不存在，请检查后重新输入。",
  INVITE_CODE_USED: "邀请码已经被使用，请更换邀请码。",
  INVITE_CODE_EXPIRED: "邀请码已经过期，请联系邀请人重新生成。",
  INVITE_CODE_INACTIVE: "邀请码暂不可用，请联系邀请人确认。",
  CLIENT_TASK_FORBIDDEN: "你没有权限查看这个任务。",
  CLIENT_TASK_TYPE_INVALID: "当前图片处理能力不存在，请返回图片批处理页重新选择。",
  CLIENT_PRODUCT_NOT_FOUND: "当前商品不存在或还没有接入，请返回商品列表重新选择。",
  CLIENT_ASSET_NOT_FOUND: "当前素材不存在，请重新选择或上传素材。",
  CLIENT_ASSET_URL_INVALID: "图片地址格式不正确，请重新上传图片。",
  CLIENT_ASSET_USER_REQUIRED: "登录状态不完整，请刷新页面后重新选择素材。",
  CLIENT_ASSET_PREVIEW_UNAVAILABLE: "当前图片暂时不能用于 3D 预览，请重新上传后再试。",
  CLIENT_ASSET_PREVIEW_TOO_LARGE: "图片文件过大，暂时不能用于 3D 预览。",
  CLIENT_QUEUE_LIMIT_REACHED: "当前排队任务较多，请稍后再提交。",
  CLIENT_BUSINESS_ENDPOINT_MISSING: "当前图片处理能力缺少业务接口配置，请先完成接入。",
  CLIENT_BATCH_FAILED: "这批图片里有任务处理失败，请进入任务详情查看原因。",
  CLIENT_SHIPPING_ADDRESS_REQUIRED: "请先填写完整收货信息，再提交试做订单。",
  CLIENT_SHIPPING_OPTION_INVALID: "请选择中通或顺丰配送后再提交订单。",
  CLIENT_ORDER_NOT_FOUND: "当前订单不存在，请刷新订单列表后重试。",
  CLIENT_ORDER_PAYMENT_AMOUNT_MISMATCH: "支付金额与订单待付金额不一致，请刷新订单后重试。",
  CLIENT_ORDER_SUPPLY_CHAIN_PAYLOAD_INVALID: "当前商品信息还不完整，暂时不能提交生产订单。",
  CLIENT_PRODUCT_REQUIRED: "请先选择商品，再进入 AI 帮我设计。",
  CLIENT_DESIGN_AGENT_SESSION_NOT_FOUND: "这个 AI 设计会话不存在，请重新开始一个设计。",
  CLIENT_DESIGN_AGENT_MESSAGE_REQUIRED: "请先告诉 AI 你想怎么设计。",
  CLIENT_DESIGN_AGENT_PLAN_NOT_FOUND: "这个设计方案已经失效，请重新生成方案。",
  CLIENT_DESIGN_AGENT_CLARIFY_REQUIRED: "这个方案还需要先补充设计方向。",
  BUSINESS_API_KEY_INACTIVE: "当前访问凭证已停用，请联系平台处理。",
  BUSINESS_API_KEY_EXPIRED: "当前访问凭证已过期，请联系平台处理。",
  BUSINESS_API_KEY_BUSINESS_NOT_ALLOWED: "当前功能还没有开通，请联系平台处理。",
  VENDOR_API_CLIENT_FORBIDDEN: "上游能力服务暂时不可用，请稍后重试。",
  EXECUTOR_BUSY: "当前处理队列较忙，请稍后再试。",
  COMFYUI_EXECUTOR_UNAVAILABLE: "图片处理节点暂时不可用或队列已满，请稍后再试。",
  RATE_LIMIT_REACHED: "当前请求过于频繁，请稍等一会儿再试。",
  QUEUE_LIMIT_REACHED: "当前排队任务较多，请稍后再提交。",
  MIDPLATFORM_UNAVAILABLE: "中台能力服务暂时没有连接成功。当前不会使用本地假结果，请启动中台或检查业务服务到中台的配置后再提交。",
};

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

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function textFromUnknown(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value.trim();
  if (value instanceof Error) return value.message.trim();
  if (isPlainObject(value)) {
    const detail = value.detail;
    if (isPlainObject(detail)) {
      const code = detail.errorCode || detail.code;
      const message = detail.message || detail.error;
      return [code, message].filter(Boolean).map(String).join(": ");
    }
    const code = value.errorCode || value.code;
    const message = value.message || value.error || value.detail;
    if (code || message) return [code, message].filter(Boolean).map(String).join(": ");
  }
  return String(value).trim();
}

function knownCodeFromText(text: string): string | undefined {
  const direct = Object.keys(codeMessages).find((code) => text.includes(code));
  if (direct) return direct;
  const errorCodeMatch = text.match(/['"]errorCode['"]:\s*['"]([^'"]+)['"]/);
  if (errorCodeMatch?.[1] && codeMessages[errorCodeMatch[1]]) return errorCodeMatch[1];
  const codeMatch = text.match(/['"]code['"]:\s*['"]([^'"]+)['"]/);
  if (codeMatch?.[1] && codeMessages[codeMatch[1]]) return codeMatch[1];
  return undefined;
}

function friendlyErrorMessage(
  value: unknown,
  options: { status?: number; context?: RequestContext; fallback?: string } = {}
): string {
  const context = options.context || "client";
  const fallback = options.fallback || contextFallback[context];
  const text = textFromUnknown(value);
  const lower = text.toLowerCase();
  const knownCode = knownCodeFromText(text);

  if (knownCode) return codeMessages[knownCode];
  if (lower.includes("abort") || text.includes("请求超时") || lower.includes("timeout") || lower.includes("timed out")) {
    return context === "business"
      ? "处理时间较长，请稍后到任务中心查看结果；如果没有生成结果，再重新提交。"
      : "请求时间较长，请稍后重试。";
  }
  if (
    lower.includes("failed to fetch") ||
    lower.includes("networkerror") ||
    lower.includes("connection refused") ||
    lower.includes("econnrefused") ||
    lower.includes("couldn't connect") ||
    lower.includes("failed to connect") ||
    text.includes("后端不可达")
  ) {
    return "暂时连接不上服务，请稍后重试。若你正在本地测试，请确认后端服务已启动。";
  }

  if (options.status) {
    if (options.status === 400) return "填写信息不完整或格式不正确，请检查后再提交。";
    if (options.status === 401) return "登录状态已失效，请重新登录。";
    if (options.status === 403) return "当前账号没有权限使用这个功能。";
    if (options.status === 404) return "请求的内容不存在，可能已经被删除或功能尚未开放。";
    if (options.status === 409) return "当前数据状态已变化，请刷新后再试。";
    if (options.status === 413) return "文件太大，请压缩或换一张图片后再上传。";
    if (options.status === 422) return "填写信息不完整或格式不正确，请检查后再提交。";
    if (options.status === 429) return "当前请求过于频繁，请稍等一会儿再试。";
    if (options.status >= 500) return "服务暂时不可用，请稍后重试。";
  }

  if (/^[A-Z0-9_:-]+$/.test(text) || /^HTTP\s+\d+/i.test(text)) return fallback;
  if (/[\u4e00-\u9fa5]/.test(text) && text.length <= 80) return text;
  return fallback;
}

function requestErrorMessage(error: unknown, context: RequestContext): string {
  return friendlyErrorMessage(error, { context });
}

function responseErrorMessage(response: Response, data: unknown, context: RequestContext): string {
  return friendlyErrorMessage(data, { status: response.status, context });
}

async function jsonRequest<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const { apiBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...headers(),
        ...(init.headers || {})
      }
    }, timeoutMs);
  } catch (error) {
    throw new Error(requestErrorMessage(error, "client"));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data, "client"));
  }
  return data as T;
}

function normalizeUrl(value: string, fallback: string): string {
  const trimmed = value.trim();
  return (trimmed || fallback).replace(/\/$/, "");
}

function isLegacyLocalMidPlatformUrl(value?: string | null): boolean {
  if (!value) return false;
  return /^https?:\/\/(localhost|127\.0\.0\.1):8099(\/.*)?$/i.test(value.trim());
}

function isLocalBusinessMediaUrl(value?: string | null): boolean {
  if (!value) return false;
  return /^https?:\/\/(localhost|127\.0\.0\.1):8240\/api\/media(\/.*)?$/i.test(value.trim());
}

function migrateLegacyLocalUrl(value: string | undefined, fallback: string): string {
  if (isLegacyLocalMidPlatformUrl(value) && !isLegacyLocalMidPlatformUrl(fallback)) {
    return fallback;
  }
  return value || fallback;
}

function migrateMediaUrl(value: string | undefined, fallback: string): string {
  if (isLocalBusinessMediaUrl(value) && !isLocalBusinessMediaUrl(fallback)) {
    return fallback;
  }
  return migrateLegacyLocalUrl(value, fallback);
}

function defaultConfig(): RuntimeConfig {
  const apiBaseUrl = defaultBaseUrl;
  return {
    apiBaseUrl,
    mediaBaseUrl: normalizeUrl(import.meta.env.VITE_PODI_MEDIA_BASE || `${apiBaseUrl}/api/media`, `${apiBaseUrl}/api/media`),
    businessBaseUrl: normalizeUrl(import.meta.env.VITE_PODI_BUSINESS_BASE || apiBaseUrl, apiBaseUrl),
    apiKey: defaultApiKey
  };
}

export function getRuntimeConfig(): RuntimeConfig {
  const fallback = defaultConfig();
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(CONFIG_STORAGE_KEY);
    const stored = raw ? (JSON.parse(raw) as Partial<RuntimeConfig>) : {};
    const apiBaseUrl = normalizeUrl(migrateLegacyLocalUrl(stored.apiBaseUrl, fallback.apiBaseUrl), fallback.apiBaseUrl);
    return {
      apiBaseUrl,
      mediaBaseUrl: normalizeUrl(
        migrateMediaUrl(stored.mediaBaseUrl, fallback.mediaBaseUrl || `${apiBaseUrl}/api/media`),
        `${apiBaseUrl}/api/media`
      ),
      businessBaseUrl: normalizeUrl(
        migrateLegacyLocalUrl(stored.businessBaseUrl, fallback.businessBaseUrl || apiBaseUrl),
        apiBaseUrl
      ),
      apiKey: (stored.apiKey || fallback.apiKey || "").trim()
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
    businessBaseUrl: normalizeUrl(config.businessBaseUrl || apiBaseUrl, apiBaseUrl),
    apiKey: config.apiKey.trim()
  };
  cachedUploadKey = null;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

function headers(): HeadersInit {
  const apiKey = getRuntimeConfig().apiKey;
  const value: HeadersInit = {
    "Content-Type": "application/json"
  };
  if (apiKey) {
    value["X-PODI-API-Key"] = apiKey;
  }
  return value;
}

function authHeaders(accessToken?: string | null): HeadersInit {
  const value: Record<string, string> = { ...(headers() as Record<string, string>) };
  if (accessToken) {
    value.Authorization = `Bearer ${accessToken}`;
  }
  return value;
}

async function authRequest<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  const { apiBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        ...headers(),
        ...(init.headers || {})
      }
    }, timeoutMs);
  } catch (error) {
    throw new Error(requestErrorMessage(error, "account"));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data, "account"));
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
  if (!value) return undefined;
  return friendlyErrorMessage(value, { context: "business" });
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
    throw new Error(requestErrorMessage(error, "media"));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data, "media"));
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

function isLocalApiBase(): boolean {
  const { mediaBaseUrl } = getRuntimeConfig();
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/.*)?$/i.test(mediaBaseUrl);
}

function normalize(payload: unknown): ApiResult {
  const body = payload as Record<string, unknown> | null;
  const imageUrls = body ? collectUrls(body.imageUrls || body.images || body.assets || body.resultPayload || body.result) : [];
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
      return { ok: false, message: responseErrorMessage(response, {}, "health") };
    }
    const data = await response.json().catch(() => ({}));
    const status = data?.status ? String(data.status) : "ok";
    return { ok: status === "ok", message: status };
  } catch (error) {
    return {
      ok: false,
      message: requestErrorMessage(error, "health")
    };
  }
}

export async function loginClient(payload: ClientLoginPayload): Promise<ClientAuthSession> {
  const identifier = payload.usernameOrEmail.trim();
  const body = identifier.includes("@")
    ? { email: identifier, password: payload.password }
    : { username: identifier, password: payload.password };
  return authRequest<ClientAuthSession>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  }, 15000);
}

export async function registerClient(payload: ClientRegisterPayload): Promise<ClientAuthSession> {
  const body: Record<string, string> = {
    email: payload.email.trim(),
    username: payload.username.trim(),
    password: payload.password,
  };
  if (payload.displayName?.trim()) body.displayName = payload.displayName.trim();
  if (payload.inviteCode?.trim()) body.inviteCode = payload.inviteCode.trim();
  return authRequest<ClientAuthSession>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  }, 15000);
}

export async function requestPhoneCode(payload: ClientPhoneCodePayload): Promise<SmsCodeResponse> {
  return authRequest<SmsCodeResponse>("/api/auth/sms-code", {
    method: "POST",
    body: JSON.stringify({ phone: payload.phone.trim() }),
  }, 12000);
}

export async function loginWithPhoneCode(payload: ClientPhoneLoginPayload): Promise<ClientAuthSession> {
  const body: Record<string, string> = {
    phone: payload.phone.trim(),
    code: payload.code.trim(),
  };
  if (payload.mode) body.mode = payload.mode;
  if (payload.displayName?.trim()) body.displayName = payload.displayName.trim();
  if (payload.inviteCode?.trim()) body.inviteCode = payload.inviteCode.trim();
  return authRequest<ClientAuthSession>("/api/auth/phone-login", {
    method: "POST",
    body: JSON.stringify(body),
  }, 15000);
}

export async function getCurrentAuthUser(accessToken: string): Promise<ClientAuthUser> {
  return authRequest<ClientAuthUser>("/api/auth/me", {
    headers: authHeaders(accessToken),
  }, 12000);
}

export async function refreshAuthSession(refreshToken: string): Promise<ClientAuthSession> {
  return authRequest<ClientAuthSession>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refreshToken }),
  }, 12000);
}

export async function logoutClient(accessToken?: string | null, refreshToken?: string | null): Promise<void> {
  if (!accessToken) return;
  await authRequest("/api/auth/logout", {
    method: "POST",
    headers: authHeaders(accessToken),
    body: JSON.stringify({ refreshToken: refreshToken || undefined }),
  }, 10000);
}

function normalizePublishStatus(value: string): PublishApplicationSnapshot["status"] {
  if (value === "approved") return "已通过";
  if (value === "rejected") return "已拒绝";
  return "待审核";
}

function normalizePublishApplication(item: PublishApplicationSnapshot & { status: string }): PublishApplicationSnapshot {
  return {
    ...item,
    status: normalizePublishStatus(item.status),
  };
}

export async function getClientBootstrap(userId = "guest"): Promise<ClientBootstrap> {
  const search = new URLSearchParams({ userId });
  const data = await jsonRequest<ClientBootstrap>(`/api/client/v1/bootstrap?${search.toString()}`, {}, 12000);
  return {
    ...data,
    publishApplications: (data.publishApplications || []).map((item) =>
      normalizePublishApplication(item as PublishApplicationSnapshot & { status: string })
    ),
  };
}

export async function createClientAsset(payload: {
  userId?: string;
  id?: string;
  type?: AssetItem["type"];
  title: string;
  url: string;
  thumbnailUrl?: string | null;
  source?: string;
  visibility?: AssetItem["visibility"];
  licenseMode?: AssetItem["licenseMode"];
  licenseSource?: AssetItem["licenseSource"];
  licensePoints?: number | null;
  author?: string | null;
  acquiredAt?: string | null;
  usedInProducts?: number | null;
  width?: number | null;
  height?: number | null;
  dpi?: number | null;
  metadata?: Record<string, unknown>;
}): Promise<AssetItem> {
  const body = {
    userId: "demo-user",
    type: "original" as AssetItem["type"],
    source: "用户上传",
    visibility: "private" as AssetItem["visibility"],
    ...payload,
  };
  const isLocalPreviewUrl = body.url.startsWith("data:") || body.url.startsWith("blob:");
  const localAsset = (): AssetItem => ({
    id: `local-asset-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type: body.type,
    title: body.title,
    url: body.url,
    thumbnailUrl: body.thumbnailUrl || body.url,
    source: body.source,
    createdAt: new Date().toISOString(),
    selected: true,
    favorite: false,
    visibility: body.visibility,
    licenseMode: body.licenseMode,
    licenseSource: body.licenseSource,
    licensePoints: body.licensePoints,
    author: body.author || undefined,
    acquiredAt: body.acquiredAt || undefined,
    usedInProducts: body.usedInProducts || 0,
    width: body.width ?? null,
    height: body.height ?? null,
    dpi: body.dpi ?? null,
    metadata: {
      ...body.metadata,
      localOnly: true,
      localFallbackReason: "local_preview_url",
    },
  });
  if (isLocalApiBase() && isLocalPreviewUrl) return localAsset();
  try {
    return await jsonRequest<AssetItem>("/api/client/v1/assets", {
      method: "POST",
      body: JSON.stringify(body)
    }, 12000);
  } catch (error) {
    if (!isLocalApiBase() || !isLocalPreviewUrl) throw error;
    return localAsset();
  }
}

export async function createVerifiedSeamlessArtwork(payload: {
  userId?: string;
  sourceUrl: string;
  sourceAssetId?: string;
  businessRunId?: string;
  title?: string;
  width: number;
  height: number;
  dpi?: number;
  seamlessMode?: "two_way" | "four_way";
}): Promise<AssetItem> {
  return jsonRequest<AssetItem>("/api/client/v1/production-artwork/seamless", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 90000);
}

export async function createClientProcessTask(payload: CreateProcessTaskPayload): Promise<ProcessTask & { wallet?: ClientBootstrap["wallet"] }> {
  return jsonRequest<ProcessTask & { wallet?: ClientBootstrap["wallet"] }>("/api/client/v1/process-tasks", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 20000);
}

export async function getClientCommerceConfig(): Promise<ClientCommerceConfig> {
  return jsonRequest<ClientCommerceConfig>("/api/client/v1/commerce-config", {}, 12000);
}

export async function getClientProductPricing(): Promise<ClientProductPricing[]> {
  return jsonRequest<ClientProductPricing[]>("/api/client/v1/product-pricing", {}, 12000);
}

export async function updateClientProcessTask(payload: UpdateProcessTaskPayload): Promise<ProcessTask> {
  return jsonRequest<ProcessTask>("/api/client/v1/process-tasks/update", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 12000);
}

export async function advanceClientProcessTask(payload: AdvanceProcessTaskPayload): Promise<ProcessTask> {
  return jsonRequest<ProcessTask>("/api/client/v1/process-tasks/advance", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 30000);
}

export async function createClientProductSample(payload: {
  userId?: string;
  productId: string;
  productName?: string;
  assetId: string;
  sourceAssetUrl?: string;
  sourceAssetTitle?: string;
  surfaceName?: string | null;
  sizeLabel?: string | null;
  designConfig?: Record<string, unknown>;
}): Promise<AssetItem> {
  return jsonRequest<AssetItem>("/api/client/v1/product-samples", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 20000);
}

export async function createProductDesignAgentSession(payload: {
  userId?: string;
  productId: string;
  productName?: string;
  productContext?: Record<string, unknown>;
  sourceAssetIds?: string[];
  sourceImageUrls?: string[];
  message: string;
}): Promise<ProductDesignAgentSession> {
  return jsonRequest<ProductDesignAgentSession>("/api/client/v1/product-design-agent/sessions", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 90000);
}

export async function createProductDesignQuickIntake(payload: {
  userId?: string;
  productId: string;
  productName?: string;
  productContext?: Record<string, unknown>;
  sourceAssetIds?: string[];
  message?: string;
}): Promise<ProductDesignQuickIntake> {
  return jsonRequest<ProductDesignQuickIntake>("/api/client/v1/product-design-intakes", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 90000);
}

export async function getProductDesignAgentSession(payload: {
  userId?: string;
  sessionId: string;
}): Promise<ProductDesignAgentSession> {
  const search = new URLSearchParams({ userId: payload.userId || "demo-user" });
  return jsonRequest<ProductDesignAgentSession>(
    `/api/client/v1/product-design-agent/sessions/${encodeURIComponent(payload.sessionId)}?${search.toString()}`,
    {},
    12000
  );
}

export async function sendProductDesignAgentMessage(payload: {
  userId?: string;
  sessionId: string;
  message: string;
  sourceAssetIds?: string[];
  sourceImageUrls?: string[];
}): Promise<ProductDesignAgentSession> {
  const { sessionId, ...body } = payload;
  return jsonRequest<ProductDesignAgentSession>(
    `/api/client/v1/product-design-agent/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: "POST",
      body: JSON.stringify({
        userId: "demo-user",
        ...body,
      })
    },
    90000
  );
}

export async function confirmProductDesignAgentPlan(payload: {
  userId?: string;
  sessionId: string;
  planId: string;
}): Promise<{
  session: ProductDesignAgentSession;
  resultAssets: AssetItem[];
  status?: string;
  message?: string;
  wallet?: ClientBootstrap["wallet"];
}> {
  const { sessionId, planId, ...body } = payload;
  return jsonRequest<{
    session: ProductDesignAgentSession;
    resultAssets: AssetItem[];
    status?: string;
    message?: string;
    wallet?: ClientBootstrap["wallet"];
  }>(
    `/api/client/v1/product-design-agent/sessions/${encodeURIComponent(sessionId)}/plans/${encodeURIComponent(planId)}/confirm`,
    {
      method: "POST",
      body: JSON.stringify({
        userId: "demo-user",
        ...body,
      })
    },
    60000
  );
}

export async function confirmProductDesignAgentStep(payload: {
  userId?: string;
  sessionId: string;
  stepId: string;
  assetId?: string | null;
  surfaceId: string;
  surfaceLabel?: string | null;
  mode?: string;
  fullBleed?: boolean;
  needsSeamless?: boolean;
  scale?: number;
  position?: { x: number; y: number };
}): Promise<ProductDesignAgentSession> {
  const { sessionId, stepId, ...body } = payload;
  return jsonRequest<ProductDesignAgentSession>(
    `/api/client/v1/product-design-agent/sessions/${encodeURIComponent(sessionId)}/steps/${encodeURIComponent(stepId)}/confirm`,
    {
      method: "POST",
      body: JSON.stringify({
        userId: "demo-user",
        ...body,
      })
    },
    18000
  );
}

export async function applyProductDesignAgentPreview(payload: {
  userId?: string;
  sessionId: string;
  assetId?: string | null;
  designConfig?: Record<string, unknown>;
}): Promise<{ session: ProductDesignAgentSession; previewAsset: AssetItem }> {
  const { sessionId, ...body } = payload;
  return jsonRequest<{ session: ProductDesignAgentSession; previewAsset: AssetItem }>(
    `/api/client/v1/product-design-agent/sessions/${encodeURIComponent(sessionId)}/apply-preview`,
    {
      method: "POST",
      body: JSON.stringify({
        userId: "demo-user",
        ...body,
      })
    },
    20000
  );
}

export async function createClientOrder(payload: {
  userId?: string;
  productId: string;
  productName?: string;
  assetId: string;
  sourceAssetId?: string;
  sourceAssetUrl?: string;
  sourceAssetTitle?: string;
  clientRequestId?: string;
  checkoutGroupId?: string;
  shippingMethod?: "zto" | "sf";
  quantity?: number;
  useProductCoupon?: boolean;
  shippingSummary?: string | null;
  shippingAddress?: {
    country: string;
    state: string;
    city: string;
    district?: string;
    postalCode: string;
    address: string;
    phoneNumber: string;
    recipientName: string;
    email?: string;
  } | null;
}): Promise<ProductionOrderSnapshot> {
  return jsonRequest<ProductionOrderSnapshot>("/api/client/v1/orders", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      quantity: 1,
      ...payload,
    })
  }, 15000);
}

export async function payClientOrder(payload: {
  userId?: string;
  orderId: string;
  method?: "mock" | "wallet" | "wechat" | "alipay";
  confirmAmountCents?: number | null;
}): Promise<ProductionOrderSnapshot & { wallet?: ClientBootstrap["wallet"] }> {
  const { orderId, ...body } = payload;
  return jsonRequest<ProductionOrderSnapshot>(`/api/client/v1/orders/${encodeURIComponent(orderId)}/pay`, {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      method: "mock",
      ...body,
    })
  }, 15000);
}

export async function redeemClientCouponCode(payload: {
  userId: string;
  code: string;
}): Promise<{ coupon: ClientCoupon; wallet: ClientBootstrap["wallet"] }> {
  return jsonRequest<{ coupon: ClientCoupon; wallet: ClientBootstrap["wallet"] }>("/api/client/v1/coupons/redeem", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 15000);
}

export async function submitClientPublishApplication(payload: {
  userId?: string;
  kind: WorkKind;
  title: string;
  tags: string;
  usage: string;
  image: string;
  licenseMode?: AssetLicenseMode;
  pricePoints?: number | null;
}): Promise<PublishApplicationSnapshot> {
  const data = await jsonRequest<PublishApplicationSnapshot & { status: string }>("/api/client/v1/publish-applications", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 15000);
  return normalizePublishApplication(data);
}

export async function submitClientComplaint(payload: {
  userId?: string;
  workId: string;
  workTitle: string;
  workKind: WorkKind;
  author?: string;
  image?: string;
  type: string;
  contact: string;
  evidence: string;
  detail?: string;
}): Promise<Record<string, unknown>> {
  return jsonRequest<Record<string, unknown>>("/api/client/v1/complaints", {
    method: "POST",
    body: JSON.stringify({
      userId: "demo-user",
      ...payload,
    })
  }, 12000);
}

export async function submitBusinessRun(endpoint: string, payload: Record<string, unknown>): Promise<ApiResult> {
  const { businessBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${businessBaseUrl}${endpoint}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    }, 20000);
  } catch (error) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: requestErrorMessage(error, "business")
    };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: responseErrorMessage(response, data, "business"),
      raw: data
    };
  }
  return normalize(data);
}

export async function getBusinessRun(runId: string): Promise<ApiResult> {
  const { businessBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${businessBaseUrl}/api/business/runs/get`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ runId, detail: "full" })
    }, 15000);
  } catch (error) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: requestErrorMessage(error, "business")
    };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      ok: false,
      imageUrls: [],
      videoUrls: [],
      error: responseErrorMessage(response, data, "business"),
      raw: data
    };
  }
  return normalize(data);
}

export async function previewBusinessRoute(endpoint: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const { businessBaseUrl } = getRuntimeConfig();
  let response: Response;
  try {
    response = await fetchWithTimeout(`${businessBaseUrl}${endpoint}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload)
    }, 15000);
  } catch (error) {
    throw new Error(requestErrorMessage(error, "route"));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseErrorMessage(response, data, "route"));
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
  if (!credential.ossCredentials.accessKeyId || !credential.ossCredentials.accessKeySecret) {
    if (isLocalApiBase()) {
      const localPreviewUrl = await fileToDataUrl(file);
      try {
        const stored = await mediaRequest<{ url: string; objectKey: string }>("/v1/local-upload", {
          uploadKey,
          objectKey: credential.objectKey,
          fileName: file.name,
          mimeType: file.type || "application/octet-stream",
          fileSize: file.size,
          dataUrl: localPreviewUrl,
        });
        return {
          url: stored.url,
          objectKey: stored.objectKey,
          name: file.name,
          size: file.size
        };
      } catch {
        // 本地业务 API 未启动 local-upload 时，仍保留浏览器预览能力。
      }
      return {
        url: localPreviewUrl,
        objectKey: `local-upload/${userId}/${Date.now()}-${file.name}`,
        name: file.name,
        size: file.size
      };
    }
    throw new Error("图片上传服务还没有配置完成，请稍后再试。");
  }
  const client = createOssClient(credential.ossCredentials);
  await client.put(credential.objectKey, file);
  return {
    url: buildObjectUrl(credential),
    objectKey: credential.objectKey,
    name: file.name,
    size: file.size
  };
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("本地图片预览生成失败，请重新选择图片。"));
    reader.readAsDataURL(file);
  });
}

export function getApiBaseUrl(): string {
  return getRuntimeConfig().apiBaseUrl;
}

export function getMediaBaseUrl(): string {
  return getRuntimeConfig().mediaBaseUrl;
}

export function getBusinessBaseUrl(): string {
  return getRuntimeConfig().businessBaseUrl;
}

export function getClientAssetPreviewUrl(assetId: string, userId: string): string {
  const cleanAssetId = assetId.trim();
  const cleanUserId = userId.trim();
  if (!cleanAssetId || !cleanUserId) return "";
  const query = new URLSearchParams({ userId: cleanUserId });
  return `${getRuntimeConfig().businessBaseUrl}/api/client/v1/assets/${encodeURIComponent(cleanAssetId)}/preview?${query.toString()}`;
}

export function hasApiKey(): boolean {
  return Boolean(getRuntimeConfig().apiKey);
}
