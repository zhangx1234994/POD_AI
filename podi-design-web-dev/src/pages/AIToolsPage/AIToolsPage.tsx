import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AI_ACTIONS } from '@/constants/sidebar';
import type { SidebarMenuItem } from '@/types/sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Image as DefaultIcon, Search as SearchIcon, Sparkles, Zap, Scissors, Copy } from 'lucide-react';

type CategoryChip = { key: string; label: string; keywords?: string[]; icon?: any };

const categoryChips: CategoryChip[] = [
  { key: 'all', label: '全部工具', icon: Sparkles },
  { key: 'enhance', label: '图片增强', keywords: ['hires'], icon: Zap },
  { key: 'edit', label: '图片编辑', keywords: ['pattern-extract', 'extend'], icon: Scissors },
  { key: 'generate', label: '图片生成', keywords: ['fission', 'seamless', 'edit'], icon: Copy },
];

/**
 * Return tools to display for a given active tab and search query.
 * Extracted out of render for testability and clarity.
 */
export function getToolsForActiveTab(
  allTools: SidebarMenuItem[],
  chips: CategoryChip[],
  activeKey: string,
  searchQuery?: string
): SidebarMenuItem[] {
  const q = (searchQuery || '').trim().toLowerCase();
  const chip = chips.find((c) => c.key === activeKey) || chips[0];

  const base = allTools.filter((t) => {
    if (!q) return true;
    return t.label.toLowerCase().includes(q);
  });

  if (!chip || chip.key === 'all') return base;

  const keywords = chip.keywords || [];
  // If we have label-based base results, filter them by category keywords.
  let results = base.filter((t) =>
    keywords.some((kw) =>
      t.label.toLowerCase().includes(kw.toLowerCase()) ||
      (t.description || '').toLowerCase().includes(kw.toLowerCase()) ||
      t.id.toLowerCase().includes(kw.toLowerCase())
    )
  );

  if (q && results.length === 0) {
    const fallback = allTools.filter((t) =>
      (t.label.toLowerCase().includes(q) ||
        (t.description || '').toLowerCase().includes(q) ||
        t.id.toLowerCase().includes(q))
    );
    results = fallback.filter((t) =>
      keywords.some((kw) =>
        t.label.toLowerCase().includes(kw.toLowerCase()) ||
        (t.description || '').toLowerCase().includes(kw.toLowerCase()) ||
        t.id.toLowerCase().includes(kw.toLowerCase())
      )
    );
  }

  return results;
}

export function AIToolsPage() {
  const [search, setSearch] = useState('');
  const [active, setActive] = useState('all');

  const popularIds = ['hires', 'fission'];
  const toolsToShow = useMemo(() => getToolsForActiveTab(AI_ACTIONS as SidebarMenuItem[], categoryChips, active, search), [active, search]);

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">AI作图工具</h1>
          <p className="text-sm text-muted-foreground mt-1">{AI_ACTIONS?.length}个精选AI工具，打造POD业务利器</p>
        </div>
      </div>
      <div className="flex max-w-2xl mb-6">
        <div className="relative w-full">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground w-4 h-4" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索工具..."
            aria-label="搜索工具"
            className="w-full rounded-lg border border-slate-200 pl-10 pr-4 py-2 shadow-sm bg-white text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50 disabled:pointer-events-none"
          />
        </div>
      </div>

      <Tabs defaultValue={active} onValueChange={(v) => setActive(v)} className="mb-6">
        <TabsList>
          {categoryChips.map((c) => {
            const TabIcon = (c as any).icon as any;
            return (
              <TabsTrigger key={c.key} value={c.key} className="text-sm flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-slate-100 text-slate-700">
                  {TabIcon ? <TabIcon className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                </span>
                <span>{c.label}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>

      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {toolsToShow.map((tool) => {
          const Icon = tool.icon || DefaultIcon;
          const isHot = popularIds.includes(tool.id);
          return (
            <Card key={tool.id} className="bg-card text-card-foreground flex flex-col gap-6 rounded-xl border group cursor-pointer hover:shadow-lg transition-all hover:border-primary">
              <CardHeader className="px-6 pt-6 pb-4">
                <div className="w-full flex items-start justify-between">
                  <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center text-white group-hover:scale-110 transition-transform">
                    {Icon ? <Icon className="w-6 h-6" /> : <div className="w-4 h-4 bg-white rounded-sm" />}
                  </div>
                  {tool.badge && <span className="text-xs inline-flex items-center justify-center rounded-md border px-2 py-0.5 font-medium w-fit whitespace-nowrap shrink-0 bg-secondary text-secondary-foreground">{tool.badge}</span>}
                  {isHot && <span className="text-xs inline-flex items-center justify-center rounded-md border px-2 py-0.5 font-medium w-fit whitespace-nowrap shrink-0 bg-secondary text-secondary-foreground">热门</span>}
                </div>

                <div className="mt-3">
                  <CardTitle className="text-lg font-semibold mb-1">{tool.label}</CardTitle>
                  <p className="text-sm text-muted-foreground">{tool.description || ''}</p>
                </div>
              </CardHeader>

              <CardContent className="pb-6 px-6">
                <Link to={tool.path}>
                  <Button className="rounded-md text-sm font-medium disabled:pointer-events-none disabled:opacity-50 border bg-background text-foreground hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 h-9 px-4 py-2 w-full py-3 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">开始使用</Button>
                </Link>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

export default AIToolsPage;
