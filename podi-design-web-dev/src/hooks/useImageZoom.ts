import React, { useState, useCallback, useRef, useEffect } from 'react';
import { toast } from 'sonner';

interface Position {
  x: number;
  y: number;
}

interface UseImageZoomProps {
  initialScale?: number;
  minScale?: number;
  maxScale?: number;
}

export function useImageZoom({
  initialScale = 1,
  minScale = 0.1, // 10%
  maxScale = 5,   // 500%
}: UseImageZoomProps = {}) {
  const [scale, setScale] = useState(initialScale);
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<Position | null>(null);

  // Callback ref to manage the element reference robustly
  // This is crucial for Dialog/Portal usage where the ref might change or be set after initial render
  const [containerEl, setContainerEl] = useState<HTMLDivElement | null>(null);
  const containerRef = useCallback((node: HTMLDivElement | null) => {
    setContainerEl(node);
  }, []);

  const handleWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();

      // Normalize delta
      // Common standard: deltaY is in pixels (approx) or lines.
      // We want a consistent feel.
      // Standard mouse wheel: ~100 per tick.
      // Trackpad: ~1-10 per tick (continuous).
      
      let deltaY = e.deltaY;
      
      // Normalize deltaMode
      if (e.deltaMode === 1) { // DOM_DELTA_LINE
        deltaY *= 40;
      } else if (e.deltaMode === 2) { // DOM_DELTA_PAGE
        deltaY *= 800;
      }

      // Universal sensitivity: 0.002 per pixel of delta
      // 100 pixels (one mouse notch) -> 0.2 scale change (20%)
      // 10 pixels (trackpad swipe) -> 0.02 scale change (2%)
      const sensitivity = 0.002;
      const delta = -deltaY * sensitivity;

      setScale((prevScale) => {
        // Linear zoom addition
        const newScale = prevScale + delta;
        const clamped = Math.min(Math.max(newScale, minScale), maxScale);
        
        // Optional: Show toast at limits? (Maybe too spammy on wheel)
        return clamped;
      });
    },
    [minScale, maxScale]
  );

  useEffect(() => {
    if (!containerEl) return;
    
    // Attach non-passive listener to prevent browser zoom/scroll
    containerEl.addEventListener('wheel', handleWheel, { passive: false });
    
    return () => {
      containerEl.removeEventListener('wheel', handleWheel);
    };
  }, [containerEl, handleWheel]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Allow dragging if scale > minScale OR explicitly if user wants to pan at 100%
      // (Usually dragging is useful when content > container, but here we just allow it generally)
      if (true) {
        setIsDragging(true);
        dragStartRef.current = { x: e.clientX - position.x, y: e.clientY - position.y };
        e.preventDefault();
      }
    },
    [position]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isDragging && dragStartRef.current && containerEl) {
        const rawX = e.clientX - dragStartRef.current.x;
        const rawY = e.clientY - dragStartRef.current.y;

        const { clientWidth, clientHeight } = containerEl;
        
        // Calculate boundaries based on current scale
        // Limit X/Y so image center doesn't go too far
        const limitX = Math.max(0, (clientWidth * scale - clientWidth) / 2);
        const limitY = Math.max(0, (clientHeight * scale - clientHeight) / 2);

        const clampedX = Math.max(-limitX, Math.min(limitX, rawX));
        const clampedY = Math.max(-limitY, Math.min(limitY, rawY));

        setPosition({ x: clampedX, y: clampedY });
      }
    },
    [isDragging, scale, containerEl]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  // --- Touch Support ---
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      setIsDragging(true);
      const touch = e.touches[0];
      dragStartRef.current = { x: touch.clientX - position.x, y: touch.clientY - position.y };
    }
  }, [position]);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (isDragging && dragStartRef.current && containerEl && e.touches.length === 1) {
      const touch = e.touches[0];
      const rawX = touch.clientX - dragStartRef.current.x;
      const rawY = touch.clientY - dragStartRef.current.y;

      const { clientWidth, clientHeight } = containerEl;
      const limitX = Math.max(0, (clientWidth * scale - clientWidth) / 2);
      const limitY = Math.max(0, (clientHeight * scale - clientHeight) / 2);

      const clampedX = Math.max(-limitX, Math.min(limitX, rawX));
      const clampedY = Math.max(-limitY, Math.min(limitY, rawY));

      setPosition({ x: clampedX, y: clampedY });
    }
  }, [isDragging, scale, containerEl]);

  const handleTouchEnd = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  // Actions
  const zoomIn = useCallback(() => {
    setScale((prev) => {
      const next = Math.min(prev + 0.25, maxScale);
      if (next === maxScale && prev !== maxScale) toast.info('已达到最大缩放比例');
      return next;
    });
  }, [maxScale]);

  const zoomOut = useCallback(() => {
    setScale((prev) => {
      const next = Math.max(prev - 0.25, minScale);
      if (next === minScale && prev !== minScale) toast.info('已达到最小缩放比例');
      return next;
    });
  }, [minScale]);

  const resetZoom = useCallback(() => {
    setScale(initialScale);
    setPosition({ x: 0, y: 0 });
  }, [initialScale]);

  const setScaleExplicit = useCallback((newScale: number) => {
    const clamped = Math.min(Math.max(newScale, minScale), maxScale);
    setScale(clamped);
  }, [minScale, maxScale]);

  return {
    scale,
    position,
    isDragging,
    containerRef, // This is now a callback ref
    handlers: {
      onMouseDown: handleMouseDown,
      onMouseMove: handleMouseMove,
      onMouseUp: handleMouseUp,
      onMouseLeave: handleMouseLeave,
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd,
    },
    actions: {
      zoomIn,
      zoomOut,
      resetZoom,
      setScale: setScaleExplicit,
    },
  };
}

export default useImageZoom;
