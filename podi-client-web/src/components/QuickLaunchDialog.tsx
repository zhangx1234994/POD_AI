import { useEffect, useMemo, useState } from 'react';
import { SearchIcon } from 'tdesign-icons-react';
import { Dialog, Input } from 'tdesign-react';
import { Link } from 'react-router-dom';
import { designTools, navItems, shootTools, shortcuts, studioAgents, toolboxTools } from '../config/clientCatalog';

type QuickItem = {
  id: string;
  title: string;
  subtitle: string;
  path: string;
  group: string;
};

function buildItems(): QuickItem[] {
  return [
    ...navItems.map((item) => ({
      id: `nav-${item.key}`,
      title: item.label,
      subtitle: '顶部主导航入口',
      path: item.path,
      group: '导航',
    })),
    ...shortcuts.map((item) => ({
      id: `shortcut-${item.key}`,
      title: item.title,
      subtitle: item.subtitle,
      path: item.path,
      group: '快捷动作',
    })),
    ...studioAgents
      .filter((item) => item.path)
      .map((item) => ({
        id: `agent-${item.id}`,
        title: item.title,
        subtitle: item.subtitle,
        path: item.path || '/home',
        group: '智能体',
      })),
    ...designTools.slice(0, 6).map((item) => ({
      id: `design-${item.key}`,
      title: item.title,
      subtitle: item.description,
      path: item.path,
      group: '研发设计',
    })),
    ...shootTools.slice(0, 6).map((item) => ({
      id: `shoot-${item.key}`,
      title: item.title,
      subtitle: item.description,
      path: item.path,
      group: '视觉商拍',
    })),
    ...toolboxTools.slice(0, 6).map((item) => ({
      id: `toolbox-${item.key}`,
      title: item.title,
      subtitle: item.description,
      path: item.path,
      group: '工具箱',
    })),
  ];
}

export default function QuickLaunchDialog({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const [keyword, setKeyword] = useState('');
  const items = useMemo(buildItems, []);

  useEffect(() => {
    if (!visible) {
      setKeyword('');
      return;
    }
    const timer = window.setTimeout(() => {
      const input = document.querySelector('.client-quick-launch input') as HTMLInputElement | null;
      input?.focus();
    }, 30);
    return () => window.clearTimeout(timer);
  }, [visible]);

  const filtered = useMemo(() => {
    const query = keyword.trim().toLowerCase();
    if (!query) return items;
    return items.filter((item) =>
      [item.title, item.subtitle, item.group].some((field) => field.toLowerCase().includes(query)),
    );
  }, [items, keyword]);

  return (
    <Dialog
      destroyOnClose
      visible={visible}
      width={880}
      header="快捷入口"
      confirmBtn={null}
      cancelBtn={false}
      onClose={onClose}
    >
      <div className="client-quick-launch">
        <div className="client-quick-launch__input">
          <Input
            prefixIcon={<SearchIcon />}
            value={keyword}
            onChange={(value) => setKeyword(String(value))}
            placeholder="搜索页面、功能、智能体，例如：图案提取 / 套图 / 钱包"
          />
        </div>
        <div className="client-quick-launch__grid">
          {filtered.map((item) => (
            <Link key={item.id} className="client-quick-launch__card" to={item.path} onClick={onClose}>
              <span>{item.group}</span>
              <strong>{item.title}</strong>
              <p>{item.subtitle}</p>
            </Link>
          ))}
        </div>
      </div>
    </Dialog>
  );
}
