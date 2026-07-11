/**
 * 个人中心 — 私人工作台入口
 * 公开主页仍然保留为 ProfilePage，避免账号管理和对外展示混在一起。
 */
import {
  ArrowRight,
  ClipboardList,
  Grid3X3,
  PackageCheck,
  ShieldCheck,
  Sparkles,
  Star,
  Ticket,
  WalletCards,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useApp } from "../hooks/useAppState";
import type { AppView } from "../types";

export default function AccountPage() {
  const { state, navigate } = useApp();

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
          <span className="account-avatar xl">张</span>
          <div>
            <small>当前账号</small>
            <strong>张鑫</strong>
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
      </section>
    </main>
  );
}
