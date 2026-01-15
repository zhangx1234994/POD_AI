import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { TaskStatistics } from '@/types/task';
import { Layers, Image } from 'lucide-react';
import { fetchUserTaskStatistics } from '@/utils/workflow';

export function BatchTaskOverview({ fetchStatistics = true }: { fetchStatistics?: boolean }) {
  const [taskStatistics, setTaskStatistics] = useState<TaskStatistics>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!fetchStatistics) return;
    let mounted = true;
    const load = async () => {
      try {
        setLoading(true);
        const data = await fetchUserTaskStatistics();
        if (!mounted) return;
        const taskToday = data.taskToday ?? data.task_today ?? undefined;
        const taskTotal = data.taskTotal ?? data.task_total ?? undefined;
        const subToday = data.subTaskToday ?? data.sub_task_today ?? undefined;
        const subTotal = data.subTaskTotal ?? data.sub_task_total ?? undefined;

        setTaskStatistics({
          userId: data.userId ?? data.user_id,
          taskToday,
          taskTotal,
          subTaskToday: subToday,
          subTaskTotal: subTotal,
        });
      } catch (err) {
        console.debug('TaskOverview: could not fetch stats', err);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => {
      mounted = false;
    };
  }, [fetchStatistics]);

  const renderValue = (key: keyof TaskStatistics): React.ReactNode => {
    const v = taskStatistics[key];
    if (typeof v === 'number' || typeof v === 'string') {
      return (
        <span className="">
          {v.toLocaleString()}
        </span>
      );
    }
    return loading ? '加载中' : '0';
  };

  const renderSmall = (val: unknown) => {
    if (typeof val === 'number') return <>{val.toLocaleString()}</>;
    if (typeof val === 'string' && /^[0-9]+$/.test(val)) return <>{val}</>;
    return loading ? '加载中' : '0';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
      <Card className="flex flex-col gap-6 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 border-transparent">
        <CardContent className="px-6 py-6 space-y-0 pt-6">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0 space-y-1">
              <p className="text-xs text-white/70">今日批量任务</p>
              <p className="text-4xl font-bold text-white">{renderValue('taskToday')}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="bg-blue-500 w-12 h-12 rounded-xl backdrop-blur-sm flex items-center justify-center">
                <Layers className="w-6 h-6 text-white" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-white/70">总任务数</span>
                <span className="text-xs text-white">{renderSmall(taskStatistics.taskTotal ?? undefined)}</span>
                
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      <Card className="flex flex-col gap-6 rounded-xl bg-gradient-to-br from-purple-500/95 to-purple-600/95 border-transparent shadow">
        <CardContent className="px-6 py-6 space-y-0 pt-6">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0 space-y-1">
              <p className="text-xs text-white/70">今日子任务</p>
              <p className="text-4xl font-bold text-white">{renderValue('subTaskToday')}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="bg-purple-500 w-12 h-12 rounded-xl backdrop-blur-sm flex items-center justify-center">
                <Image className="w-6 h-6 text-white" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-white/70">子任务总数</span><span className="text-xs text-white">{renderSmall(taskStatistics.subTaskTotal ?? undefined)}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default BatchTaskOverview;
