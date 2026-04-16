import { NavLink } from 'react-router-dom';
import type { ToolItem } from '../types';

export default function ModuleSidebar({
  title,
  subtitle,
  items,
  itemTitles,
}: {
  title: string;
  subtitle: string;
  items: ToolItem[];
  itemTitles?: Record<string, string>;
}) {
  const groups = items.reduce<Record<string, ToolItem[]>>((acc, item) => {
    const key = item.group || '默认分组';
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <aside className="client-sidebar">
      <div className="client-sidebar__header">
        <p className="client-eyebrow">{subtitle}</p>
        <h2>{title}</h2>
        <p className="client-sidebar__summary">选择动作后直接进入工作区。</p>
      </div>
      <div className="client-sidebar__items">
        {Object.entries(groups).map(([groupName, groupItems]) => (
          <div key={groupName} className="client-sidebar__group">
            <div className="client-sidebar__group-label">{groupName}</div>
            <div className="client-sidebar__group-items">
              {groupItems.map((item) => (
                <NavLink
                  key={item.key}
                  to={item.path}
                  className={({ isActive }) => `client-sidebar__item client-accent--${item.accent}${isActive ? ' is-active' : ''}`}
                >
                  <div>
                    <div className="client-sidebar__item-title">{itemTitles?.[item.key] || item.title}</div>
                    <div className="client-sidebar__item-subtitle">{item.subtitle}</div>
                  </div>
                  <span className="client-sidebar__item-arrow">→</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
