import React, { useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { LayoutGrid, Image as ImageIcon, ChevronRight } from 'lucide-react';
import { useTaskSummaryData } from '@/hooks/useTaskSummaryData';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { mapActionToChinese, getStatusConfig } from '@/utils/taskUtils';
import { getThumbnailUrl } from '@/utils/imageUtils';
import { TASK_CENTER_PREVIEW_TASK_COUNT } from '@/constants/task';

type TaskCenterHoverProps = { collapsed?: boolean };

export const TaskCenterHover: React.FC<TaskCenterHoverProps> = ({ collapsed = true }) => {
  const navigate = useNavigate();

  // Controlled open state to allow programmatic opening from other components
  const [open, setOpen] = React.useState(false);
  const [_, setForcedOpen] = React.useState(false);

  useEffect(() => {
    const handler = () => {
      setForcedOpen(true);
      setOpen(true);
    };

    window.addEventListener('openTaskCenterHover', handler as EventListener);
    return () => window.removeEventListener('openTaskCenterHover', handler as EventListener);
  }, []);

  // create a stable source timestamp for this TaskCenter instance (used to mark requests)
  const sourceTimestamp = React.useMemo(() => Date.now(), []);

  const { tasks = [], pagination, status, startPolling, stopPolling } = useTaskSummaryData({
    action: undefined,
    initialPage: 0,
    initialSize: 10,
    pollingInterval: 3000,
    pollingAlwaysOn: true,
    sourceTimestamp,
    enableGlobalRefreshListener: true,
    refreshTrigger: 0,
  });

  // Ensure polling runs continuously for the Task Center regardless of hover/open state.
  useEffect(() => {
    try {
      if (startPolling) startPolling();
    } catch (e) {
      // ignore
    }
    return () => {
      try {
        if (stopPolling) stopPolling();
      } catch (e) {
        // ignore
      }
    };
  }, [startPolling, stopPolling]);

  const previewTasks = tasks.slice(0, TASK_CENTER_PREVIEW_TASK_COUNT);

  // Badge display: use the aggregated `status` returned by the hook (simpler and authoritative)
  const normalizedStatus = useMemo< string | null>(() => {
    if (status === undefined || status === null) return null;
    try {
      const s = String(status).trim().toUpperCase();
      return s || null;
    } catch (e) {
      return null;
    }
  }, [status]);

  const badgeStatusCfg = getStatusConfig(normalizedStatus ?? '');
  const BadgeIcon = tasks && tasks.length > 0 ? badgeStatusCfg?.icon as any : null;
  const badgeBgClass = badgeStatusCfg?.bg || '';
  
  const openTask = (taskId?: string) => {
    if (!taskId) return;
    navigate(`/task-detail/${taskId}`);
  };

  const openAllTasks = () => {
    navigate('/dashboard');
  };

  return (
    <HoverCard open={open} onOpenChange={(v: boolean) => { setOpen(v); if (!v) setForcedOpen(false); }}>
      <HoverCardTrigger asChild>
        <div className="relative inline-block">
          <Button
            aria-label={'任务中心'}
            className="w-full h-12 flex flex-col items-center justify-center border border-border rounded-md bg-transparent hover:bg-secondary/80 text-muted-foreground shadow-none px-2 py-0"
          >
            <LayoutGrid className="w-4 h-4" />
            {!collapsed && <span className="text-[10px] leading-tight">任务中心</span>}
          </Button>
          {BadgeIcon ? (
            <div className={`absolute -top-1 right-0 z-10 w-5 h-5 rounded-full flex items-center justify-center ${badgeBgClass}`}>
              {typeof BadgeIcon === 'function' || typeof BadgeIcon === 'object' ? (
                <BadgeIcon className={`w-3 h-3 text-white`} />
              ) : null}
            </div>
          ) : null}
        </div>
      </HoverCardTrigger>

      <HoverCardContent
        side="left"
        align="center"
        sideOffset={8}
        className="!bg-white text-foreground rounded-md shadow-lg"
        style={{ width: 440, maxHeight: 440, overflow: 'hidden' }}
      >
        <div className="p-2 flex flex-col" style={{ maxHeight: 440 }}>
          <div className="flex items-center justify-between mb-2 px-2">
            <div className="text-sm font-medium">任务中心</div>
            {tasks && tasks.length > 0 ? (
              <div className="text-xs text-muted-foreground">共 {pagination?.total ?? tasks.length} 条</div>
            ) : null}
          </div>

          <div className="border flex-1 overflow-y-auto px-3 py-3" style={{ maxHeight: 300 }}>
              {previewTasks && previewTasks.length > 0 ? (
                previewTasks.filter(Boolean).map((t, i) => {
                  try {
                  const statusCfg = getStatusConfig(String(t.status)) || { label: '', color: '', icon: undefined };
                  const count = t.subTaskCount ?? t.successCount ?? 1;
                  let rawImg: any = (t.originalImages && t.originalImages[0]) || (t.subTaskImages && t.subTaskImages[0]) || '';
                // If API returns image objects, try to extract a URL-like field
                if (rawImg && typeof rawImg === 'object') {
                  rawImg = rawImg.url || rawImg.ossUrl || rawImg.oss_url || rawImg.thumbnail || rawImg.path || '';
                }
                const thumbnail = typeof rawImg === 'string' && rawImg ? getThumbnailUrl(rawImg) : '';

                const StatusIcon = statusCfg.icon as any;

                return (
                  <div
                    key={t.taskId || t.id}
                    onClick={() => openTask(String(t.taskId || t.id))}
                    className={`flex items-center gap-3 p-2 ${i === Math.min(tasks.length, TASK_CENTER_PREVIEW_TASK_COUNT) - 1 ? '' : 'mb-2'} border rounded-md hover:shadow-md hover:bg-muted/5 cursor-pointer`}
                  >
                    {thumbnail ? (
                      <img src={thumbnail} alt={t.name} className="w-14 h-14 object-cover rounded" />
                    ) : (
                      <div className="w-14 h-14 flex items-center justify-center rounded bg-muted/5 text-muted-foreground">
                        <ImageIcon className="w-6 h-6" />
                      </div>
                    )}

                    <div className="flex-1 flex flex-col justify-between">
                      <div className="text-sm font-medium truncate">{mapActionToChinese(String(t.action))}</div>
                      <div className="text-xs text-muted-foreground mt-1">数量: {count}</div>
                      <div className="text-xs text-muted-foreground mt-1">{t.createTime}</div>
                    </div>

                    <div className="flex items-center ml-2 whitespace-nowrap">
                      {StatusIcon && (typeof StatusIcon === 'function' || typeof StatusIcon === 'object') ? (
                        <StatusIcon className={`${statusCfg.color ?? ''} w-4 h-4`} />
                      ) : null}
                      <span className="text-xs ml-1">{statusCfg.label ?? ''}</span>
                    </div>
                  </div>
                );
                } catch (err) {
                  // Log the problematic task to aid debugging and skip rendering it
                  // eslint-disable-next-line no-console
                  console.error('TaskCenterHover: error rendering preview task', { task: t, err });
                  return null;
                }
              })
            ) : (
              <div className="w-full h-40 flex items-center justify-center text-muted-foreground">暂无任务数据</div>
            )}
          </div>

          {tasks && tasks.length > 0 ? (
            <div className="py-3 px-3 border-l border-r border-b">
              <div className="text-center">
                <Button type="button" onClick={openAllTasks} className="w-full flex items-center justify-center gap-2">
                  全部任务
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
};

export default TaskCenterHover;
