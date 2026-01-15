import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ZoomIn, ZoomOut, RotateCcw, X, Move, ChevronLeft, ChevronRight } from 'lucide-react';
import { useImageZoom } from '@/hooks/useImageZoom';
import { cn } from '@/components/ui/utils';
import { VisuallyHidden } from '@/components/ui/visually-hidden';

interface ImagePreviewProps {
  open: boolean;
  onClose: () => void;
  images: string[];
  initialIndex?: number;
  title?: string;
}

export function ImagePreview({
  open,
  onClose,
  images,
  initialIndex = 0,
  title = "图片预览",
}: ImagePreviewProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  
  // Reset index when opening
  useEffect(() => {
    if (open) {
      setCurrentIndex(initialIndex);
    }
  }, [open, initialIndex]);

  // Use the shared hook for zoom/pan logic
  const { 
    scale, 
    position, 
    isDragging, 
    handlers, 
    actions,
    containerRef 
  } = useImageZoom({
    minScale: 0.1,
    maxScale: 5,
    initialScale: 1,
  });

  // Reset zoom when opening or changing index
  useEffect(() => {
    if (open) {
      actions.resetZoom();
    }
  }, [open, actions.resetZoom]);

  useEffect(() => {
    actions.resetZoom();
  }, [currentIndex, actions.resetZoom]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return;
      
      switch (e.key) {
        case 'ArrowLeft':
          setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
          break;
        case 'ArrowRight':
          setCurrentIndex((prev) => (prev + 1) % images.length);
          break;
        case 'Escape':
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, images.length, onClose]);

  const handlePrev = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev - 1 + images.length) % images.length);
  }, [images.length]);

  const handleNext = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev + 1) % images.length);
  }, [images.length]);

  if (!open || images.length === 0) return null;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent 
        className="max-w-none sm:max-w-none p-0 bg-white dark:bg-zinc-900 border-none shadow-2xl overflow-hidden rounded-xl flex flex-col"
        style={{ 
          width: 'min(90vw, 92vh)', 
          height: 'min(90vw, 92vh)', 
          maxWidth: '100vw', 
          maxHeight: '100vh',
          aspectRatio: '1 / 1'
        }}
        showCloseButton={false}
      >
        <VisuallyHidden>
            <DialogTitle>{title}</DialogTitle>
        </VisuallyHidden>

        {/* Toolbar */}
        <div 
          className="absolute top-0 left-0 right-0 z-50 flex items-center justify-between px-6 h-[44px] border-b border-border/10"
          style={{ backgroundColor: 'rgba(240,240,240,0.95)' }}
        >
          <div className="text-foreground text-sm font-medium px-2">
            {title} ({currentIndex + 1}/{images.length})
          </div>
          
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={actions.zoomOut}
              className="w-8 h-8 text-muted-foreground hover:text-foreground hover:bg-black/5 rounded-full"
              title="缩小"
            >
              <ZoomOut className="w-4 h-4" />
            </Button>
            
            <span className="text-muted-foreground text-xs w-10 text-center font-mono select-none">
              {Math.round(scale * 100)}%
            </span>
            
            <Button
              variant="ghost"
              size="icon"
              onClick={actions.zoomIn}
              className="w-8 h-8 text-muted-foreground hover:text-foreground hover:bg-black/5 rounded-full"
              title="放大"
            >
              <ZoomIn className="w-4 h-4" />
            </Button>

            <div className="w-px h-4 bg-border/40 mx-2" />

            <Button
              variant="ghost"
              size="icon"
              onClick={actions.resetZoom}
              className="w-8 h-8 text-muted-foreground hover:text-foreground hover:bg-black/5 rounded-full"
              title="重置"
            >
              <RotateCcw className="w-4 h-4" />
            </Button>

            <div className="w-px h-4 bg-border/40 mx-2" />

            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="w-8 h-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full"
              title="关闭"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Main Content */}
        <div 
          ref={containerRef}
          className={cn(
            "flex-1 w-full h-full overflow-hidden relative touch-none bg-slate-50 dark:bg-zinc-950/50",
            isDragging ? "cursor-grabbing" : scale > 1 ? "cursor-grab" : "cursor-default"
          )}
          {...handlers}
        >
          {/* Image Container with Transform */}
          <div 
            className="w-full h-full flex items-center justify-center transition-transform duration-75 ease-linear will-change-transform pt-14 pb-4 px-4"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
              transformOrigin: 'center center',
            }}
          >
            <img 
              src={images[currentIndex]} 
              alt={`Preview ${currentIndex + 1}`}
              className="max-w-full max-h-full object-contain select-none shadow-sm"
              draggable={false}
            />
          </div>

          {/* Navigation Arrows (Only show if multiple images) */}
          {images.length > 1 && (
            <>
              <Button
                variant="ghost"
                size="icon"
                onClick={handlePrev}
                className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/80 hover:bg-white text-foreground/70 hover:text-foreground border shadow-sm transition-all z-20"
              >
                <ChevronLeft className="w-6 h-6" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleNext}
                className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/80 hover:bg-white text-foreground/70 hover:text-foreground border shadow-sm transition-all z-20"
              >
                <ChevronRight className="w-6 h-6" />
              </Button>
            </>
          )}

          {/* Helper Hint */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 px-4 py-1.5 rounded-full bg-white/90 backdrop-blur-sm border shadow-sm text-muted-foreground text-xs flex items-center gap-2 pointer-events-none opacity-0 hover:opacity-100 transition-opacity duration-300 select-none group-hover:opacity-100">
            <Move className="w-3 h-3" />
            <span>滚轮缩放 · 拖拽移动</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ImagePreview;
