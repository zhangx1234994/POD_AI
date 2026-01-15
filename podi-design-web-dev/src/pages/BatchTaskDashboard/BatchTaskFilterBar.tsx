import React from 'react';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Funnel, Search, CheckCircle, X } from 'lucide-react';
import { getStatusConfig, renderActionIcon } from '@/utils/taskUtils';
import type { SidebarMenuItem } from '@/types/sidebar';

interface BatchTaskFilterBarProps {
  typeSearch: string;
  setTypeSearch: (v: string) => void;
  actionFilter: string;
  setActionFilter: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  aiTools: SidebarMenuItem[];
  mapActionToChinese: (id: string) => string;
  resetFilters: () => void;
}

export const BatchTaskFilterBar: React.FC<BatchTaskFilterBarProps> = ({
  typeSearch,
  setTypeSearch,
  actionFilter,
  setActionFilter,
  statusFilter,
  setStatusFilter,
  aiTools,
  mapActionToChinese,
}) => {

  const renderStatusItem = (statusKey: string, label: string) => {
    return (
      <SelectItem value={statusKey} className="flex items-center gap-2">
        {label}
      </SelectItem>
    );
  };

  const renderStatusTrigger = (statusKey: string) => {
    if (!statusKey || statusKey === 'all') {
      return (
        <>
          <CheckCircle className="w-4 h-4 text-muted-foreground" />
          <SelectValue placeholder="全部状态" />
        </>
      );
    }

    const cfg = getStatusConfig(statusKey);
    const Icon = cfg.icon as any;
    const textColor = (cfg.color || '').split(' ').find((c: string) => c.startsWith('text-')) || '';
    return (
      <>
        <Icon className={`${textColor} w-4 h-4`} />
        <SelectValue placeholder={`${cfg.label}`} />
      </>
    );
  };

  const renderActionItem = (actionKey: string, label: string) => {
    return (
      <SelectItem value={actionKey} className="flex items-center gap-2">
        {label}
      </SelectItem>
    );
  };

  const renderActionTrigger = (actionKey: string) => {
    if (!actionKey || actionKey === 'all') {
      return (
        <>
          <Funnel className="w-4 h-4 mr-2 text-muted-foreground" />
          <SelectValue placeholder="任务类型" />
        </>
      );
    }

    const label = mapActionToChinese(actionKey) || '任务类型';
    const iconEl = renderActionIcon(actionKey, 'w-4 h-4');
    return (
      <>
        {iconEl}
        <SelectValue placeholder={label} />
      </>
    );
  };
  
  return (
    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
      <div className="w-full border rounded-md p-4 flex items-center gap-2 bg-white dark:bg-input/30 dark:text-card-foreground">
        <div className="flex-1">
          <div className="relative w-full dark:bg-input/30">
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground dark:text-white">
              <Search className="h-4 w-4" />
            </div>
            <input
              className="pl-8 pr-10 h-9 w-full rounded-md bg-input-background dark:bg-input/30 text-sm dark:text-white placeholder:text-muted-foreground"
              placeholder="搜索原图名称..."
              value={typeSearch}
              onChange={(e) => setTypeSearch(e.target.value)}
            />

            {typeSearch.trim() !== '' && (
              <button
                type="button"
                aria-label="清除搜索"
                onClick={() => setTypeSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-slate-100 dark:hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Select value={actionFilter} onValueChange={(v) => setActionFilter(v)}>
            <SelectTrigger className="w-[160px] h-9 bg-input-background">
              <div className="flex items-center gap-4">
                {renderActionTrigger(actionFilter)}
              </div>
            </SelectTrigger>
            <SelectContent>
              {renderActionItem('all', '全部类型')}
              {aiTools.map((t) => (
                <React.Fragment key={t.id}>{renderActionItem(t.id, mapActionToChinese(t.id))}</React.Fragment>
              ))}
            </SelectContent>
          </Select>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[140px] h-9 bg-input-background">
                <div className="flex items-center gap-4">
                  {renderStatusTrigger(statusFilter)}
                </div>
              </SelectTrigger>
              <SelectContent>
                {renderStatusItem('all', '全部状态')}
                {renderStatusItem('COMPLETED', '已完成')}
                {renderStatusItem('RUNNING', '处理中')}
                {renderStatusItem('PENDING', '等待中')}
              </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
};

export default BatchTaskFilterBar;
