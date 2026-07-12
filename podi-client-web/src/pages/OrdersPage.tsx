/**
 * 订单页 — 从原 App.tsx 迁移，内容不变，改用 useApp() 获取状态
 */
import { useState } from "react";
import { BadgeCheck, CheckCircle2, CreditCard, PackageCheck, ShieldCheck } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import type { ProductionOrderSnapshot, WorkKind } from "../types";
import { baseOrderItems } from "../data/mock-data";
import PageHeader from "../components/PageHeader";
import DesignPreviewThumb from "../components/DesignPreviewThumb";
import { payClientOrder } from "../api";

type OrderPanel = "logistics" | "quality" | "cancel" | "detail";

function readPayableCents(order: ProductionOrderSnapshot) {
  const payment = order.metadata?.payment;
  if (!payment || typeof payment !== "object") return null;
  const payableCents = (payment as Record<string, unknown>).payableCents;
  return typeof payableCents === "number" && Number.isFinite(payableCents) ? payableCents : null;
}

function formatPayableAmount(cents: number | null) {
  return cents === null ? "以结算页为准" : `${Math.round(Math.max(0, cents) / 100)} 积分`;
}

function displayOrderStatus(status: ProductionOrderSnapshot["status"]) {
  if (status === "待确认") return "待平台确认";
  if (status === "制作中") return "制作中";
  return status;
}

function orderSourceImage(order: ProductionOrderSnapshot) {
  const supplyChain = order.metadata?.supplyChain;
  if (supplyChain && typeof supplyChain === "object" && Array.isArray((supplyChain as Record<string, unknown>).renderImageUrls)) {
    return null;
  }
  const value = order.metadata?.sourceAssetUrl;
  return typeof value === "string" && value ? value : null;
}

export default function OrdersPage() {
  const { state, dispatch, navigate, isAuthenticated, activeUserId } = useApp();
  const [activeOrderPanel, setActiveOrderPanel] = useState<OrderPanel>("logistics");
  const [activeOrderId, setActiveOrderId] = useState<string | null>(null);
  const [payingOrderId, setPayingOrderId] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState("");

  const latestProductionOrder = state.orders.length > baseOrderItems.length ? state.orders[0] : null;

  const orderItems = state.orders;

  if (!isAuthenticated) {
    return (
      <main className="page-shell">
        <PageHeader
          eyebrow="制作订单"
          title="登录后查看订单进度。"
          desc="订单、制作和物流状态会保存到你的账号。"
        />
        <section className="auth-required-panel">
          <PackageCheck size={28} />
          <div>
            <strong>登录后查看订单</strong>
            <p>从产品试做页提交订单后，进度会同步到这里。</p>
          </div>
          <button className="primary" onClick={() => navigate("account")}>去登录</button>
        </section>
      </main>
    );
  }

  const activeOrder =
    orderItems.find((o) => o.id === activeOrderId) ??
    latestProductionOrder ??
    orderItems[0] ??
    null;

  if (!activeOrder) {
    return (
      <main className="page-shell">
        <PageHeader
          eyebrow="制作订单"
          title="还没有制作订单。"
          desc="从产品试做页把设计放入设计篮并提交订单后，会在这里查看平台确认、生产、物流和售后状态。"
        />
        <section className="auth-required-panel">
          <PackageCheck size={28} />
          <div>
            <strong>从第一件试做开始</strong>
            <p>完成设计并提交订单后，制作、物流和售后进度会显示在这里。</p>
          </div>
          <button className="primary" onClick={() => navigate("products")}>继续做产品</button>
        </section>
      </main>
    );
  }

  const activeOrderIsWaiting = activeOrder.status === "待确认" || activeOrder.status === "待支付";
  const isPaymentPending = activeOrder.status === "待支付";
  const payableAmount = formatPayableAmount(readPayableCents(activeOrder));
  const supplyChain = activeOrder.metadata?.supplyChain;
  const supplierSubmitted = Boolean(
    supplyChain && typeof supplyChain === "object" && (supplyChain as Record<string, unknown>).platOrderId
  );
  const orderSteps = [
    { title: "设计已保存", body: "图案位置、款式和数量已写入订单。", done: true },
    isPaymentPending
      ? { title: "待支付", body: "确认金额并完成支付后，订单才会进入运营核对。", done: false }
      : { title: "已支付", body: "平台支付已完成，订单正在等待运营核对。", done: true },
    { title: "运营确认并推送蜂鸟", body: supplierSubmitted ? "蜂鸟订单已创建，等待供应链确认与效果图回传。" : "运营会核对设计稿和收货信息后推送蜂鸟。", done: supplierSubmitted },
    { title: "制作中", body: "按已接入款式和设计面制作。", done: ["制作中", "已发出", "已完成"].includes(activeOrder.status) },
    { title: "已发出/收货", body: "发货后同步物流，收货满意后可申请公开作品。", done: ["已发出", "已完成"].includes(activeOrder.status) },
  ];

  const openOrderDetail = (orderId: string) => {
    setActiveOrderId(orderId);
    setActiveOrderPanel("detail");
  };

  const handleMockPay = async (order: ProductionOrderSnapshot) => {
    if (payingOrderId || order.status !== "待支付") return;
    setPayingOrderId(order.id);
    setPaymentError("");
    try {
      const paidOrder = await payClientOrder({ userId: activeUserId, orderId: order.id, method: "mock", confirmAmountCents: readPayableCents(order) });
      dispatch({ type: "UPDATE_ORDER", id: order.id, patch: paidOrder });
      setActiveOrderId(order.id);
      setActiveOrderPanel("detail");
    } catch (error) {
      setPaymentError(error instanceof Error ? error.message : "支付确认失败，请稍后重试。");
    } finally {
      setPayingOrderId(null);
    }
  };

  const orderPanels: Record<OrderPanel, { title: string; body: string; steps: string[]; action: string }> = {
    logistics: {
      title: "物流与制作进度",
      body: isPaymentPending
        ? `${activeOrder.product} 正在等待平台支付。`
        : supplierSubmitted
          ? `${activeOrder.product} 已推送蜂鸟，供应链状态和效果图会回传到这里。`
          : `${activeOrder.product} 已支付，等待运营核对后推送蜂鸟。`,
      steps: isPaymentPending ? ["确认金额", "完成支付", "进入运营核对"] : supplierSubmitted ? ["蜂鸟后台选择快递", "蜂鸟后台完成供应链付款", "同步生产和物流"] : ["运营核对设计稿", "确认推送蜂鸟", "等待供应链回执"],
      action: isPaymentPending ? "去支付" : supplierSubmitted ? "查看供应链状态" : "等待运营确认",
    },
    quality: {
      title: "质量问题处理",
      body: "适用于破损、明显错印、漏印等问题。需要上传照片，确认后给出补发或退款方案。",
      steps: ["上传问题照片", "填写问题说明", "确认责任和处理方式"],
      action: "提交质量问题",
    },
    cancel: {
      title: "取消与退款",
      body: "待确认订单可以取消；已进入制作的定制产品，非质量问题不支持无理由退款。",
      steps: ["蜂鸟未确认前可在供应链侧取消", "制作中订单只处理质量问题", "平台不再扣除产品券"],
      action: "查看可取消订单",
    },
    detail: {
      title: "订单详情",
      body: "订单详情用于确认款式、数量、图片素材、收货信息和当前公开状态。",
      steps: [
        `${activeOrder.product} · ${activeOrder.quantity}`,
        `收货信息：${activeOrder.shippingSummary}`,
        "作品默认私有，收货满意后可申请公开",
      ],
      action: "查看完整详情",
    },
  };

  const activePanel = orderPanels[activeOrderPanel];

  const orderActions = [
    { key: "logistics" as OrderPanel, title: "制作/物流", body: "发货前看制作节点，发货后看物流。", action: "查看进度", icon: PackageCheck },
    { key: "quality" as OrderPanel, title: "质量问题", body: "破损、错印、漏印时上传照片处理。", action: "提交问题", icon: ShieldCheck },
    { key: "cancel" as OrderPanel, title: "取消/退款", body: activeOrderIsWaiting ? "当前订单未排产，可查看取消条件。" : "已进入制作，非质量问题不支持无理由退款。", action: "查看条件", icon: BadgeCheck },
  ];

  const openPublish = (_kind: WorkKind) => {
    navigate("publish");
  };

  return (
    <main className="page-shell">
      <PageHeader
        eyebrow="制作订单"
        title="订单进度"
        desc="先完成平台支付，再由运营核对并推送蜂鸟；后续生产、物流和蜂鸟效果图会同步回来。"
      />
      {latestProductionOrder && (
        <section className="latest-order-banner" aria-live="polite">
          <CheckCircle2 size={20} />
          <div>
            <strong>刚刚提交的制作订单已进入列表</strong>
            <p>{latestProductionOrder.createdAt} · {latestProductionOrder.product} · {latestProductionOrder.quantity} · {displayOrderStatus(latestProductionOrder.status)}</p>
          </div>
          <button className="secondary" onClick={() => openOrderDetail(latestProductionOrder.id)}>查看订单详情</button>
        </section>
      )}
      <section className="order-overview">
        {[
          { label: "待支付", value: String(orderItems.filter((o) => o.status === "待支付").length), note: "创建后未付款" },
          { label: "待运营确认", value: String(orderItems.filter((o) => o.status === "待确认").length), note: "已支付，等待核对" },
          { label: "制作中", value: String(orderItems.filter((o) => o.status === "制作中").length), note: "试做或已排产" },
          { label: "可公开", value: "2", note: "收货满意后申请" },
        ].map((item) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <p>{item.note}</p>
          </article>
        ))}
      </section>
      <section className="order-board">
        <div className="order-list">
          <div className="order-list-header">
            <div>
              <p className="eyebrow">我的制作订单</p>
              <h2>订单和售后都在这里。</h2>
            </div>
            <button className="secondary" onClick={() => navigate("products")}>继续做产品</button>
          </div>
          {orderItems.map((order) => (
            <article
              key={order.id}
              className={[
                "order-item",
                latestProductionOrder?.id === order.id ? "fresh" : "",
                activeOrder.id === order.id ? "active" : "",
              ].filter(Boolean).join(" ")}
            >
              <DesignPreviewThumb
                productImage={order.image}
                sourceImage={orderSourceImage(order)}
                alt={order.product}
                className="order-design-preview"
              />
              <div>
                <span className={order.status === "制作中" ? "type-tag product" : "type-tag"}>{displayOrderStatus(order.status)}</span>
                <h2>{order.product}</h2>
                <p>{order.asset} · {order.quantity}</p>
                <div className="tag-row">
                  <span>{order.createdAt}</span>
                  <span>{order.eta}</span>
                  <span>作品默认私有</span>
                </div>
                <small>{order.discount} · {order.shippingSummary}</small>
              </div>
              <button className="secondary" onClick={() => openOrderDetail(order.id)}>查看详情</button>
            </article>
          ))}
        </div>
        <aside className="order-side">
          <div className="order-side-head">
            <p className="eyebrow">当前订单</p>
            <h2>{activeOrder.product}</h2>
            <p>{displayOrderStatus(activeOrder.status)} · {activeOrder.asset} · {activeOrder.quantity}</p>
          </div>
          {isPaymentPending && (
            <div className="order-payment-callout">
              <CreditCard size={18} />
              <div><strong>待支付订单</strong><p>支付完成后才会进入运营核对，避免未付款订单误提交供应链。</p></div>
              <span>{payableAmount}</span>
              <button className="primary" disabled={payingOrderId === activeOrder.id} onClick={() => handleMockPay(activeOrder)}>{payingOrderId === activeOrder.id ? "确认中" : "测试支付"}</button>
            </div>
          )}
          {paymentError && <div className="order-payment-error" role="alert">{paymentError}</div>}
          <div className="order-timeline">
            {orderSteps.map((step) => (
              <article key={step.title} className={step.done ? "done" : ""}>
                <span>{step.done ? <CheckCircle2 size={14} /> : null}</span>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.body}</p>
                </div>
              </article>
            ))}
          </div>
          <div className="order-action-strip">
            {orderActions.map(({ key, title, body, action, icon: Icon }) => (
              <button
                key={key}
                className={activeOrderPanel === key ? "active" : ""}
                aria-label={action}
                onClick={() => setActiveOrderPanel(key)}
              >
                <Icon size={16} />
                <span>
                  <strong>{title}</strong>
                  <small>{body}</small>
                </span>
                <em>{action}</em>
              </button>
            ))}
          </div>
          <div className="order-context-panel" aria-live="polite">
            <div>
              <p className="eyebrow">当前处理</p>
              <h3>{activePanel.title}</h3>
              <p>{activePanel.body}</p>
            </div>
            <div className="support-step-list compact">
              {activePanel.steps.map((step, index) => (
                <article key={step}>
                  <span>{index + 1}</span>
                  <strong>{step}</strong>
                </article>
              ))}
            </div>
          </div>
          <div className="inline-actions">
            <button className="secondary" onClick={() => setActiveOrderPanel("detail")}>订单详情</button>
            <button className="primary" onClick={() => openPublish("产品作品")}>申请公开作品</button>
          </div>
        </aside>
      </section>
      <section className="after-sale-rules">
        {[
          { title: "物流问题", body: "发出后展示物流状态；长时间未更新时可提交查询。" },
          { title: "质量问题", body: "破损、明显印刷错位或漏印，可上传照片申请处理。" },
          { title: "取消退款", body: "未排产可取消；进入制作后按质量问题处理，不做无理由退。" },
          { title: "产品券", body: "产品券按订单状态退回；已核销并进入制作后按售后规则处理。" },
          { title: "公开审核", body: "订单作品默认私有；申请公开并审核通过后才进入灵感广场。" },
        ].map((item) => (
          <article key={item.title}>
            <ShieldCheck size={18} />
            <strong>{item.title}</strong>
            <p>{item.body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
