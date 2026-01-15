import { useState, useCallback, useRef, useEffect, useMemo, memo } from 'react';
import { Button } from './ui/button';

interface StablePaginationProps {
  initialPage?: number;
  initialSize?: number;
  hasMore?: boolean;
  loading?: boolean;
  onPageChange?: (page: number) => void;
  onSizeChange?: (size: number) => void;
  /** 总的匹配数（根据当前筛选条件） */
  totalMatches?: number;
  totalPages?: number;
  /** 当前页的任务数量（当前页返回的 items 数量） */
  currentPageCount?: number;
  /** 可选：自定义显示总数的渲染函数，接收 (total, [start, end]) */
  showTotal?: (total: number, range: [number, number]) => string;
}

// 创建一个完全稳定的分页组件，有自己的状态管理
export const StablePagination = memo(function StablePagination({
  initialPage = 0,
  initialSize = 5,
  hasMore = false,
  loading = false,
  onPageChange,
  onSizeChange,
  totalMatches,
  totalPages = 1,
  currentPageCount,
  showTotal,
}: StablePaginationProps) {
  // 内部状态，只在初始化和用户操作时更新
  const [internalPage, setInternalPage] = useState<number>(initialPage);
  const [internalSize, setInternalSize] = useState<number>(initialSize);
  const [isInitialized, setIsInitialized] = useState<boolean>(false);

  // 使用ref来跟踪最新的props值，避免闭包问题
  const hasMoreRef = useRef<boolean>(hasMore);
  hasMoreRef.current = hasMore;

  const loadingRef = useRef<boolean>(loading);
  loadingRef.current = loading;

  const onPageChangeRef = useRef<((page: number) => void) | undefined>(onPageChange);
  onPageChangeRef.current = onPageChange;

  const onSizeChangeRef = useRef<((size: number) => void) | undefined>(onSizeChange);
  onSizeChangeRef.current = onSizeChange;

  // 使用防抖来避免频繁的状态更新
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 添加状态变化跟踪，避免不必要的重渲染
  const prevHasMoreRef = useRef<boolean>(hasMore);
  const prevLoadingRef = useRef<boolean>(loading);

  // 添加一个状态来跟踪是否应该更新按钮状态
  const [shouldUpdateButtonState, setShouldUpdateButtonState] = useState<boolean>(false);

  // 初始化时设置内部状态
  useEffect(() => {
    if (!isInitialized) {
      setInternalPage(initialPage);
      setInternalSize(initialSize);
      setIsInitialized(true);
      prevHasMoreRef.current = hasMore;
      prevLoadingRef.current = loading;
    }
  }, [initialPage, initialSize, isInitialized, hasMore, loading]);

  // 监控hasMore和loading的变化，使用防抖减少状态更新频率
  useEffect(() => {
    if (isInitialized) {
      // 检查hasMore是否真的发生了变化
      if (prevHasMoreRef.current !== hasMore) {
        // 使用防抖来避免频繁更新
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }

        debounceTimerRef.current = setTimeout(() => {
          prevHasMoreRef.current = hasMore;
          setShouldUpdateButtonState((prev: boolean) => !prev); // 触发按钮状态更新
        }, 300); // 减少防抖延迟到300ms，提高响应性
      }

      // 检查loading是否真的发生了变化
      if (prevLoadingRef.current !== loading) {
        // 使用防抖来避免频繁更新
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }

        debounceTimerRef.current = setTimeout(() => {
          prevLoadingRef.current = loading;
          setShouldUpdateButtonState((prev: boolean) => !prev); // 触发按钮状态更新
        }, 300); // 减少防抖延迟到300ms，提高响应性
      }
    }
  }, [hasMore, loading, isInitialized]);

  // 只有当props真正变化时才更新内部状态，增加更严格的条件
  useEffect(() => {
    if (isInitialized && initialPage !== internalPage) {
      // 移除防抖延迟，确保页码显示立即更新
      // 对于分页操作，用户期望看到即时的页码反馈
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // 直接更新内部页码状态，无需延迟
      setInternalPage(initialPage);
    }
  }, [initialPage, internalPage, isInitialized]);

  useEffect(() => {
    if (isInitialized && initialSize !== internalSize) {
      // 使用防抖来避免频繁更新
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        setInternalSize(initialSize);
      }, 200); // 增加防抖时间
    }
  }, [initialSize, internalSize, isInitialized]);

  // 清理防抖定时器
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // 处理页码变化
  const handleFirstPage = useCallback(() => {
    if (internalPage > 0) {
      setInternalPage(0);
      // 立即调用onPageChange，不等待状态更新
      onPageChangeRef.current?.(0);
    }
  }, [internalPage]);

  const handlePrevPage = useCallback(() => {
    if (internalPage > 0) {
      const newPage = internalPage - 1;
      setInternalPage(newPage);
      // 立即调用onPageChange，不等待状态更新
      onPageChangeRef.current?.(newPage);
    }
  }, [internalPage]);

  const handleNextPage = useCallback(() => {
    // 使用ref确保获取最新的hasMore值
    if (hasMoreRef.current) {
      const newPage = internalPage + 1;
      setInternalPage(newPage);
      // 立即调用onPageChange，不等待状态更新
      onPageChangeRef.current?.(newPage);
    }
  }, [internalPage]);

  // 计算按钮是否应该禁用，使用稳定的引用避免重新渲染
  // 使用useMemo确保按钮状态只在必要时更新
  const buttonStates = useMemo(() => {
    const isFirstDisabled = loadingRef.current || internalPage === 0;
    const isPrevDisabled = loadingRef.current || internalPage === 0;
    const isNextDisabled = loadingRef.current || !hasMoreRef.current;
    return { isFirstDisabled, isPrevDisabled, isNextDisabled };
  }, [internalPage, shouldUpdateButtonState]); // 只依赖内部页码和按钮状态更新标记

  // 使用useMemo来稳定的按钮样式，避免每次渲染都重新计算
  const buttonStyle = useMemo(
    () => ({
      transition: 'none' as const,
      // 添加最小宽度，防止按钮大小变化
      minWidth: '80px',
      // 添加额外的样式来防止闪烁
      willChange: 'auto' as const,
      // 禁用过渡效果
      WebkitTransition: 'none',
      MozTransition: 'none',
      msTransition: 'none',
      OTransition: 'none',
    }),
    []
  );

  return (
    <div className="flex items-center justify-between w-full" style={{ isolation: 'isolate' }}>
      {/* 左侧：两部分：当前页任务数量 + 任务总数（支持自定义格式化） */}
      <div className="flex items-center gap-6 text-base text-muted-foreground">
        {(() => {
          const total = typeof totalMatches === 'number' ? totalMatches : 0;
          const start = internalPage * internalSize + 1;
          const end = internalPage * internalSize + (typeof currentPageCount === 'number' ? currentPageCount : internalSize);
          if (typeof showTotal === 'function') {
            return (
              <div className="inline-flex items-baseline gap-2">
                <span className="text-muted-foreground">{showTotal(total, [start, end])}</span>
              </div>
            );
          }

          return (
            <>
              <div className="inline-flex items-baseline gap-2">
                <span className="text-muted-foreground">显示</span>
                <span className="font-medium">{typeof currentPageCount === 'number' ? currentPageCount : '-'}</span>
                <span className="text-muted-foreground">个任务</span>
              </div>
              <div className="inline-flex items-baseline gap-2">
                <span className="text-muted-foreground">共</span>
                <span className="font-medium">{typeof totalMatches === 'number' ? totalMatches : '-'}</span>
                <span className="text-muted-foreground">个</span>
              </div>
            </>
          );
        })()}
      </div>

      {/* 右侧：上一页 / 当前页 / 下一页 */}
      <div className="flex items-center gap-2" style={{ contain: 'layout style paint' }}>
        <Button
          size="sm"
          variant="outline"
          onClick={handlePrevPage}
          disabled={buttonStates.isPrevDisabled}
          style={buttonStyle}
        >
          上一页
        </Button>

        <div className="px-4 py-2 text-base text-muted-foreground">第 {internalPage + 1} / {totalPages} 页</div>

        <Button
          size="sm"
          onClick={handleNextPage}
          disabled={buttonStates.isNextDisabled}
          style={buttonStyle}
        >
          下一页
        </Button>
      </div>
    </div>
  );
});
