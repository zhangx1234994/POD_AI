/**
 * 顶部导航栏 — 全局共享
 */
import {
  Images,
  Grid3X3,
  ShoppingBag,
  ClipboardList,
  Star,
  WalletCards,
  Home,
  UserRound,
  PackageCheck,
  ChevronDown,
  ShieldCheck,
  Settings,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useApp } from "../hooks/useAppState";
import type { AppView } from "../types";

const navItems: Array<{ id: AppView; label: string }> = [
  { id: "home", label: "首页" },
  { id: "products", label: "全部商品" },
  { id: "process", label: "图片批处理" },
  { id: "assets", label: "素材库" },
  { id: "inspire", label: "灵感广场" },
];

const mobileNavItems: Array<{ id: AppView; label: string; icon: typeof Home }> = [
  { id: "home", label: "首页", icon: Home },
  { id: "process", label: "批处理", icon: Images },
  { id: "assets", label: "素材", icon: Grid3X3 },
  { id: "products", label: "产品", icon: ShoppingBag },
  { id: "inspire", label: "灵感", icon: Star },
  { id: "account", label: "我的", icon: UserRound },
];

const accountLinks: Array<{ id: AppView; label: string; icon: typeof Home }> = [
  { id: "tasks", label: "任务中心", icon: ClipboardList },
  { id: "orders", label: "我的订单", icon: PackageCheck },
  { id: "wallet", label: "钱包与权益", icon: WalletCards },
  { id: "assets", label: "我的素材", icon: Grid3X3 },
];

export default function AppHeader() {
  const { state, navigate, isAuthenticated, logout } = useApp();
  const [accountOpen, setAccountOpen] = useState(false);
  const [taskNoticeCount, setTaskNoticeCount] = useState(0);
  const taskStatusRef = useRef<Record<string, string>>({});
  const taskNoticeReadyRef = useRef(false);
  const { currentView, aiCredits } = state;
  const runningTaskCount =
    state.processTasks.filter((task) => task.status === "pending" || task.status === "processing").length +
    state.designAgentSessions.filter((session) => session.status === "executing").length;
  const taskCount = runningTaskCount || state.processTasks.length + state.designAgentSessions.length;
  const draftCount = state.orderDrafts.length;
  const accountActive = ["account", "tasks", "orders", "wallet", "publish", "profile"].includes(currentView);
  const showMobileTabBar = !["productDesign", "checkout", "imageEditor"].includes(currentView);
  const isNavActive = (id: AppView) =>
    currentView === id || (id === "products" && ["productDesign", "checkout"].includes(currentView));
  const displayName = state.currentUser?.displayName || state.currentUser?.username || "登录";
  const avatarLabel = (displayName.trim()[0] || "我").toUpperCase();
  const go = (view: AppView) => {
    setAccountOpen(false);
    navigate(view);
  };
  const goTasks = () => {
    setTaskNoticeCount(0);
    go("tasks");
  };

  useEffect(() => {
    const nextStatuses = Object.fromEntries(state.processTasks.map((task) => [task.id, task.status]));
    if (!taskNoticeReadyRef.current) {
      taskStatusRef.current = nextStatuses;
      taskNoticeReadyRef.current = true;
      return;
    }
    const completedNow = state.processTasks.filter((task) => {
      const previousStatus = taskStatusRef.current[task.id];
      return task.status === "completed" && previousStatus && previousStatus !== "completed";
    }).length;
    if (completedNow > 0) {
      setTaskNoticeCount((count) => count + completedNow);
    }
    taskStatusRef.current = nextStatuses;
  }, [state.processTasks]);

  return (
    <>
      {/* 桌面端顶部导航 */}
      <header className="site-header">
        <button
          className="brand-button"
          onClick={() => go("home")}
          aria-label="返回首页"
        >
          <img className="brand-symbol" src="/brand/ai-chuangpin-mark.png" alt="" />
          <span>
            <strong>AI创品</strong>
            <small>把想法做成产品</small>
          </span>
        </button>

        <nav className="main-nav" aria-label="主导航">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={isNavActive(item.id) ? "active" : ""}
              onClick={() => go(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="header-actions">
          {isAuthenticated && draftCount > 0 && (
            <button className="pending-cart-chip" onClick={() => go("checkout")} aria-label={`设计篮有 ${draftCount} 件产品`}>
              <ShoppingBag size={16} />
              <strong>{draftCount}</strong>
              <span>设计篮</span>
            </button>
          )}
          {isAuthenticated && (
            <button
              className={`task-chip ${runningTaskCount > 0 ? "active" : ""} ${taskNoticeCount > 0 ? "has-notice" : ""}`}
              onClick={goTasks}
              title="查看任务中心"
              aria-label={runningTaskCount > 0 ? `有 ${runningTaskCount} 个任务进行中` : "查看任务中心"}
            >
              <ClipboardList size={16} />
              <span>任务</span>
              {runningTaskCount > 0 && <strong>{runningTaskCount}</strong>}
              {taskNoticeCount > 0 && <em>{taskNoticeCount} 个已完成</em>}
            </button>
          )}
          {isAuthenticated && (
            <button
              className="credit-chip"
              onClick={() => go("wallet")}
              title="查看钱包与权益"
            >
              <WalletCards size={16} />
              {aiCredits} 积分
            </button>
          )}
          {!isAuthenticated ? (
            <button
              className={`account-trigger ${accountActive ? "active" : ""}`}
              onClick={() => go("account")}
              aria-label="登录 AI创品"
            >
              <span className="account-avatar">登</span>
              <span>
                <strong>登录</strong>
                <small>保存素材和订单</small>
              </span>
            </button>
          ) : (
          <div className={`account-menu ${accountActive ? "active" : ""} ${accountOpen ? "open" : ""}`}>
            <button
              className="account-trigger"
              onClick={() => setAccountOpen((open) => !open)}
              aria-expanded={accountOpen}
              aria-label="打开个人中心"
            >
              <span className="account-avatar">{avatarLabel}</span>
              <span>
                <strong>{displayName}</strong>
                {taskCount > 0 && <small>{taskCount} 个任务</small>}
              </span>
              <ChevronDown size={15} />
            </button>
            <div className="account-popover" aria-label="个人中心菜单">
              <div className="account-popover-head">
                <span className="account-avatar large">{avatarLabel}</span>
                <div>
                  <strong>{displayName}</strong>
                  <small>{aiCredits} 积分 · {state.productCouponCount} 张产品券</small>
                </div>
              </div>
              <div className="account-popover-grid">
                {accountLinks.map(({ id, label, icon: Icon }) => (
                  <button key={id} onClick={() => go(id)}>
                    <Icon size={16} />
                    <span>
                      <strong>{label}</strong>
                    </span>
                    {id === "tasks" && taskCount > 0 && <em>{taskCount}</em>}
                  </button>
                ))}
              </div>
              <button className="account-settings" onClick={() => go("account")}>
                <Settings size={15} />
                账号设置与资料
              </button>
              <button className="account-settings danger" onClick={() => { setAccountOpen(false); void logout(); }}>
                退出登录
              </button>
            </div>
          </div>
          )}
        </div>
      </header>

      {/* 移动端底部 Tab 栏 */}
      {showMobileTabBar && (
        <nav className="mobile-tab-bar" aria-label="移动端导航">
          {mobileNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = isNavActive(item.id);
            return (
              <button
                key={item.id}
                className={isActive ? "tab-active" : ""}
                onClick={() => go(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      )}
    </>
  );
}
