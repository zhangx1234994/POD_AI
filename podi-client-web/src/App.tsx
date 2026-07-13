/**
 * App.tsx — 路由壳（< 150 行）
 * 使用 AppProvider 包裹，根据 currentView 路由到各页面组件
 */
import { useEffect } from "react";
import { AppProvider, useApp } from "./hooks/useAppState";
import type { AppView } from "./types";
import AppHeader from "./components/AppHeader";

/* ── 页面懒加载（直接 import，后续可切 lazy） ── */
import HomePage from "./pages/HomePage";
import ProcessPage from "./pages/ProcessPage";
import ProcessTasksPage from "./pages/ProcessTasksPage";
import AssetsPage from "./pages/AssetsPage";
import ProductsPage from "./pages/ProductsPage";
import ProductDesignPage from "./pages/ProductDesignPage";
import CheckoutPage from "./pages/CheckoutPage";
import EditorPage from "./pages/EditorPage";
import ImageEditorPage from "./pages/ImageEditorPage";
import AccountPage from "./pages/AccountPage";
import OrdersPage from "./pages/OrdersPage";
import WalletPage from "./pages/WalletPage";
import InspirePage from "./pages/InspirePage";
import PublishPage from "./pages/PublishPage";
import ProfilePage from "./pages/ProfilePage";

const pageComponents: Record<AppView, React.ComponentType> = {
  home: HomePage,
  process: ProcessPage,
  tasks: ProcessTasksPage,
  assets: AssetsPage,
  products: ProductsPage,
  productDesign: ProductDesignPage,
  checkout: CheckoutPage,
  editor: EditorPage,
  imageEditor: ImageEditorPage,
  account: AccountPage,
  orders: OrdersPage,
  wallet: WalletPage,
  inspire: InspirePage,
  publish: PublishPage,
  profile: ProfilePage,
};

function AppShell() {
  const { state, navigate } = useApp();
  const PageComponent = pageComponents[state.currentView] ?? HomePage;

  /* 监听浏览器前进/后退 */
  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname.replace(/\/+$/, "") || "/";
      const aliasView = routeAliases[path];
      const entry = aliasView
        ? ([aliasView, viewRoutes[aliasView]] as [AppView, string])
        : (Object.entries(viewRoutes) as Array<[AppView, string]>).find(([, p]) => p === path);
      if (entry && entry[0] !== state.currentView) {
        navigate(entry[0]);
      }
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [navigate, state.currentView]);

  /* 更新 document title */
  useEffect(() => {
    const meta = viewMetaMap[state.currentView];
    if (meta) document.title = meta.title;
  }, [state.currentView]);

  return (
    <div className="client-app">
      <AppHeader />
      <PageComponent />
    </div>
  );
}

/* ── 路由表 ── */
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

const viewMetaMap: Record<AppView, { title: string; desc: string }> = {
  home: { title: "AI创品 · 有品，必不同", desc: "把个性做成别人复制不了的产品。" },
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

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}
