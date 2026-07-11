/**
 * 钱包页 — 从原 App.tsx 迁移，内容不变，改用 useApp() 获取状态
 */
import { useState } from "react";
import { CheckCircle2, Gift, Share2, Ticket, WalletCards } from "lucide-react";
import { useApp } from "../hooks/useAppState";
import PageHeader from "../components/PageHeader";

export default function WalletPage() {
  const { state, dispatch } = useApp();
  const { aiCredits, productCouponCount, shareBalance, latestWalletEvent } = state;

  const creditPackages = [
    { title: "轻量试用", amount: 100, credits: "100 AI 积分", price: 19, note: "适合少量洗图和裂变" },
    { title: "常用处理", amount: 600, credits: "600 AI 积分", price: 99, note: "适合批量处理一批素材" },
    { title: "创作者包", amount: 1500, credits: "1500 AI 积分", price: 199, note: "适合频繁生成产品样例" },
  ];

  const [selectedPack, setSelectedPack] = useState(creditPackages[1]);
  const [purchaseConfirmed, setPurchaseConfirmed] = useState(false);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeemed, setRedeemed] = useState(false);
  const [useShareCredit, setUseShareCredit] = useState(true);
  const [walletFocus, setWalletFocus] = useState<"coupon" | "redeem" | "share" | null>(null);

  const productBaseAmount = 2450;
  const couponDiscount = 49;
  const shareCreditAmount = useShareCredit ? shareBalance : 0;
  const payableAmount = productBaseAmount - couponDiscount - shareCreditAmount;

  const scrollToRecharge = () => {
    window.setTimeout(() => {
      document.querySelector(".wallet-checkout")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  };

  const focusWalletSection = (target: "coupon" | "redeem" | "share") => {
    setWalletFocus(target);
    window.setTimeout(() => {
      if (target === "coupon") {
        document.querySelector(".coupon-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      if (target === "redeem") {
        const input = document.querySelector<HTMLInputElement>(".redeem-row input");
        input?.scrollIntoView({ behavior: "smooth", block: "center" });
        input?.focus();
        return;
      }
      document.querySelector(".checkout-example")?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  };

  const choosePack = (item: (typeof creditPackages)[number]) => {
    setSelectedPack(item);
    setPurchaseConfirmed(false);
    scrollToRecharge();
  };

  const handleRedeem = () => {
    if (!redeemCode.trim()) return;
    dispatch({ type: "ADD_REDEEM_REWARD" });
    setRedeemed(true);
  };

  const handleCreditPurchase = () => {
    dispatch({
      type: "ADD_CREDITS",
      amount: selectedPack.amount,
      event: `购买了 ${selectedPack.credits}（${selectedPack.title}）`,
    });
    setPurchaseConfirmed(true);
  };

  const shareBalanceText = `¥${shareBalance.toFixed(2)}`;
  const couponRows =
    state.walletCoupons.length > 0
      ? state.walletCoupons.map((coupon) => [coupon.name, coupon.scope, coupon.expiresAt] as [string, string, string])
      : ([
          ["新人产品券", "可试做一件 T 恤", productCouponCount > 0 ? "7 天后过期" : "已使用"],
          ["创作者体验券", "可生成 5 组产品样例", productCouponCount > 1 ? "30 天后过期" : "暂无可用"],
          ["社群体验券", "可试做一件马克杯", productCouponCount > 2 ? "12 天后过期" : "暂无可用"],
        ] as Array<[string, string, string]>);

  const walletAssets = [
    {
      title: "AI 积分",
      value: String(aiCredits),
      body: "用于批量洗图、扩图、提取、裂变和产品样例生成。",
      rule: "未产出不消耗",
      icon: WalletCards,
      action: "购买积分",
      onUse: scrollToRecharge,
      primary: true,
    },
    {
      title: "产品券",
      value: `${productCouponCount} 张`,
      body: "用于指定产品款式的样例生成或试做一件实物。",
      rule: "不等同现金",
      icon: Ticket,
      action: "查看可用券",
      onUse: () => focusWalletSection("coupon"),
      primary: false,
    },
    {
      title: "站内抵扣",
      value: shareBalanceText,
      body: "公开作品被用同款后形成站内抵扣权益，可抵扣货款或兑换 AI 积分。",
      rule: "不可提现",
      icon: Share2,
      action: "查看抵扣",
      onUse: () => focusWalletSection("share"),
      primary: false,
    },
  ];

  return (
    <main className="page-shell">
      <PageHeader
        eyebrow="钱包"
        title="钱包与权益"
        desc="AI 积分、产品券和站内抵扣分开结算，做产品前再确认费用。"
      />
      <section className="wallet-asset-board" aria-label="钱包资产">
        {walletAssets.map(({ title, value, body, rule, icon: Icon, action, onUse, primary }) => (
          <article key={title}>
            <Icon size={22} />
            <div>
              <span>{title}</span>
              <strong>{value}</strong>
              <p>{body}</p>
            </div>
            <em>{rule}</em>
            <button className={primary ? "primary" : "secondary"} onClick={onUse}>{action}</button>
          </article>
        ))}
      </section>
      {latestWalletEvent && (
        <section className="wallet-ledger-banner" aria-live="polite">
          <CheckCircle2 size={18} />
          <div>
            <strong>最近账户变动</strong>
            <p>{latestWalletEvent}</p>
          </div>
        </section>
      )}
      <section className="payment-lane">
        <div className="payment-copy">
          <p className="eyebrow">充值与结算</p>
          <h2>积分和制作费分开算。</h2>
          <p>AI 积分适合小额高频消耗；产品制作按款式、数量、产品券和站内抵扣后再支付差额。</p>
        </div>
        <div className="credit-packages">
          {creditPackages.map((item) => (
            <article key={item.title} className={selectedPack.title === item.title ? "selected" : ""}>
              <span>{item.title}</span>
              <strong>{item.credits}</strong>
              <p>{item.note}</p>
              <button className="primary" onClick={() => choosePack(item)}>¥{item.price} 购买</button>
            </article>
          ))}
        </div>
      </section>
      <section className="wallet-checkout">
        <div>
          <p className="eyebrow">积分购买确认</p>
          <h2>{selectedPack.title}</h2>
          <p>{selectedPack.credits} · {selectedPack.note}</p>
        </div>
        <div className="wallet-checkout-summary">
          <span>本次应付</span>
          <strong>¥{selectedPack.price}</strong>
          <button className="primary" disabled={purchaseConfirmed} onClick={handleCreditPurchase}>
            {purchaseConfirmed ? "已加入账户" : "确认购买"}
          </button>
        </div>
        {purchaseConfirmed && (
          <div className="wallet-success wallet-checkout-success">
            <CheckCircle2 size={18} />
            <span>{selectedPack.credits} 已加入账户，当前可用 {aiCredits} AI 积分。</span>
          </div>
        )}
      </section>
      <section className={`checkout-example ${walletFocus === "share" ? "wallet-focus" : ""}`}>
        <div>
          <p className="eyebrow">制作费用预览</p>
          <h2>优惠先抵扣，制作前确认。</h2>
          <p>确认样例后才进入制作结算；图片处理积分和实物制作费用分开计算。</p>
        </div>
        <div className="checkout-breakdown">
          {(
            [
              ["基础短袖 T 恤", "50 件", "¥2,450"],
              ["产品券抵扣", "创作者体验券", "-¥49"],
              ["站内抵扣权益", useShareCredit ? `已使用 ${shareBalanceText}` : "未使用", useShareCredit ? `-${shareBalanceText}` : "-¥0"],
              ["待支付", "制作前确认", `¥${payableAmount.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`],
            ] as Array<[string, string, string]>
          ).map(([label, desc, value]) => (
            <div key={label}>
              <span>{label}</span>
              <em>{desc}</em>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <label className="share-credit-toggle">
          <input type="checkbox" checked={useShareCredit} onChange={(event) => setUseShareCredit(event.target.checked)} />
          <span>使用站内抵扣权益 {shareBalanceText}</span>
        </label>
      </section>
      <div className="wallet-panels">
        <section className={`wallet-panel redeem-panel ${walletFocus === "redeem" ? "wallet-focus" : ""}`}>
          <h2>兑换码</h2>
          <p>输入活动或邀请兑换码，可换 AI 积分或产品券。</p>
          <div className="redeem-row">
            <input
              value={redeemCode}
              onChange={(event) => {
                setRedeemCode(event.target.value);
                setRedeemed(false);
              }}
              placeholder="输入兑换码"
            />
            <button className="primary" disabled={!redeemCode.trim() || redeemed} onClick={handleRedeem}>
              {redeemed ? "已兑换" : "兑换"}
            </button>
          </div>
          {redeemed && (
            <div className="wallet-success">
              <CheckCircle2 size={18} />
              <span>兑换成功，已加入 100 AI 积分和 1 张产品券。</span>
            </div>
          )}
        </section>
        <section className={`wallet-panel coupon-panel ${walletFocus === "coupon" ? "wallet-focus" : ""}`}>
          <h2>产品券</h2>
          {couponRows.map(([name, scope, time]) => (
            <div key={name} className="coupon-row">
              <Gift size={18} />
              <div><strong>{name}</strong><span>{scope}</span></div>
              <em>{time}</em>
            </div>
          ))}
        </section>
      </div>
      <section className="wallet-rules">
        {(
          [
            ["AI 积分", "用于批量处理、图案裂变、产品样例等图片和样例生成；未产出不消耗，主动取消按实际进度结算。"],
            ["产品券", "用于指定产品款式的样例生成或试做一件，不等同现金，不支持转账。"],
            ["站内抵扣", "公开作品通过审核后才参与站内抵扣；权益留在站内，可抵扣货款或兑换 AI 积分，不支持提现。"],
          ] as Array<[string, string]>
        ).map(([title, body]) => (
          <article key={title}>
            <strong>{title}</strong>
            <p>{body}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
