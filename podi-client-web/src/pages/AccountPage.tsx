/**
 * 个人中心 — 私人工作台入口
 * 公开主页仍然保留为 ProfilePage，避免账号管理和对外展示混在一起。
 */
import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  AlertCircle,
  ClipboardList,
  Grid3X3,
  MapPin,
  MessageCircle,
  PackageCheck,
  ShieldCheck,
  Sparkles,
  Star,
  Ticket,
  WalletCards,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import type { AppView, ClientShippingAddress } from "../types";
import { loginWithPhoneCode, requestPhoneCode } from "../api";
import { readStoredAddress, writeStoredAddress } from "../utils/addressBook";

const postAuthReturnKey = "podi.postAuthReturn";

export default function AccountPage() {
  const { state, navigate, isAuthenticated, setAuthSession, logout } = useApp();
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [codeNotice, setCodeNotice] = useState("");
  const [authError, setAuthError] = useState("");
  const [codeSending, setCodeSending] = useState(false);
  const [codeCooldown, setCodeCooldown] = useState(0);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [addressInfo, setAddressInfo] = useState<ClientShippingAddress>(() => readStoredAddress());
  const [addressSaved, setAddressSaved] = useState(false);

  const displayName = state.currentUser?.displayName || state.currentUser?.username || "创作者";
  const avatarLabel = (displayName.trim()[0] || "我").toUpperCase();

  const updateAddressInfo = (field: keyof ClientShippingAddress, value: string) => {
    setAddressInfo((current) => ({ ...current, [field]: field === "country" ? value.toUpperCase() : value }));
    setAddressSaved(false);
  };

  const saveAddressInfo = () => {
    setAddressInfo(writeStoredAddress(addressInfo));
    setAddressSaved(true);
    window.setTimeout(() => setAddressSaved(false), 2200);
  };

  useEffect(() => {
    if (!isAuthenticated) {
      setPhone("");
      setCode("");
      setCodeNotice("");
      setAuthError("");
      setCodeSending(false);
      setCodeCooldown(0);
      setAuthSubmitting(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (codeCooldown <= 0) return;
    const timer = window.setTimeout(() => setCodeCooldown((current) => Math.max(0, current - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [codeCooldown]);

  const sendPhoneCode = async () => {
    setAuthError("");
    setCodeNotice("");
    setCodeSending(true);
    try {
      const response = await requestPhoneCode({ phone });
      setCodeCooldown(response.resendAfter ?? 60);
      if (response.testCode) {
        setCode(response.testCode);
        setCodeNotice(`本地测试验证码已填入：${response.testCode}。`);
      } else {
        setCode("");
        setCodeNotice("验证码已发送，请查看手机短信。");
      }
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "验证码发送失败，请稍后重试。");
    } finally {
      setCodeSending(false);
    }
  };

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError("");
    setAuthSubmitting(true);
    try {
      const session = await loginWithPhoneCode({
        phone,
        code,
        mode: "login",
      });
      setAuthSession(session);
      setPhone("");
      setCode("");
      setCodeNotice("");
      const returnView = window.sessionStorage.getItem(postAuthReturnKey);
      window.sessionStorage.removeItem(postAuthReturnKey);
      navigate(returnView === "productDesign" ? "productDesign" : "home");
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "账号请求失败，请稍后重试。");
    } finally {
      setAuthSubmitting(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <main className="account-auth-page">
        <section className="auth-login-shell" aria-label="登录 AI创品">
          <aside className="auth-login-visual" aria-hidden="true">
            <img src="/demo/market/product-tumbler-blue-botanical.png" alt="" />
            <div className="auth-login-visual-copy">
              <span>AI创品 · 有品，不必一样</span>
              <strong>登录后，<br />继续定义你的不同。</strong>
              <small>保存灵感、设计和订单。</small>
            </div>
          </aside>
          <form className="auth-login-card" onSubmit={submitAuth}>
            <div className="auth-login-head">
              <small>手机号登录</small>
              <h1>登录 AI创品</h1>
              <p>输入验证码即可继续创作</p>
            </div>

            <label>
              <span>手机号</span>
              <div className="auth-code-row">
                <input value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="请输入 11 位手机号" autoComplete="tel" inputMode="tel" />
                <button type="button" className="auth-code-action" onClick={sendPhoneCode} disabled={codeSending || codeCooldown > 0}>
                  <MessageCircle size={15} />
                  {codeSending ? "发送中" : codeCooldown > 0 ? `${codeCooldown}s` : "获取验证码"}
                </button>
              </div>
            </label>
            <label>
              <span>验证码</span>
              <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="请输入短信验证码" inputMode="numeric" autoComplete="one-time-code" />
            </label>
            {codeNotice && <p className="auth-inline-note">{codeNotice}</p>}

            {authError && (
              <div className="auth-error" role="alert">
                <AlertCircle size={16} />
                <span>{authError}</span>
              </div>
            )}
            <button className="auth-login-submit" disabled={authSubmitting}>
              {authSubmitting ? "正在进入" : "进入 AI创品"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  const runningTasks = state.processTasks.filter((task) => task.status === "pending" || task.status === "processing");
  const completedTasks = state.processTasks.filter((task) => task.status === "completed");
  const publicAssets = state.assets.filter((asset) => asset.visibility === "public");
  const reviewingAssets = state.assets.filter((asset) => asset.visibility === "reviewing");
  const latestOrder = state.orders[0];

  const workbenchItems: Array<{
    title: string;
    desc: string;
    metric: string;
    view: AppView;
    action: string;
    icon: typeof ClipboardList;
  }> = [
    {
      title: "任务中心",
      desc: "批量图片处理的进度、结果和失败记录集中在这里。",
      metric: `${runningTasks.length} 个运行中`,
      view: "tasks",
      action: "查看任务",
      icon: ClipboardList,
    },
    {
      title: "我的订单",
      desc: "查看试做、制作、物流和售后；供应链状态作为订单证据展示。",
      metric: `${state.orders.length} 个订单`,
      view: "orders",
      action: "查看订单",
      icon: PackageCheck,
    },
    {
      title: "钱包与权益",
      desc: "AI 积分、产品券和分享抵扣都归到账号权益里。",
      metric: `${state.aiCredits} 积分`,
      view: "wallet",
      action: "查看权益",
      icon: WalletCards,
    },
    {
      title: "我的素材",
      desc: "原图、处理图、花纹、裂变图和 AI 生成图都沉淀到素材库。",
      metric: `${state.assets.length} 张素材`,
      view: "assets",
      action: "打开素材库",
      icon: Grid3X3,
    },
    {
      title: "公开审核",
      desc: "只有审核通过的图片或产品作品才会进入灵感广场。",
      metric: `${reviewingAssets.length + state.publishApplications.length} 个待确认`,
      view: "publish",
      action: "提交公开",
      icon: ShieldCheck,
    },
    {
      title: "公开主页",
      desc: "这是对外分享的作品空间，和私人账号管理分开。",
      metric: `${publicAssets.length} 个公开资产`,
      view: "profile",
      action: "查看主页",
      icon: Star,
    },
  ];

  return (
    <main className="page-shell account-page">
      <PageHeader
        eyebrow="个人中心"
        title="任务、订单和权益，都在这里。"
        desc="主导航只放核心业务；账号相关的工作记录、订单、钱包和公开主页统一收进个人中心。"
      />

      <section className="account-hero-panel">
        <div className="account-id-card">
          <span className="account-avatar xl">{avatarLabel}</span>
          <div>
            <small>当前账号</small>
            <strong>{displayName}</strong>
            <p>普通用户也能批量处理图片、保存素材、试做产品；公开作品通过审核后参与站内抵扣。</p>
          </div>
        </div>
        <div className="account-balance-strip">
          <article>
            <WalletCards size={18} />
            <span>AI 积分</span>
            <strong>{state.aiCredits}</strong>
          </article>
          <article>
            <Ticket size={18} />
            <span>产品券</span>
            <strong>{state.productCouponCount} 张</strong>
          </article>
          <article>
            <Sparkles size={18} />
            <span>站内抵扣</span>
            <strong>¥{state.shareBalance.toFixed(2)}</strong>
          </article>
        </div>
      </section>

      <section className="account-wallet-shortcuts" aria-label="钱包快捷入口">
        <div>
          <small>钱包快捷入口</small>
          <strong>充值积分、兑换活动码和查看产品券。</strong>
          <p>推广期的产品券、兑换码和 AI 积分都收在钱包里；产品制作前会优先展示可用权益。</p>
        </div>
        <div className="account-wallet-actions">
          <button className="primary" onClick={() => navigate("wallet")}>
            <WalletCards size={16} />
            充值积分
          </button>
          <button className="secondary" onClick={() => navigate("wallet")}>
            <Ticket size={16} />
            输入兑换码
          </button>
          <button className="secondary" onClick={() => navigate("wallet")}>
            <Sparkles size={16} />
            查看产品券
          </button>
        </div>
      </section>

      <section className="account-address-panel" aria-label="默认收货信息">
        <div className="account-address-copy">
          <MapPin size={20} />
          <div>
            <small>默认收货信息</small>
            <strong>产品试做会自动带入这里的地址。</strong>
            <p>当前先保存在本机浏览器；后续接入服务端地址簿后，会在账号下同步多个地址。</p>
          </div>
        </div>
        <div className="account-address-form">
          <label>
            <span>收货人</span>
            <input value={addressInfo.recipientName} onChange={(event) => updateAddressInfo("recipientName", event.target.value)} placeholder="姓名" />
          </label>
          <label>
            <span>联系电话</span>
            <input value={addressInfo.phoneNumber} onChange={(event) => updateAddressInfo("phoneNumber", event.target.value)} placeholder="手机号或国际号码" />
          </label>
          <label>
            <span>国家</span>
            <input value={addressInfo.country} onChange={(event) => updateAddressInfo("country", event.target.value)} placeholder="CN / US" />
          </label>
          <label>
            <span>省/州</span>
            <input value={addressInfo.state} onChange={(event) => updateAddressInfo("state", event.target.value)} placeholder="省份或州" />
          </label>
          <label>
            <span>城市</span>
            <input value={addressInfo.city} onChange={(event) => updateAddressInfo("city", event.target.value)} placeholder="城市" />
          </label>
          <label>
            <span>邮编</span>
            <input value={addressInfo.postalCode} onChange={(event) => updateAddressInfo("postalCode", event.target.value)} placeholder="邮编" />
          </label>
          <label className="wide">
            <span>详细地址</span>
            <input value={addressInfo.address} onChange={(event) => updateAddressInfo("address", event.target.value)} placeholder="街道、门牌号、补充信息" />
          </label>
          <label>
            <span>邮箱</span>
            <input value={addressInfo.email} onChange={(event) => updateAddressInfo("email", event.target.value)} placeholder="订单通知邮箱，可选" />
          </label>
          <button className="primary" onClick={saveAddressInfo}>
            {addressSaved ? "已保存" : "保存默认地址"}
          </button>
        </div>
      </section>

      <section className="account-quick-status">
        <article>
          <small>最近任务</small>
          <strong>{state.processTasks[0]?.abilityTitle ?? "还没有任务"}</strong>
          <span>{completedTasks.length} 个任务已完成</span>
        </article>
        <article>
          <small>最近订单</small>
          <strong>{latestOrder?.product ?? "还没有订单"}</strong>
          <span>{latestOrder ? `${latestOrder.status} · ${latestOrder.eta}` : "选商品后可试做"}</span>
        </article>
        <article>
          <small>公开状态</small>
          <strong>{publicAssets.length} 个公开资产</strong>
          <span>{reviewingAssets.length} 个素材正在等待确认</span>
        </article>
      </section>

      <section className="account-workbench-grid" aria-label="个人中心功能">
        {workbenchItems.map(({ title, desc, metric, view, action, icon: Icon }) => (
          <article key={title} className="account-workbench-card">
            <Icon size={20} />
            <div>
              <span>{metric}</span>
              <strong>{title}</strong>
              <p>{desc}</p>
            </div>
            <button onClick={() => navigate(view)}>
              {action}
              <ArrowRight size={15} />
            </button>
          </article>
        ))}
      </section>

      <section className="account-boundary-note">
        <div>
          <small>边界说明</small>
          <strong>个人中心是私人工作台，公开主页是对外展示。</strong>
          <p>素材默认私有；只有主动申请公开并通过审核后，才会进入灵感广场。同款使用会保留来源，用于后续站内抵扣和分成结算。</p>
        </div>
        <button className="secondary" onClick={() => navigate("inspire")}>
          去灵感广场
        </button>
        <button className="secondary" onClick={logout}>
          退出登录
        </button>
      </section>
    </main>
  );
}
