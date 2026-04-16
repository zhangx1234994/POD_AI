import { useEffect, useMemo, useState } from 'react';
import { MessagePlugin } from 'tdesign-react';
import { Link, useNavigate } from 'react-router-dom';
import './WorkbenchPage.css';
import { demoRecentAssets, demoRecentTasks } from '../config/clientDemoData';
import { commercialSignals, launchWorkflows, studioRoutes, templateLibrary } from '../config/clientProduct';
import { useAuth } from '../app/AuthContext';
import { useWalletSnapshot } from '../hooks/useWalletSnapshot';
import { useAbilityTasks } from '../hooks/useAbilityTasks';
import { useAbilityPresentationMap } from '../hooks/useAbilityPresentationMap';
import { useClientAssets } from '../hooks/useClientAssets';
import {
  exportClientEventsJson,
  flushClientEvents,
  type ClientAnalyticsFlushResult,
  getClientAnalyticsTransportConfig,
  listClientEvents,
  subscribeClientEvents,
  summarizeClientOperations,
  trackClientEvent,
} from '../services/clientAnalytics';
import { buildTemplateLocationState, resolveContinueCreationTarget } from '../services/workspaceSeeds';
import { describeTaskSummary, extractPreviewUrl, mapTaskStatus } from '../services/workspaceRuntime';

export default function WorkbenchPage() {
  const navigate = useNavigate();
  const { auth, isAuthenticated } = useAuth();
  const { balance } = useWalletSnapshot(auth?.user.id);
  const { tasks, loading: tasksLoading, error: tasksError } = useAbilityTasks(auth?.accessToken, 6);
  const presentationNameMap = useAbilityPresentationMap();
  const assets = useClientAssets();
  const [eventVersion, setEventVersion] = useState(0);
  const [flushingEvents, setFlushingEvents] = useState(false);
  const [lastFlushResult, setLastFlushResult] = useState<ClientAnalyticsFlushResult | null>(null);

  const recentTaskRows = !isAuthenticated
    ? demoRecentTasks.slice(0, 4).map((task) => ({
        id: task.id,
        title: task.title,
        summary: task.summary,
        time: task.time,
        status: task.status,
        image: task.image,
      }))
    : tasks.slice(0, 4).map((task) => ({
        id: task.id,
        title: (task.capabilityKey && presentationNameMap.get(task.capabilityKey)) || task.abilityName || task.capabilityKey || '能力任务',
        summary: describeTaskSummary(task),
        time: new Date(task.createdAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        status: mapTaskStatus(task.status),
        image: extractPreviewUrl(task.resultPayload) || '',
      }));

  const recentAssetRows = (isAuthenticated ? assets : demoRecentAssets).slice(0, 4);
  const operatingSummary = useMemo(() => summarizeClientOperations(listClientEvents()), [eventVersion]);
  const analyticsTransport = getClientAnalyticsTransportConfig();
  const analyticsSummary = analyticsTransport.endpoint
    ? '经营事件已接到统计出口，可以继续核对转化和留存是否真实发生。'
    : '当前先保留本地经营事件，后续再统一接正式统计出口。';

  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'studio' });
  }, []);

  useEffect(() => subscribeClientEvents(() => setEventVersion((value) => value + 1)), []);

  function handleContinueAsset(asset: { image: string; title: string; source?: string; type?: 'image' | 'video'; tags?: string[]; pathHint?: string; origin?: 'upload' | 'result'; abilityKey?: string }) {
    const target = resolveContinueCreationTarget(asset);
    trackClientEvent('asset_continue_click', { source: 'studio', title: asset.title, path: target.path });
    navigate(target.path, { state: target.state });
  }

  async function handleCopyEvents() {
    try {
      await navigator.clipboard.writeText(exportClientEventsJson());
      MessagePlugin.success('本地经营事件快照已复制。');
    } catch {
      MessagePlugin.error('复制失败，请检查浏览器权限。');
    }
  }

  async function handleFlushEvents() {
    setFlushingEvents(true);
    const result = await flushClientEvents();
    setLastFlushResult(result);
    if (result.status === 'success') {
      MessagePlugin.success(result.message);
    } else if (result.status === 'disabled') {
      MessagePlugin.warning(result.message);
    } else {
      MessagePlugin.error(result.message);
    }
    setFlushingEvents(false);
    setEventVersion((value) => value + 1);
  }

  return (
    <div className="workbench-page">
      <section className="workbench-overview">
        <div className="workbench-overview__copy">
          <span className="client-eyebrow">Studio / Phase 1</span>
          <h1>今天先做哪一步？</h1>
          <p>
            Studio 先负责三件事：发起首任务、回看最近结果、从资产继续创作。先把高频动作跑通，再决定要不要补余额和换套餐。
          </p>
          <div className="workbench-overview__actions">
            <Link className="workbench-overview__primary" to="/design/text-to-style">
              从高频工作流开始
            </Link>
            <Link className="workbench-overview__secondary" to="/assets">
              查看资产与模板
            </Link>
          </div>
          <div className="workbench-overview__checklist">
            <span>01 首任务发起</span>
            <span>02 结果回看</span>
            <span>03 继续创作</span>
          </div>
        </div>
        <div className="workbench-overview__meta">
          <div className="workbench-kpi-card">
            <span>当前余额</span>
            <strong>{typeof balance === 'number' ? `${balance.toLocaleString()} 点` : '预览模式'}</strong>
            <p>{isAuthenticated ? '真实钱包快照已接入，可直接判断是否够发起下一步任务。' : '登录后会切到真实余额和消费数据。'}</p>
          </div>
          <div className="workbench-kpi-card">
            <span>本轮主线</span>
            <strong>先发起，再回看，再继续</strong>
            <p>先保证首个结果能回到当前页、进入任务中心，并能从资产层继续往下走。</p>
          </div>
        </div>
      </section>

      <section className="workbench-ops-board">
        <div className="workbench-section-head">
          <div>
            <h2>经营验证</h2>
            <p>等主链跑起来后，再用事件和指标确认“获客 {'->'} 激活 {'->'} 留存 {'->'} 变现”有没有真的发生。</p>
          </div>
          <div className="workbench-streams__actions">
            <button className="client-soft-button" type="button" onClick={() => void handleCopyEvents()}>
              复制事件快照
            </button>
            <button className="client-soft-button" type="button" onClick={() => void handleFlushEvents()}>
              {flushingEvents ? '上报中...' : analyticsTransport.endpoint ? '尝试上报' : '查看出口配置'}
            </button>
          </div>
        </div>
        <div className="workbench-ops-board__grid">
          <div className="workbench-ops-board__metrics">
            {operatingSummary.metrics.map((metric) => (
              <article key={metric.id} className={`workbench-ops-card is-${metric.status}`}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <p>{metric.note}</p>
              </article>
            ))}
          </div>
          <div className="workbench-ops-board__feed">
            <div className="workbench-stream-panel__head">
              <span>最近事件</span>
              <strong>本地埋点时间线</strong>
              <p>{analyticsSummary}</p>
            </div>
            {lastFlushResult ? (
              <div className={`client-callout${lastFlushResult.status === 'failed' ? ' client-callout--warm' : ''}`}>
                {lastFlushResult.message}
                {lastFlushResult.statusCode ? ` · HTTP ${lastFlushResult.statusCode}` : ''}
                {lastFlushResult.failureCode ? ` · ${lastFlushResult.failureCode}` : ''}
                {lastFlushResult.status === 'failed'
                  ? lastFlushResult.retryable
                    ? ' · 当前失败会保留待发事件，下次可继续重试。'
                    : ' · 当前失败不会自动推断可重试，请先确认出口配置。'
                  : null}
              </div>
            ) : null}
            <div className="workbench-template-stack">
              {operatingSummary.recentEvents.length ? (
                operatingSummary.recentEvents.map((item) => (
                  <article key={item.id} className="workbench-signal-card">
                    <strong>{item.label}</strong>
                    <p>{item.note}</p>
                    <span className="workbench-ops-card__time">{item.at}</span>
                  </article>
                ))
              ) : (
                <article className="workbench-signal-card">
                  <strong>还没有经营事件</strong>
                  <p>先从首页或 Studio 触发一条模板或工作流，经营看板才会开始累积数据。</p>
                </article>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="workbench-focus">
        <div className="workbench-section-head">
          <div>
            <h2>先做高频动作</h2>
            <p>先做深 6 个高频动作，不把目录铺满。</p>
          </div>
        </div>
        <div className="workbench-focus__grid">
          {launchWorkflows.map((workflow) => (
            <Link
              key={workflow.id}
              to={workflow.path}
              className={`workbench-focus__card client-accent--${workflow.accent}`}
              onClick={() => trackClientEvent('studio_workflow_click', { workflowId: workflow.id, path: workflow.path })}
            >
              <span>{workflow.category.toUpperCase()}</span>
              <strong>{workflow.title}</strong>
              <p>{workflow.subtitle}</p>
              <em>{workflow.note}</em>
            </Link>
          ))}
        </div>
      </section>

      <section className="workbench-routes">
        <div className="workbench-section-head">
          <div>
            <h2>下一步路径</h2>
            <p>不是做完一个工具就结束，而是直接告诉用户下一步往哪走。</p>
          </div>
        </div>
        <div className="workbench-routes__grid">
          {studioRoutes.map((route) => (
            <article key={route.id} className="workbench-route-card">
              <span>{route.title}</span>
              <p>{route.summary}</p>
              <div className="workbench-route-card__steps">
                {route.steps.map((step) => (
                  <em key={step}>{step}</em>
                ))}
              </div>
              <button
                className="client-soft-button"
                type="button"
                onClick={() => {
                  trackClientEvent('studio_route_click', { routeId: route.id, path: route.path });
                  navigate(route.path);
                }}
              >
                进入这条路径
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="workbench-streams">
        <div className="workbench-section-head">
          <div>
            <h2>最近任务与最近资产</h2>
            <p>第二次回来时，先看最近做了什么，再决定继续、重做还是换一条路径。</p>
          </div>
          <div className="workbench-streams__actions">
            <Link to="/tasks">任务中心</Link>
            <Link to="/assets">资产与模板中心</Link>
          </div>
        </div>
        <div className="workbench-streams__grid">
          <div className="workbench-stream-panel">
            <div className="workbench-stream-panel__head">
              <span>最近任务</span>
              <strong>{isAuthenticated ? '真实任务已接入' : '当前展示演示任务'}</strong>
            </div>
            <div className="workbench-stream-panel__list">
              {isAuthenticated && tasksLoading ? <div className="client-callout">正在同步最近任务...</div> : null}
              {isAuthenticated && tasksError ? <div className="client-callout client-callout--warm">{tasksError}</div> : null}
              {recentTaskRows.length ? (
                recentTaskRows.map((task) => (
                  <button key={task.id} className="workbench-stream-item" type="button" onClick={() => navigate('/tasks')}>
                    <div
                      className={`workbench-stream-item__media${task.image ? '' : ' workbench-stream-item__media--empty'}`}
                      style={task.image ? { backgroundImage: `url(${task.image})` } : undefined}
                    />
                    <div className="workbench-stream-item__body">
                      <div className="workbench-stream-item__meta">
                        <span>{task.time}</span>
                        <em className={`is-${task.status}`}>{task.status}</em>
                      </div>
                      <strong>{task.title}</strong>
                      <p>{task.summary}</p>
                    </div>
                  </button>
                ))
              ) : (
                <div className="client-empty-panel">
                  <strong>{isAuthenticated ? '还没有真实任务' : '还没有演示任务'}</strong>
                  <p>{isAuthenticated ? '先从高频工作流发起第一条真实任务，任务中心和结果回看才会开始积累。' : '先从一个模板或高频工作流开始，任务流转会在这里演示。'}</p>
                  <div className="client-empty-panel__actions">
                    <Link className="client-primary-link" to="/design/text-to-style">先做第一条设计任务</Link>
                    <Link className="client-secondary-link" to="/studio">回工作室</Link>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="workbench-stream-panel">
            <div className="workbench-stream-panel__head">
              <span>最近资产</span>
              <strong>结果要沉淀成下一次创作入口</strong>
            </div>
            <div className="workbench-asset-grid">
              {recentAssetRows.length ? (
                recentAssetRows.map((asset) => (
                  <button
                    key={asset.id}
                    className="workbench-asset-card"
                    type="button"
                    onClick={() =>
                      handleContinueAsset({
                        image: asset.image,
                        title: asset.title,
                        source: asset.source,
                        type: asset.type,
                        tags: asset.tags,
                        pathHint: 'pathHint' in asset && typeof asset.pathHint === 'string' ? asset.pathHint : undefined,
                        origin: 'origin' in asset && (asset.origin === 'upload' || asset.origin === 'result') ? asset.origin : undefined,
                        abilityKey: 'abilityKey' in asset && typeof asset.abilityKey === 'string' ? asset.abilityKey : undefined,
                      })
                    }
                  >
                    <div className="workbench-asset-card__media" style={{ backgroundImage: `url(${asset.image})` }} />
                    <strong>{asset.title}</strong>
                    <span>{asset.source}</span>
                  </button>
                ))
              ) : (
                <div className="client-empty-panel">
                  <strong>{isAuthenticated ? '还没有真实资产' : '还没有演示资产'}</strong>
                  <p>{isAuthenticated ? '上传原图或完成一次生成后，结果会自动沉淀到这里，下一次可以直接继续创作。' : '先体验一次结果沉淀后，这里会出现可继续创作的素材。'}
                  </p>
                  <div className="client-empty-panel__actions">
                    <Link className="client-primary-link" to="/design/text-to-style">先生成一个结果</Link>
                    <Link className="client-secondary-link" to="/assets">打开资产中心</Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="workbench-templates">
        <div className="workbench-section-head">
          <div>
            <h2>模板与运营线索</h2>
            <p>模板负责降低首任务门槛，运营线索负责判断用户有没有继续回来。</p>
          </div>
        </div>
        <div className="workbench-templates__grid">
          <div className="workbench-template-stack">
            {templateLibrary.slice(0, 4).map((template) => (
              <article key={template.id} className="workbench-template-card">
                <span>{template.category.toUpperCase()}</span>
                <strong>{template.title}</strong>
                <p>{template.summary}</p>
                <button
                  className="client-soft-button"
                  type="button"
                  onClick={() => {
                    trackClientEvent('template_start_click', { source: 'studio', templateId: template.id, path: template.path });
                    navigate(template.path, { state: buildTemplateLocationState(template) });
                  }}
                >
                  用模板开始
                </button>
              </article>
            ))}
          </div>
          <div className="workbench-signal-stack">
            {commercialSignals.map((signal) => (
              <article key={signal.title} className="workbench-signal-card">
                <strong>{signal.title}</strong>
                <p>{signal.note}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
