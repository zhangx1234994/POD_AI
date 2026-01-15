import { useState, useRef, useCallback, useEffect } from 'react';
import { ImageWithFallback } from '@/components/ImageWithFallback';

interface ZoomableImageProps {
  src: string;
  alt: string;
  initialScale?: number;
  minScale?: number;
  maxScale?: number;
};

export function ZoomableImage({
  src,
  alt,
  initialScale = 1,
  minScale = 0.5,
  maxScale = 3,
}: ZoomableImageProps) {
  const [scale, setScale] = useState(initialScale);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });
  const imageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = imageRef.current;
    if (!el) return;

    const onWheel = (ev: WheelEvent) => {
      try {
        ev.preventDefault();
        ev.stopPropagation();
      } catch (e) {
        // ignore
      }
      const delta = ev.deltaY > 0 ? -0.1 : 0.1;
      setScale((prev) => Math.max(minScale, Math.min(maxScale, prev + delta)));
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel as EventListener);
  }, [minScale, maxScale]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    setLastMousePos({ x: e.clientX, y: e.clientY });
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      e.preventDefault();
      e.stopPropagation();
      const deltaX = e.clientX - lastMousePos.x;
      const deltaY = e.clientY - lastMousePos.y;
      setPosition((prev: { x: number; y: number }) => ({ x: prev.x + deltaX, y: prev.y + deltaY }));
      setLastMousePos({ x: e.clientX, y: e.clientY });
    },
    [isDragging, lastMousePos]
  );

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDoubleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setScale(initialScale);
    setPosition({ x: 0, y: 0 });
  }, [initialScale]);

  return (
    <div
      ref={imageRef}
      className="relative w-full h-full overflow-hidden"
      style={{ cursor: isDragging ? 'grabbing' : 'grab', userSelect: 'none', touchAction: 'none' }}
      onMouseDown={(e) => handleMouseDown(e as any)}
      onMouseMove={(e) => handleMouseMove(e as any)}
      onMouseUp={(e) => handleMouseUp(e as any)}
      onMouseLeave={(e) => handleMouseUp(e as any)}
      onDoubleClick={(e) => handleDoubleClick(e as any)}
    >
      <ImageWithFallback
        src={src}
        alt={alt}
        className="w-full h-full object-contain transition-transform duration-0 ease-out"
        style={{ transform: `scale(${scale}) translate(${position.x}px, ${position.y}px)`, transformOrigin: 'center center', pointerEvents: 'none' }}
      />
    </div>
  );
};

export default ZoomableImage;
