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
  CouponItem,
  InspirationWork,
  PointLedgerEntry,
  ProcessTask,
  ProductionOrderSnapshot,
  PublishApplicationSnapshot,
  PublishDraftSource,
  WorkKind,
} from "../types";
import { initialAssets } from "../data/mock-data";
import {
  clientAssetToAssetItem,
  fetchClientAssets,
  fetchClientMe,
  fetchClientProductionOrders,
  fetchClientWallet,
  hasAccessToken,
  type ClientWalletResponse,
  type ClientProductionOrder,
} from "../api";

const loginRequiredEventName = "podi:login-required";
const protectedViews = new Set<AppView>([
  "process",
  "tasks",
  "assets",
  "editor",
  "account",
  "orders",
  "wallet",
  "publish",
  "profile",
]);

export function isProtectedView(view: AppView): boolean {
  return protectedViews.has(view);
}

export function emitLoginRequired() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(loginRequiredEventName));
}

export { loginRequiredEventName };

/* ── State ── */

export interface AppState {
  // 导航
  currentView: AppView;
  previousView: AppView | null;

  // 素材
  assets: AssetItem[];
  selectedAssetIds: string[];

  // 服务端账户
  clientUserName: string;
  clientUserInitial: string;
  clientWorkspaceName: string;
  clientSyncStatus: "local" | "syncing" | "synced" | "error";
  clientSyncMessage: string | null;

  // AI 批处理任务
  processTasks: ProcessTask[];
  latestProcessTaskId: string | null;

  // 产品
  selectedProductId: string | null;
  selectedSurface: string | null;

  // 钱包（保持现有逻辑）
  aiCredits: number;
  productCouponCount: number;
  shareBalance: number;
  walletCoupons: CouponItem[];
  walletLedger: PointLedgerEntry[];

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
  | { type: "NAVIGATE"; view: AppView }
  | { type: "TOGGLE_ASSET"; id: string }
  | { type: "SELECT_ASSETS"; ids: string[] }
  | { type: "CLEAR_SELECTION" }
  | { type: "SET_CLIENT_SYNC_STATUS"; status: AppState["clientSyncStatus"]; message?: string | null }
  | { type: "SET_CLIENT_IDENTITY"; userName: string; userInitial: string; workspaceName: string }
  | { type: "SET_ASSETS"; assets: AssetItem[] }
  | { type: "ADD_ASSETS"; assets: AssetItem[] }
  | { type: "UPDATE_ASSET"; id: string; patch: Partial<AssetItem> }
  | { type: "SET_CLIENT_WALLET"; aiCredits: number; productCouponCount: number; coupons: CouponItem[]; ledger: PointLedgerEntry[] }
  | { type: "ADD_PROCESS_TASK"; task: ProcessTask }
  | { type: "UPDATE_PROCESS_TASK"; id: string; patch: Partial<ProcessTask> }
  | { type: "SET_SELECTED_PRODUCT"; productId: string }
  | { type: "SET_SELECTED_SURFACE"; surface: string | null }
  | { type: "ADD_ORDER"; order: ProductionOrderSnapshot }
  | { type: "SET_ORDERS"; orders: ProductionOrderSnapshot[] }
  | { type: "SET_SAME_STYLE_WORK"; work: InspirationWork | null }
  | { type: "ADD_CREDITS"; amount: number; event: string }
  | { type: "USE_PRODUCT_COUPON" }
  | { type: "ADD_REDEEM_REWARD" }
  | { type: "SET_PUBLISH_DRAFT"; kind: WorkKind; source: PublishDraftSource | null }
  | { type: "SUBMIT_PUBLISH"; application: PublishApplicationSnapshot }
  | { type: "CLEAR_WALLET_EVENT" };

/* ── Route helpers (must be before initialState) ── */

const viewRoutes: Record<AppView, string> = {
  home: "/",
  process: "/process",
  tasks: "/tasks",
  assets: "/assets",
  products: "/products",
  editor: "/editor",
  account: "/account",
  orders: "/orders",
  wallet: "/wallet",
  inspire: "/inspiration",
  publish: "/publish",
  profile: "/profile",
};

const legacyViewRoutes: Record<string, AppView> = {
  "/products/design": "products",
};

const viewMeta: Record<AppView, { title: string; desc: string }> = {
  home: { title: "AI创品 · 有品，不必一样", desc: "上传图片，批量处理素材，也可以选择杯型试做实物。" },
  process: { title: "图片批量处理 · AI创品", desc: "清理、扩图、提取花纹和裂变生成，一批图片一次处理。" },
  tasks: { title: "处理任务 · AI创品", desc: "查看 AI 图片处理任务进度和结果。" },
  assets: { title: "素材库 · AI创品", desc: "管理处理后的图片、花纹和裂变结果。" },
  products: { title: "定制杯子 · AI创品", desc: "选择杯型和图片，生成预览后试做实物。" },
  editor: { title: "图编辑器 · AI创品", desc: "单图精修。" },
  account: { title: "个人中心 · AI创品", desc: "管理任务、订单、钱包、素材和公开主页。" },
  orders: { title: "制作订单 · AI创品", desc: "查看制作进度。" },
  wallet: { title: "钱包 · AI创品", desc: "管理 AI 积分、产品券和站内抵扣。" },
  inspire: { title: "灵感广场 · AI创品", desc: "浏览公开作品。" },
  publish: { title: "公开申请 · AI创品", desc: "提交作品公开审核。" },
  profile: { title: "作者主页 · AI创品", desc: "展示公开作品。" },
};

function viewFromLocation(): AppView {
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  const legacyView = legacyViewRoutes[currentPath];
  if (legacyView) {
    window.history.replaceState({ view: legacyView }, "", viewRoutes[legacyView]);
    return legacyView;
  }
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

/* ── Initial State ── */

const initialState: AppState = {
  currentView: !hasAccessToken() && isProtectedView(viewFromLocation()) ? "home" : viewFromLocation(),
  previousView: null,
  assets: hasAccessToken() ? initialAssets : [],
  selectedAssetIds: hasAccessToken() ? initialAssets.filter((a) => a.selected).map((a) => a.id) : [],
  clientUserName: "游客",
  clientUserInitial: "访",
  clientWorkspaceName: "未登录",
  clientSyncStatus: "local",
  clientSyncMessage: null,
  processTasks: [],
  latestProcessTaskId: null,
  selectedProductId: null,
  selectedSurface: null,
  aiCredits: 0,
  productCouponCount: 0,
  shareBalance: 42.8,
  walletCoupons: [],
  walletLedger: [],
  orders: [],
  inspirationWorks: [],
  sameStyleWork: null,
  publishApplications: [],
  publishDraftKind: "图片作品",
  publishDraftSource: null,
  latestWalletEvent: null,
};

/* ── Reducer ── */

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
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

    case "CLEAR_SELECTION":
      return {
        ...state,
        selectedAssetIds: [],
        assets: state.assets.map((a) => ({ ...a, selected: false })),
      };

    case "SET_CLIENT_SYNC_STATUS":
      return {
        ...state,
        clientSyncStatus: action.status,
        clientSyncMessage: action.message ?? null,
      };

    case "SET_CLIENT_IDENTITY":
      return {
        ...state,
        clientUserName: action.userName,
        clientUserInitial: action.userInitial,
        clientWorkspaceName: action.workspaceName,
      };

    case "SET_ASSETS":
      return {
        ...state,
        assets: action.assets,
        selectedAssetIds: action.assets.filter((a) => a.selected).map((a) => a.id),
      };

    case "ADD_ASSETS":
      return {
        ...state,
        assets: [...action.assets, ...state.assets.map((a) => ({ ...a, selected: false }))],
        selectedAssetIds: action.assets.filter((a) => a.selected).map((a) => a.id),
      };

    case "UPDATE_ASSET":
      return {
        ...state,
        assets: state.assets.map((a) =>
          a.id === action.id ? { ...a, ...action.patch } : a
        ),
      };

    case "ADD_PROCESS_TASK":
      return {
        ...state,
        processTasks: [action.task, ...state.processTasks],
        latestProcessTaskId: action.task.id,
      };

    case "UPDATE_PROCESS_TASK":
      return {
        ...state,
        processTasks: state.processTasks.map((task) =>
          task.id === action.id ? { ...task, ...action.patch } : task
        ),
      };

    case "SET_SELECTED_PRODUCT":
      return { ...state, selectedProductId: action.productId };

    case "SET_SELECTED_SURFACE":
      return { ...state, selectedSurface: action.surface };

    case "ADD_ORDER":
      return { ...state, orders: [action.order, ...state.orders] };

    case "SET_ORDERS":
      return { ...state, orders: action.orders };

    case "SET_SAME_STYLE_WORK":
      return { ...state, sameStyleWork: action.work };

    case "ADD_CREDITS":
      return {
        ...state,
        aiCredits: state.aiCredits + action.amount,
        latestWalletEvent: action.event,
      };

    case "SET_CLIENT_WALLET":
      return {
        ...state,
        aiCredits: action.aiCredits,
        productCouponCount: action.productCouponCount,
        walletCoupons: action.coupons,
        walletLedger: action.ledger,
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
  viewRoutes: Record<AppView, string>;
  viewMeta: Record<AppView, { title: string; desc: string }>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    if (!hasAccessToken()) {
      dispatch({ type: "SET_CLIENT_SYNC_STATUS", status: "local", message: null });
      if (isProtectedView(viewFromLocation())) {
        writeViewRoute("home", "replace");
        emitLoginRequired();
      }
      return;
    }

    let cancelled = false;
    dispatch({ type: "SET_CLIENT_SYNC_STATUS", status: "syncing", message: null });

    Promise.all([fetchClientMe(), fetchClientAssets({ limit: 100 }), fetchClientWallet(), fetchClientProductionOrders()])
      .then(([me, assets, wallet, orders]) => {
        if (cancelled) return;
        const userName = me.user.displayName || me.user.username || "我的账户";
        dispatch({
          type: "SET_CLIENT_IDENTITY",
          userName,
          userInitial: userName.slice(0, 1).toUpperCase(),
          workspaceName: me.workspace.name,
        });
        dispatch({ type: "SET_ASSETS", assets: assets.items.map(clientAssetToAssetItem) });
        dispatch({ type: "SET_CLIENT_WALLET", ...mapClientWallet(wallet) });
        dispatch({ type: "SET_ORDERS", orders: orders.map(mapClientProductionOrder) });
        dispatch({ type: "SET_CLIENT_SYNC_STATUS", status: "synced", message: null });
      })
      .catch((error) => {
        if (cancelled) return;
        dispatch({
          type: "SET_CLIENT_SYNC_STATUS",
          status: "error",
          message: error instanceof Error ? error.message : "账户数据同步失败",
        });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const navigate = (view: AppView) => {
    if (!hasAccessToken() && isProtectedView(view)) {
      emitLoginRequired();
      return;
    }
    dispatch({ type: "NAVIGATE", view });
    writeViewRoute(view);
    window.scrollTo({ top: 0 });
  };

  return (
    <AppContext.Provider value={{ state, dispatch, navigate, viewRoutes, viewMeta }}>
      {children}
    </AppContext.Provider>
  );
}

export function mapClientProductionOrder(order: ClientProductionOrder): ProductionOrderSnapshot {
  const firstItem = order.items[0];
  const statusMap: Record<string, ProductionOrderSnapshot["status"]> = {
    awaiting_payment: "待支付",
    ops_review: "运营核对",
    submitted_to_supplier: "已推送供应商",
    producing: "制作中",
    quality_check: "制作中",
    shipped: "已发货",
    delivered: "已完成",
    completed: "已完成",
  };
  const address = order.shippingAddress || {};
  return {
    id: order.id,
    orderNo: order.orderNo,
    product: firstItem?.productName || "定制产品",
    asset: "已生成生产文件",
    quantity: `${order.items.reduce((total, item) => total + item.quantity, 0)} 件`,
    status: statusMap[order.status] || "待确认",
    eta: order.status === "submitted_to_supplier" ? "已推送供应链，等待生产状态回传" : "等待下一步处理",
    image: firstItem?.supplierEffectImageUrl || firstItem?.productionAssetUrl || firstItem?.sourceAssetUrl || "",
    createdAt: new Date(order.createdAt).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
    shippingSummary: [address.city, address.district, address.address].filter(Boolean).join(" ") || "收货信息已保存",
    discount: order.paymentStatus === "paid" ? "已支付，等待运营核对" : "等待支付",
    usedProductCoupon: false,
    paymentStatus: order.paymentStatus,
    supplierStatus: order.supplierStatus,
    productionAssetUrl: firstItem?.productionAssetUrl,
    supplierEffectImageUrl: firstItem?.supplierEffectImageUrl || null,
    preflightPassed: firstItem?.preflight?.passed === true,
  };
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

function mapClientWallet(wallet: ClientWalletResponse): {
  aiCredits: number;
  productCouponCount: number;
  coupons: CouponItem[];
  ledger: PointLedgerEntry[];
} {
  return {
    aiCredits: wallet.pointBalance,
    productCouponCount: wallet.productCouponCount,
    coupons: wallet.productCoupons.map((coupon) => ({
      id: coupon.id,
      type: "product",
      name: coupon.name || "产品券",
      scope: coupon.businessKey || coupon.packageKey,
      value: `${coupon.remainingUnits} ${coupon.unitName || "张"}`,
      status: coupon.remainingUnits > 0 ? "available" : "used",
      expiresAt: coupon.expiresAt || "长期有效",
      source: coupon.source || "账户权益",
    })),
    ledger: wallet.ledger.map((entry) => ({
      id: entry.id,
      time: entry.createdAt || "",
      action: entry.description || "账户变动",
      amount: entry.points,
      note: entry.traceId || entry.taskId || "",
    })),
  };
}

export function useAssetTypeLabel(type: AssetItem["type"]) {
  const map: Record<AssetItem["type"], string> = {
    original: "原图",
    processed: "处理图",
    variation: "裂变图",
    pattern: "花纹",
    ai_generated: "AI 生成",
  };
  return map[type] ?? type;
}
