import { useState } from 'react';
import { UnifiedViewerContainer } from './UnifiedViewerContainer';

interface OverlayModeProps {
  originalUrl: string;
  generatedUrl: string;
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  handlers: any;
  mode?: any;
}

export function OverlayMode({
  originalUrl,
  generatedUrl,
  scale,
  position,
  isDragging,
  handlers,
  mode,
}: OverlayModeProps) {
  const [opacity, setOpacity] = useState(50); // 0-100

  const transformStyle = {
    transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
    transformOrigin: 'center',
    willChange: 'transform'
  };

  return (
    <UnifiedViewerContainer
      referenceUrl={generatedUrl}
      scale={scale}
      position={position}
      isDragging={isDragging}
      handlers={handlers}
      mode={mode}
      disableTransform={true}
      fixedContent={
        /* Opacity Control - Floating Fixed UI */
        <div 
          className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40 bg-background/90 backdrop-blur border rounded-full px-6 py-3 w-72 shadow-xl flex items-center gap-3 cursor-auto select-none"
          onMouseDown={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
           <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">叠加透明度</span>
           <div className="relative flex-1 h-5 flex items-center">
             <input 
                type="range"
                min={0}
                max={100}
                step={1}
                value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))}
                className="w-full h-1.5 rounded-lg appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/20"
                style={{
                  background: `linear-gradient(to right, hsl(var(--primary)) ${opacity}%, hsl(var(--secondary)) ${opacity}%)`
                }}
             />
             <style>{`
               input[type=range]::-webkit-slider-thumb {
                 -webkit-appearance: none;
                 height: 16px;
                 width: 16px;
                 border-radius: 50%;
                 background: hsl(var(--primary));
                 border: 2px solid hsl(var(--background));
                 box-shadow: 0 0 0 1px hsl(var(--primary)), 0 2px 4px rgba(0,0,0,0.1);
                 margin-top: 0px; /* Adjust if needed */
               }
               input[type=range]::-moz-range-thumb {
                 height: 16px;
                 width: 16px;
                 border-radius: 50%;
                 background: hsl(var(--primary));
                 border: 2px solid hsl(var(--background));
                 box-shadow: 0 0 0 1px hsl(var(--primary)), 0 2px 4px rgba(0,0,0,0.1);
               }
             `}</style>
           </div>
           <span className="text-xs font-mono w-9 text-right">{opacity}%</span>
        </div>
      }
    >
      {/* Base Layer: Original Image (Bottom) */}
      <img
          src={originalUrl}
          alt="原图"
          className="absolute inset-0 w-full h-full object-contain block select-none"
          style={transformStyle}
          draggable={false}
      />

      {/* Overlay Layer: Generated Result (Top) */}
      <div 
          className="absolute inset-0 transition-opacity duration-75 select-none"
          style={{ opacity: opacity / 100 }}
      >
           <img
              src={generatedUrl}
              alt="结果图"
              className="w-full h-full object-contain block select-none"
              style={transformStyle}
              draggable={false}
          />
      </div>

      {/* 
          Custom Labels for Overlay Mode 
          Replacing CornerLabel because text is dynamic and needs to be longer.
          Using pill-shaped badges with consistent colors.
      */}
      
      {/* Top Left: Result (Green) */}
      <div 
        className="absolute top-3 left-3 z-20 pointer-events-none px-3 py-1.5 rounded-md shadow-sm text-xs font-medium text-white backdrop-blur-sm"
        style={{ backgroundColor: '#4CD964' }} // Matching the green from CornerLabel
      >
        顶层：结果图 ({opacity}%)
      </div>

      {/* Top Right: Original (Gray) */}
      <div 
        className="absolute top-3 right-3 z-20 pointer-events-none px-3 py-1.5 rounded-md shadow-sm text-xs font-medium text-white backdrop-blur-sm"
        style={{ backgroundColor: '#B9B9B9' }} // Matching the gray from CornerLabel
      >
        底层：原图
      </div>
      
    </UnifiedViewerContainer>
  );
};

export default OverlayMode;
