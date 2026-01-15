import React, { forwardRef } from 'react';
import { cn } from '@/components/ui/utils';

interface UnifiedViewerContainerProps {
  referenceUrl: string;
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  handlers: any;
  children: React.ReactNode;
  fixedContent?: React.ReactNode;
  mode?: any;
  disableTransform?: boolean;
}

export const UnifiedViewerContainer = forwardRef<HTMLDivElement, UnifiedViewerContainerProps>(
  ({ referenceUrl, scale, position, isDragging, handlers, children, fixedContent, mode, disableTransform = false }, ref) => {
    return (
      <div 
        className={cn(
          "UnifiedViewerContainer relative w-full h-full overflow-hidden select-none bg-transparent touch-none",
          isDragging ? "cursor-grabbing" : scale > 1 ? "cursor-grab" : "cursor-default"
        )}
        {...handlers}
      >
        {/* Fixed UI Elements (that shouldn't scale/move) */}
        {fixedContent}

        {/* Center the content in the viewport */}
        <div className="w-full h-full flex items-center justify-center px-4">
          
          {/* 
              The Transformed Content Container 
              This is the single source of truth for dimensions across all modes.
          */}
          <div 
            ref={ref}
            className="w-full h-full relative"
            style={disableTransform ? undefined : {
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
              transformOrigin: 'center',
              willChange: 'transform'
            }}
          >
            {/* 
                Sizing Reference Image (Hidden)
                This forces the container to take the exact dimensions of the image
                constrained by the viewport (max-w/max-h).
                All modes use this to ensure pixel-perfect alignment.
            */}
            {mode === 'overlay' && (
              <img
                src={referenceUrl}
                alt="sizing-reference"
                className="max-w-full max-h-full object-contain opacity-0 pointer-events-none block"
                draggable={false}
              />
            )}

            {/* Content Overlay - Where the actual mode content goes */}
            <div className="absolute inset-0">
              {children}
            </div>
          </div>
        </div>
      </div>
    );
  }
);

export default UnifiedViewerContainer;
