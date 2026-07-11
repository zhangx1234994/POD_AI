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
import EditorPage from "./pages/EditorPage";
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
  editor: EditorPage,
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
      const entry = (Object.entries(viewRoutes) as Array<[AppView, string]>).find(
        ([, p]) => p === path
      );
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
  editor: "/editor",
  account: "/account",
  orders: "/orders",
  wallet: "/wallet",
  inspire: "/inspiration",
  publish: "/publish",
  profile: "/profile",
};

const viewMetaMap: Record<AppView, { title: string; desc: string }> = {
  home: { title: "AI创品 · 有品，不必一样", desc: "上传图片，处理素材，再做成属于你的实物。" },
  process: { title: "图片批处理 · AI创品", desc: "清理、扩图、提取花纹和裂变生成，一批图片一次处理。" },
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

export default function App() {
  return (
    <AppProvider>
      <AppShell />
    </AppProvider>
  );
}
