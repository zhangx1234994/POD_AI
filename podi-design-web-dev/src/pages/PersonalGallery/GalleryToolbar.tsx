import { useEffect, useState } from 'react';
import { usePlatform } from '@/hooks/usePlatform';
import { getSourceOptions } from '@/utils/sourceOptions';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Search, Grid3x3, List, Funnel, X } from 'lucide-react';
import { renderActionIcon } from '@/utils/taskUtils';
import type { SidebarMenuItem } from '@/types/sidebar';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { mapActionToChinese } from '@/utils/taskUtils';

export function GalleryToolbar({
  activeTab,
  searchQuery,
  onSearchChange,
  filterTags,
  onFilterTagsChange,
  filterSourceType,
  onFilterSourceTypeChange,
  sortBy,
  onSortByChange,
  onEnterSelectionMode,
  totalCount,
  uploadedCount,
  generatedCount,
  sendCount,
  viewMode,
  onViewModeChange,
  selectionMode,
  actionFilter,
  onActionFilterChange,
  aiTools,
}: {
  activeTab: string;
  searchQuery: string;
  onSearchChange: (v: string) => void;
  filterTags: string;
  onFilterTagsChange: (v: string) => void;
  filterSourceType: string;
  onFilterSourceTypeChange: (v: string) => void;
  sortBy: string;
  onSortByChange: (v: string) => void;
  onEnterSelectionMode: () => void;
  totalCount: number;
  uploadedCount: number;
  generatedCount: number;
  sendCount?: number;
  viewMode: 'grid' | 'list';
  onViewModeChange: (v: 'grid' | 'list') => void;
  selectionMode: boolean;
  actionFilter?: string;
  onActionFilterChange?: (v: string) => void;
  aiTools?: SidebarMenuItem[];
}) {
  const [localTags, setLocalTags] = useState<string>(filterTags || '');

  // 使用 hook 获取 isEmbedded
  const { isEmbedded } = usePlatform();

  // 本地输入值与父组件的 filterTags 保持同步
  useEffect(() => {
    setLocalTags(filterTags || '');
  }, [filterTags]);

  // 防抖：延迟将标签变更发送给父组件
  useEffect(() => {
    const id = window.setTimeout(() => {
      if (onFilterTagsChange && localTags !== (filterTags || '')) onFilterTagsChange(localTags || '');
    }, 300);
    return () => window.clearTimeout(id);
  }, [localTags, onFilterTagsChange, filterTags]);

  // 使用共享方法构建来源选项
  const sourceOptions = getSourceOptions(isEmbedded);

  /**
   * 格式化顶部统计文本（包含本地上传、工具生成、以及可选的第三方平台数量）
   * 说明：将原先的内联自执行函数抽离为命名函数，便于测试与维护。
   */
  const formatCounts = () => {
    // 判断是否展示第三方平台数据：基于 hook 的 isEmbedded
    const showSend = isEmbedded;

    // 如果父组件传入了 sendCount 则优先使用，否则使用回退计算
    const actualSendCount = typeof sendCount !== 'undefined'
      ? sendCount
      : Math.max(0, totalCount - uploadedCount - generatedCount);

    // 基础文本（本地上传 + 工具生成）
    const base = `包含本地上传 ${uploadedCount} 张，工具生成 ${generatedCount} 张`;

    if (showSend) {
      return `${base}，第三方平台 ${actualSendCount} 张`;
    } else {
      return base;
    }
  };

  return (
    <div className="mb-4">
      <Tabs value={activeTab} onValueChange={() => {}}>
        <TabsList className="h-12 mb-3 px-2 rounded-md">
            <TabsTrigger value="all" className="h-8 rounded-md">全部图片 <Badge variant="secondary" className="ml-2 rounded-md">{totalCount}</Badge></TabsTrigger>
            {
              // determine whether to show third-party (SEND) info
            }
            <div className="px-4 text-sm text-muted-foreground">
              {formatCounts()}
            </div>
          </TabsList>
      </Tabs>
          
      <div className="flex flex-wrap items-center justify-between gap-3 md:flex-nowrap">
        <div className="relative max-w-[640px] w-full flex-1 min-w-[160px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-8 pr-10 w-full"
            placeholder="搜索图片名称..."
          />
          {searchQuery ? (
            <button
              type="button"
              aria-label="清除搜索"
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-md hover:bg-muted/20"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          ) : null}
        </div>

        {!selectionMode && (
          <Button variant="outline" size="sm" className="h-8" onClick={onEnterSelectionMode}>批量操作</Button>
        )}

        <Select value={actionFilter || 'all'} onValueChange={(v) => onActionFilterChange && onActionFilterChange(v)}>
          <SelectTrigger className="w-[160px] h-8">
            <div className="flex items-center gap-4">
              {(!actionFilter || actionFilter === 'all') ? (
                <>
                  <Funnel className="w-4 h-4 mr-2 text-muted-foreground" />
                  <SelectValue placeholder="全部类型" />
                </>
              ) : (
                <>
                  {renderActionIcon(actionFilter || '', 'w-4 h-4')}
                  <SelectValue placeholder={mapActionToChinese ? mapActionToChinese(actionFilter || '') : actionFilter} />
                </>
              )}
            </div>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部类型</SelectItem>
            {aiTools && aiTools.map((t) => (
              <SelectItem key={t.id} value={t.id}>{mapActionToChinese ? mapActionToChinese(t.id) : (t.label || t.id)}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={filterSourceType} onValueChange={onFilterSourceTypeChange}>
          <SelectTrigger className="w-36 h-8"><SelectValue placeholder="全部来源" /></SelectTrigger>
          <SelectContent>
            {sourceOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={onSortByChange}>
          <SelectTrigger className="w-36 h-8"><SelectValue placeholder="排序" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="date-desc">最新优先</SelectItem>
            <SelectItem value="date-asc">最旧优先</SelectItem>
            <SelectItem value="name-asc">名称 A-Z</SelectItem>
            <SelectItem value="name-desc">名称 Z-A</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">标签:</span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={localTags}
                onChange={(e) => setLocalTags(e.target.value)}
                className="w-38 pl-8 pr-10 file:text-foreground placeholder:text-muted-foreground dark:bg-input/30 border-input h-9 min-w-0 rounded-md border text-base bg-input-background"
                placeholder="标签模糊匹配"
              />
              {localTags ? (
                <button
                  type="button"
                  aria-label="清除标签"
                  onClick={() => {
                    setLocalTags('');
                    if (onFilterTagsChange) onFilterTagsChange('');
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-md hover:bg-muted/20"
                >
                  <X className="w-4 h-4 text-muted-foreground" />
                </button>
              ) : null}
          </div>
        </div>

        <div className="ml-2">
          <div className="flex border rounded-md overflow-hidden">
            <button
              onClick={() => onViewModeChange('grid')}
              className={`h-8 w-8 flex items-center justify-center ${viewMode === 'grid' ? 'bg-primary text-primary-foreground' : 'bg-transparent'}`}
              aria-label="grid"
            >
              <Grid3x3 className="w-4 h-4" />
            </button>
            <div className="w-px bg-border" />
            <button
              onClick={() => onViewModeChange('list')}
              className={`h-8 w-8 flex items-center justify-center ${viewMode === 'list' ? 'bg-primary text-primary-foreground' : 'bg-transparent'}`}
              aria-label="list"
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GalleryToolbar;
