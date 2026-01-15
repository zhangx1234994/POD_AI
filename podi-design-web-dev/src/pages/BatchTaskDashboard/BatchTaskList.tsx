import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { TaskSummaryItem } from '@/types/task';
import { toast } from 'sonner';
import { submitImageRegenerationTask } from '@/utils/workflow';
import { generateTaskId } from '@/utils/taskUtils';
import { downloadUrl } from '@/utils/downloadUtils';
import { getUserId } from '@/utils/http';
import { StablePagination } from '@/components/StablePagination';
import { BatchTaskFilterBar } from './BatchTaskFilterBar';
import { BatchTaskCard } from './BatchTaskCard';
import { useTaskSummaryData } from '@/hooks/useTaskSummaryData';
import { mapActionToChinese } from '@/utils/taskUtils';
import { AI_ACTIONS } from '@/constants/sidebar';

const getGridColumns = () => {
  if (typeof window === 'undefined') return 3;
  if (window.matchMedia('(min-width: 1280px)').matches) return 4;
  return 3;
};

const getPageSize = (cols: number) => {
  if (cols >= 5) return 10;
  if (cols === 4 || cols === 2) return 8;
  return 9;
};

export function BatchTaskList() {
  const navigate = useNavigate();
  const gridRef = useRef<HTMLDivElement>(null);

  const [cols, setCols] = useState(() => getGridColumns());

  useEffect(() => {
    const checkColumns = () => {
      if (gridRef.current) {
        const style = window.getComputedStyle(gridRef.current);
        const template = style.gridTemplateColumns;
        const actualCols = template.split(' ').length;
        if (actualCols > 0 && actualCols !== cols) {
          setCols(actualCols);
        }
      }
    };

    checkColumns();
    let timeoutId: NodeJS.Timeout;
    const debouncedResize = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(checkColumns, 200);
    };

    window.addEventListener('resize', debouncedResize);
    return () => {
      window.removeEventListener('resize', debouncedResize);
      clearTimeout(timeoutId);
    };
  }, [cols]);

  const handleRegenerate = async (task: TaskSummaryItem) => {
    toast.info('开始重新执行任务');
    if (!task) {
      toast.error('任务信息不存在');
      return;
    }
    try {
      const userId = getUserId();
      const newTaskId = generateTaskId();
      const res = await submitImageRegenerationTask(task.action || '', userId, task.taskId, newTaskId);
      if (res && res.success) {
        toast.success('任务重新执行完成');
        try {
          window.dispatchEvent(new CustomEvent('refreshTaskList', { detail: { forceRefresh: true } }));
        } catch (e) {
          console.error('触发全局刷新事件失败:', e);
        }
      } else {
        toast.error(res?.message || '重绘请求失败');
      }
    } catch (err) {
      console.error('重绘失败', err);
      toast.error('重绘失败，请稍后重试');
    }
  };

  const [actionFilter, setActionFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeSearch, setTypeSearch] = useState<string>('');
  const searchParam = typeSearch && typeSearch.trim() !== '' ? typeSearch.trim() : undefined;

  const {
    tasks,
    loading,
    pagination: { page, setPage, size, setSize, hasNext, total, totalPages },
  } = useTaskSummaryData({
    initialPage: 0,
    initialSize: getPageSize(cols),
    pollingInterval: 3000,
    enableGlobalRefreshListener: true,
    action: actionFilter === 'all' ? undefined : actionFilter,
    status: statusFilter === 'all' ? undefined : statusFilter,
    search: searchParam,
  });

  useEffect(() => {
    const targetSize = getPageSize(cols);
    if (size !== targetSize) {
      setSize(targetSize);
    }
  }, [cols, size, setSize]);

  const handleTaskClick = (task: TaskSummaryItem) => {
    navigate(`/task-detail/${task.taskId}`, { state: { task } });
  };

  const downloadImage = (url: string, filename?: string) => {
    if (!url) return;
    try {
      downloadUrl(url, filename).catch((err) => console.error('图片下载失败', err));
    } catch (err) {
      console.error('图片下载失败！', err);
    }
  };

  const resetFilters = () => {
    setTypeSearch('');
    setActionFilter('all');
    setStatusFilter('all');
  };

  return (
    <div className="space-y-6">
      <BatchTaskFilterBar
        typeSearch={typeSearch}
        setTypeSearch={setTypeSearch}
        actionFilter={actionFilter}
        setActionFilter={setActionFilter}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        aiTools={AI_ACTIONS}
        mapActionToChinese={mapActionToChinese}
        resetFilters={resetFilters}
      />

      <div ref={gridRef} className="grid gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
        {tasks.map((task: TaskSummaryItem) => (
          <BatchTaskCard key={task.taskId } task={task} onClick={handleTaskClick} onRegenerate={handleRegenerate} onDownload={(url, fn) => downloadImage(url, fn)} />
        ))}
      </div>

      {tasks.length === 0 && !loading && (
        <div className="text-center py-10 text-muted-foreground">暂无任务数据</div>
      )}

      {tasks.length > 0 && (
        <div className="mt-6 flex justify-center border rounded-md p-4">
          <StablePagination
            initialPage={page}
            initialSize={size}
            onPageChange={setPage}
            loading={loading}
            hasMore={hasNext}
            totalMatches={total}
            totalPages={totalPages}
            currentPageCount={tasks.length}
            showTotal={(total) => `共 ${total} 个任务`}
          />
        </div>
      )}
    </div>
  );
}

export default BatchTaskList;
