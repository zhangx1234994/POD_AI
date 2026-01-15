import { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { toast } from 'sonner';
import { FolderOpen } from 'lucide-react';
import { getUserId } from '@/utils/http';
import { http } from '@/utils/http';
import { downloadZip, downloadUrl } from '@/utils/downloadUtils';
import { GalleryImage } from '@/types/galleryImage';
import {
  GALLERY_DEFAULT_GAP,
  GALLERY_DEFAULT_PAGE_SIZE,
  GALLERY_DEFAULT_ROOT_MARGIN,
  GALLERY_DEFAULT_PREFETCH_ENABLED,
  GALLERY_DEFAULT_PREFETCH_DEPTH,
  LOAD_MORE_TOAST_DURATION_MS,
} from '@/constants/gallery';
import { fetchGalleryImages } from '@/hooks/useGalleryData';
import { GalleryToolbar } from './GalleryToolbar';
import { AI_ACTIONS } from '@/constants/sidebar';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { BatchToolbar } from './BatchToolbar';
import { GridView } from './GridView';
import { ImageCard } from './ImageCard';
import { ListImageCard } from './ListImageCard';
import { ListImageCardSkeletons } from './ListImageCardSkeletons';
import { GeneratedImagePreview } from './GeneratedImagePreview';
import { UploadImagePreview } from './UploadImagePreview';
import { SeamlessPreviewDialog } from './SeamlessPreviewDialog';
import defaultGrid from '@/assets/images/grid_default.png';

export interface PersonalGalleryProps {
  pageSize?: number;
  rootMargin?: string;
  prefetchEnabled?: boolean;
  prefetchDepth?: number;
  windowedPages?: number;
}

export function PersonalGalleryPage(props: PersonalGalleryProps = {}) {
  const {
    pageSize = GALLERY_DEFAULT_PAGE_SIZE,
    rootMargin: rootMarginProp = GALLERY_DEFAULT_ROOT_MARGIN,
    prefetchEnabled = GALLERY_DEFAULT_PREFETCH_ENABLED,
    prefetchDepth = GALLERY_DEFAULT_PREFETCH_DEPTH,
    windowedPages = 0,
  } = props;
  // 所有图片数据（含分页标记）
  const [taskImages, setTaskImages] = useState<GalleryImage[]>([]);
  const gridRef = useRef<any>(null);
  const _refreshTimer = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  // 优化加载状态管理，减少不必要的重渲染
  const [isLoading, setIsLoading] = useState(false);
  // 分页状态（按 tab 独立维护）
  const size = pageSize;
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState<number | null>(null);
  const [pageUploads, setPageUploads] = useState(0);
  const [totalUploads, setTotalUploads] = useState<number | null>(null);
  const [pageDesigns, setPageDesigns] = useState(0);
  const [totalDesigns, setTotalDesigns] = useState<number | null>(null);
  const [pageSended, setPageSended] = useState(0);
  const [totalSended, setTotalSended] = useState<number | null>(null);

  // 筛选与搜索状态
  const [filterTags, setFilterTags] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [filterSourceType, setFilterSourceType] = useState('all');
  const [sortBy, setSortBy] = useState('date-desc');

  // 视图与选择模式
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedImages, setSelectedImages] = useState<string[]>([]);
  
  // 对话框状态
  const [pendingFilter, setPendingFilter] = useState<(() => void) | null>(null);
  const [, setPendingDescriptor] = useState<any>(null);
  const [showFilterConfirm, setShowFilterConfirm] = useState(false);
  const [showBatchDeleteConfirm, setShowBatchDeleteConfirm] = useState(false);
  const [showBatchDownloadConfirm, setShowBatchDownloadConfirm] = useState(false);
  const [activeTab, _setActiveTab] = useState<string>('all');
  const [previewImage, setPreviewImage] = useState<GalleryImage | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [showGeneratedPreview, setShowGeneratedPreview] = useState(false);
  const [showSeamlessPreview, setShowSeamlessPreview] = useState(false);
  const [selectedSeamlessImage, setSelectedSeamlessImage] = useState<GalleryImage | null>(null);

  // 懒加载相关 refs
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const _loadingMore = useRef<boolean>(false);
  const _fetching = useRef<boolean>(false);
  const _didInitialLoad = useRef<boolean>(false);
  const _skipInitialFilterEffect = useRef<boolean>(true);
  const _ignoreIntersection = useRef<boolean>(false);
  const _userScrolled = useRef<boolean>(false);
  const _hasMoreAll = useRef<boolean>(true);
  const _hasMoreUploads = useRef<boolean>(true);
  const _hasMoreDesigns = useRef<boolean>(true);
  const _hasMoreSended = useRef<boolean>(true);
  const _loadMoreToastId = useRef<string | null>(null);

  // 刷新网格布局（防抖）
  const refreshGrid = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (_refreshTimer.current) {
      window.clearTimeout(_refreshTimer.current);
    }
    // 防抖：合并快速的图片/加载事件
    _refreshTimer.current = window.setTimeout(() => {
      const g = gridRef.current as any;
      const inst = (g && (typeof g.getInstance === 'function' ? g.getInstance() : g._grid)) || g;
      if (!inst) return;
      // 在重新布局前更新容器引用（如果支持）
      if (containerRef.current && typeof inst.setContainer === 'function') {
        try { inst.setContainer(containerRef.current); } catch (e) { /* ignore */ }
      }
      // 使用 requestAnimationFrame 避免在 JS 执行期间强制同步布局
      window.requestAnimationFrame(() => {
        const methods = ['relayout', 'layout', 'requestLayout', 'updateLayout', 'refresh', 'update'];
        let did = false;
        for (const m of methods) {
          const fn = inst[m];
          if (typeof fn === 'function') {
            try {
              // 优先调用带 `true` 的版本以强制完整重新测量；若失败则回退为无参调用
              try { fn.call(inst, true); } catch (inner) { fn.call(inst); }
            } catch (err) {
              console.warn('[PersonalGallery] grid method', m, 'threw', err);
            }
            did = true;
            break;
          }
        }
        if (!did && typeof inst.render === 'function') {
          try { inst.render(); } catch (e) { /* ignore */ }
        }
        // 小幅后续重排以确保网格稳定
        try {
          window.setTimeout(() => {
            const follow = inst.relayout || inst.layout || inst.refresh;
            if (typeof follow === 'function') {
              try { follow.call(inst); } catch (e) { /* ignore */ }
            }
          }, 80);
        } catch (e) { /* ignore */ }
      });
    }, 200) as unknown as number;
  }, [containerRef]);

  // 对外可用的刷新调度包装（由图片加载处理器调用）
  const scheduleGridRefresh = useCallback(() => {
    // refreshGrid 已实现防抖；这里提供一个稳定的包装器
    try {
      refreshGrid();
    } catch (e) {
      // ignore
    }
  }, [refreshGrid]);

  // 图片加载完成时触发网格重排
  const handleImageLoaded = useCallback(() => {
    try { scheduleGridRefresh(); } catch (e) { /* ignore */ }
  }, [scheduleGridRefresh]);

  /**
   * 获取图片数据
   * @param type 图片类型（uploaded/generated/sended）
   * @param pageOverride 页码覆盖
   * @param reset 是否重置（清空已有数据）
   */
  const fetchImages = useCallback(
    async (type?: 'uploaded' | 'generated' | 'sended', pageOverride?: number, reset?: boolean): Promise<number> => {
      if (_fetching.current) {
        return 0;
      }
      _fetching.current = true;
      let pageToFetch: number = page;
      try {
        if (reset) {
          if (type === 'uploaded') {
            _hasMoreUploads.current = true;
          } else if (type === 'generated') {
            _hasMoreDesigns.current = true;
          } else if (type === 'sended') {
            _hasMoreSended.current = true;
          } else {
            _hasMoreAll.current = true;
          }
        }
        const userId = getUserId();

        let endpoint = '/gallery/all';
        let setTotalState = setTotal;
        if (type === 'uploaded') {
          endpoint = '/gallery/uploads';
          pageToFetch = typeof pageOverride === 'number' ? pageOverride : pageUploads;
          setTotalState = setTotalUploads;
        } else if (type === 'generated') {
          endpoint = '/gallery/designs';
          pageToFetch = typeof pageOverride === 'number' ? pageOverride : pageDesigns;
          setTotalState = setTotalDesigns;
        } else if (type === 'sended') {
          endpoint = '/gallery/sended';
          pageToFetch = typeof pageOverride === 'number' ? pageOverride : pageSended;
          setTotalState = setTotalSended;
        } else {
          pageToFetch = typeof pageOverride === 'number' ? pageOverride : page;
        }

        if (reset || taskImages.length === 0) setIsLoading(true);

        let queryParams = `user_id=${userId}&page=${pageToFetch}&size=${size}`;
        if (filterSourceType && filterSourceType !== 'all') {
          queryParams += `&source_type=${filterSourceType}`;
        }
        if (filterTags && filterTags.trim() !== '') {
          queryParams += `&tags=${encodeURIComponent(filterTags.trim())}`;
        }
        if (searchQuery && searchQuery.trim() !== '') {
          queryParams += `&name=${encodeURIComponent(searchQuery.trim())}`;
        }
        if (actionFilter && actionFilter !== 'all') {
          queryParams += `&type=${encodeURIComponent(actionFilter)}`;
        }
        queryParams += `&sort=${sortBy}`;

        const { images: fetchedImages, total: totalCount, counts } = await fetchGalleryImages(endpoint, queryParams);

        setTotalState(Number(totalCount) || 0);
        if (!type) {
          setTotalUploads(Number(counts?.uploaded || 0));
          setTotalDesigns(Number(counts?.generated || 0));
          setTotalSended(Number(counts?.send || 0));
        }

        const pageAnnotated = fetchedImages.map((img) => ({ ...img, __page: pageToFetch, __sourceKey: type || 'all' } as any));

        setTaskImages((prev) => {
          const merged = reset ? pageAnnotated : [...prev, ...pageAnnotated];
          const seen = new Set<string>();
          if (!reset && selectionMode && selectedImages.length > 0) {
            try {
              // 仅显示一次"加载更多"提示。Sonner 会返回一个 id，我们保存它；
              // 在持续时间结束后清除该 id，以免重复加载时产生重复提示。
              if (!_loadMoreToastId.current) {
                try {
                  const id = toast.info('加载了更多图片，如需将它们纳入批量操作，请手动勾选或重新点击“全选”。', {
                    position: 'top-center',
                    duration: LOAD_MORE_TOAST_DURATION_MS,
                    icon: null,
                    className: 'text-xs text-muted-foreground font-medium px-3 py-2'
                  });
                  _loadMoreToastId.current = String(id);
                  // 在持续时间结束后稍微延迟清除该引用
                  window.setTimeout(() => { _loadMoreToastId.current = null; }, LOAD_MORE_TOAST_DURATION_MS);
                } catch (e) { /* ignore */ }
              }
            } catch (e) { /* ignore */ }
          }
          return merged.filter((img: any) => {
            const key = `${img.type}-${img.id}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          }) as GalleryImage[];
        });

        try {
          const fetchedCount = fetchedImages.length;
          const serverTotal = Number(totalCount ?? fetchedCount);
          const pageEnd = (pageToFetch + 1) * size;
          const hasMore = !(fetchedCount < size || (typeof serverTotal === 'number' && !Number.isNaN(serverTotal) && pageEnd >= serverTotal));
          if (type === 'uploaded') {
            _hasMoreUploads.current = hasMore;
          } else if (type === 'generated') {
            _hasMoreDesigns.current = hasMore;
          } else if (type === 'sended') {
            _hasMoreSended.current = hasMore;
          } else {
            _hasMoreAll.current = hasMore;
          }
        } catch (e) { /* ignore */ }

        return fetchedImages.length;
      } catch (e) {
        console.error(`加载${type || '全部'}图片失败`, e);
        return 0;
      } finally {
        _fetching.current = false;
        setIsLoading(false);
      }
    },
    [filterSourceType, filterTags, searchQuery, sortBy, actionFilter, page, pageUploads, pageDesigns, pageSended]
  );

  // 加载更多数据（根据当前激活的 tab）
  const loadMore = useCallback(async () => {
    if (_loadingMore.current) return;
    // 如果已确定当前 tab 无更多页，则不要尝试再加载
    //（避免重复请求）
    if (activeTab === 'uploaded' && !_hasMoreUploads.current) return;
    if (activeTab === 'generated' && !_hasMoreDesigns.current) return;
    if (activeTab === 'all' && !_hasMoreAll.current) return;
    _loadingMore.current = true;
    try {
      if (activeTab === 'uploaded') {
        const next = pageUploads + 1;
        const fetched = await fetchImages('uploaded', next, false);
        // 仅在实际收到项目时才推进页码计数器
        if (fetched > 0) setPageUploads(next);
        if (prefetchEnabled && fetched >= size) {
          // 根据配置深度进行预取
          for (let d = 1; d <= prefetchDepth; d++) {
            const next2 = next + d;
            const fetched2 = await fetchImages('uploaded', next2, false);
            if (fetched2 > 0) setPageUploads(next2);
            if (fetched2 < size) break; // 若为最后一页则提前停止
          }
        }
      } else if (activeTab === 'generated') {
        const next = pageDesigns + 1;
        const fetched = await fetchImages('generated', next, false);
        if (fetched > 0) setPageDesigns(next);
        if (prefetchEnabled && fetched >= size) {
          for (let d = 1; d <= prefetchDepth; d++) {
            const next2 = next + d;
            const fetched2 = await fetchImages('generated', next2, false);
            if (fetched2 > 0) setPageDesigns(next2);
            if (fetched2 < size) break;
          }
        }
      } else if (activeTab === 'sended') {
        const next = pageSended + 1;
        const fetched = await fetchImages('sended', next, false);
        if (fetched > 0) setPageSended(next);
        if (prefetchEnabled && fetched >= size) {
          for (let d = 1; d <= prefetchDepth; d++) {
            const next2 = next + d;
            const fetched2 = await fetchImages('sended', next2, false);
            if (fetched2 > 0) setPageSended(next2);
            if (fetched2 < size) break;
          }
        }
      } else {
        const next = page + 1;
        const fetched = await fetchImages(undefined, next, false);
        if (fetched > 0) setPage(next);
        if (prefetchEnabled && fetched >= size) {
          for (let d = 1; d <= prefetchDepth; d++) {
            const next2 = next + d;
            const fetched2 = await fetchImages(undefined, next2, false);
            if (fetched2 > 0) setPage(next2);
            if (fetched2 < size) break;
          }
        }
      }
    } finally {
      // 允许后续加载
      _loadingMore.current = false;
    }
  }, [activeTab, fetchImages, page, pageUploads, pageDesigns, size]);

  // 滚动到底部时触发 loadMore
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;

    // 确定滚动根元素，优先使用主应用布局容器（如果存在），
    // 因为许多单页应用使用内部滚动容器而非视口。
    let rootElement: Element | null = null;
    try {
      const mainLayout = typeof document !== 'undefined' ? document.getElementById('main-layout-content') : null;
      if (mainLayout) rootElement = mainLayout;
      else if (containerRef.current) rootElement = containerRef.current.parentElement || null;
      else rootElement = null;
    } catch (e) {
      rootElement = null;
    }

    const rootMargin = rootMarginProp || '200px';
    const obs = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          // 首次挂载完成前不要自动加载
          if (!_didInitialLoad.current) {
            continue;
          }
          // 如果刚切换视图模式，忽略此次交叉事件，可能为布局回流导致而非用户滚动
          if (_ignoreIntersection.current) {
            continue;
          }
          // 在用户主动滚动或交互前不要自动加载更多页，
          // 避免页面初次布局时就触发分页加载
          if (!_userScrolled.current) {
            continue;
          }
          loadMore();
        }
      }
    }, { root: rootElement, rootMargin, threshold: 0.01 });

    const node = sentinelRef.current;
    if (node) obs.observe(node);
    return () => obs.disconnect();
  }, [loadMore]);

  // 监听用户滚动事件，解锁自动加载
  useEffect(() => {
    const onUserScroll = (ev: Event) => {
      // 仅考虑可信（用户发起）的事件，避免程序化滚动触发自动加载。
      // 当 `isTrusted` 为 true 时，表示该事件来自真实用户操作。
      try {
        if (ev && ev.isTrusted !== true) return;
      } catch (e) { /* ignore */ }
      if (!_userScrolled.current) {
        _userScrolled.current = true;
        // 一旦检测到用户滚动，就可以移除这些监听器
        try {
          window.removeEventListener('wheel', onUserScroll as EventListener);
          window.removeEventListener('touchmove', onUserScroll as EventListener);
        } catch (e) { /* ignore */ }
      }
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('wheel', onUserScroll, { passive: true } as any);
      window.addEventListener('touchmove', onUserScroll, { passive: true } as any);
    }

    return () => {
      try {
        window.removeEventListener('wheel', onUserScroll as EventListener);
        window.removeEventListener('touchmove', onUserScroll as EventListener);
      } catch (e) { /* ignore */ }
    };
  }, []);

  // 首次加载
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await fetchImages(undefined, 0, true);
        if (mounted) {
          _didInitialLoad.current = true;
        }
      } catch (e) { /* ignore */ }
    })();
    return () => { mounted = false; };
  }, []);

  // 筛选条件变化时重新加载（跳过首次）
  useEffect(() => {
    if (_skipInitialFilterEffect.current) {
      _skipInitialFilterEffect.current = false;
      return;
    }

    // 重置分页与数据
    try {
      setPage(0);
      setPageUploads(0);
      setPageDesigns(0);
      setTaskImages([]);
      setSelectedImages([]);
    } catch (e) { /* ignore */ }

    const t = window.setTimeout(() => {
      try { fetchImages(undefined, 0, true); } catch (e) { /* ignore */ }
    }, 120) as unknown as number;
    return () => { try { window.clearTimeout(t); } catch (e) { /* ignore */ } };
  }, [filterSourceType, filterTags, searchQuery, sortBy, actionFilter]);

  // 根据 activeTab 计算当前可见图片列表
  const visibleImages = activeTab === 'uploaded'
    ? taskImages.filter((i) => i.sourceType === 'UPLOAD')
    : activeTab === 'generated'
    ? taskImages.filter((i) => i.sourceType === 'GENERATE')
    : activeTab === 'sended'
    ? taskImages.filter((i) => i.sourceType === 'SEND')
    : taskImages;

  // 优化渲染列表计算，避免频繁变化导致闪烁，窗口化渲染：仅保留最近 N 页的图片
  const renderedVisibleImages = useMemo(() => {
    if (!windowedPages || windowedPages <= 0) return visibleImages;
    const currentPage = activeTab === 'uploaded' ? pageUploads : activeTab === 'generated' ? pageDesigns : activeTab === 'sended' ? pageSended : page;
    const minPage = Math.max(0, currentPage - windowedPages + 1);
    return visibleImages.filter((img: any) => {
      if (typeof img === 'object' && img != null && typeof (img as any).__page === 'number') {
        return (img as any).__page >= minPage;
      }
      // 无分页信息则保留
      return true;
    });
  }, [visibleImages, windowedPages, activeTab, pageUploads, pageDesigns, page, pageSended]);

  // 进入/退出选择模式
  const enterSelectionMode = () => {
    setSelectionMode(true);
    setSelectedImages([]);
  };

  const exitSelectionMode = () => {
    setSelectionMode(false);
    setSelectedImages([]);
  };

  // 全选当前可见图片（基于 DOM 实际渲染的图片）
  const selectAllVisible = () => {
    // 获取当前渲染的可见图片 ID 列表
    const visibleIds = renderedVisibleImages.map((i) => i.id);
    if (visibleIds.length === 0) {
      setSelectedImages([]);
      return;
    }

    // 检查是否所有可见图片都已选中
    const allSelected = visibleIds.every((id) => selectedImages.includes(id));
    if (allSelected) {
      // 取消选择所有可见图片
      setSelectedImages((prev) => prev.filter((id) => !visibleIds.includes(id)));
    } else {
      // 选择所有可见图片
      setSelectedImages((prev) => {
        const set = new Set(prev || []);
        for (const id of visibleIds) set.add(id);
        return Array.from(set);
      });
    }
  };

  // 安全应用筛选器（如果有选中图片则提示确认）
  const safeApplyFilter = useCallback((applyFn: () => void, descriptor?: any) => {
    if (selectionMode && selectedImages.length > 0) {
      setPendingFilter(() => applyFn);
      setPendingDescriptor(descriptor ?? null);
      setShowFilterConfirm(true);
    } else {
      applyFn();
    }
  }, [selectionMode, selectedImages.length]);

  // 点击图片查看详情
  const handleImageClick = (image: GalleryImage) => {
    if (selectionMode) {
      setSelectedImages((prev) =>
        prev.includes(image.id) ? prev.filter((id) => id !== image.id) : [...prev, image.id]
      );
      return;
    }

    setPreviewImage(image);
    if (image.sourceType === 'GENERATE') setShowGeneratedPreview(true);
    else setShowPreview(true);
  };

  // 查看无缝图预览
  const handleViewSeamless = useCallback((image: GalleryImage) => {
    setSelectedSeamlessImage(image);
    setShowSeamlessPreview(true);
  }, []);

  // 切换视图模式时刷新网格布局
  const handleViewModeChange = useCallback((v: 'grid' | 'list') => {
    // 忽略由布局回流引起的立即交叉事件
    _ignoreIntersection.current = true;
    try {
      setViewMode(v);
    } finally {
      if (typeof window !== 'undefined') {
        window.setTimeout(() => { _ignoreIntersection.current = false; }, 350);
      } else {
        _ignoreIntersection.current = false;
      }
    }
  }, [setViewMode]);

  // 切换单个图片选择状态
  const handleToggleSelect = useCallback((id: string) => {
    setSelectedImages((prev) => (prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]));
  }, [setSelectedImages]);

  // 渲染网格项
  const renderGridItem = useCallback((img: any) => (
    <ImageCard
      image={img}
      onViewDetails={handleImageClick}
      selected={selectedImages.includes(img.id)}
      batchMode={selectionMode}
      onToggleSelect={handleToggleSelect}
      onImageLoad={handleImageLoaded}
    />
  ), [handleImageClick, selectedImages, selectionMode, handleToggleSelect, handleImageLoaded]);

  // 重置筛选并加载
  const applyFilterReset = useCallback((applyFn: () => void) => {
    try {
      setPage(0);
      setPageUploads(0);
      setPageDesigns(0);
      setPageSended(0);
      setTaskImages([]);
      setSelectedImages([]);
      _fetching.current = false;
      _loadingMore.current = false;
      _hasMoreAll.current = true;
      _hasMoreUploads.current = true;
      _hasMoreDesigns.current = true;
      _hasMoreSended.current = true;
    } catch (e) { /* ignore */ }

    try { applyFn(); } catch (e) { /* ignore */ }
  }, []);

  // 各种筛选器变更处理函数
  const handleSearchChange = useCallback((v: string) => {
    safeApplyFilter(() => applyFilterReset(() => setSearchQuery(v)), { type: 'search', value: v })
  }, [safeApplyFilter, applyFilterReset]);

  const handleFilterTagsChange = useCallback((v: string) => {
    safeApplyFilter(() => applyFilterReset(() => setFilterTags(v)), { type: 'tags', value: v })
  
  }, [safeApplyFilter, applyFilterReset]);
  
  const handleFilterSourceTypeChange = useCallback((v: string) => {
    safeApplyFilter(() => applyFilterReset(() => setFilterSourceType(v)), { type: 'source', value: v })
  }, [safeApplyFilter, applyFilterReset]);

  const handleSortByChange = useCallback((v: string) => {
    safeApplyFilter(() => applyFilterReset(() => setSortBy(v)), { type: 'sort', value: v })
  }, [safeApplyFilter, applyFilterReset]);

  const handleActionFilterChange = useCallback((v: string) => {
    safeApplyFilter(() => applyFilterReset(() => setActionFilter(v)), { type: 'action', value: v })
  }, [safeApplyFilter, applyFilterReset]);

  // 批量删除与下载
  const handleBatchDelete = async () => {
    if (selectedImages.length === 0) return;
    const selected = selectedImages
      .map((id) => taskImages.find((t) => t.id === id))
      .filter(Boolean) as GalleryImage[];
    // 发送 imgId（若不可用则回退为 id）
    const ids = selected.map((i) => (i?.imgId || i?.id)).filter(Boolean) as string[];
    const userId = getUserId();
    try {
      if (ids.length) await http.post(`/gallery/imgs/batch-delete?user_id=${userId}`, { ids });
      setTaskImages((prev) => prev.filter((i) => !selectedImages.includes(i.id)));
    } catch (e) {
      console.error('批量删除失败', e);
    } finally {
      setSelectedImages([]);
      exitSelectionMode();
    }
  };

  const handleBatchDownload = async () => {
    if (selectedImages.length === 0) return;
    const selected = selectedImages
      .map((id) => taskImages.find((i) => i.id === id))
      .filter(Boolean)
      .map((i) => i!.url);

    if (selected.length === 1) {
      // 单张直接下载（使用 helper）
      const filename = taskImages.find((i) => i.id === selectedImages[0])?.name || 'image.png';
      await downloadUrl(selected[0], filename);
      return;
    }

    // 多张图片时打包为 ZIP 下载，避免浏览器限制多次自动下载
    const baseFilename = `downloaded-${Date.now()}`;
    const result = await downloadZip(selected, baseFilename);
    if (!result.success) {
      console.error('批量打包下载失败', result.message);
    }
  };

  // 确认批量删除
  const confirmBatchDelete = async () => {
    setShowBatchDeleteConfirm(false);
    try {
      await handleBatchDelete();
    } catch (e) {
      console.error('批量删除确认失败', e);
    }
  };


  // 确认批量下载
  const confirmBatchDownload = async () => {
    setShowBatchDownloadConfirm(false);
    try {
      await handleBatchDownload();
    } catch (e) {
      console.error('批量下载确认失败', e);
    }
  };

  // 下载单张图片，找不到对应图片则不执行
  const handleDownload = useCallback(async (id: string) => {
    const img = taskImages.find((i) => i.id === id);
    if (!img) return;
    await downloadUrl(img.url, img.name || 'image.png');
  }, [taskImages]);

  // 删除单张图片：调用批量删除接口并从 UI 中移除对应条目
  const handleDelete = useCallback(async (id: string) => {
    try {
      const userId = getUserId();
      const img = taskImages.find((i) => i.id === id);
      const idToSend = img?.imgId || id;
      await http.post(`/gallery/imgs/batch-delete?user_id=${userId}`, { ids: [idToSend] });
      setTaskImages((prev) => prev.filter((i) => i.id !== id));
    } catch (e) {
      console.error('删除失败', e);
    }
  }, [taskImages, setTaskImages]);

  // 确认应用待定筛选器
  const applyPendingFilter = () => {
    if (pendingFilter) {
      // 先清空选择再应用筛选
      setSelectedImages([]);
      try {
        pendingFilter();
      } catch (e) {
        console.error('应用筛选失败', e);
      }
    }
    setPendingFilter(null);
    setPendingDescriptor(null);
    setShowFilterConfirm(false);
  };

  // 当 activeTab 变化时，清理 selectedImages 中不再可见的图片 ID
  useEffect(() => {
    setSelectedImages((prev) =>
      prev.filter((id) =>
        taskImages.some((i) =>
          i.id === id &&
          (activeTab === 'all' || (activeTab === 'uploaded' && i.sourceType === 'UPLOAD') || (activeTab === 'generated' && i.sourceType === 'GENERATE') || (activeTab === 'sended' && i.sourceType === 'SEND'))
        )
      )
    );
  }, [activeTab, taskImages]);

  // 内存优化，窗口化渲染：当页码变化时清理过旧图片数据
  useEffect(() => {
    if (!windowedPages || windowedPages <= 0) return;

    setTaskImages((prev) => {
      const minAll = Math.max(0, page - windowedPages + 1);
      const minUploads = Math.max(0, pageUploads - windowedPages + 1);
      const minDesigns = Math.max(0, pageDesigns - windowedPages + 1);
      const minSended = Math.max(0, pageSended - windowedPages + 1);

      return prev.filter((img: any) => {
        const p = typeof (img as any).__page === 'number' ? (img as any).__page : null;
        const sourceKey = (img as any).__sourceKey || (img.sourceType === 'UPLOAD' ? 'uploaded' : img.sourceType === 'GENERATE' ? 'generated' : img.sourceType === 'SEND' ? 'sended' : 'all');

        // 如果没有页元数据则保留（保守策略）
        if (p === null) return true;
        if (sourceKey === 'uploaded') return p >= minUploads;
        if (sourceKey === 'generated') return p >= minDesigns;
        if (sourceKey === 'sended') return p >= minSended;
        return p >= minAll;
      }) as GalleryImage[];
    });
  }, [page, pageUploads, pageDesigns, pageSended, windowedPages]);

  // 更新图片信息（名称、标签）
  const handleImageUpdate = async (imageId: string, updates: { name?: string; tags?: string[] }) => {
    try {
      setTaskImages(prev => prev.map(img => {
        if (img.id === imageId) {
          return {
            ...img,
            name: updates.name || img.name,
            tags: updates.tags || img.tags
          };
        }
        return img;
      }));
      // 将更新发送到服务器
      const img = taskImages.find(i => i.id === imageId);
      if (img) {
        await http.post('/img/update', {
          img_id: img.imgId,
          img_name: updates.name,
          tags: updates.tags
        });
      }
    } catch (error) {
      console.error('更新图片失败:', error);
    }
  };

  // 计算各种图片总数
  const totalCount = typeof total === 'number' && total !== null ? total : taskImages.length;
  const uploadedCount = typeof totalUploads === 'number' && totalUploads !== null
    ? totalUploads
    : taskImages.filter((i) => i.sourceType === 'UPLOAD').length;
  const sendCount = typeof totalSended === 'number' && totalSended !== null
    ? totalSended
    : taskImages.filter((i) => i.sourceType === 'SEND').length;
  const generatedCount = typeof totalDesigns === 'number' && totalDesigns !== null
    ? totalDesigns
    : Math.max(0, totalCount - uploadedCount - sendCount);

    // 视图模式变化时刷新网格布局
  useEffect(() => {
    try {
      scheduleGridRefresh();
    } catch (e) { /* ignore */ }
  }, [renderedVisibleImages.length, viewMode]);

  return (
    <div className="p-6 bg-gradient-to-br from-background via-background to-muted/20">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">我的图库</h1>
        <p className="text-muted-foreground text-sm mt-1">管理您上传和生成的所有图片</p>
      </div>

      <GalleryToolbar
        activeTab={activeTab}
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
        filterTags={filterTags}
        onFilterTagsChange={handleFilterTagsChange}
        filterSourceType={filterSourceType}
        onFilterSourceTypeChange={handleFilterSourceTypeChange}
        sortBy={sortBy}
        onSortByChange={handleSortByChange}
        onEnterSelectionMode={enterSelectionMode}
        totalCount={totalCount}
        uploadedCount={uploadedCount}
        generatedCount={generatedCount}
        sendCount={sendCount}
        actionFilter={actionFilter}
        onActionFilterChange={handleActionFilterChange}
        aiTools={AI_ACTIONS}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        selectionMode={selectionMode}
      />

      {selectionMode && (
        <BatchToolbar
          selectedCount={selectedImages.length}
          visibleIds={renderedVisibleImages.map((i) => i.id)}
          selectedIds={selectedImages}
          onExit={exitSelectionMode}
          onSelectAllVisible={selectAllVisible}
          onBatchDownload={() => { setShowBatchDownloadConfirm(true); }}
          onBatchDelete={() => { setShowBatchDeleteConfirm(true); }}
        />
      )}

      {visibleImages.length === 0 ? (
        <Card className="p-12">
          <div className="text-center space-y-3">
            <FolderOpen className="w-16 h-16 mx-auto text-muted-foreground opacity-20" />
            <h3 className="font-medium">暂无图片</h3>
            <p className="text-sm text-muted-foreground">开始上传或生成您的第一张图片吧</p>
          </div>
        </Card>
      ) : (
        <>
          {viewMode === 'grid' ? (
            <div ref={containerRef} className="gallery-grid-wrapper">
              <GridView
                items={renderedVisibleImages}
                renderItem={renderGridItem}
                gridRef={gridRef}
                containerRef={containerRef}
                showSkeletons={isLoading && renderedVisibleImages.length === 0}
                skeletonCount={20}
                placeholderSrc={defaultGrid}
                gap={GALLERY_DEFAULT_GAP}
              />
            </div>
          ) : (
            <div className="space-y-3">
              {renderedVisibleImages.map((img) => (
                <div key={img.id}>
                  <ListImageCard
                    image={img}
                    onClick={handleImageClick}
                    onDownload={handleDownload}
                    onDelete={handleDelete}
                    onViewDetails={handleImageClick}
                    onViewSeamless={handleViewSeamless}
                    selected={selectedImages.includes(img.id)}
                    onImageLoad={() => {
                      scheduleGridRefresh();
                    }}
                  />
                </div>
              ))}
              {/* Skeletons placeholders for list view */}
              {isLoading && renderedVisibleImages.length === 0 && (
                <ListImageCardSkeletons count={Math.min(size, 6)} placeholderSrc={defaultGrid} />
              )}
            </div>
          )}
        </>
      )}

      <div ref={sentinelRef} aria-hidden="true" style={{ width: '1px', height: '1px' }} />

      {/* Uploaded image preview dialog */}
      {previewImage && previewImage.sourceType === 'UPLOAD' && (
        <UploadImagePreview 
          open={showPreview} 
          onOpenChange={setShowPreview} 
          image={previewImage} 
          onUpdate={handleImageUpdate}
          onDownload={handleDownload}
          onDelete={handleDelete}
        />
      )}

      {/* Generated image preview dialog */}
      {previewImage && previewImage.sourceType === 'GENERATE' && (
        <GeneratedImagePreview
          open={showGeneratedPreview}
          onOpenChange={(open) => setShowGeneratedPreview(open)}
          image={previewImage}
          onDownload={(id) => handleDownload(id)}
          onDelete={(id) => handleDelete(id)}
        />
      )}

      {/* 拼接结果预览对话框 */}
      {selectedSeamlessImage && (
        <SeamlessPreviewDialog
          open={showSeamlessPreview}
          onOpenChange={setShowSeamlessPreview}
          task={selectedSeamlessImage}
          onDownload={() => {
            handleDownload(selectedSeamlessImage.id);
          }}
        />
      )}

      {/* 过滤筛选更改确认对话框 */}
      <Dialog open={showFilterConfirm} onOpenChange={() => setShowFilterConfirm(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认更改筛选</DialogTitle>
          </DialogHeader>
          <div className="py-2">当前已选择 {selectedImages.length} 张图片，更改筛选后将清空当前选择。是否继续？</div>
          <DialogFooter>
            <div className="flex gap-2 justify-end w-full">
              <Button variant="outline" onClick={() => { setPendingFilter(null); setPendingDescriptor(null); setShowFilterConfirm(false); }}>取消</Button>
              <Button onClick={applyPendingFilter}>继续</Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 批量删除确认对话框 */}
      <Dialog open={showBatchDeleteConfirm} onOpenChange={() => setShowBatchDeleteConfirm(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`确认删除 ${selectedImages.length} 张图片？`}</DialogTitle>
          </DialogHeader>
          <div className="py-2">{`您将删除 ${selectedImages.length} 张图片，删除后无法恢复。是否确认删除？`}</div>
          <DialogFooter>
            <div className="flex gap-2 justify-end w-full">
              <Button variant="outline" onClick={() => { setShowBatchDeleteConfirm(false); }}>取消</Button>
              <Button
                onClick={confirmBatchDelete}
                className="ml-2"
              >
                删除
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 批量下载确认对话框 */}
      <Dialog open={showBatchDownloadConfirm} onOpenChange={() => setShowBatchDownloadConfirm(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`确认下载 ${selectedImages.length} 张图片？`}</DialogTitle>
          </DialogHeader>
          <div className="py-2">{`您将下载 ${selectedImages.length} 张图片，是否确认下载？`}</div>
          <DialogFooter>
            <div className="flex gap-2 justify-end w-full">
              <Button variant="outline" onClick={() => { setShowBatchDownloadConfirm(false); }}>取消</Button>
              <Button
                onClick={confirmBatchDownload}
                className="ml-2"
              >
                下载
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default PersonalGalleryPage;
