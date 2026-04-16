import { Link } from 'react-router-dom';

interface WorkspaceSidebarProps {
  tool?: { key?: string } | string;
  mode?: string;
}

export default function WorkspaceSidebar({ tool, mode }: WorkspaceSidebarProps) {
  const activeTool = typeof tool === 'string' ? tool : tool?.key;
  const tools = [
    { id: 'text-to-design', name: '灵感款式', tag: '研发设计', href: '/design/text-to-design' },
    { id: 'sketch-to-design', name: '草图款式', tag: '研发设计', href: '/design/sketch-to-design' },
    { id: 'flat-to-model', name: '模特图生成', tag: '视觉商拍', href: '/shoot/flat-to-model' },
    { id: 'product-to-video', name: '营销视频', tag: '视觉商拍', href: '/shoot/product-to-video' },
    { id: 'fabric-replace', name: '面料替换', tag: '智能工具', href: '/toolbox/fabric-replace' },
    { id: 'seamless-pattern', name: '四方连续', tag: '智能工具', href: '/toolbox/seamless-pattern' },
  ];

  return (
    <aside className="client-sidebar">
      <div className="client-sidebar__header">
        <h2>工具选择</h2>
        <p className="client-sidebar__summary">选择您要使用的 AI 工具</p>
      </div>

      <div className="client-sidebar__items">
        {tools.map((t) => (
          <Link
            key={t.id}
            to={t.href}
            className={`client-sidebar__item${activeTool === t.id ? ' is-active' : ''}`}
          >
            <div>
              <div className="client-sidebar__item-title">{t.name}</div>
              <div className="client-sidebar__item-subtitle">{t.tag}</div>
            </div>
            <span className="client-sidebar__item-arrow">→</span>
          </Link>
        ))}
      </div>
    </aside>
  );
}
