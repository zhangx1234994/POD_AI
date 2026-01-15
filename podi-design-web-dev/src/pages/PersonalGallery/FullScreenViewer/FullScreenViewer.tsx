import { useState, useEffect } from 'react';
import { useImageZoom } from '@/hooks/useImageZoom';
import { Toolbar, ViewMode } from './Toolbar';
import { SplitMode } from './SplitMode';
import { SliderMode } from './SliderMode';
import { OverlayMode } from './OverlayMode';
import { SeamlessMode } from './SeamlessMode';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Lightbulb } from 'lucide-react';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';

interface FullScreenViewerProps {
  isOpen: boolean;
  onClose: () => void;
  originalUrl: string;
  generatedUrl: string;
  /** 如果为 true，则让 Dialog 内容铺满整个视口（真正的全屏弹窗） */
  isFullscreen?: boolean;
  isSeamless?: boolean;
  patternType?: string | undefined;
  generatedUrls?: string[];
};

export function FullScreenViewer({
  isOpen,
  onClose,
  originalUrl,
  generatedUrl,
  isFullscreen = false,
  isSeamless = false,
  patternType,
  generatedUrls = [],
}: FullScreenViewerProps) {
  const [mode, setMode] = useState<ViewMode>('split');
  
  // Reset mode to 'split' when opened
  useEffect(() => {
    if (isOpen) {
      setMode('split');
    }
  }, [isOpen]);

  const { 
    scale, 
    position, 
    isDragging, 
    handlers, 
    actions,
    containerRef 
  } = useImageZoom({
    minScale: 0.1, // 10%
    maxScale: 5,   // 500%
    initialScale: 1,
  });

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Ensure cursor is reset when closing/unmounting
  useEffect(() => {
    return () => {
      document.body.style.cursor = '';
    };
  }, []);

  const contentClass = isFullscreen
    ? 'inset-0 top-0 left-0 translate-x-0 translate-y-0 w-full h-full max-w-none max-h-none rounded-none p-0 overflow-y-auto'
    : 'w-full max-w-[1800px] w-screen overflow-y-auto max-h-[90vh]';

  const outerClass = isFullscreen
    ? 'relative flex-1 w-full h-full min-h-0 overflow-hidden flex flex-col'
    : 'relative flex-1 w-full min-h-0 overflow-hidden flex flex-col';

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent showCloseButton={false} className={contentClass} isFullscreen={isFullscreen} aria-label="全屏图片对比">
        <VisuallyHidden>
          <DialogTitle>全屏图片对比</DialogTitle>
        </VisuallyHidden>
        <div className={outerClass}>
          <Toolbar 
            mode={mode} 
            onModeChange={setMode}
            scale={scale}
            onZoomIn={actions.zoomIn}
            onZoomOut={actions.zoomOut}
            onResetZoom={actions.resetZoom}
            onScaleChange={actions.setScale}
            onClose={onClose}
            className="shrink-0 relative border-b"
            isSeamless={isSeamless}
          />
          
          <div 
            ref={containerRef}
            className={"flex-1 w-full min-h-0 relative  bg-muted/10 " + (isFullscreen ? 'h-full' : '')}
          >
            {mode === 'split' && (
              <SplitMode 
                originalUrl={originalUrl} 
                generatedUrl={generatedUrl} 
                scale={scale}
                position={position}
                isDragging={isDragging}
                handlers={handlers}
              />
            )}
            {mode === 'slider' && (
              <SliderMode 
                originalUrl={originalUrl} 
                generatedUrl={generatedUrl} 
                scale={scale}
                position={position}
                isDragging={isDragging}
                handlers={handlers}
              />
            )}
            {mode === 'overlay' && (
              <OverlayMode 
                originalUrl={originalUrl} 
                generatedUrl={generatedUrl} 
                scale={scale}
                position={position}
                isDragging={isDragging}
                handlers={handlers}
                mode={mode}
              />
            )}
            {mode === 'seamless' && (
              <SeamlessMode 
                generatedUrl={generatedUrl}
                generatedUrls={generatedUrls}
                patternType={patternType}
                scale={scale}
                position={position}
                isDragging={isDragging}
                handlers={handlers}
              />
            )}
          </div>

          {/* Footer Hint */}
          <div className="shrink-0 h-8 flex items-center justify-center bg-muted/30 border-t text-xs text-muted-foreground gap-2 select-none">
            <Lightbulb className="w-3 h-3 text-yellow-500" />
            <span>鼠标滚轮缩放 | 拖拽移动</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default FullScreenViewer;
