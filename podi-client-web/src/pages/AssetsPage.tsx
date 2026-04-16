import { useEffect, useMemo, useState } from 'react';
import { DownloadIcon, PlayCircleIcon, StarIcon } from 'tdesign-icons-react';
import { useNavigate } from 'react-router-dom';
import './AssetsPage.css';
import { demoRecentAssets } from '../config/clientDemoData';
import { templateLibrary } from '../config/clientProduct';
import { useAuth } from '../app/AuthContext';
import { useClientAssets } from '../hooks/useClientAssets';
import { removeClientAsset } from '../services/assetLibrary';
import { trackClientEvent } from '../services/clientAnalytics';
import { buildTemplateLocationState, resolveContinueCreationTarget } from '../services/workspaceSeeds';

const filters = ['全部', '原图', '结果图', '视频', '收藏'] as const;

function inferMockAssetMeta(source: string) {
  if (source.includes('图案提取')) {
    return { pathHint: '/design/pattern-extract', abilityKey: 'yinhua_tiqu' };
  }
  if (source.includes('四方连续')) {
    return { pathHint: '/design/seamless', abilityKey: 'sifang_lianxu' };
  }
  if (source.includes('图生视频')) {
    return { pathHint: '/shoot/image-to-video', abilityKey: 'seedance_1_5_pro' };
  }
  if (source.includes('扩图')) {
    return { pathHint: '/toolbox/outpaint', abilityKey: 'huawen_kuotu' };
  }
  return { pathHint: '/design/style-to-style', abilityKey: undefined };
}

function mapMockAssets() {
  return demoRecentAssets.concat(demoRecentAssets).map((asset, index) => ({
    id: `${asset.id}-${index}`,
    title: asset.title,
    source: asset.source,
    createdAt: asset.createdAt,
    image: asset.image,
    type: asset.type,
    tags: asset.tags,
    origin: 'result' as const,
    ...inferMockAssetMeta(asset.source),
  }));
}

export default function AssetsPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [activeFilter, setActiveFilter] = useState<(typeof filters)[number]>('全部');
  const assets = useClientAssets();
  const sourceAssets = useMemo(() => (isAuthenticated ? assets : mapMockAssets()), [assets, isAuthenticated]);

  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'assets' });
  }, []);

  const displayAssets = useMemo(() => {
    return sourceAssets.filter((asset) => {
      if (activeFilter === '全部') return true;
      if (activeFilter === '视频') return asset.type === 'video';
      if (activeFilter === '原图') return asset.origin === 'upload';
      if (activeFilter === '结果图') return asset.type === 'image' && asset.origin === 'result';
      if (activeFilter === '收藏') return asset.tags.includes('已收藏');
      return true;
    });
  }, [activeFilter, sourceAssets]);
  const assetStats = useMemo(
    () => [
      { label: '全部素材', value: sourceAssets.length, filter: '全部' as const },
      { label: '原图', value: sourceAssets.filter((asset) => asset.origin === 'upload').length, filter: '原图' as const },
      { label: '结果图', value: sourceAssets.filter((asset) => asset.type === 'image' && asset.origin === 'result').length, filter: '结果图' as const },
      { label: '视频', value: sourceAssets.filter((asset) => asset.type === 'video').length, filter: '视频' as const },
    ],
    [sourceAssets],
  );

  function handleContinueAsset(asset: { image: string; title: string; source?: string; type?: 'image' | 'video'; tags?: string[]; pathHint?: string; origin?: 'upload' | 'result'; abilityKey?: string }) {
    const target = resolveContinueCreationTarget(asset);
    trackClientEvent('asset_continue_click', { source: 'assets', title: asset.title, path: target.path });
    navigate(target.path, { state: target.state });
  }

  return (
    <div className="client-page">
      <section className="client-section client-section--narrow">
        <div className="client-section__heading">
          <div>
            <p className="client-eyebrow">资产与模板中心</p>
            <h1>把原图、结果图、视频和模板放进同一个可复用中心。</h1>
            <p>
              {isAuthenticated
                ? '这里现在只展示真实上传和真实生成结果，不再混入演示素材。先把筛选、下载、继续创作和模板复跑做稳。'
                : 'Phase 1 先把高频资产操作做稳：筛选、下载、回工作区继续创作、直接带模板复跑。'}
            </p>
          </div>
          <button className="client-soft-button" type="button" onClick={() => navigate('/studio')}>
            回工作室
          </button>
        </div>
        <div className="client-assets-intro-grid">
          <article className="client-assets-intro-card">
            <span>资产沉淀</span>
            <strong>{displayAssets.length}</strong>
            <p>不再把结果散落在聊天记录和下载目录里，而是直接变成下一次创作的起点。</p>
          </article>
          <article className="client-assets-intro-card">
            <span>模板入口</span>
            <strong>{templateLibrary.length}</strong>
            <p>每个高频工作流都要有模板可复跑，避免用户每次面对空白输入框。</p>
          </article>
          <article className="client-assets-intro-card">
            <span>持续使用</span>
            <strong>继续创作</strong>
            <p>素材中心不是仓库，而是继续做设计、商拍和交付处理的跳板。</p>
          </article>
        </div>
        <div className="client-ops-summary">
          {assetStats.map((item) => (
            <button
              key={item.label}
              className={`client-ops-summary__card${activeFilter === item.filter ? ' is-active' : ''}`}
              type="button"
              onClick={() => setActiveFilter(item.filter)}
            >
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </button>
          ))}
        </div>
        <div className="client-task-toolbar">
          <div className="client-tab-strip">
            {filters.map((tab) => (
              <button
                key={tab}
                className={`client-tab-strip__item${activeFilter === tab ? ' is-active' : ''}`}
                type="button"
                onClick={() => setActiveFilter(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
        <div className="client-list-toolbar-note">
          <span>操作提示</span>
          <strong>
            {isAuthenticated
              ? assets.length
                ? '上传和生成结果都会自动进入素材库，先筛类型，再决定下载还是继续创作。'
                : '当前还没有真实素材，先去工作台上传原图或生成结果，素材库会自动开始积累。'
              : '先按素材类型筛选，再决定下载、继续创作或整理收藏。'}
          </strong>
        </div>
        <div className="client-assets-masonry">
          {displayAssets.map((asset) => (
            <article key={asset.id} className="client-library-card">
              <div className="client-library-card__media" style={{ backgroundImage: `url(${asset.image})` }}>
                <span className="client-media-badge">{asset.origin === 'upload' ? '原图' : asset.type === 'video' ? '视频' : '结果图'}</span>
              </div>
              <div className="client-library-card__body">
                <div>
                  <div className="client-library-card__meta">
                    <span>{asset.source}</span>
                    <span>{asset.createdAt}</span>
                  </div>
                  <strong>{asset.title}</strong>
                  <p>{asset.origin === 'upload' ? '原始素材，可直接继续加工。' : asset.type === 'video' ? '生成结果已沉淀，可继续用于内容延展。' : '结果素材已沉淀，可回工作区继续创作。'}</p>
                </div>
                <div className="client-library-card__tags">
                  {asset.tags.map((tag) => <span key={tag}>{tag}</span>)}
                </div>
                <div className="client-library-card__actions">
                  <a className="client-soft-button" href={asset.image} target="_blank" rel="noreferrer">
                    <DownloadIcon size="16" /> 下载
                  </a>
                  <button
                    className="client-soft-button"
                    type="button"
                    onClick={() =>
                      handleContinueAsset({
                        image: asset.image,
                        title: asset.title,
                        source: asset.source,
                        type: asset.type,
                        tags: asset.tags,
                        pathHint: asset.pathHint,
                        origin: asset.origin,
                        abilityKey: 'abilityKey' in asset ? asset.abilityKey : undefined,
                      })
                    }
                  >
                    <PlayCircleIcon size="16" /> 继续
                  </button>
                  <button
                    className="client-icon-button"
                    type="button"
                    aria-label="移除素材"
                    onClick={() => removeClientAsset(asset.id)}
                  >
                    <StarIcon size="16" />
                  </button>
                </div>
              </div>
            </article>
          ))}
          {!displayAssets.length ? (
            <div className="client-empty-panel">
              <strong>当前筛选下还没有素材</strong>
              <p>可以切换素材类型，或者先去工作台发起新的设计、商拍或处理任务。</p>
              <div className="client-empty-panel__actions">
                <button className="client-primary-button" type="button" onClick={() => navigate('/design/text-to-style')}>
                  先生成一个结果
                </button>
                <button className="client-soft-button" type="button" onClick={() => navigate('/studio')}>
                  回工作室
                </button>
              </div>
            </div>
          ) : null}
        </div>
        <div className="client-asset-template-section">
          <div className="client-list-toolbar-note">
            <span>模板推荐</span>
            <strong>如果你不知道下一步做什么，直接从高频模板进入，先把可复跑路径建起来。</strong>
          </div>
          <div className="client-asset-template-grid">
            {templateLibrary.map((template) => (
              <article key={template.id} className="client-asset-template-card">
                <span>{template.category.toUpperCase()}</span>
                <strong>{template.title}</strong>
                <p>{template.summary}</p>
                <button
                  className="client-soft-button"
                  type="button"
                  onClick={() => {
                    trackClientEvent('template_start_click', { source: 'assets', templateId: template.id, path: template.path });
                    navigate(template.path, { state: buildTemplateLocationState(template) });
                  }}
                >
                  带模板进入
                </button>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
