import React, { useState, useRef, useEffect, useCallback } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { UnifiedViewerContainer } from './UnifiedViewerContainer';
import { CornerLabel } from '@/components/icons/CornerLabel';

interface SliderModeProps {
  originalUrl: string;
  generatedUrl: string;
  scale: number;
  position: { x: number; y: number };
  isDragging: boolean;
  handlers: any;
}

export function SliderMode({
  originalUrl,
  generatedUrl,
  scale,
  position,
  isDragging,
  handlers,
}: SliderModeProps) {
  const [sliderPosition, setSliderPosition] = useState(50); // percentage 0-100
  const contentRef = useRef<HTMLDivElement>(null);
  const isResizingRef = useRef(false);

  // --- Mouse Events ---
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent default text selection
    e.stopPropagation(); // Prevent triggering pan
    isResizingRef.current = true;
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizingRef.current || !contentRef.current) return;
    
    const rect = contentRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const percentage = (x / rect.width) * 100;
    
    setSliderPosition(percentage);
  }, []);

  const handleMouseUp = useCallback(() => {
    isResizingRef.current = false;
    document.body.style.cursor = '';
  }, []);

  // --- Touch Events ---
  const handleTouchStart = (e: React.TouchEvent) => {
    e.stopPropagation(); // Prevent triggering pan
    isResizingRef.current = true;
  };

  const handleTouchMove = useCallback((e: TouchEvent) => {
    if (!isResizingRef.current || !contentRef.current) return;
    
    // Prevent scrolling while dragging slider
    if (e.cancelable) e.preventDefault();
    
    const touch = e.touches[0];
    const rect = contentRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(touch.clientX - rect.left, rect.width));
    const percentage = (x / rect.width) * 100;
    
    setSliderPosition(percentage);
  }, []);

  const handleTouchEnd = useCallback(() => {
    isResizingRef.current = false;
  }, []);

  // --- Effects ---

  // Cursor handling
  useEffect(() => {
    if (isResizingRef.current) {
        document.body.style.cursor = 'ew-resize';
    } else {
        document.body.style.cursor = '';
    }
    return () => {
        document.body.style.cursor = '';
    };
  }, [isResizingRef.current]);

  // Event Listeners
  useEffect(() => {
    // Mouse
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    // Touch - use passive: false to allow preventDefault if needed
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleTouchEnd);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handleMouseMove, handleMouseUp, handleTouchMove, handleTouchEnd]);

  const transformStyle = {
    transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
    transformOrigin: 'center',
    willChange: 'transform'
  };

  return (
    <UnifiedViewerContainer
      ref={contentRef}
      referenceUrl={generatedUrl}
      scale={scale}
      position={position}
      isDragging={isDragging}
      handlers={handlers}
      disableTransform={true}
    >
      {/* Layer 1: Original (Background/Bottom) */}
      <img
          src={originalUrl}
          alt="原图"
          className="absolute inset-0 w-full h-full object-contain block select-none"
          style={transformStyle}
          draggable={false}
      />

      {/* Layer 2: Generated Result (Foreground/Top/Overlay) */}
      <div 
          className="absolute inset-0 overflow-hidden select-none"
          style={{ 
              clipPath: `inset(0 ${100 - sliderPosition}% 0 0)`,
          }}
      >
          <img
              src={generatedUrl}
              alt="结果图"
              className="w-full h-full object-contain block select-none"
              style={transformStyle}
              draggable={false}
          />
      </div>

      {/* Slider Handle Container */}
      {/* Increased touch area: w-8 (32px) centered on the split line */}
      <div
          className="absolute top-0 bottom-0 z-30 cursor-ew-resize touch-none"
          style={{ 
              left: `${sliderPosition}%`,
              width: '32px',
              transform: 'translateX(-50%)',
              // Use explicit CSS to ensure positioning works even if Tailwind classes fail
          }}
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
      >
            {/* Visual Line - Vertical divider */}
            <div 
                style={{ 
                    position: 'absolute',
                    top: 0,
                    bottom: 0,
                    left: '50%',
                    width: '2px', // Explicit width
                    transform: 'translateX(-50%)',
                    backgroundColor: '#ffffff', // Pure white base
                    opacity: 0.8, // 80% opacity
                    boxShadow: '0 0 4px rgba(0, 0, 0, 0.6)', // Slightly stronger shadow for visibility
                    pointerEvents: 'none'
                }}
            />

            {/* Handle Circle */}
            <div 
              className="absolute top-1/2 left-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center text-black hover:scale-110 transition-transform"
              style={{ 
                  transform: 'translate(-50%, -50%)',
              }}
            >
              <SlidersHorizontal className="w-4 h-4" />
            </div>
      </div>

      {/* Badges - Fixed to screen corners */}
      <CornerLabel variant="result" corner="top-left" />
      <CornerLabel variant="original" corner="top-right" />
    </UnifiedViewerContainer>
  );
};

export default SliderMode;
