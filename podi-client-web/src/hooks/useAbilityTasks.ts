import { useEffect, useState } from 'react';
import { clientApi, type AbilityTask } from '../services/clientApi';

export function useAbilityTasks(accessToken?: string | null, limit = 20) {
  const [tasks, setTasks] = useState<AbilityTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;

    async function loadTasks() {
      if (!accessToken) {
        setTasks([]);
        setLoading(false);
        setError(null);
        return;
      }
      if (!cancelled) {
        setLoading(true);
      }
      try {
        const data = await clientApi.listAbilityTasks(accessToken, limit);
        if (!cancelled) {
          setTasks(data.items);
          setError(null);
          setLoading(false);
          const hasInFlight = data.items.some((task) => ['queued', 'running'].includes(task.status));
          const nextDelay = hasInFlight ? 4000 : 15000;
          if (timer) {
            window.clearTimeout(timer);
          }
          timer = window.setTimeout(() => {
            void loadTasks();
          }, nextDelay);
        }
      } catch {
        if (!cancelled) {
          setTasks([]);
          setError('任务列表暂时拉取失败，请稍后重试或刷新页面。');
          setLoading(false);
        }
        if (timer) {
          window.clearTimeout(timer);
        }
        timer = window.setTimeout(() => {
          void loadTasks();
        }, 15000);
      }
    }
    void loadTasks();
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [accessToken, limit]);

  return {
    tasks,
    loading,
    error,
  };
}
