import { useEffect, useState } from 'react';
import { MessagePlugin } from 'tdesign-react';
import { useLocation, useNavigate } from 'react-router-dom';
import './WalletPage.css';
import { useAuth } from '../app/AuthContext';
import { demoWalletLedger, demoWalletPacks } from '../config/clientDemoData';
import { clientVisualRegistry } from '../config/clientVisuals';
import { useWalletSnapshot } from '../hooks/useWalletSnapshot';
import { clientApi, type RechargeOrderResponse, type WalletLedgerItem } from '../services/clientApi';
import { trackClientEvent } from '../services/clientAnalytics';

export default function WalletPage() {
  const { auth, isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { balance, frozenBalance, grantedToday, expense30Days, setBalance } = useWalletSnapshot(auth?.user.id);
  const [ledgerRows, setLedgerRows] = useState<WalletLedgerItem[]>([]);
  const [latestOrder, setLatestOrder] = useState<RechargeOrderResponse | null>(null);
  const [creatingOrder, setCreatingOrder] = useState<string | null>(null);
  const [refreshingOrder, setRefreshingOrder] = useState(false);
  const locationState = location.state as {
    returnTo?: string;
    returnState?: unknown;
    returnLabel?: string;
    requiredPoints?: number | null;
    currentBalance?: number | null;
    shortfallPoints?: number | null;
  } | null;
  const searchParams = new URLSearchParams(location.search);
  const effectiveReturnTo = locationState?.returnTo || searchParams.get('returnTo') || undefined;
  const effectiveReturnLabel = locationState?.returnLabel || searchParams.get('returnLabel') || undefined;
  const effectiveRequiredPoints =
    typeof locationState?.requiredPoints === 'number'
      ? locationState.requiredPoints
      : searchParams.get('requiredPoints')
        ? Number(searchParams.get('requiredPoints'))
        : null;
  const effectiveCurrentBalance =
    typeof locationState?.currentBalance === 'number'
      ? locationState.currentBalance
      : searchParams.get('currentBalance')
        ? Number(searchParams.get('currentBalance'))
        : null;
  const effectiveShortfallPoints =
    typeof locationState?.shortfallPoints === 'number'
      ? locationState.shortfallPoints
      : searchParams.get('shortfallPoints')
        ? Number(searchParams.get('shortfallPoints'))
        : null;
  const walletVisuals = {
    packA: clientVisualRegistry.walletPackStarter.url,
    packB: clientVisualRegistry.walletPackGrowth.url,
    packC: clientVisualRegistry.walletPackScale.url,
    hero: clientVisualRegistry.walletHero.url,
  };

  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'wallet', returnTo: effectiveReturnTo || null });
  }, [effectiveReturnTo]);

  const shortfallPoints = typeof effectiveShortfallPoints === 'number' ? effectiveShortfallPoints : null;
  const recommendedPack = shortfallPoints
    ? demoWalletPacks.find((pack) => pack.points >= shortfallPoints) || demoWalletPacks[demoWalletPacks.length - 1]
    : null;
  const estimatedRepeatRuns =
    recommendedPack && typeof effectiveRequiredPoints === 'number' && effectiveRequiredPoints > 0
      ? Math.max(1, Math.floor(recommendedPack.points / effectiveRequiredPoints))
      : null;

  useEffect(() => {
    if (latestOrder?.status !== 'paid' || !effectiveReturnTo) return;
    const timer = window.setTimeout(() => {
      navigate(effectiveReturnTo, { state: locationState?.returnState });
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [effectiveReturnTo, latestOrder?.status, locationState?.returnState, navigate]);

  useEffect(() => {
    let cancelled = false;
    async function loadLedger() {
      if (!auth?.user.id) return;
      try {
        const ledger = await clientApi.getWalletLedger(auth.user.id, 1, 8);
        if (!cancelled) setLedgerRows(ledger.items);
      } catch {
        if (!cancelled) setLedgerRows([]);
      }
    }
    void loadLedger();
    return () => {
      cancelled = true;
    };
  }, [auth?.user.id]);

  useEffect(() => {
    if (!latestOrder?.orderNo || latestOrder.status === 'paid' || latestOrder.status === 'failed' || latestOrder.status === 'canceled') {
      return;
    }
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const next = await clientApi.getRechargeOrder(latestOrder.orderNo);
        if (cancelled) return;
        setLatestOrder(next);
        if (next.status === 'paid' && auth?.user.id) {
          const wallet = await clientApi.getWalletBalance(auth.user.id);
          if (!cancelled) {
            setBalance(wallet.balance);
          }
          window.clearInterval(timer);
        }
      } catch {
        window.clearInterval(timer);
      }
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [auth?.user.id, latestOrder?.orderNo, latestOrder?.status]);

  async function handleCreateOrder(amount: string) {
    if (!auth?.user.id) {
      MessagePlugin.warning('请先登录，再创建充值订单。');
      return;
    }
    setCreatingOrder(amount);
    try {
      const order = await clientApi.createRechargeOrder(auth.user.id, Number(amount), 'manual');
      setLatestOrder(order);
      trackClientEvent('wallet_order_created', {
        amount: Number(amount),
        returnTo: effectiveReturnTo || null,
      });
      MessagePlugin.success(`充值单已创建：${order.orderNo}`);
    } catch (error) {
      MessagePlugin.error(error instanceof Error ? error.message : '充值单创建失败');
    } finally {
      setCreatingOrder(null);
    }
  }

  async function handleRefreshOrder() {
    if (!latestOrder?.orderNo) return;
    setRefreshingOrder(true);
    try {
      const next = await clientApi.getRechargeOrder(latestOrder.orderNo);
      setLatestOrder(next);
      if (next.status === 'paid' && auth?.user.id) {
        const wallet = await clientApi.getWalletBalance(auth.user.id);
        setBalance(wallet.balance);
        trackClientEvent('wallet_order_paid', {
          orderNo: next.orderNo,
          amount: next.amount,
          returnTo: effectiveReturnTo || null,
        });
      }
      MessagePlugin.success(`订单状态已刷新：${next.status}`);
    } catch (error) {
      MessagePlugin.error(error instanceof Error ? error.message : '订单状态刷新失败');
    } finally {
      setRefreshingOrder(false);
    }
  }
  const walletInsights = [
    { label: '当前余额', value: typeof balance === 'number' ? balance.toLocaleString() : '预览模式', note: '先判断是否足够继续提交' },
    { label: '最近订单', value: latestOrder?.status || '待创建', note: '充值单状态可随时刷新' },
    { label: '今日赠送', value: typeof grantedToday === 'number' ? grantedToday.toLocaleString() : '100', note: '适合补足轻量体验消耗' },
    { label: '近 30 天消耗', value: typeof expense30Days === 'number' ? expense30Days.toLocaleString() : '3,402', note: '主要来自设计与商拍' },
  ];

  return (
    <div className="client-page">
      <section className="client-section client-section--narrow">
        <div className="client-section__heading">
          <div>
            <p className="client-eyebrow">账户与积分中心</p>
            <h1>{isAuthenticated ? '先看余额，再决定充值，再返回原任务继续提交。' : '把余额、充值、账单和回流放进同一条真实业务链。'}</h1>
          </div>
        </div>
        {!isAuthenticated ? (
          <div className="client-callout">当前是预览模式。登录后钱包页会切到真实余额、流水和统计。</div>
        ) : null}
        {effectiveReturnTo ? (
          <div className="client-callout client-callout--warm">
            {shortfallPoints
              ? `你是从“${effectiveReturnLabel || '当前工作流'}”因为积分不足跳转过来的，当前大约还差 ${shortfallPoints.toLocaleString()} 点。`
              : '你是从功能页因为积分不足跳转过来的。创建充值单后，可以直接返回原页面继续提交。'}
            {typeof effectiveCurrentBalance === 'number' && typeof effectiveRequiredPoints === 'number' ? (
              <div>当前余额 {effectiveCurrentBalance.toLocaleString()} 点，预计消耗 {effectiveRequiredPoints.toLocaleString()} 点。</div>
            ) : null}
            <div className="client-callout__actions">
              <button
                className="client-soft-button"
                type="button"
                onClick={() => effectiveReturnTo && navigate(effectiveReturnTo, { state: locationState?.returnState })}
              >
                返回原页面
              </button>
            </div>
          </div>
        ) : null}
        {latestOrder ? (
          <div className="client-callout client-callout--warm">
            已创建充值单：{latestOrder.orderNo} · 状态：{latestOrder.status} · 金额：RMB {latestOrder.amount}
            <div className="client-callout__actions">
              <button className="client-soft-button" type="button" onClick={() => void handleRefreshOrder()}>
                {refreshingOrder ? '刷新中...' : '刷新订单状态'}
              </button>
              {latestOrder.status === 'paid' && effectiveReturnTo ? (
                <button
                  className="client-soft-button"
                  type="button"
                  onClick={() => navigate(effectiveReturnTo, { state: locationState?.returnState })}
                >
                  返回继续提交
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
        <div className="client-wallet-hero">
          <div className="client-wallet-hero__copy">
            <p className="client-eyebrow">账户 / 积分 / 充值</p>
            <h2>余额、充值、回流，一页看清。</h2>
            <p>这里只负责一件事：让用户在点数不足时快速理解差额、选一档套餐、完成充值后回原页面继续提交。</p>
            <div className="client-wallet-hero__steps">
              <div><span>01</span><strong>看余额</strong></div>
              <div><span>02</span><strong>下充值单</strong></div>
              <div><span>03</span><strong>{'返回 -> 继续提交'}</strong></div>
            </div>
          </div>
          <div
            className="client-wallet-hero__media"
            style={{ backgroundImage: `url(${walletVisuals.hero})` }}
          />
        </div>
        <div className="client-insight-grid client-insight-grid--wallet">
          {walletInsights.map((item) => (
            <article key={item.label} className="client-insight-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
        <div className="client-list-toolbar-note">
          <span>当前重点</span>
          <strong>
            {effectiveReturnTo
              ? `先补足当前差额，再返回${effectiveReturnLabel || '原工作流'}继续提交。`
              : '先看余额和最近账单，再决定是否创建新的充值单。'}
          </strong>
        </div>
        {recommendedPack ? (
          <div className="client-callout client-callout--warm">
            推荐套餐：{recommendedPack.title}，可补足当前差额并直接返回 {effectiveReturnLabel || '原任务'} 继续提交。
            {estimatedRepeatRuns ? <div>按当前预计消耗，这档大约还能支持 {estimatedRepeatRuns} 次同类任务。</div> : null}
          </div>
        ) : null}
        <div className="client-wallet-layout">
          <div className="client-panel">
            <div className="client-panel__header client-panel__header--compact">
              <div>
                <p className="client-eyebrow">充值套餐</p>
                <h3>先选能覆盖当前差额的一档</h3>
              </div>
            </div>
            <div className="client-wallet-pack-grid">
              {demoWalletPacks.map((pack) => (
                <button
                  key={pack.id}
                  className={`client-pack-card${pack.featured ? ' is-featured' : ''}${recommendedPack?.id === pack.id ? ' is-recommended' : ''}`}
                  type="button"
                  onClick={() => void handleCreateOrder(pack.price)}
                >
                  <div
                    className="client-pack-card__media"
                    style={{
                      backgroundImage: `url(${
                        pack.id === 'pack-s'
                          ? walletVisuals.packA
                          : pack.id === 'pack-m'
                            ? walletVisuals.packB
                            : walletVisuals.packC
                      })`,
                    }}
                  />
                  <div className="client-pack-card__top">
                    <span>{pack.title}</span>
                    {recommendedPack?.id === pack.id ? <em>建议补足</em> : pack.featured ? <em>推荐</em> : null}
                  </div>
                  <strong>{pack.points.toLocaleString()} 点</strong>
                  <p>{pack.notes}</p>
                  {recommendedPack?.id === pack.id && shortfallPoints ? (
                    <small className="client-pack-card__hint">
                      当前差额 {shortfallPoints.toLocaleString()} 点，这一档最适合直接回流。
                    </small>
                  ) : null}
                  <div className="client-pack-card__price">
                    {creatingOrder === pack.price ? '创建中...' : `RMB ${pack.price}`}
                  </div>
                </button>
              ))}
            </div>
          </div>
          <div className="client-panel">
            <div className="client-panel__header client-panel__header--compact">
              <div>
                <p className="client-eyebrow">最近账单</p>
                <h3>先看清每一笔点数花去了哪里</h3>
              </div>
            </div>
            <div className="client-list-toolbar-note client-list-toolbar-note--compact">
              <span>账单辅助</span>
              <strong>
                当前冻结 {typeof frozenBalance === 'number' ? frozenBalance.toLocaleString() : '24'} 点，
                主要来自尚未最终确认的任务。
              </strong>
            </div>
            <div className="client-ledger-list">
              {(ledgerRows.length
                ? ledgerRows.map((row) => ({
                    id: row.id,
                    type: row.changeType,
                    title: row.description || row.taskId || '钱包流水',
                    points: row.points,
                    time: row.createdAt ? new Date(row.createdAt).toLocaleString('zh-CN') : '-',
                  }))
                : demoWalletLedger
              ).map((row) => (
                <div key={row.id} className="client-ledger-row">
                  <div>
                    <strong>{row.title}</strong>
                    <p>{row.type} · {row.time}</p>
                  </div>
                  <span className={row.points > 0 ? 'is-positive' : 'is-negative'}>
                    {row.points > 0 ? '+' : ''}{row.points}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
