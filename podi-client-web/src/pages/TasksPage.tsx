import { useEffect, useMemo, useState } from 'react';
import { FilterIcon, HistoryIcon } from 'tdesign-icons-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Dialog } from 'tdesign-react';
import './TasksPage.css';
import { useAuth } from '../app/AuthContext';
import { demoRecentTasks } from '../config/clientDemoData';
import { funnelMetrics } from '../config/clientProduct';
import { resolveWorkspacePathForTask } from '../config/toolConfigs';
import { useAbilityTasks } from '../hooks/useAbilityTasks';
import { useAbilityPresentationMap } from '../hooks/useAbilityPresentationMap';
import StatusPill from '../components/StatusPill';
import { buildWorkspaceSeedFromTask, describeTaskSummary, extractPreviewUrl, mapTaskStatus } from '../services/workspaceRuntime';
import { trackClientEvent } from '../services/clientAnalytics';
import { resolveContinueCreationTarget } from '../services/workspaceSeeds';
import type { TaskItem } from '../types';
import type { WorkspaceSeedTask } from '../types/workspace';

const tabs = ['全部', '排队中', '处理中', '已完成', '失败'];
const statusFilterMap: Record<string, string | null> = {
  全部: null,
  排队中: 'queued',
  处理中: 'running',
  已完成: 'success',
  失败: 'failed',
};

type TaskRow = TaskItem & {
  abilityLabel?: string;
  continuePath?: string | null;
  continueState?: unknown;
  retryPath?: string | null;
  retryState?: unknown;
  seedTask?: WorkspaceSeedTask;
  retrySeedTask?: WorkspaceSeedTask;
};

export default function TasksPage() {
  const navigate = useNavigate();
  const { auth, isAuthenticated } = useAuth();
  const { tasks, loading: tasksLoading, error: tasksError } = useAbilityTasks(auth?.accessToken, 30);
  const presentationNameMap = useAbilityPresentationMap();
  const [activeTab, setActiveTab] = useState('全部');
  const [showFilters, setShowFilters] = useState(false);
  const [activeAbilityFilter, setActiveAbilityFilter] = useState('全部功能');
  const [previewTask, setPreviewTask] = useState<TaskRow | null>(null);

  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'tasks', authenticated: isAuthenticated });
  }, [isAuthenticated]);

  const allRows = useMemo<TaskRow[]>(() => {
    const source = !isAuthenticated
      ? demoRecentTasks.map((task) => ({
          ...task,
          abilityLabel: task.title.split(' · ')[0] || '模拟任务',
          resultUrl: task.image,
          continuePath: null,
          continueState: null,
          retryPath: null,
          retryState: null,
        }))
      : tasks.map((task) => {
          const title = (task.capabilityKey && presentationNameMap.get(task.capabilityKey)) || task.abilityName || task.capabilityKey || '能力任务';
          const previewUrl = extractPreviewUrl(task.resultPayload) || '';
          const resolvedWorkspacePath = resolveWorkspacePathForTask(
            task.capabilityKey,
            Object.keys((task.requestPayload as Record<string, unknown> | null)?.inputs as Record<string, unknown> | undefined || {}),
          );
          const continueTarget = resolveContinueCreationTarget({
            image: previewUrl,
            title,
            source: task.provider,
            provider: task.provider,
            type: String(task.capabilityKey || '').includes('video') ? 'video' : 'image',
            tags: [task.provider, task.capabilityKey || '', title],
            pathHint: resolvedWorkspacePath || undefined,
            origin: 'result',
            abilityKey: task.capabilityKey || undefined,
          });
          const retryTarget = resolvedWorkspacePath
            ? { path: resolvedWorkspacePath, state: { seedTask: buildWorkspaceSeedFromTask(task, false) } }
            : null;
          return {
            id: task.id,
            title,
            abilityLabel: title,
            status: mapTaskStatus(task.status),
            time: new Date(task.createdAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
            summary: describeTaskSummary(task),
            image: previewUrl,
            resultUrl: previewUrl || undefined,
            continuePath: continueTarget?.path || null,
            continueState: continueTarget?.state || null,
            retryPath: retryTarget?.path || null,
            retryState: retryTarget?.state || null,
            seedTask: buildWorkspaceSeedFromTask(task, true),
            retrySeedTask: buildWorkspaceSeedFromTask(task, false),
          };
        });
    return source;
  }, [isAuthenticated, presentationNameMap, tasks]);

  const abilityFilters = useMemo(() => {
    const counter = new Map<string, number>();
    allRows.forEach((task) => {
      const key = task.abilityLabel || '未分类';
      counter.set(key, (counter.get(key) || 0) + 1);
    });
    return [{ label: '全部功能', count: allRows.length }].concat(
      Array.from(counter.entries()).map(([label, count]) => ({ label, count })),
    );
  }, [allRows]);

  const rows = useMemo(() => {
    const filter = statusFilterMap[activeTab];
    return allRows.filter((task) => {
      if (filter && task.status !== filter) return false;
      if (activeAbilityFilter !== '全部功能' && task.abilityLabel !== activeAbilityFilter) return false;
      return true;
    });
  }, [activeAbilityFilter, activeTab, allRows]);
  const taskStats = useMemo(
    () => [
      { label: '全部任务', value: allRows.length, tab: '全部' },
      { label: '处理中', value: allRows.filter((task) => task.status === 'running').length, tab: '处理中' },
      { label: '已完成', value: allRows.filter((task) => task.status === 'success').length, tab: '已完成' },
      { label: '失败', value: allRows.filter((task) => task.status === 'failed').length, tab: '失败' },
    ],
    [allRows],
  );

  return (
    <div className="client-page">
      <section className="client-section client-section--narrow">
        <div className="client-section__heading">
          <div>
            <p className="client-eyebrow">任务中心</p>
            <h1>{isAuthenticated ? '先看进度，再确认结果，再决定继续还是重做。' : '先用演示任务理解“提交 -> 回看 -> 重做 -> 沉淀”的完整闭环。'}</h1>
            <p>{isAuthenticated ? `最近 ${allRows.length} 条任务会集中展示在这里，先筛状态，再决定查看结果、继续创作还是直接复跑。` : '登录后这里会自动切到你的真实任务列表和结果回看入口。'}</p>
          </div>
          <button className="client-soft-button" type="button" onClick={() => navigate('/studio')}>
            回工作室
          </button>
        </div>
        <div className="client-task-intro-grid">
          {funnelMetrics.slice(1, 4).map((item) => (
            <article key={item.label} className="client-task-intro-card">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
        <div className="client-ops-summary">
          {taskStats.map((item) => (
            <button
              key={item.label}
              className={`client-ops-summary__card${activeTab === item.tab ? ' is-active' : ''}`}
              type="button"
              onClick={() => setActiveTab(item.tab)}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </button>
          ))}
        </div>
        <div className="client-task-toolbar">
          <div className="client-tab-strip">
            {tabs.map((tab) => (
              <button
                key={tab}
                className={`client-tab-strip__item${activeTab === tab ? ' is-active' : ''}`}
                type="button"
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <button className="client-soft-button" type="button" onClick={() => setShowFilters((prev) => !prev)}>
            <FilterIcon size="16" />
            {activeAbilityFilter === '全部功能' ? '筛选功能' : `功能：${activeAbilityFilter}`}
          </button>
        </div>
        {showFilters ? (
          <div className="client-filter-panel">
            {abilityFilters.map((item) => (
              <button
                key={item.label}
                className={`client-filter-chip${activeAbilityFilter === item.label ? ' is-active' : ''}`}
                type="button"
                onClick={() => setActiveAbilityFilter(item.label)}
              >
                <span>{item.label}</span>
                <strong>{item.count}</strong>
              </button>
            ))}
          </div>
        ) : null}
        <div className="client-panel">
          {!isAuthenticated ? <div className="client-callout">当前为体验模式，任务状态和结果均为演示数据。</div> : null}
          {isAuthenticated && tasksLoading ? <div className="client-callout">正在加载真实任务列表...</div> : null}
          {isAuthenticated && tasksError ? <div className="client-callout client-callout--warm">{tasksError}</div> : null}
          <div className="client-list-toolbar-note">
            <span>操作提示</span>
            <strong>先筛状态，再看结果，再决定返回工作区继续改，还是直接再来一次。</strong>
          </div>
          <div className="client-task-table">
            {rows.map((task) => (
              <div
                key={task.id}
                className={`client-task-table__row${task.resultUrl ? ' is-clickable' : ''}`}
                onClick={() => {
                  if (!task.resultUrl) return;
                  trackClientEvent('task_preview_opened', { taskId: task.id, ability: task.abilityLabel || task.title });
                  setPreviewTask(task);
                }}
              >
                <div
                  className={`client-task-table__visual${task.image ? '' : ' client-task-table__visual--empty'}`}
                  style={task.image ? { backgroundImage: `url(${task.image})` } : undefined}
                >
                  <span className="client-media-badge">{task.image ? task.abilityLabel || '任务' : '等待结果'}</span>
                </div>
                <div className="client-task-table__main">
                  <div className="client-task-table__label-row">
                    <span>{task.abilityLabel || '能力任务'}</span>
                    <span>{task.time}</span>
                  </div>
                  <strong>{task.title}</strong>
                  <p>{task.summary}</p>
                  <div className="client-task-table__meta">
                    <StatusPill status={task.status} />
                    <span className="client-task-table__id">{task.id}</span>
                  </div>
                </div>
                <div className="client-task-table__actions">
                  {task.resultUrl && task.continuePath ? (
                    <button
                      className="client-soft-button"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        trackClientEvent('task_result_reopen', { taskId: task.id, path: task.continuePath });
                        navigate(task.continuePath!, { state: task.continueState });
                      }}
                    >
                      继续
                    </button>
                  ) : task.resultUrl ? (
                    <a
                      className="client-soft-button"
                      href={task.resultUrl}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(event) => event.stopPropagation()}
                    >
                      结果
                    </a>
                  ) : (
                    <span className="client-task-table__pending">等待完成后可查看</span>
                  )}
                  {task.retryPath ? (
                    <button
                      className="client-soft-button"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        trackClientEvent('task_retry_click', { taskId: task.id, path: task.retryPath });
                        navigate(task.retryPath!, { state: task.retryState });
                      }}
                    >
                      <HistoryIcon size="16" /> 重做
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
            {!rows.length ? (
              <div className="client-empty-panel">
                <strong>{isAuthenticated ? '当前筛选下还没有真实任务' : '当前筛选下还没有任务'}</strong>
                <p>
                  {isAuthenticated
                    ? '先回工作台发起一条真实任务，结果会回到当前页，也会同步进入任务中心。'
                    : '可以切换状态或功能筛选，或者先回工作台发起新的创作任务。'}
                </p>
                <div className="client-empty-panel__actions">
                  <Link className="client-primary-link" to="/design/text-to-style">先发起一条任务</Link>
                  <Link className="client-secondary-link" to="/studio">回工作室</Link>
                </div>
              </div>
            ) : null}
          </div>
        </div>
        <div className="client-task-next-grid">
          <Link to="/assets" className="client-task-next-card">
            <span>结果沉淀</span>
            <strong>回到资产与模板中心</strong>
            <p>把已验证结果沉淀成素材，下一次直接从资产继续创作。</p>
          </Link>
          <Link to="/studio" className="client-task-next-card">
            <span>再次激活</span>
            <strong>返回工作室继续下一条路径</strong>
            <p>任务不是终点，Studio 负责承接下一步动作和推荐路径。</p>
          </Link>
          <Link to="/wallet" className="client-task-next-card">
            <span>商业入口</span>
            <strong>查看余额和套餐策略</strong>
            <p>高频重做前先确认余额和套餐，避免在提交时才理解成本。</p>
          </Link>
        </div>
        <Dialog
          visible={Boolean(previewTask)}
          width={900}
          header={previewTask ? `${previewTask.title} · 结果预览` : '结果预览'}
          confirmBtn={null}
          cancelBtn={false}
          onClose={() => setPreviewTask(null)}
        >
          {previewTask ? (
            <div className="client-result-preview">
              <div
                className={`client-result-preview__media${previewTask.resultUrl || previewTask.image ? '' : ' client-result-preview__media--empty'}`}
                style={previewTask.resultUrl || previewTask.image ? { backgroundImage: `url(${previewTask.resultUrl || previewTask.image})` } : undefined}
              />
              <div className="client-result-preview__body">
                <div className="client-dialog-metric">
                  <span>任务状态</span>
                  <strong>{previewTask.summary}</strong>
                </div>
                <div className="client-dialog-metric">
                  <span>任务时间</span>
                  <strong>{previewTask.time}</strong>
                </div>
                <div className="client-dialog-metric">
                  <span>任务编号</span>
                  <strong>{previewTask.id}</strong>
                </div>
                <div className="client-callout">
                  你可以先在这里快速确认结果，再决定是返回工作台继续改，还是直接下载素材。
                </div>
                <div className="client-result-preview__actions">
                  {previewTask.resultUrl ? (
                    <a className="client-soft-button" href={previewTask.resultUrl} target="_blank" rel="noreferrer">
                      查看原图
                    </a>
                  ) : null}
                  {previewTask.continuePath ? (
                    <Button
                      theme="primary"
                      onClick={() => {
                        trackClientEvent('task_result_reopen', { taskId: previewTask.id, path: previewTask.continuePath });
                        navigate(previewTask.continuePath!, { state: previewTask.continueState });
                      }}
                    >
                      继续创作
                    </Button>
                  ) : null}
                  {previewTask.retryPath ? (
                    <button
                      className="client-soft-button"
                      type="button"
                      onClick={() => {
                        trackClientEvent('task_retry_click', { taskId: previewTask.id, path: previewTask.retryPath });
                        navigate(previewTask.retryPath!, { state: previewTask.retryState });
                      }}
                    >
                      再来一次
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </Dialog>
      </section>
    </div>
  );
}
