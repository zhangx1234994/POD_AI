import { Dialog } from 'tdesign-react';
import { DownloadIcon, HistoryIcon } from 'tdesign-icons-react';
import { Link } from 'react-router-dom';
import { getToolPresentation } from '../../config/toolPresentation';
import type { ToolItem } from '../../types';
import type { AbilityInfo } from '../../types/api';
import type { ResultState } from '../../types/workspace';
import type { ShellMode } from '../../types/workspace';
import { getAbilityExpectedOutput, getAbilityPresentationName } from '../../utils/abilityPresentation';

type RecentCandidate = {
  id?: string;
  image: string;
  title: string;
};

export default function WorkspaceResultPanel({
  tool,
  mode,
  ability,
  result,
  resultTitle,
  recentCandidates,
  onApplyCandidate,
  onOpenAssets,
  onOpenTasks,
  rechargeVisible,
  balance,
  estimatedPoints,
  onCloseRecharge,
  onGoRecharge,
}: {
  tool: ToolItem;
  mode: ShellMode;
  ability: AbilityInfo | null;
  result: ResultState;
  resultTitle: string;
  recentCandidates: RecentCandidate[];
  onApplyCandidate: (asset: RecentCandidate) => void;
  onOpenAssets: () => void;
  onOpenTasks: () => void;
  rechargeVisible: boolean;
  balance: number | null;
  estimatedPoints: number | null;
  onCloseRecharge: () => void;
  onGoRecharge: () => void;
}) {
  const presentation = getToolPresentation(tool.key, mode);
  const displayTitle = getAbilityPresentationName(ability) || tool.title;
  const expectedOutput = getAbilityExpectedOutput(ability);
  const modeCopy =
    mode === 'design'
      ? {
          eyebrow: '效果参考',
          title: '结果预览与下一步设计动作',
          spotlight: '先看方向感，再判断要不要继续往下做。',
        }
      : mode === 'shoot'
        ? {
            eyebrow: '出图参考',
            title: '结果预览与下一步出图动作',
            spotlight: '先看当前画面能不能打，再决定要不要补细节图和套图。',
          }
        : {
            eyebrow: '处理参考',
            title: '结果预览与下一步处理动作',
            spotlight: '先判断这一步是否到位，再继续做尺寸和清晰度收口。',
          };
  const followupLinks = presentation.followups || [];
  const hasResult = Boolean(result.mediaUrl || result.text || result.status === 'success');
  const shouldOpenTasks = Boolean(result.taskId && !hasResult);
  const statusCards = [
    {
      label: '当前阶段',
      value: result.status === 'idle' ? '等待提交' : resultTitle,
    },
    {
      label: '当前产出',
      value: result.mediaUrl ? '已生成图片' : result.text ? '已生成文本' : '还未开始',
    },
    {
      label: '下一步',
      value: result.mediaUrl ? '继续加工或沉淀素材' : '先看示例再提交',
    },
  ];
  const caseViews = presentation.caseViews || [];
  const headerActionLabel = hasResult ? '资产中心' : result.taskId ? '任务中心' : null;

  return (
    <section className="client-panel client-panel--results">
      <div className="client-panel__header client-panel__header--compact">
        <div>
          <p className="client-eyebrow">{modeCopy.eyebrow}</p>
          <h3>{modeCopy.title}</h3>
        </div>
        {headerActionLabel ? (
          <button className="client-soft-button" type="button" onClick={shouldOpenTasks ? onOpenTasks : onOpenAssets}>
            <HistoryIcon size="16" />
            {headerActionLabel}
          </button>
        ) : null}
      </div>

      <div className="client-result-spotlight">
        <div className="client-result-spotlight__copy">
          <span>这一步会得到什么</span>
          <strong>{result.mediaUrl ? `${displayTitle} 已经有结果，可以继续往下走。` : modeCopy.spotlight}</strong>
          <p>{result.mediaUrl ? '拿到结果后，可以继续加工、沉淀素材，或者转到下一步工作流。' : expectedOutput || '这里先帮你建立对结果的预期，提交后当前结果会优先回到这里。'}</p>
        </div>
        <div className="client-result-spotlight__stats">
          {statusCards.map((item) => (
            <div key={item.label} className="client-result-spotlight__stat">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="client-result-card">
        {result.mediaUrl ? (
          <div className="client-result-card__media" style={{ backgroundImage: `url(${result.mediaUrl})` }} />
        ) : (
          <div className="client-result-card__media client-result-card__media--placeholder">
            <div className="client-result-card__placeholder-copy">
              <span>结果区</span>
              <strong>提交后，这里会优先显示这一步的结果。</strong>
              <p>如果任务时间较长，也可以稍后从任务中心回来继续看。</p>
            </div>
          </div>
        )}
        <div className="client-result-card__body">
          <div>
            <p className="client-eyebrow">当前产出</p>
            <h3>{resultTitle}</h3>
          </div>
          <p>{result.message || '拿到结果后，可以先判断是否达到预期，再决定是继续加工、沉淀到素材库，还是回到上一步重做。'}</p>
          {['queued', 'running'].includes(result.status) ? (
            <div className="client-callout client-callout--warm">
              这一步还在处理中。你可以先去别的页面继续操作，稍后再回来查看结果。
            </div>
          ) : null}
          {result.text ? <pre className="client-result-card__text">{result.text}</pre> : null}
          {result.mediaUrl || result.taskId ? (
            <div className="client-result-card__actions">
              {result.mediaUrl ? (
                <a className="client-soft-button" href={result.mediaUrl} target="_blank" rel="noreferrer">
                  <DownloadIcon size="16" /> 下载
                </a>
              ) : null}
              {result.taskId ? (
                <Link className="client-soft-button" to="/tasks">
                  <HistoryIcon size="16" /> 查看任务进度
                </Link>
              ) : null}
              {hasResult ? (
                <button className="client-soft-button" type="button" onClick={onOpenAssets}>
                  去素材库继续用
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {recentCandidates.length ? (
        <div className="client-example-grid">
          {recentCandidates.map((asset, index) => (
            <button key={`${asset.id || asset.title}-${index}`} className="client-example-card" type="button" onClick={() => onApplyCandidate(asset)}>
              <div
                className={`client-example-card__media client-accent--${['sky', 'amber', 'emerald', 'rose'][index % 4]}`}
                style={{ backgroundImage: `url(${asset.image})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
              >
                <span className="client-example-card__badge">{caseViews[index]?.badge || '案例'}</span>
              </div>
              <div className="client-example-card__body">
                <strong>{caseViews[index]?.title || asset.title}</strong>
                <span>{caseViews[index]?.note || '点击带入最近素材'}</span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="client-inline-note">最近结果还没有沉淀到这里，先完成一次真实提交，右侧会自动开始累积可复用素材。</div>
      )}

      {hasResult ? (
        <div className="client-followup-grid">
          {followupLinks.map((item) => (
            <Link key={item.path} className="client-followup-card" to={item.path}>
              <span>继续往下做</span>
              <strong>{item.label}</strong>
              <p>{item.note}</p>
            </Link>
          ))}
        </div>
      ) : (
        <div className="client-inline-note">先把当前这一步跑通。拿到结果后，下一步工作流会在这里明确给出，不需要现在分心判断。</div>
      )}

      <Dialog visible={rechargeVisible} header="当前积分不足" confirmBtn="去充值" cancelBtn="稍后再说" onClose={onCloseRecharge} onConfirm={onGoRecharge}>
        <div className="client-dialog-stack">
          <p>当前积分不足，先补足余额后再回来继续这一步，已有表单和素材会保留。</p>
          <div className="client-dialog-metric">
            <span>当前余额</span>
            <strong>{typeof balance === 'number' ? balance.toLocaleString() : '--'} 点</strong>
          </div>
          <div className="client-dialog-metric">
            <span>本次预计消耗</span>
            <strong>{typeof estimatedPoints === 'number' ? estimatedPoints.toLocaleString() : '--'} 点</strong>
          </div>
          <div className="client-dialog-metric">
            <span>处理方式</span>
            <strong>去充值后返回当前页面，表单和上传素材会自动保留</strong>
          </div>
        </div>
      </Dialog>
    </section>
  );
}
