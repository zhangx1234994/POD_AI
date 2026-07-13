/**
 * 全局状态管理 — React Context + useReducer
 * 替代原 App.tsx 中散落的 useState
 */
import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type {
  AppView,
  AssetItem,
  InspirationWork,
  ProcessTask,
  ProductDesignAgentSession,
  ProductCheckoutDraft,
  ProductOrderDraft,
  ProductionOrderSnapshot,
  PublishApplicationSnapshot,
  PublishDraftSource,
  WorkKind,
} from "../types";
import {
  advanceClientProcessTask,
  getClientBootstrap,
  getProductDesignAgentSession,
  getCurrentAuthUser,
  logoutClient,
  refreshAuthSession,
  type ClientAuthSession,
  type ClientAuthUser,
  type ClientCoupon,
} from "../api";
import { inspirationWorks as defaultInspirationWorks } from "../data/mock-data";

/* ── State ── */

export interface AppState {
  // 账号
  currentUser: ClientAuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;

  // 导航
  currentView: AppView;
  previousView: AppView | null;

  // 素材
  assets: AssetItem[];
  selectedAssetIds: string[];
  pendingProductDesignAssetId: string | null;

  // AI 批处理任务
  processTasks: ProcessTask[];
  latestProcessTaskId: string | null;

  // AI 产品设计助手
  designAgentSessions: ProductDesignAgentSession[];

  // 产品
  selectedProductId: string | null;
  selectedProductSizeLabel: string | null;
  selectedSurface: string | null;
  checkoutDraft: ProductCheckoutDraft | null;
  orderDrafts: ProductOrderDraft[];

  // 钱包（保持现有逻辑）
  aiCredits: number;
  productCouponCount: number;
  walletCoupons: ClientCoupon[];
  shareBalance: number;

  // 订单
  orders: ProductionOrderSnapshot[];

  // 灵感
  inspirationWorks: InspirationWork[];
  sameStyleWork: InspirationWork | null;

  // 公开
  publishApplications: PublishApplicationSnapshot[];
  publishDraftKind: WorkKind;
  publishDraftSource: PublishDraftSource | null;

  // 临时通知
  latestWalletEvent: string | null;
}

/* ── Actions ── */

export type AppAction =
  | {
      type: "SET_AUTH_SESSION";
      payload: {
        user: ClientAuthUser;
        accessToken: string;
        refreshToken: string | null;
      };
    }
  | { type: "UPDATE_AUTH_USER"; user: ClientAuthUser }
  | { type: "CLEAR_AUTH_SESSION" }
  | {
      type: "HYDRATE_CLIENT_BOOTSTRAP";
      payload: {
        assets: AssetItem[];
        processTasks: ProcessTask[];
        designAgentSessions?: ProductDesignAgentSession[];
        orders: ProductionOrderSnapshot[];
        wallet: {
          aiCredits: number;
          productCouponCount: number;
          shareBalance: number;
          latestWalletEvent?: string | null;
          coupons?: ClientCoupon[];
        };
        inspirationWorks: InspirationWork[];
        publishApplications: PublishApplicationSnapshot[];
      };
    }
  | { type: "NAVIGATE"; view: AppView }
  | { type: "TOGGLE_ASSET"; id: string }
  | { type: "SELECT_ASSETS"; ids: string[] }
  | { type: "SET_PENDING_PRODUCT_DESIGN_ASSET"; id: string | null }
  | { type: "CLEAR_SELECTION" }
  | { type: "ADD_ASSETS"; assets: AssetItem[] }
  | { type: "UPDATE_ASSET"; id: string; patch: Partial<AssetItem> }
  | { type: "DELETE_ASSET"; id: string }
  | { type: "ADD_PROCESS_TASK"; task: ProcessTask }
  | { type: "UPDATE_PROCESS_TASK"; id: string; patch: Partial<ProcessTask> }
  | { type: "UPSERT_DESIGN_AGENT_SESSION"; session: ProductDesignAgentSession }
  | { type: "SET_SELECTED_PRODUCT"; productId: string; sizeLabel?: string | null }
  | { type: "SET_SELECTED_SURFACE"; surface: string | null }
  | { type: "SET_CHECKOUT_DRAFT"; draft: ProductCheckoutDraft }
  | { type: "ADD_ORDER_DRAFT"; draft: ProductOrderDraft }
  | { type: "REMOVE_ORDER_DRAFT"; draftId: string }
  | { type: "CLEAR_ORDER_DRAFTS" }
  | { type: "CLEAR_CHECKOUT_DRAFT" }
  | { type: "ADD_ORDER"; order: ProductionOrderSnapshot }
  | { type: "UPDATE_ORDER"; id: string; patch: Partial<ProductionOrderSnapshot> }
  | { type: "SET_SAME_STYLE_WORK"; work: InspirationWork | null }
  | {
      type: "SET_WALLET";
      wallet: {
        aiCredits: number;
        productCouponCount: number;
        shareBalance: number;
        latestWalletEvent?: string | null;
        coupons?: ClientCoupon[];
      };
    }
  | { type: "ADD_CREDITS"; amount: number; event: string }
  | { type: "SPEND_CREDITS"; amount: number; event: string }
  | { type: "USE_PRODUCT_COUPON" }
  | { type: "ADD_REDEEM_REWARD" }
  | { type: "SET_PUBLISH_DRAFT"; kind: WorkKind; source: PublishDraftSource | null }
  | { type: "SUBMIT_PUBLISH"; application: PublishApplicationSnapshot }
  | { type: "CLEAR_WALLET_EVENT" };

function isUsableAsset(asset: AssetItem) {
  return !asset.url?.startsWith("blob:");
}

function cleanAssets(assets: AssetItem[]) {
  return assets.filter(isUsableAsset);
}

const PROCESS_TASK_STALE_MS = 60 * 60 * 1000;
const ACTIVE_PROCESS_ITEM_STATUSES = new Set([
  "queued",
  "dispatching",
  "running",
  "submitted",
  "pending",
  "processing",
]);

function formatLocalTimestamp(date = new Date()) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function isActiveProcessTask(task: ProcessTask) {
  return task.status === "pending" || task.status === "processing";
}

function isActiveProcessItemStatus(status: unknown) {
  return ACTIVE_PROCESS_ITEM_STATUSES.has(String(status || "").toLowerCase());
}

function parseProcessTimestamp(value?: string | null) {
  if (!value) return NaN;
  const direct = Date.parse(value);
  if (Number.isFinite(direct)) return direct;
  const match = value.match(
    /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?/
  );
  if (!match) return NaN;
  const [, year, month, day, hour, minute, second = "0"] = match;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second)
  ).getTime();
}

function normalizeStaleProcessTask(task: ProcessTask): ProcessTask {
  if (!isActiveProcessTask(task)) return task;
  const createdAt = parseProcessTimestamp(task.createdAt);
  if (!Number.isFinite(createdAt) || Date.now() - createdAt < PROCESS_TASK_STALE_MS) {
    return task;
  }
  const inputCount = task.inputCount ?? task.inputImages?.length ?? task.inputAssetIds?.length ?? 0;
  const resultCount = task.resultCount ?? task.resultImages?.length ?? task.outputAssetIds?.length ?? 0;
  const hasPartialResult = resultCount > 0 && (!inputCount || resultCount < inputCount);
  const queueItems = Array.isArray(task.params?.queueItems)
    ? task.params.queueItems.map((item: Record<string, unknown>) =>
        isActiveProcessItemStatus(item.status)
          ? {
              ...item,
              status: "failed",
              errorMessage: item.errorMessage || "等待时间过长，已停止。可重新提交。",
              completedAt: item.completedAt || formatLocalTimestamp(),
            }
          : item
      )
    : task.params?.queueItems;
  return {
    ...task,
    status: "failed",
    completedAt: task.completedAt ?? formatLocalTimestamp(),
    finalStatus: "timeout",
    callbackStatus: "已停止",
    errorCode: task.errorCode ?? "CLIENT_PROCESS_TASK_EXPIRED",
    errorMessage:
      task.errorMessage ??
      (hasPartialResult
        ? `已生成 ${resultCount}/${inputCount} 张，其余图片等待时间过长，已停止。可查看已生成结果或重新提交。`
        : "这批图片等待时间过长，已停止。请重新提交任务。"),
    params: {
      ...(task.params || {}),
      queueItems,
      staleNormalized: true,
    },
  };
}

function taskHasResult(task: ProcessTask) {
  return Boolean(
    task.status === "completed" ||
      task.completedAt ||
      (task.resultImages?.length ?? 0) > 0 ||
      (task.outputAssetIds?.length ?? 0) > 0 ||
      (task.resultCount ?? 0) > 0
  );
}

function mergeProcessTask(current: ProcessTask | undefined, incoming: ProcessTask): ProcessTask {
  incoming = normalizeStaleProcessTask(incoming);
  current = current ? normalizeStaleProcessTask(current) : undefined;
  if (!current) return incoming;
  if (!isActiveProcessTask(incoming) && isActiveProcessTask(current)) {
    return {
      ...current,
      ...incoming,
      inputImages: incoming.inputImages?.length ? incoming.inputImages : current.inputImages,
      resultImages: incoming.resultImages?.length ? incoming.resultImages : current.resultImages,
      outputAssetIds: incoming.outputAssetIds?.length ? incoming.outputAssetIds : current.outputAssetIds,
      resultCount: incoming.resultCount ?? current.resultCount,
      completedAt: incoming.completedAt ?? current.completedAt,
    };
  }
  const currentHasResult = taskHasResult(current);
  const incomingIsNonTerminal = isActiveProcessTask(incoming);
  const incomingRegresses =
    currentHasResult &&
    incomingIsNonTerminal;
  if (current.status === "failed" && incomingIsNonTerminal) {
    return current;
  }
  if (!incomingRegresses) {
    return {
      ...current,
      ...incoming,
      inputImages: incoming.inputImages?.length ? incoming.inputImages : current.inputImages,
      resultImages: incoming.resultImages?.length ? incoming.resultImages : current.resultImages,
      outputAssetIds: incoming.outputAssetIds?.length ? incoming.outputAssetIds : current.outputAssetIds,
      resultCount: incoming.resultCount ?? current.resultCount,
      completedAt: incoming.completedAt ?? current.completedAt,
    };
  }
  return {
    ...current,
    inputImages: current.inputImages?.length ? current.inputImages : incoming.inputImages,
    inputCount: current.inputCount ?? incoming.inputCount,
    finalStatus: current.finalStatus ?? incoming.finalStatus,
    callbackStatus: current.callbackStatus ?? incoming.callbackStatus,
    params: { ...(incoming.params || {}), ...(current.params || {}) },
  };
}

function mergeProcessTaskList(serverTasks: ProcessTask[], localTasks: ProcessTask[]) {
  const normalizedLocalTasks = localTasks.map(normalizeStaleProcessTask);
  const normalizedServerTasks = serverTasks.map(normalizeStaleProcessTask);
  const localById = new Map(normalizedLocalTasks.map((task) => [task.id, task]));
  const merged = normalizedServerTasks.map((task) => mergeProcessTask(localById.get(task.id), task));
  const serverIds = new Set(normalizedServerTasks.map((task) => task.id));
  const localOnly = normalizedLocalTasks.filter((task) => !serverIds.has(task.id));
  return [...localOnly, ...merged].sort((a, b) => parseProcessTimestamp(b.createdAt) - parseProcessTimestamp(a.createdAt));
}

/* ── Route helpers (must be before initialState) ── */

const viewRoutes: Record<AppView, string> = {
  home: "/",
  process: "/process",
  tasks: "/tasks",
  assets: "/assets",
  products: "/products",
  productDesign: "/products/design",
  checkout: "/checkout",
  editor: "/editor",
  imageEditor: "/image-editor",
  account: "/account",
  orders: "/orders",
  wallet: "/wallet",
  inspire: "/inspiration",
  publish: "/publish",
  profile: "/profile",
};

const routeAliases: Partial<Record<string, AppView>> = {
  "/login": "account",
  "/inspire": "inspire",
  "/image-tool": "imageEditor",
  "/image-edit": "imageEditor",
};

const viewMeta: Record<AppView, { title: string; desc: string }> = {
  home: { title: "AI创品 · 有品，不必一样", desc: "把你的想法做成属于你的产品。" },
  process: { title: "图片处理 · AI创品", desc: "把图片变成可以继续创作的设计素材。" },
  tasks: { title: "处理任务 · AI创品", desc: "查看 AI 图片处理任务进度和结果。" },
  assets: { title: "素材库 · AI创品", desc: "管理处理后的图片、花纹和裂变结果。" },
  products: { title: "定制杯子 · AI创品", desc: "选择杯型和图片，生成预览后试做实物。" },
  productDesign: { title: "产品试做 · AI创品", desc: "选择杯型和素材，满意后放入设计篮。" },
  checkout: { title: "订单确认 · AI创品", desc: "处理设计篮、收货信息、权益和支付状态。" },
  editor: { title: "素材详情 · AI创品", desc: "查看素材并进入处理、试做或公开流程。" },
  imageEditor: { title: "图片处理工具 · AI创品", desc: "单张图片精修、标注和参考图处理。" },
  account: { title: "个人中心 · AI创品", desc: "管理任务、订单、钱包、素材和公开主页。" },
  orders: { title: "制作订单 · AI创品", desc: "查看制作进度。" },
  wallet: { title: "钱包 · AI创品", desc: "管理 AI 积分、产品券和站内抵扣。" },
  inspire: { title: "灵感广场 · AI创品", desc: "浏览公开作品。" },
  publish: { title: "公开申请 · AI创品", desc: "提交作品公开审核。" },
  profile: { title: "作者主页 · AI创品", desc: "展示公开作品。" },
};

function viewFromLocation(): AppView {
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  const aliasView = routeAliases[currentPath];
  if (aliasView) return aliasView;
  const match = (Object.entries(viewRoutes) as Array<[AppView, string]>).find(
    ([, path]) => path === currentPath
  );
  return match?.[0] ?? "home";
}

function writeViewRoute(view: AppView, mode: "push" | "replace" = "push") {
  const targetPath = viewRoutes[view];
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  if (currentPath === targetPath) return;
  window.history[mode === "push" ? "pushState" : "replaceState"](
    { view },
    "",
    targetPath
  );
}

/* ── Auth storage helpers ── */

const AUTH_STORAGE_KEY = "podi-client-web.auth.v1";
const DESIGN_BASKET_STORAGE_KEY = "podi-client-web.design-basket.v1";

function readStoredAuth(): Pick<AppState, "currentUser" | "accessToken" | "refreshToken"> {
  if (typeof window === "undefined") {
    return { currentUser: null, accessToken: null, refreshToken: null };
  }
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return { currentUser: null, accessToken: null, refreshToken: null };
    const data = JSON.parse(raw) as {
      user?: ClientAuthUser;
      accessToken?: string;
      refreshToken?: string | null;
    };
    if (!data.user?.id || !data.accessToken) {
      return { currentUser: null, accessToken: null, refreshToken: null };
    }
    return {
      currentUser: data.user,
      accessToken: data.accessToken,
      refreshToken: data.refreshToken ?? null,
    };
  } catch {
    return { currentUser: null, accessToken: null, refreshToken: null };
  }
}

function writeStoredAuth(session: ClientAuthSession) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      user: session.user,
      accessToken: session.accessToken,
      refreshToken: session.refreshToken ?? null,
      savedAt: new Date().toISOString(),
    })
  );
}

function updateStoredAuthUser(user: ClientAuthUser) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    const data = raw ? JSON.parse(raw) : {};
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ ...data, user }));
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

function clearStoredAuth() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

function isProductOrderDraft(value: unknown): value is ProductOrderDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as Partial<ProductOrderDraft>;
  return Boolean(
    draft.draftId &&
      draft.productId &&
      draft.productName &&
      draft.previewImageUrl &&
      draft.sourceAssetId &&
      draft.status === "in_design_basket"
  );
}

function isProductCheckoutDraft(value: unknown): value is ProductCheckoutDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as Partial<ProductCheckoutDraft>;
  return Boolean(
    draft.productId &&
      draft.productName &&
      draft.previewImageUrl &&
      draft.sourceAssetId
  );
}

function readStoredDesignBasket(): Pick<AppState, "checkoutDraft" | "orderDrafts"> {
  if (typeof window === "undefined") {
    return { checkoutDraft: null, orderDrafts: [] };
  }
  try {
    const raw = window.localStorage.getItem(DESIGN_BASKET_STORAGE_KEY);
    if (!raw) return { checkoutDraft: null, orderDrafts: [] };
    const data = JSON.parse(raw) as {
      checkoutDraft?: unknown;
      orderDrafts?: unknown;
    };
    const orderDrafts = Array.isArray(data.orderDrafts)
      ? data.orderDrafts.filter(isProductOrderDraft)
      : [];
    const checkoutDraft =
      isProductOrderDraft(data.checkoutDraft) || isProductCheckoutDraft(data.checkoutDraft)
        ? data.checkoutDraft
        : orderDrafts[0] ?? null;
    return { checkoutDraft, orderDrafts };
  } catch {
    window.localStorage.removeItem(DESIGN_BASKET_STORAGE_KEY);
    return { checkoutDraft: null, orderDrafts: [] };
  }
}

function writeStoredDesignBasket(checkoutDraft: ProductCheckoutDraft | null, orderDrafts: ProductOrderDraft[]) {
  if (typeof window === "undefined") return;
  const hasDraft = Boolean(checkoutDraft || orderDrafts.length > 0);
  if (!hasDraft) {
    window.localStorage.removeItem(DESIGN_BASKET_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(
    DESIGN_BASKET_STORAGE_KEY,
    JSON.stringify({
      checkoutDraft,
      orderDrafts,
      savedAt: new Date().toISOString(),
    })
  );
}

/* ── Initial State ── */

const storedAuth = readStoredAuth();
const storedDesignBasket = readStoredDesignBasket();
const shouldRestoreUserState = Boolean(storedAuth.currentUser?.id && storedAuth.accessToken);

const initialState: AppState = {
  currentUser: storedAuth.currentUser,
  accessToken: storedAuth.accessToken,
  refreshToken: storedAuth.refreshToken,
  currentView: viewFromLocation(),
  previousView: null,
  assets: [],
  selectedAssetIds: [],
  pendingProductDesignAssetId: null,
  processTasks: [],
  latestProcessTaskId: null,
  designAgentSessions: [],
  selectedProductId: null,
  selectedProductSizeLabel: null,
  selectedSurface: null,
  checkoutDraft: shouldRestoreUserState ? storedDesignBasket.checkoutDraft : null,
  orderDrafts: shouldRestoreUserState ? storedDesignBasket.orderDrafts : [],
  aiCredits: 0,
  productCouponCount: 0,
  walletCoupons: [],
  shareBalance: 0,
  orders: [],
  inspirationWorks: defaultInspirationWorks,
  sameStyleWork: null,
  publishApplications: [],
  publishDraftKind: "图片作品",
  publishDraftSource: null,
  latestWalletEvent: null,
};

/* ── Reducer ── */

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case "SET_AUTH_SESSION":
      return {
        ...state,
        currentUser: action.payload.user,
        accessToken: action.payload.accessToken,
        refreshToken: action.payload.refreshToken,
      };

    case "UPDATE_AUTH_USER":
      return {
        ...state,
        currentUser: action.user,
      };

    case "CLEAR_AUTH_SESSION":
      return {
        ...state,
        currentUser: null,
        accessToken: null,
        refreshToken: null,
        assets: [],
        selectedAssetIds: [],
        pendingProductDesignAssetId: null,
        processTasks: [],
        latestProcessTaskId: null,
        designAgentSessions: [],
        checkoutDraft: null,
        orderDrafts: [],
        aiCredits: 0,
        productCouponCount: 0,
        walletCoupons: [],
        shareBalance: 0,
        orders: [],
        inspirationWorks: defaultInspirationWorks,
        publishApplications: [],
        latestWalletEvent: null,
      };

    case "HYDRATE_CLIENT_BOOTSTRAP": {
      const assets = cleanAssets(action.payload.assets).map((asset) => ({ ...asset, selected: false }));
      const processTasks = mergeProcessTaskList(action.payload.processTasks, state.processTasks);
      return {
        ...state,
        assets,
        selectedAssetIds: [],
        processTasks,
        latestProcessTaskId: processTasks[0]?.id ?? null,
        designAgentSessions: action.payload.designAgentSessions ?? state.designAgentSessions,
        orders: action.payload.orders,
        aiCredits: action.payload.wallet.aiCredits,
        productCouponCount: action.payload.wallet.productCouponCount,
        walletCoupons: action.payload.wallet.coupons ?? [],
        shareBalance: action.payload.wallet.shareBalance,
        latestWalletEvent: action.payload.wallet.latestWalletEvent ?? state.latestWalletEvent,
        inspirationWorks: action.payload.inspirationWorks,
        publishApplications: action.payload.publishApplications,
      };
    }

    case "NAVIGATE":
      return {
        ...state,
        previousView: state.currentView,
        currentView: action.view,
      };

    case "TOGGLE_ASSET": {
      const isSelected = state.selectedAssetIds.includes(action.id);
      return {
        ...state,
        selectedAssetIds: isSelected
          ? state.selectedAssetIds.filter((id) => id !== action.id)
          : [...state.selectedAssetIds, action.id],
        assets: state.assets.map((a) =>
          a.id === action.id ? { ...a, selected: !isSelected } : a
        ),
      };
    }

    case "SELECT_ASSETS":
      return {
        ...state,
        selectedAssetIds: action.ids,
        assets: state.assets.map((a) => ({
          ...a,
          selected: action.ids.includes(a.id),
        })),
      };

    case "SET_PENDING_PRODUCT_DESIGN_ASSET":
      return {
        ...state,
        pendingProductDesignAssetId: action.id,
      };

    case "CLEAR_SELECTION":
      return {
        ...state,
        selectedAssetIds: [],
        assets: state.assets.map((a) => ({ ...a, selected: false })),
      };

    case "ADD_ASSETS": {
      const assets = cleanAssets(action.assets);
      return {
        ...state,
        assets: [...assets, ...state.assets.map((a) => ({ ...a, selected: false }))],
      };
    }

    case "UPDATE_ASSET":
      return {
        ...state,
        assets: state.assets.map((a) =>
          a.id === action.id ? { ...a, ...action.patch } : a
        ),
      };

    case "DELETE_ASSET":
      return {
        ...state,
        selectedAssetIds: state.selectedAssetIds.filter((id) => id !== action.id),
        assets: state.assets.filter((a) => a.id !== action.id),
      };

    case "ADD_PROCESS_TASK":
      return {
        ...state,
        processTasks: [normalizeStaleProcessTask(action.task), ...state.processTasks.map(normalizeStaleProcessTask)],
        latestProcessTaskId: action.task.id,
      };

    case "UPDATE_PROCESS_TASK":
      return {
        ...state,
        processTasks: state.processTasks.map((task) =>
          task.id === action.id ? mergeProcessTask(task, { ...task, ...action.patch }) : task
        ),
      };

    case "UPSERT_DESIGN_AGENT_SESSION":
      return {
        ...state,
        designAgentSessions: [
          action.session,
          ...state.designAgentSessions.filter((item) => item.sessionId !== action.session.sessionId),
        ],
      };

    case "SET_SELECTED_PRODUCT":
      return { ...state, selectedProductId: action.productId, selectedProductSizeLabel: action.sizeLabel ?? null };

    case "SET_SELECTED_SURFACE":
      return { ...state, selectedSurface: action.surface };

    case "SET_CHECKOUT_DRAFT":
      writeStoredDesignBasket(action.draft, state.orderDrafts);
      return { ...state, checkoutDraft: action.draft };

    case "ADD_ORDER_DRAFT": {
      const orderDrafts = [
        action.draft,
        ...state.orderDrafts.filter((draft) => draft.draftId !== action.draft.draftId),
      ];
      writeStoredDesignBasket(action.draft, orderDrafts);
      return {
        ...state,
        checkoutDraft: action.draft,
        orderDrafts,
      };
    }

    case "REMOVE_ORDER_DRAFT": {
      const orderDrafts = state.orderDrafts.filter((draft) => draft.draftId !== action.draftId);
      const checkoutDraft =
        state.checkoutDraft &&
        "draftId" in state.checkoutDraft &&
        state.checkoutDraft.draftId === action.draftId
          ? orderDrafts[0] ?? null
          : state.checkoutDraft;
      writeStoredDesignBasket(checkoutDraft, orderDrafts);
      return {
        ...state,
        orderDrafts,
        checkoutDraft,
      };
    }

    case "CLEAR_ORDER_DRAFTS":
      writeStoredDesignBasket(null, []);
      return { ...state, orderDrafts: [], checkoutDraft: null };

    case "CLEAR_CHECKOUT_DRAFT":
      writeStoredDesignBasket(null, state.orderDrafts);
      return { ...state, checkoutDraft: null };

    case "ADD_ORDER":
      return { ...state, orders: [action.order, ...state.orders] };

    case "UPDATE_ORDER":
      return {
        ...state,
        orders: state.orders.map((order) =>
          order.id === action.id ? { ...order, ...action.patch } : order
        ),
      };

    case "SET_SAME_STYLE_WORK":
      return { ...state, sameStyleWork: action.work };

    case "SET_WALLET":
      return {
        ...state,
        aiCredits: action.wallet.aiCredits,
        productCouponCount: action.wallet.productCouponCount,
        walletCoupons: action.wallet.coupons ?? state.walletCoupons,
        shareBalance: action.wallet.shareBalance,
        latestWalletEvent: action.wallet.latestWalletEvent ?? state.latestWalletEvent,
      };

    case "ADD_CREDITS":
      return {
        ...state,
        aiCredits: state.aiCredits + action.amount,
        latestWalletEvent: action.event,
      };

    case "SPEND_CREDITS":
      return {
        ...state,
        aiCredits: Math.max(0, state.aiCredits - action.amount),
        latestWalletEvent: action.event,
      };

    case "USE_PRODUCT_COUPON":
      return {
        ...state,
        productCouponCount: Math.max(0, state.productCouponCount - 1),
      };

    case "ADD_REDEEM_REWARD":
      return {
        ...state,
        aiCredits: state.aiCredits + 100,
        productCouponCount: state.productCouponCount + 1,
        latestWalletEvent: "兑换码已入账：+100 AI 积分、+1 张产品券。",
      };

    case "SET_PUBLISH_DRAFT":
      return {
        ...state,
        publishDraftKind: action.kind,
        publishDraftSource: action.source,
      };

    case "SUBMIT_PUBLISH":
      return {
        ...state,
        publishApplications: [action.application, ...state.publishApplications],
      };

    case "CLEAR_WALLET_EVENT":
      return { ...state, latestWalletEvent: null };

    default:
      return state;
  }
}


/* ── Context ── */

interface AppContextValue {
  state: AppState;
  dispatch: Dispatch<AppAction>;
  navigate: (view: AppView) => void;
  setAuthSession: (session: ClientAuthSession) => void;
  logout: () => Promise<void>;
  activeUserId: string;
  isAuthenticated: boolean;
  viewRoutes: Record<AppView, string>;
  viewMeta: Record<AppView, { title: string; desc: string }>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const activeUserId = state.currentUser?.id ?? "guest";
  const isAuthenticated = Boolean(state.currentUser?.id && state.accessToken);
  const runningDesignSessionKey = state.designAgentSessions
    .filter((session) => session.status === "executing")
    .map((session) => session.sessionId)
    .join("|");

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    getClientBootstrap(activeUserId)
      .then((payload) => {
        if (!cancelled) {
          dispatch({ type: "HYDRATE_CLIENT_BOOTSTRAP", payload });
        }
      })
      .catch(() => {
        // 本地没有后端时保留内置演示数据，便于继续打磨前端。
      });
    return () => {
      cancelled = true;
    };
  }, [activeUserId, isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const runningTasks = state.processTasks.filter((task) =>
      task.params?.realBusinessRun && (task.status === "pending" || task.status === "processing")
    );
    if (!runningTasks.length) return;
    let cancelled = false;
    const advanceRunningTasks = async () => {
      for (const task of runningTasks) {
        if (cancelled) return;
        const nextTask = await advanceClientProcessTask({ userId: activeUserId, taskId: task.id }).catch(() => null);
        if (cancelled || !nextTask) continue;
        dispatch({ type: "UPDATE_PROCESS_TASK", id: task.id, patch: nextTask });
      }
    };
    const timer = window.setInterval(() => {
      void advanceRunningTasks();
    }, 10000);
    void advanceRunningTasks();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeUserId, isAuthenticated, state.processTasks]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const runningSessions = state.designAgentSessions.filter((session) => session.status === "executing");
    if (!runningSessions.length) return;
    let cancelled = false;
    const refreshDesignSessions = async () => {
      for (const session of runningSessions) {
        if (cancelled) return;
        const latest = await getProductDesignAgentSession({
          userId: activeUserId,
          sessionId: session.sessionId,
        }).catch(() => null);
        if (!cancelled && latest) dispatch({ type: "UPSERT_DESIGN_AGENT_SESSION", session: latest });
      }
    };
    void refreshDesignSessions();
    const timer = window.setInterval(() => void refreshDesignSessions(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeUserId, isAuthenticated, runningDesignSessionKey]);

  useEffect(() => {
    if (!state.accessToken) return;
    let cancelled = false;
    const verifySession = async () => {
      try {
        const user = await getCurrentAuthUser(state.accessToken || "");
        if (cancelled) return;
        updateStoredAuthUser(user);
        dispatch({ type: "UPDATE_AUTH_USER", user });
      } catch {
        if (!state.refreshToken) {
          if (cancelled) return;
          clearStoredAuth();
          dispatch({ type: "CLEAR_AUTH_SESSION" });
          return;
        }
        try {
          const session = await refreshAuthSession(state.refreshToken);
          if (cancelled) return;
          writeStoredAuth(session);
          dispatch({
            type: "SET_AUTH_SESSION",
            payload: {
              user: session.user,
              accessToken: session.accessToken,
              refreshToken: session.refreshToken ?? null,
            },
          });
        } catch {
          if (cancelled) return;
          clearStoredAuth();
          dispatch({ type: "CLEAR_AUTH_SESSION" });
        }
      }
    };
    void verifySession();
    return () => {
      cancelled = true;
    };
  }, [state.accessToken, state.refreshToken]);

  const navigate = (view: AppView) => {
    dispatch({ type: "NAVIGATE", view });
    writeViewRoute(view);
    window.scrollTo({ top: 0 });
  };

  const setAuthSession = (session: ClientAuthSession) => {
    writeStoredAuth(session);
    dispatch({
      type: "SET_AUTH_SESSION",
      payload: {
        user: session.user,
        accessToken: session.accessToken,
        refreshToken: session.refreshToken ?? null,
      },
    });
  };

  const logout = async () => {
    const accessToken = state.accessToken;
    const refreshToken = state.refreshToken;
    clearStoredAuth();
    dispatch({ type: "CLEAR_AUTH_SESSION" });
    try {
      await logoutClient(accessToken, refreshToken);
    } catch {
      // 登出以本地清理为主，服务端会话失败不阻断用户继续使用。
    }
  };

  return (
    <AppContext.Provider
      value={{
        state,
        dispatch,
        navigate,
        setAuthSession,
        logout,
        activeUserId,
        isAuthenticated,
        viewRoutes,
        viewMeta,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

/* ── 便捷 selectors ── */

export function useSelectedAssets(state: AppState) {
  return state.assets.filter((a) => state.selectedAssetIds.includes(a.id));
}

export function useAssetTypeLabel(type: AssetItem["type"]) {
  const map: Record<AssetItem["type"], string> = {
    original: "原图",
    processed: "处理图",
    variation: "裂变图",
    pattern: "花纹",
    ai_generated: "AI 生成",
    product_preview: "产品预览",
  };
  return map[type] ?? type;
}
