import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { toolRuntimeConfig } from '../config/toolConfigs';
import { getToolPresentation } from '../config/toolPresentation';
import { useAbilityPresentationMap } from '../hooks/useAbilityPresentationMap';
import ModuleSidebar from './ModuleSidebar';
import WorkspaceShell from './WorkspaceShell';
import type { ToolItem } from '../types';
import type { ShellMode } from '../types/workspace';

const modeCopy: Record<ShellMode, { eyebrow: string; title: string; description: string }> = {
  design: {
    eyebrow: 'Creative Design',
    title: '围绕单个设计动作直接开始',
    description: '先选动作，再输入，再看结果。',
  },
  shoot: {
    eyebrow: 'Visual Shoot',
    title: '把营销素材生产放进稳定工作区',
    description: '先选场景，再输入，再出图。',
  },
  toolbox: {
    eyebrow: 'AI Toolbox',
    title: '把处理动作变成随时可插入的一步',
    description: '先选处理方式，再提交当前素材。',
  },
};

export default function ModuleWorkspacePage({
  title,
  subtitle,
  items,
  mode,
}: {
  title: string;
  subtitle: string;
  items: ToolItem[];
  mode: ShellMode;
}) {
  const { tool } = useParams();
  const presentationNameMap = useAbilityPresentationMap();
  const current = useMemo(() => items.find((item) => item.key === tool) || items[0], [items, tool]);
  const runtime = toolRuntimeConfig[current.path.replace(/^\//, '')];
  const presentation = getToolPresentation(current.key, mode);
  const copy = modeCopy[mode];
  const itemTitles = useMemo(() => {
    const entries = items.map((item) => {
      const abilityKey = toolRuntimeConfig[item.path.replace(/^\//, '')]?.abilityKey;
      return [item.key, (abilityKey && presentationNameMap.get(abilityKey)) || item.title] as const;
    });
    return Object.fromEntries(entries);
  }, [items, presentationNameMap]);
  const currentTitle = itemTitles[current.key] || current.title;
  const processTitle = runtime?.requiresImage
    ? `先上传${runtime.imageSlots && runtime.imageSlots > 1 ? `${runtime.imageSlots} 张参考图` : '参考图'}，再填写说明并提交。`
    : '先填写目标与参数，再提交查看结果。';
  const hints = [
    runtime?.requiresImage ? `${runtime.imageSlots || 1} 张参考图` : '无需参考图',
    runtime?.invokeMode === 'task' ? '结果稍后回到当前页' : '提交后直接返回',
  ];

  return (
    <div className="client-page client-module-page">
      <div className="client-workspace-layout">
        <ModuleSidebar title={title} subtitle={subtitle} items={items} itemTitles={itemTitles} />
        <div className="client-workspace-layout__main">
          <section className="client-workspace-header">
            <div className="client-workspace-header__copy">
              <p className="client-eyebrow">{copy.eyebrow}</p>
              <h1>{currentTitle}</h1>
              <p>{presentation.heroNote || copy.description}</p>
            </div>
            <div className="client-workspace-header__meta">
              <span className="client-eyebrow">当前步骤</span>
              <strong>{processTitle}</strong>
              <div className="client-workspace-header__chips">
                {hints.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </div>
          </section>
          <WorkspaceShell tool={current} mode={mode} />
        </div>
      </div>
    </div>
  );
}
