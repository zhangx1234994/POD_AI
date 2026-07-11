/**
 * 订单页 — 从原 App.tsx 迁移，内容不变，改用 useApp() 获取状态
 */
import { useState } from "react";
import { CheckCircle2, PackageCheck, ShieldCheck, BadgeCheck } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import type { ProductionOrderSnapshot, WorkKind } from "../types";
import PageHeader from "../components/PageHeader";

type OrderPanel = "logistics" | "quality" | "cancel" | "detail";

export default function OrdersPage() {
  const { state, dispatch, navigate } = useApp();
  const [activeOrderPanel, setActiveOrderPanel] = useState<OrderPanel>("logistics");
  const [activeOrderId, setActiveOrderId] = useState<string | null>(null);

  const orderItems = state.orders;
  const activeOrder =
    orderItems.find((o) => o.id === activeOrderId) ??
    orderItems[0];
  const latestProductionOrder = orderItems[0] ?? null;

  if (!activeOrder) {
    return (
      <main className="page-shell">
        <PageHeader eyebrow="制作订单" title="还没有制作订单" desc="在商品页提交后，中台会先生成并预检生产文件；支付完成后再进入运营核对。" />
        <section className="order-empty-state">
          <PackageCheck size={28} />
          <strong>从一张素材开始做产品</strong>
          <p>订单、生产文件、供应链状态和效果图都会在这里保留证据。</p>
          <button className="primary" onClick={() => navigate("products")}>去选杯型</button>
        </section>
      </main>
    );
  }

  const activeOrderIsWaiting = ["待支付", "运营核对", "待确认"].includes(activeOrder.status);
  const activeOrderIsSubmitted = activeOrder.status === "已推送供应商";
  const orderSteps = activeOrderIsWaiting
    ? [
        { title: "生产文件", body: activeOrder.preflightPassed ? "已按指定尺寸完成预检。" : "等待生成并通过生产预检。", done: Boolean(activeOrder.preflightPassed) },
        { title: "支付确认", body: activeOrder.status === "待支付" ? "等待平台支付回调。" : "支付已确认。", done: activeOrder.status !== "待支付" },
        { title: "运营核对", body: activeOrder.status === "运营核对" ? "运营正在核对款式、生产文件和收货信息。" : "支付完成后进入运营核对。", done: false },
        { title: "推送供应链", body: "运营确认后才会推送蜂鸟。", done: false },
        { title: "生产与物流", body: "供应商会回传生产、效果图和物流信息。", done: false },
      ]
    : [
        { title: "生产文件", body: "已保存生产文件及预检记录。", done: true },
        { title: "已支付", body: "平台已确认收款。", done: true },
        { title: "已推送蜂鸟", body: activeOrderIsSubmitted ? "供应商已接收订单，等待后续回传。" : "供应商生产状态已同步。", done: true },
        { title: "效果图与质检", body: activeOrder.supplierEffectImageUrl ? "已归档供应商效果图。" : "等待供应商回传效果图或质检信息。", done: Boolean(activeOrder.supplierEffectImageUrl) },
        { title: "物流与签收", body: activeOrder.status === "已发货" || activeOrder.status === "已完成" ? "物流状态已回填。" : "等待供应商发货。", done: ["已发货", "已完成"].includes(activeOrder.status) },
      ];

  const openOrderDetail = (orderId: string) => {
    setActiveOrderId(orderId);
    setActiveOrderPanel("detail");
  };

  const orderPanels: Record<OrderPanel, { title: string; body: string; steps: string[]; action: string }> = {
    logistics: {
      title: activeOrderIsWaiting ? "生产前确认" : "物流与制作进度",
      body: activeOrderIsWaiting
        ? `${activeOrder.product} 已保存生产文件，当前还没有推送供应商。`
        : `${activeOrder.product} 已进入供应链闭环，供应商回传的状态、效果图和物流证据会在此归档。`,
      steps: activeOrderIsWaiting ? ["生产文件已保存", "等待支付", "支付后运营核对"] : ["供应商订单已建立", "等待效果图/生产状态", "发货后回填物流"],
      action: activeOrderIsWaiting ? "查看支付状态" : "查看供应链状态",
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
      steps: ["待确认订单可取消", "制作中订单只处理质量问题", "产品券按实际规则退回"],
      action: "查看可取消订单",
    },
    detail: {
      title: "订单详情",
      body: "订单详情用于确认款式、数量、图片素材、收货信息和当前公开状态。",
      steps: [
        `${activeOrder.product} · ${activeOrder.quantity}`,
        `收货信息：${activeOrder.shippingSummary}`,
        activeOrder.orderNo ? `订单号：${activeOrder.orderNo}` : "订单号生成中",
      ],
      action: "查看完整详情",
    },
  };

  const activePanel = orderPanels[activeOrderPanel];

  const orderActions = [
    { key: "logistics" as OrderPanel, title: activeOrderIsWaiting ? "订单进度" : "供应链状态", body: activeOrderIsWaiting ? "支付后进入运营核对。" : "效果图、生产状态和物流会持续同步。", action: activeOrderIsWaiting ? "查看状态" : "查看进度", icon: PackageCheck },
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
        desc="生产文件、支付、运营核对、供应链状态和售后证据都在这里。"
      />
      {latestProductionOrder && (
        <section className="latest-order-banner" aria-live="polite">
          <CheckCircle2 size={20} />
          <div>
            <strong>{latestProductionOrder.status} · {latestProductionOrder.product}</strong>
            <p>{latestProductionOrder.orderNo ?? latestProductionOrder.id} · {latestProductionOrder.createdAt} · {latestProductionOrder.eta}</p>
          </div>
          <button className="secondary" onClick={() => openOrderDetail(latestProductionOrder.id)}>查看订单详情</button>
        </section>
      )}
      <section className="order-overview">
        {[
          { label: "待支付", value: String(orderItems.filter((o) => o.status === "待支付").length), note: "等待平台支付确认" },
          { label: "运营核对", value: String(orderItems.filter((o) => o.status === "运营核对").length), note: "支付完成后核对生产文件" },
          { label: "供应链中", value: String(orderItems.filter((o) => ["已推送供应商", "制作中", "已发货"].includes(o.status)).length), note: "蜂鸟状态持续同步" },
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
              {order.image ? <img src={order.image} alt={order.product} /> : <div className="order-image-placeholder">生产文件</div>}
              <div>
                <span className={["已推送供应商", "制作中", "已发货", "已完成"].includes(order.status) ? "type-tag product" : "type-tag"}>{order.status}</span>
                <h2>{order.product}</h2>
                <p>{order.asset} · {order.quantity}</p>
                <div className="tag-row">
                  <span>{order.createdAt}</span>
                  <span>{order.eta}</span>
                  <span>{order.preflightPassed ? "生产预检已通过" : "等待生产预检"}</span>
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
            <p>{activeOrder.status} · {activeOrder.asset} · {activeOrder.quantity}</p>
          </div>
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
            <button className="primary" disabled={activeOrder.status !== "已完成"} onClick={() => openPublish("产品作品")}>申请公开作品</button>
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
