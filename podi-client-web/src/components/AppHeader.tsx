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
  Upload,
  Home,
  UserRound,
  PackageCheck,
  ChevronDown,
  ShieldCheck,
  Settings,
} from "lucide-react";
import { useEffect, useState } from "react";
import { loginRequiredEventName, useApp } from "../hooks/useAppState";
import { hasAccessToken, hasApiKey, loginClient, logoutClient } from "../api";
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

const accountLinks: Array<{ id: AppView; label: string; desc: string; icon: typeof Home }> = [
  { id: "tasks", label: "任务中心", desc: "批处理进度和结果", icon: ClipboardList },
  { id: "orders", label: "我的订单", desc: "制作、物流和售后", icon: PackageCheck },
  { id: "wallet", label: "钱包与权益", desc: "积分、产品券、抵扣", icon: WalletCards },
  { id: "assets", label: "我的素材", desc: "图片资产和处理结果", icon: Grid3X3 },
  { id: "publish", label: "公开审核", desc: "申请进入灵感广场", icon: ShieldCheck },
  { id: "profile", label: "公开主页", desc: "可分享的作品空间", icon: Star },
];

export default function AppHeader() {
  const { state, navigate } = useApp();
  const { currentView, aiCredits } = state;
  const signedIn = hasAccessToken();
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);
  const runningTaskCount = state.processTasks.filter((task) => task.status === "pending" || task.status === "processing").length;
  const taskCount = runningTaskCount || state.processTasks.length;
  const accountActive = ["account", "tasks", "orders", "wallet", "publish", "profile"].includes(currentView);
  const businessApiReady = hasApiKey();
  const runtimeReady = signedIn && (state.clientSyncStatus === "synced" || businessApiReady);
  const syncLabel =
    state.clientSyncStatus === "synced"
      ? state.clientWorkspaceName
      : state.clientSyncStatus === "syncing"
        ? "同步中"
      : state.clientSyncStatus === "error"
        ? "本地数据"
        : businessApiReady
          ? "真实业务"
          : "未配置";

  useEffect(() => {
    const openLogin = () => {
      setLoginError(null);
      setLoginOpen(true);
    };
    window.addEventListener(loginRequiredEventName, openLogin);
    return () => window.removeEventListener(loginRequiredEventName, openLogin);
  }, []);

  return (
    <>
      <div className="site-promo-bar">
        <strong>AI创品 · 有品，不必一样</strong>
        <span>从图片到实物 · 1 件起做 · 结果可保存</span>
        <button onClick={() => navigate("products")}>查看可做杯型</button>
      </div>

      {/* 桌面端顶部导航 */}
      <header className="site-header">
        <button
          className="brand-button"
          onClick={() => navigate("home")}
          aria-label="返回首页"
        >
          <span className="brand-symbol">品</span>
          <span>
            <strong>AI创品</strong>
            <small>有品，不必一样</small>
          </span>
        </button>

        <nav className="main-nav" aria-label="主导航">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={currentView === item.id ? "active" : ""}
              onClick={() => navigate(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="header-actions">
          {signedIn ? (
            <>
              <span className={`runtime-chip ${runtimeReady ? "synced" : "demo"}`}>
                {state.clientSyncStatus === "synced" ? "账户已连接" : "同步中"}
              </span>
              <button className="credit-chip" onClick={() => navigate("wallet")}>
                <WalletCards size={16} />
                {aiCredits} 积分
              </button>
              <button className="primary small" onClick={() => navigate("process")}>
                <Upload size={16} />
                开始处理
              </button>
              <div className={`account-menu ${accountActive ? "active" : ""}`}>
                <button className="account-trigger" onClick={() => navigate("account")} aria-label="打开个人中心">
                  <span className="account-avatar">{state.clientUserInitial}</span>
                  <span>
                    <strong>我的</strong>
                    {taskCount > 0 && <small>{taskCount} 个任务</small>}
                  </span>
                  <ChevronDown size={15} />
                </button>
                <div className="account-popover" aria-label="个人中心菜单">
                  <div className="account-popover-head">
                    <span className="account-avatar large">{state.clientUserInitial}</span>
                    <div>
                      <strong>{state.clientUserName}</strong>
                      <small>{aiCredits} 积分 · {state.productCouponCount} 张产品券 · {syncLabel}</small>
                    </div>
                  </div>
                  <div className="account-popover-grid">
                    {accountLinks.map(({ id, label, desc, icon: Icon }) => (
                      <button key={id} onClick={() => navigate(id)}>
                        <Icon size={16} />
                        <span>
                          <strong>{label}</strong>
                          <small>{desc}</small>
                        </span>
                        {id === "tasks" && taskCount > 0 && <em>{taskCount}</em>}
                      </button>
                    ))}
                  </div>
                  <button className="account-settings" onClick={() => navigate("account")}>
                    <Settings size={15} />
                    账号设置与资料
                  </button>
                  <button
                    className="account-settings danger"
                    onClick={() => {
                      logoutClient();
                      window.location.reload();
                    }}
                  >
                    退出登录
                  </button>
                </div>
              </div>
            </>
          ) : (
            <button className="account-trigger standalone" onClick={() => setLoginOpen(true)}>
              <UserRound size={16} />
              登录
            </button>
          )}
        </div>
      </header>

      {/* 移动端底部 Tab 栏 */}
      <nav className="mobile-tab-bar" aria-label="移动端导航">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              className={isActive ? "tab-active" : ""}
              onClick={() => navigate(item.id)}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      {loginOpen && (
        <div className="login-overlay" role="dialog" aria-modal="true" aria-label="登录">
          <form
            className="login-dialog"
            onSubmit={async (event) => {
              event.preventDefault();
              setLoginError(null);
              setLoginLoading(true);
              try {
                await loginClient(loginUsername, loginPassword);
                window.location.reload();
              } catch (error) {
                setLoginError(error instanceof Error ? error.message : "登录失败");
              } finally {
                setLoginLoading(false);
              }
            }}
          >
            <div className="login-dialog-head">
              <span>账号登录</span>
              <button type="button" onClick={() => setLoginOpen(false)} aria-label="关闭登录">
                ×
              </button>
            </div>
            <label>
              <span>账号</span>
              <input
                autoFocus
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder="请输入账号"
                autoComplete="username"
              />
            </label>
            <label>
              <span>密码</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="请输入密码"
                autoComplete="current-password"
              />
            </label>
            {loginError && <p className="login-error">{loginError}</p>}
            <button className="primary" type="submit" disabled={loginLoading || !loginUsername.trim() || !loginPassword}>
              {loginLoading ? "登录中" : "登录"}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
