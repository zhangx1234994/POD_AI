import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { usePoints } from '@/contexts/PointsContext';
import { POINT_CHANGE_TYPES, POINT_TYPES } from '@/constants/points';
import pointsAPI from '@/services/pointsAPI';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { RefreshCw, Download, Calendar, X } from 'lucide-react';
import { getDebouncedFunction, triggerDebouncedFunction, clearDebouncedFunction } from '@/utils/debounce';

export const PointsFilterBar: React.FC = () => {
  const {
    changeType,
    pointsType,
    taskId,
    setChangeType,
    setPointsType,
    setTaskId,
    setPage,
    fetchTransactions,
    refresh,
    transactionsList
  } = usePoints();
  const [search, setSearch] = useState(taskId || '');
  const [exporting, setExporting] = useState(false);
  const searchRef = useRef(search);
  const DEBOUNCE_KEY = 'pointsFilterSearch';

  useEffect(() => {
    // create debounced function which reads latest value from searchRef
    getDebouncedFunction(DEBOUNCE_KEY, () => {
      const q = String(searchRef.current ?? '').trim();
      setTaskId(q);
      setPage(1);
      fetchTransactions({ taskId: q, current: 1 });
    }, 400);

    return () => {
      clearDebouncedFunction(DEBOUNCE_KEY);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleExport = async () => {
    if (!transactionsList || !transactionsList.length) return;
    setExporting(true);
    try {
      // 构造与旧版 filters 兼容的导出参数 (snake_case 为后端常见命名)
      const exportParams: any = {};
      if (changeType && changeType !== 'all') exportParams.change_type = changeType;
      if (pointsType && pointsType !== 'all') exportParams.point_type = pointsType;
      if (search && String(search).trim() !== '') exportParams.q = String(search).trim();

      const res = await pointsAPI.exportPoints(exportParams);
      const blob = res instanceof Blob ? res : res?.data ?? null;
      if (blob) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const filename = `points_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('export error', err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="bg-card border rounded-md p-6">
      {/* top row: title + actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calendar className="w-5 h-5 text-muted-foreground" />
          <h3 className="text-sm font-medium">积分变动明细</h3>
        </div>

        <div className="flex items-center gap-2">
          <Button
            title="导出"
            variant="ghost"
            onClick={handleExport}
            disabled={!exporting}
            className="px-3 py-2 rounded-md border disabled:cursor-not-allowed"
          >
            <Download className="w-4 h-4 mr-2" /> 导出
          </Button>

          <Button
            title="刷新"
            variant="ghost"
            onClick={() => refresh()}
            className="px-3 py-2 rounded-md border"
          >
            <RefreshCw className="w-4 h-4 mr-2" /> 刷新
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-4 sm:grid-cols-4 gap-4 mt-4">
        <div>
          <div className="text-sm text-muted-foreground mb-2">变动类型</div>
          <Select
            value={changeType}
            onValueChange={(v: any) => {
              // 更新变动类型过滤器，并重新拉取事务（重置到第一页）
              setChangeType(v);
              setPage(1);
              fetchTransactions({ changeType: v, current: 1 });
            }}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>

            <SelectContent>
              <SelectItem value={POINT_CHANGE_TYPES.ALL}>全部类型</SelectItem>
              <SelectItem value={POINT_CHANGE_TYPES.GAIN}>积分获得</SelectItem>
              <SelectItem value={POINT_CHANGE_TYPES.CONSUME}>积分消耗</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <div className="text-sm text-muted-foreground mb-2">积分类型</div>
          <Select
            value={pointsType}
            onValueChange={(v: any) => {
              // 更新积分类型过滤器，并重新拉取事务（重置到第一页）
              setPointsType(v);
              setPage(1);
              fetchTransactions({ pointsType: v, current: 1 });
            }}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>

            <SelectContent>
              <SelectItem value={POINT_TYPES.ALL}>全部积分</SelectItem>
              <SelectItem value={POINT_TYPES.TEMP}>临时积分</SelectItem>
              <SelectItem value={POINT_TYPES.RECHARGE}>充值积分</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <div className="text-sm text-muted-foreground mb-2">搜索</div>
          <div className="relative">
            <Input
              value={search}
              placeholder="搜索任务ID或备注关键词"
              onChange={(e: any) => {
                const v = String(e.target.value);
                setSearch(v);
                searchRef.current = v;
                // trigger the debounced fetch
                triggerDebouncedFunction(DEBOUNCE_KEY);
              }}
              className="rounded-md pr-10 w-full"
            />
            {search && (
              <button
                type="button"
                title="清除"
                onClick={() => {
                  // 将搜索词清除，并重新拉取事务（重置到第一页）
                  setSearch('');
                  setTaskId('');
                  setPage(1);
                  fetchTransactions({ taskId: '', current: 1 });
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center justify-center w-7 h-7 rounded text-muted-foreground hover:bg-accent"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PointsFilterBar;
