import { useEffect, useMemo } from 'react';
import { ArrowRightIcon, TimeIcon } from 'tdesign-icons-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { demoRecentAssets, demoRecentTasks, demoWhiteboardProjects } from '../config/clientDemoData';
import { useAbilityTasks } from '../hooks/useAbilityTasks';
import { useAbilityPresentationMap } from '../hooks/useAbilityPresentationMap';
import { useClientAssets } from '../hooks/useClientAssets';
import { trackClientEvent } from '../services/clientAnalytics';
import { resolveContinueCreationTarget } from '../services/workspaceSeeds';
import { describeTaskSummary, extractPreviewUrl, mapTaskStatus } from '../services/workspaceRuntime';

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { auth, isAuthenticated } = useAuth();
  const { tasks: liveTasks } = useAbilityTasks(auth?.accessToken, 8);
  const presentationNameMap = useAbilityPresentationMap();
  const liveAssets = useClientAssets();

  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'project-detail', projectId: projectId || 'new' });
  }, [projectId]);
  const project = useMemo(
    () =>
      demoWhiteboardProjects.find((item) => item.id === projectId) || {
        id: 'new',
        title: '当前项目',
        summary: '把灵感参考、历史任务和结果素材重新挂回一个可继续推进的上下文。',
        tag: '工作室',
        image: isAuthenticated ? undefined : demoRecentAssets[0].image,
      },
    [isAuthenticated, projectId],
  );

  const timelineItems = useMemo(() => {
    if (!isAuthenticated) return demoRecentTasks;
    if (!liveTasks.length) return [];
    return liveTasks.slice(0, 6).map((task) => ({
      id: task.id,
      title: (task.capabilityKey && presentationNameMap.get(task.capabilityKey)) || task.abilityName || task.capabilityKey || '能力任务',
      summary: describeTaskSummary(task),
      time: new Date(task.createdAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
      status: mapTaskStatus(task.status),
      image: extractPreviewUrl(task.resultPayload) || '',
    }));
  }, [isAuthenticated, liveTasks, presentationNameMap]);

  const projectAssets = useMemo(() => {
    if (liveAssets.length) return liveAssets.slice(0, 4);
    return isAuthenticated ? [] : demoRecentAssets;
  }, [isAuthenticated, liveAssets]);
  const projectMoments = [
    {
      id: 'moment-1',
      label: project.tag,
      title: '项目方向',
      note: '适合先确认当前项目是继续设计，还是进入商拍与交付。',
      image: project.image || (!isAuthenticated ? demoRecentAssets[0].image : ''),
    },
    {
      id: 'moment-2',
      label: '最近任务',
      title: '任务回看',
      note: '适合快速判断最近生成结果是否值得继续迭代。',
      image: timelineItems[0]?.image || (!isAuthenticated ? demoRecentAssets[1].image : ''),
    },
    {
      id: 'moment-3',
      label: '素材沉淀',
      title: '资产沉淀',
      note: '适合把已经稳定的结果继续沉淀到素材库和白板。',
      image: projectAssets[0]?.image || (!isAuthenticated ? demoRecentAssets[2].image : ''),
    },
  ];

  return (
    <div className="client-page">
      <section className="client-section client-section--narrow">
        <div
          className="client-project-hero"
          style={project.image ? { backgroundImage: `linear-gradient(135deg, rgba(255,255,255,0.84), rgba(247,241,231,0.88)), radial-gradient(circle at top right, rgba(31,93,131,0.08), transparent 35%), url(${project.image})` } : undefined}
        >
          <div>
            <p className="client-eyebrow">{project.tag}</p>
            <h1>{project.title}</h1>
            <p>{project.summary}</p>
            <div className="client-project-hero__actions">
              <Link className="client-primary-link" to="/design/text-to-style">
                去研发设计 <ArrowRightIcon size="16" />
              </Link>
              <Link className="client-secondary-link" to="/shoot/marketing-variants">
                去视觉商拍
              </Link>
            </div>
          </div>
          <div className="client-project-hero__stats">
            <div className="client-project-hero__stat">
              <span>相关任务</span>
              <strong>{timelineItems.length}</strong>
            </div>
            <div className="client-project-hero__stat">
              <span>相关素材</span>
              <strong>{projectAssets.length}</strong>
            </div>
            <div className="client-project-hero__stat">
              <span>当前阶段</span>
              <strong>继续迭代</strong>
            </div>
          </div>
        </div>
        <div className="client-project-showcase">
          {projectMoments.map((item) => (
            <article key={item.id} className="client-project-showcase__card">
              <div
                className={`client-project-showcase__media${item.image ? '' : ' client-project-showcase__media--empty'}`}
                style={item.image ? { backgroundImage: `url(${item.image})` } : undefined}
              >
                <span className="client-media-badge">{item.label}</span>
              </div>
              <div className="client-project-showcase__body">
                <span>{item.label}</span>
                <strong>{item.title}</strong>
                <p>{item.note}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="client-home-grid">
          <div className="client-panel">
            <div className="client-panel__header client-panel__header--compact">
              <div>
                <p className="client-eyebrow">项目时间线</p>
                <h3>把设计、任务和结果挂回一个可追踪的面板</h3>
              </div>
            </div>
            <div className="client-project-timeline">
              {timelineItems.length ? (
                timelineItems.map((task) => (
                  <button
                    key={task.id}
                    className="client-project-timeline__item client-project-timeline__item--button"
                    type="button"
                    onClick={() => {
                      trackClientEvent('project_timeline_click', { projectId: project.id, taskId: task.id });
                      navigate('/tasks');
                    }}
                  >
                    <div className="client-project-timeline__marker" />
                    <div className="client-project-timeline__content">
                      {task.image ? (
                        <div className="client-project-timeline__thumb" style={{ backgroundImage: `url(${task.image})` }}>
                          <span className="client-media-badge">{task.status}</span>
                        </div>
                      ) : null}
                      <strong>{task.title}</strong>
                      <p>{task.summary}</p>
                      <span>
                        <TimeIcon size="14" /> {task.time}
                      </span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="client-empty-panel">
                  <strong>当前项目还没有真实任务</strong>
                  <p>先从研发设计或视觉商拍发起一条任务，项目时间线才会开始积累。</p>
                  <div className="client-empty-panel__actions">
                    <Link className="client-primary-link" to="/design/text-to-style">去发起设计任务</Link>
                    <Link className="client-secondary-link" to="/shoot/marketing-variants">去视觉商拍</Link>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="client-panel">
            <div className="client-panel__header client-panel__header--compact">
              <div>
                <p className="client-eyebrow">项目素材</p>
                <h3>从项目上下文继续跳回具体功能页</h3>
              </div>
            </div>
            <div className="client-asset-grid">
              {projectAssets.length ? (
                projectAssets.map((asset) => (
                  <button
                    key={asset.id}
                    className="client-asset-card client-asset-card--button"
                    type="button"
                    onClick={() => {
                      const target = resolveContinueCreationTarget({
                        image: asset.image,
                        title: asset.title,
                        source: 'source' in asset ? asset.source : '项目素材',
                        type: asset.type,
                        tags: asset.tags,
                        pathHint: 'pathHint' in asset && typeof asset.pathHint === 'string' ? asset.pathHint : undefined,
                        origin: 'origin' in asset && (asset.origin === 'upload' || asset.origin === 'result') ? asset.origin : undefined,
                        abilityKey: 'abilityKey' in asset && typeof asset.abilityKey === 'string' ? asset.abilityKey : undefined,
                      });
                      trackClientEvent('asset_continue_click', { source: 'project-detail', title: asset.title, path: target.path });
                      navigate(target.path, { state: target.state });
                    }}
                  >
                    <div className="client-asset-card__media" style={{ backgroundImage: `url(${asset.image})` }}>
                      <span className="client-media-badge">{'source' in asset ? asset.source : '项目素材'}</span>
                    </div>
                    <div className="client-asset-card__body">
                      <strong>{asset.title}</strong>
                      <span>{'source' in asset ? asset.source : '项目素材'}</span>
                      <small>{asset.createdAt}</small>
                    </div>
                  </button>
                ))
              ) : (
                <div className="client-empty-panel">
                  <strong>当前项目还没有真实素材</strong>
                  <p>先上传原图或完成一次生成，素材会自动沉淀到这里，后续可以直接继续创作。</p>
                  <div className="client-empty-panel__actions">
                    <Link className="client-primary-link" to="/design/text-to-style">先生成一个结果</Link>
                    <Link className="client-secondary-link" to="/assets">查看资产中心</Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
