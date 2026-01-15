import { UnifiedViewerContainer } from './UnifiedViewerContainer';
import { CornerLabel } from '@/components/icons/CornerLabel';

interface SplitModeProps {
  originalUrl: string;
  generatedUrl: string;
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  handlers: any;
}

export function SplitMode({
  originalUrl,
  generatedUrl,
  scale,
  position,
  isDragging,
  handlers,
}: SplitModeProps) {
  return (
    <UnifiedViewerContainer
      referenceUrl={generatedUrl}
      scale={scale}
      position={position}
      isDragging={isDragging}
      handlers={handlers}
      disableTransform={true}
    >
      {/* 
          Split View Overlay 
          Positioned absolutely over the sizing image (via UnifiedViewerContainer).
          Grid layout for side-by-side comparison.
      */}
      <div className="absolute inset-0 grid grid-cols-2 gap-1 bg-background">
          
          {/* Left Pane: Generated Image */}
          <div className="relative overflow-hidden w-full h-full group flex items-center justify-center bg-black/5">
            <img
              src={generatedUrl}
              alt="结果图"
              className="max-w-full max-h-full object-contain will-change-transform"
              style={{
                transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                transformOrigin: 'center',
              }}
              draggable={false}
            />
            {/* Counter-scaled container for the label 
                Since the image scales, we want the label to stay fixed relative to the PANE?
                Or move with the image? 
                Usually fixed to the pane corner is better for UI.
                If I put it here, it's inside the overflow-hidden pane.
                If I want it fixed to the pane corner, I should put it outside the transform, 
                but inside the pane.
                My current structure puts it as sibling to img.
                Since img is transformed but the parent div is NOT (due to disableTransform on container),
                the label will stay fixed at top-left of the pane.
                This is correct.
            */}
            <div 
              className="absolute top-0 left-0 z-20 pointer-events-none" 
              style={{ 
                width: '72px', 
                height: '72px' 
              }}
            >
              <CornerLabel variant="result" />
            </div>
          </div>

          {/* Right Pane: Original Image */}
          <div className="relative overflow-hidden w-full h-full group flex items-center justify-center bg-black/5">
            <img
              src={originalUrl}
              alt="原图"
              className="max-w-full max-h-full object-contain will-change-transform"
              style={{
                transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                transformOrigin: 'center',
              }}
              draggable={false}
            />
            {/* Counter-scaled container for the label */}
            <div 
              className="absolute top-0 left-0 z-20 pointer-events-none" 
              style={{ 
                width: '72px', 
                height: '72px' 
              }}
            >
              <CornerLabel variant="original" />
            </div>
          </div>
      </div>
    </UnifiedViewerContainer>
  );
};

export default SplitMode;
