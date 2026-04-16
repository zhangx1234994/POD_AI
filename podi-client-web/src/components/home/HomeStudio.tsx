import { studioCreateBoardCard, studioRibbon, studioShowcaseFallbacks, studioWorkbenchPrompt, studioWorkbenchSuggestions } from '../../config/clientContent';
import type { StudioAgent, WhiteboardProject } from '../../types';

export default function HomeStudio({
  agents,
  boards,
  onOpenWorkbench,
  onOpenAgent,
  onOpenSuggestion,
  onOpenBoard,
  onCreateBoard,
}: {
  agents: StudioAgent[];
  boards: WhiteboardProject[];
  onOpenWorkbench: () => void;
  onOpenAgent: (agentId: string) => void;
  onOpenSuggestion: (suggestionKey: string) => void;
  onOpenBoard: (boardId: string) => void;
  onCreateBoard: () => void;
}) {
  const studioShowcase = [
    {
      ...studioShowcaseFallbacks[0],
      title: agents[0]?.title || studioShowcaseFallbacks[0].title,
      image: agents[0]?.image || boards[0]?.image || studioShowcaseFallbacks[0].image,
    },
    {
      ...studioShowcaseFallbacks[1],
      label: boards[0]?.tag || studioShowcaseFallbacks[1].label,
      title: boards[0]?.title || studioShowcaseFallbacks[1].title,
      image: boards[0]?.image || agents[1]?.image || studioShowcaseFallbacks[1].image,
    },
    {
      ...studioShowcaseFallbacks[2],
      label: boards[1]?.tag || studioShowcaseFallbacks[2].label,
      title: boards[1]?.title || studioShowcaseFallbacks[2].title,
      image: boards[1]?.image || agents[3]?.image || studioShowcaseFallbacks[2].image,
    },
  ];

  return (
    <>
      <section className="client-section">
        <div className="client-section__heading">
          <div>
            <p className="client-eyebrow">智能体工作台</p>
            <h2>把入口做成工作室，而不是做成功能说明书。</h2>
          </div>
        </div>
        <div className="client-studio-ribbon">
          {studioRibbon.map((item) => (
            <div key={item.label} className="client-studio-ribbon__item">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
        <div className="client-studio-showcase">
          {studioShowcase.map((item) => (
            <article key={item.id} className="client-studio-showcase__card">
              <div className="client-studio-showcase__media" style={item.image ? { backgroundImage: `url(${item.image})` } : undefined} />
              <div className="client-studio-showcase__body">
                <span>{item.label}</span>
                <strong>{item.title}</strong>
                <p>{item.subtitle}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="client-agent-shell">
          <div className="client-agent-shell__prompt">
            <div className="client-agent-shell__prompt-title">
              <span>工作室输入框</span>
              <strong>今天要先做设计方向，还是先做商拍素材？</strong>
            </div>
            <div className="client-agent-shell__composer">
              <textarea
                readOnly
                value={studioWorkbenchPrompt}
              />
              <div className="client-agent-shell__suggestions">
                {studioWorkbenchSuggestions.map((item) => (
                  <button key={item.key} className="client-soft-button" type="button" onClick={() => onOpenSuggestion(item.key)}>
                    {item.label}
                  </button>
                ))}
              </div>
              <button className="client-primary-button" type="button" onClick={onOpenWorkbench}>
                进入工作台
              </button>
            </div>
          </div>
          <div className="client-agent-grid">
            {agents.map((agent) => (
              <button
                key={agent.id}
                className={`client-agent-card client-accent--${agent.accent}`}
                type="button"
                onClick={() => onOpenAgent(agent.id)}
              >
                {agent.image ? (
                  <div className="client-agent-card__media" style={{ backgroundImage: `url(${agent.image})` }} />
                ) : null}
                <div className="client-agent-card__badge">智能体</div>
                <strong>{agent.title}</strong>
                <p>{agent.subtitle}</p>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="client-section">
        <div className="client-section__heading">
          <div>
            <p className="client-eyebrow">白板与项目</p>
            <h2>让工作室首页不只是入口，也像一个能回来的创作面板。</h2>
          </div>
        </div>
        <div className="client-whiteboard-grid">
          {boards.map((board) => (
            <article key={board.id} className="client-whiteboard-card">
              {board.image ? (
                <div className="client-whiteboard-card__media" style={{ backgroundImage: `url(${board.image})` }} />
              ) : null}
              <div className="client-whiteboard-card__top">
                <span>{board.tag}</span>
                <button className="client-soft-button" type="button" onClick={() => onOpenBoard(board.id)}>
                  继续编辑
                </button>
              </div>
              <strong>{board.title}</strong>
              <p>{board.summary}</p>
              <div className="client-whiteboard-card__meta">
                <div>
                  <span>阶段</span>
                  <strong>{board.tag === '研发设计' ? '提取 / 连续 / 放大' : '主图 / 套图 / 视频'}</strong>
                </div>
                <div>
                  <span>最近动作</span>
                  <strong>{board.tag === '研发设计' ? '今天 10:22' : '昨天 18:30'}</strong>
                </div>
              </div>
            </article>
          ))}
          <article className="client-whiteboard-card client-whiteboard-card--create">
            <div
              className="client-whiteboard-card__media"
              style={{ backgroundImage: `url(${studioCreateBoardCard.image})` }}
            />
            <div className="client-whiteboard-card__top">
              <span>{studioCreateBoardCard.label}</span>
            </div>
            <strong>{studioCreateBoardCard.title}</strong>
            <p>{studioCreateBoardCard.summary}</p>
            <button className="client-primary-button" type="button" onClick={onCreateBoard}>
              新建画布
            </button>
          </article>
        </div>
      </section>
    </>
  );
}
