import React, { useRef, useEffect, useState } from 'react';
import { MasonryInfiniteGrid } from '@egjs/react-infinitegrid';
import { getGridColumns } from '@/utils/galleryUtils';
import { GALLERY_IMAGE_MIN_WIDTH } from '@/constants/gallery';
import { useSidebarSettled } from '@/hooks/useSidebarSettled';

interface GridViewProps {
  items: any[];
  renderItem: (item: any, index: number) => React.ReactNode;
  gap?: number; // 默认 12px
  gridRef?: React.Ref<any>;
  containerRef?: React.Ref<HTMLDivElement>;
  showSkeletons?: boolean;
  skeletonCount?: number;
  placeholderSrc?: string;
}

export const GridView: React.FC<GridViewProps> = ({
  items,
  renderItem,
  gap = 12,
  gridRef,
  containerRef,
  showSkeletons,
  skeletonCount,
  placeholderSrc,
}) => {
  const internalGridRef = useRef<any>(null);
  const internalContainerRef = useRef<HTMLDivElement | null>(null);
  const [itemWidth, setItemWidth] = useState<number | null>(null);
  const [columns, setColumns] = useState<number>(1);
  const [placeholderAspect, setPlaceholderAspect] = useState<number | null>(null);

  // callback ref to forward to parent-provided refs (works for object refs and function refs)
  const setContainerRef = (el: HTMLDivElement | null) => {
    internalContainerRef.current = el;
    if (!containerRef) return;
    if (typeof containerRef === 'function') {
      try { (containerRef as (instance: HTMLDivElement | null) => void)(el); } catch (e) { /* ignore */ }
    } else {
      try { (containerRef as React.MutableRefObject<HTMLDivElement | null>).current = el; } catch (e) { /* ignore */ }
    }
  };

  const setGridRef = (instance: any) => {
    internalGridRef.current = instance;
    if (!gridRef) return;
    if (typeof gridRef === 'function') {
      try { (gridRef as (inst: any) => void)(instance); } catch (e) { /* ignore */ }
    } else {
      try { (gridRef as React.MutableRefObject<any>).current = instance; } catch (e) { /* ignore */ }
    }
  };

  const updateLayout = () => {
    const container = internalContainerRef.current;
    if (!container) return;  // 防御性检查
    // Use clientWidth when possible (excludes scrollbar) and fall back to
    // bounding rect. This tends to match layout sizing used by the grid.
    const measuredWidth = (typeof container.clientWidth === 'number' && container.clientWidth > 0)
      ? container.clientWidth
      : (container.getBoundingClientRect().width || container.offsetWidth || 0);
    const width = Math.max(0, measuredWidth);
    if (width <= 0) return; // defensive

    let newColumns = Math.max(1, getGridColumns(width));
    let totalGap = gap * Math.max(0, newColumns - 1);
    let columnWidth = Math.floor((width - totalGap) / newColumns);
    const minW = typeof GALLERY_IMAGE_MIN_WIDTH === 'number' && GALLERY_IMAGE_MIN_WIDTH > 0 ? GALLERY_IMAGE_MIN_WIDTH : 200;

    // Reduce columns if columnWidth is less than minimum allowed.
    while (newColumns > 1 && columnWidth < minW) {
      newColumns -= 1;
      totalGap = gap * Math.max(0, newColumns - 1);
      columnWidth = Math.floor((width - totalGap) / newColumns);
    }

    // For the final columnWidth, ensure the total content width fits the container.
    // If it doesn't, adjust columnWidth to exactly fit the container (avoid overflow).
    const contentWidth = newColumns * columnWidth + totalGap;
    if (contentWidth > width) {
      // If only 1 column, make it fill the available width (minus gaps, though gaps=0)
      if (newColumns === 1) {
        columnWidth = Math.max(0, Math.floor(width - totalGap));
      } else {
        // Reduce columnWidth to fit. Compute floor to keep integers.
        columnWidth = Math.max(0, Math.floor((width - totalGap) / newColumns));
      }
    }

    // Final safety clamp
    columnWidth = Math.max(0, Math.floor(columnWidth));
    setItemWidth(columnWidth);
    setColumns(newColumns);
    const g = internalGridRef.current as any;
    const inst = (g && (typeof g.getInstance === 'function' ? g.getInstance() : g._grid)) || g;

    try {
      if (inst && typeof inst.setOptions === 'function') {
        try { inst.setOptions({ column: newColumns, columnSize: columnWidth, gap }); } catch (e) { /* ignore */ }
      } else if (g && typeof g.setOptions === 'function') {
        try { g.setOptions({ column: newColumns, columnSize: columnWidth, gap }); } catch (e) { /* ignore */ }
      }

      // Force layout/relayout
      if (inst && typeof inst.layout === 'function') {
        try { inst.layout(true); } catch (e) { try { inst.layout(); } catch (ee) { /* ignore */ } }
      } else if (g && typeof g.layout === 'function') {
        try { g.layout(true); } catch (e) { try { g.layout(); } catch (ee) { /* ignore */ } }
      }
    } catch (e) {
      // ignore
    }
  };

  useEffect(() => {
    updateLayout();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => updateLayout()) : null;
    try { if (ro && internalContainerRef.current) ro.observe(internalContainerRef.current); } catch (e) { /* ignore */ }
    window.addEventListener('resize', updateLayout);
    return () => {
      try { if (ro) ro.disconnect(); } catch (e) { /* ignore */ }
      window.removeEventListener('resize', updateLayout);
    };
  }, [items.length, gap]);

  // Measure placeholder image aspect ratio so skeleton heights match
  useEffect(() => {
    if (!placeholderSrc) {
      setPlaceholderAspect(null);
      return;
    }
    let mounted = true;
    try {
      const img = new Image();
      img.src = placeholderSrc;
      img.onload = () => {
        if (!mounted) return;
        if (img.naturalHeight > 0) setPlaceholderAspect(img.naturalWidth / img.naturalHeight);
      };
      img.onerror = () => {
        if (!mounted) return;
        setPlaceholderAspect(4 / 3);
      };
    } catch (e) {
      setPlaceholderAspect(4 / 3);
    }
    return () => { mounted = false; };
  }, [placeholderSrc]);

  // wait for sidebar to settle (if it toggles) then relayout
  const sidebarSettledKey = useSidebarSettled(internalContainerRef, 100);
  useEffect(() => {
    if (sidebarSettledKey > 0) {
      try { updateLayout(); } catch (e) { /* ignore */ }
    }
  }, [sidebarSettledKey]);

  // Clear the internal load guard when items length changes (typically when
  // a successful load appended new items). This allows the next requestAppend
  // to trigger another load. If the length doesn't change (no more data), the
  // guard remains set so we don't continuously call the API.
  useEffect(() => {
    const ref = (internalGridRef as any).__loadGuardRef as { current: boolean } | undefined;
    if (!ref) return;
    // If items length changed (increase/decrease), clear guard so future
    // requestAppend events can trigger a new load.
    try {
      ref.current = false;
    } catch (e) { /* ignore */ }
  }, [items.length]);

  return (
    <div ref={setContainerRef} className="w-full">
      {/** If requested and there are no items yet, render placeholder skeletons
          sized to the computed column width rather than using a generic
          CSS min-width. This ensures the skeletons match the final layout
          and avoids clipping/flicker. */}
      {showSkeletons && items.length === 0 ? (
        <div
          className="gallery-grid-skeletons"
          style={{
            display: 'grid',
            gap: `${gap}px`,
            marginTop: `${gap}px`,
            gridTemplateColumns: itemWidth && columns ? `repeat(${columns}, ${itemWidth}px)` : 'repeat(auto-fill, minmax(200px, 1fr))',
          }}
        >
          {Array.from({ length: skeletonCount || 20 }).map((_, i) => {
            const w = itemWidth || 200;
            const h = placeholderAspect ? Math.max(24, Math.round(w / placeholderAspect)) : Math.round(w * 3 / 4);
            return (
              <div key={`s-${i}`} className="p-0">
                <div className="overflow-hidden rounded-lg border bg-muted/10" style={{ width: '100%', height: `${h}px` }}>
                  <img src={placeholderSrc as string} alt="placeholder" className="block w-full h-full object-cover" />
                </div>
                <div className="mt-2">
                  <div className="h-3 bg-muted/20 rounded w-3/4" />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <MasonryInfiniteGrid
          ref={setGridRef}
          gap={gap}
          column={internalContainerRef.current ? getGridColumns(Math.max(0, internalContainerRef.current.clientWidth || internalContainerRef.current.getBoundingClientRect().width)) : 1}
          container={true}
          containerTag="div"
          className="eg-infinitegrid"
          useResizeObserver={true}
          observeChildren={true}
        >
          {items.map((item, index) => (
            <div key={(item && (item.id ?? item.key)) || index} className="eg-item" style={{ maxWidth: itemWidth || '100%' }}>
              {renderItem(item, index)}
            </div>
          ))}
        </MasonryInfiniteGrid>
      )}
    </div>
  );
};

export default GridView;