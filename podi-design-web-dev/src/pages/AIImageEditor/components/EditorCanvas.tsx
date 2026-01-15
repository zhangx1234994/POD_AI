import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Stage, Layer, Image as KonvaImage, Line } from 'react-konva';
import { Upload } from 'lucide-react';

// Define shape types
type ShapeType = 'point' | 'rect' | 'circle';

interface Shape {
  id: string;
  type: ShapeType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  radius?: number;
  color: string;
  size: number;
}

interface EditorCanvasProps {
  imageSrc?: string;
  onUpload: () => void;
  activeTool: 'select' | 'click' | 'rect' | 'circle';
  brushSize: number;
  selectedColor: string;
  onShapeAdd: (shape: Shape) => void;
  onShapeUpdate: (shape: Shape) => void;
  onShapeDelete: (shapeId: string) => void;
  onShapeSelect: (shapeId: string | null) => void;
  shapes: Shape[];
  selectedShapeId: string | null;
  highlightedShapeId: string | null;
  zoomLevel: number;
  onZoomChange: (zoom: number) => void;
}

export const EditorCanvas: React.FC<EditorCanvasProps> = ({ 
  imageSrc, 
  onUpload, 
  activeTool, 
  brushSize, 
  selectedColor,
  onShapeAdd,
  onShapeUpdate,
  onShapeDelete,
  onShapeSelect,
  shapes: externalShapes,
  selectedShapeId: externalSelectedShapeId,
  highlightedShapeId,
  zoomLevel,
  onZoomChange
}) => {
  // Canvas ref for positioning
  const canvasContainerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<any>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  
  // State for container dimensions
  const [containerWidth, setContainerWidth] = useState<number>(800);
  const [containerHeight, setContainerHeight] = useState<number>(600);
  
  // State for shapes and drawing
  const [shapes, setShapes] = useState<Shape[]>(externalShapes || []);
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawingPoints, setDrawingPoints] = useState<Array<{ x: number; y: number }>>([]);
  const [selectedShapeId, setSelectedShapeId] = useState<string | null>(externalSelectedShapeId || null);
  
  // Sync external selected shape ID with internal state
  useEffect(() => {
    setSelectedShapeId(externalSelectedShapeId || null);
  }, [externalSelectedShapeId]);
  
  // Sync external shapes with internal state
  useEffect(() => {
    if (externalShapes) {
      setShapes(externalShapes);
    }
  }, [externalShapes]);
  
  // State for image dimensions and scale
  const [imageMeta, setImageMeta] = useState({ width: 1024, height: 768 });
  
  // Sync external shapes with internal state
  useEffect(() => {
    if (externalShapes) {
      setShapes(externalShapes);
    }
  }, [externalShapes]);
  
  // Update container dimensions on resize
  useEffect(() => {
    const resize = () => {
      if (canvasContainerRef.current) {
        setContainerWidth(canvasContainerRef.current.clientWidth);
        setContainerHeight(canvasContainerRef.current.clientHeight);
      }
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  
  // Handle image load
  useEffect(() => {
    if (!imageSrc) {
      imageRef.current = null;
      return;
    }
    
    const img = new window.Image();
    img.crossOrigin = 'anonymous';
    img.src = imageSrc;
    img.onload = () => {
      imageRef.current = img;
      setImageMeta({ width: img.width, height: img.height });
    };
    img.onerror = () => {
      imageRef.current = null;
    };
  }, [imageSrc]);
  
  // Calculate view scale
  const viewScale = useMemo(() => {
    if (!imageMeta.width) return 1;
    const maxW = containerWidth - 24;
    const maxH = containerHeight - 24;
    // Base scale based on container and image size
    const baseScale = Math.min(1, Math.min(maxW / imageMeta.width, maxH / imageMeta.height));
    // Apply zoom level (zoomLevel is percentage, so divide by 100)
    const zoomFactor = zoomLevel / 100;
    return baseScale * zoomFactor;
  }, [containerWidth, containerHeight, imageMeta.width, imageMeta.height, zoomLevel]);
  
  // Handle mouse down event
  const handleMouseDown = () => {
    if (!stageRef.current || activeTool === 'select') return;
    
    const p = stageRef.current.getPointerPosition();
    const original = { x: p.x / viewScale, y: p.y / viewScale };
    setDrawingPoints([original]);
    setIsDrawing(true);
  };
  
  // Handle mouse move event
  const handleMouseMove = () => {
    if (!isDrawing || !stageRef.current || activeTool === 'select') return;
    
    const p = stageRef.current.getPointerPosition();
    const original = { x: p.x / viewScale, y: p.y / viewScale };
    
    if (activeTool === 'rect' || activeTool === 'circle') {
      setDrawingPoints([drawingPoints[0], original]);
    } else if (activeTool === 'click') {
      // Point mode: keep the first point
      setDrawingPoints([drawingPoints[0]]);
    }
  };
  
  // Handle mouse up event
  const handleMouseUp = () => {
    setIsDrawing(false);
    
    if (activeTool === 'click') {
      if (drawingPoints.length < 1) { setDrawingPoints([]); return; }
      
      // Create point shape
      const newShape: Shape = {
        id: `shape-${Date.now()}`,
        type: 'point',
        x: drawingPoints[0].x,
        y: drawingPoints[0].y,
        color: selectedColor,
        size: brushSize
      };
      setShapes(prev => [...prev, newShape]);
      if (onShapeAdd) {
        onShapeAdd(newShape);
      }
    } else if (activeTool === 'rect' || activeTool === 'circle') {
      if (drawingPoints.length < 2) { setDrawingPoints([]); return; }
      
      const p1 = drawingPoints[0];
      const p2 = drawingPoints[1];
      
      if (activeTool === 'rect') {
        // Create rectangle shape
        const x = Math.min(p1.x, p2.x);
        const y = Math.min(p1.y, p2.y);
        const width = Math.abs(p2.x - p1.x);
        const height = Math.abs(p2.y - p1.y);
        
        const newShape: Shape = {
          id: `shape-${Date.now()}`,
          type: 'rect',
          x,
          y,
          width,
          height,
          color: selectedColor,
          size: brushSize
        };
        setShapes(prev => [...prev, newShape]);
        if (onShapeAdd) {
          onShapeAdd(newShape);
        }
      } else if (activeTool === 'circle') {
        // Create circle shape
        const radius = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
        
        const newShape: Shape = {
          id: `shape-${Date.now()}`,
          type: 'circle',
          x: p1.x,
          y: p1.y,
          radius,
          color: selectedColor,
          size: brushSize
        };
        setShapes(prev => [...prev, newShape]);
        if (onShapeAdd) {
          onShapeAdd(newShape);
        }
      }
    }
    
    setDrawingPoints([]);
  };
  
  // Handle mouse leave event
  const handleMouseLeave = () => {
    if (isDrawing) {
      setIsDrawing(false);
      setDrawingPoints([]);
    }
  };

  // Handle wheel zooming by delta; we'll register a native listener with passive:false
  const handleWheelDelta = (deltaY: number) => {
    // Only allow wheel zoom when there is a loaded base image
    if (!imageRef.current) return;
    // Calculate zoom delta (each scroll is ±10% zoom)
    const delta = deltaY > 0 ? -10 : 10;
    const newZoom = Math.max(10, Math.min(200, zoomLevel + delta));
    onZoomChange(newZoom);
  };

  // Attach a native wheel listener with { passive: false } so we can call preventDefault()
  useEffect(() => {
    const el = canvasContainerRef.current;
    // Only attach wheel handler when we have a container and a base image
    if (!el || !imageSrc) return;

    const wheelHandler = (ev: WheelEvent) => {
      // Prevent page scroll when interacting with the canvas
      try {
        ev.preventDefault();
      } catch (e) {
        // ignore
      }
      handleWheelDelta(ev.deltaY);
    };

    el.addEventListener('wheel', wheelHandler as EventListener, { passive: false });
    return () => el.removeEventListener('wheel', wheelHandler as EventListener);
  }, [canvasContainerRef, zoomLevel, onZoomChange, imageSrc]);
  
  // Render shape based on type
  const renderShape = (shape: Shape) => {
    const isSelected = shape.id === selectedShapeId;
    const isHighlighted = shape.id === highlightedShapeId;
    
    // Handle shape click
    const handleShapeClick = () => {
      const newSelectedId = shape.id === selectedShapeId ? null : shape.id;
      setSelectedShapeId(newSelectedId);
      if (onShapeSelect) {
        onShapeSelect(newSelectedId);
      }
    };
    
    // Determine shape style based on selection and highlight state
    const getShapeStyle = () => {
      if (isHighlighted) {
        // Highlighted state has priority over selected state
        // Use shape's original color as base for highlight to maintain consistency
        return {
          stroke: '#FFFFFF',
          strokeWidth: 4,
          fill: `${shape.color}A0`, // Increased opacity for better visibility
          shadowColor: shape.color, // Use shape's original color for shadow
          shadowBlur: 15, // More prominent shadow for better contrast
          shadowOffset: { x: 0, y: 0 },
          shadowOpacity: 0.8,
          opacity: 1, // Ensure full opacity when highlighted
          transition: {
            duration: 0.2 // Smooth transition effect
          }
        };
      } else if (isSelected) {
        // Selected state
        return {
          stroke: '#2563eb',
          strokeWidth: 3,
          fill: `${shape.color}60`, // Slightly increased opacity for selected state
          opacity: 1
        };
      } else {
        // Default state
        return {
          stroke: shape.color,
          strokeWidth: 2,
          fill: `${shape.color}40`,
          opacity: 1,
          transition: {
            duration: 0.2 // Smooth transition effect
          }
        };
      }
    };
    
    const shapeStyle = getShapeStyle();
    
    switch (shape.type) {
      case 'point':
        const pointSize = Math.max(4, shape.size);
        const halfSize = pointSize / 2;
        return (
          <Line
            key={shape.id}
            points={[
              (shape.x - halfSize) * viewScale, (shape.y - halfSize) * viewScale,
              (shape.x + halfSize) * viewScale, (shape.y - halfSize) * viewScale,
              (shape.x + halfSize) * viewScale, (shape.y + halfSize) * viewScale,
              (shape.x - halfSize) * viewScale, (shape.y + halfSize) * viewScale
            ]}
            closed
            stroke={shapeStyle.stroke}
            strokeWidth={shapeStyle.strokeWidth}
            fill={shapeStyle.fill}
            shadowColor={shapeStyle.shadowColor}
            shadowBlur={shapeStyle.shadowBlur}
            shadowOffset={shapeStyle.shadowOffset}
            shadowOpacity={shapeStyle.shadowOpacity}
            draggable={false}
            onClick={handleShapeClick}
            // Add smooth transition effect
            onMouseEnter={() => {}}
            onMouseLeave={() => {}}
          />
        );
      case 'rect':
        return (
          <Line
            key={shape.id}
            points={[
              shape.x * viewScale, shape.y * viewScale,
              (shape.x + shape.width!) * viewScale, shape.y * viewScale,
              (shape.x + shape.width!) * viewScale, (shape.y + shape.height!) * viewScale,
              shape.x * viewScale, (shape.y + shape.height!) * viewScale
            ]}
            closed
            stroke={shapeStyle.stroke}
            strokeWidth={shapeStyle.strokeWidth}
            fill={shapeStyle.fill}
            shadowColor={shapeStyle.shadowColor}
            shadowBlur={shapeStyle.shadowBlur}
            shadowOffset={shapeStyle.shadowOffset}
            shadowOpacity={shapeStyle.shadowOpacity}
            draggable={false}
            onClick={handleShapeClick}
          />
        );
      case 'circle':
        const circlePoints: number[] = [];
        for (let i = 0; i <= 32; i++) {
          const angle = (i / 32) * Math.PI * 2;
          const x = shape.x + shape.radius! * Math.cos(angle);
          const y = shape.y + shape.radius! * Math.sin(angle);
          circlePoints.push(x * viewScale, y * viewScale);
        }
        return (
          <Line
            key={shape.id}
            points={circlePoints}
            closed
            stroke={shapeStyle.stroke}
            strokeWidth={shapeStyle.strokeWidth}
            fill={shapeStyle.fill}
            shadowColor={shapeStyle.shadowColor}
            shadowBlur={shapeStyle.shadowBlur}
            shadowOffset={shapeStyle.shadowOffset}
            shadowOpacity={shapeStyle.shadowOpacity}
            draggable={false}
            onClick={handleShapeClick}
          />
        );
      default:
        return null;
    }
  };
  
  // Render current drawing preview
  const renderDrawingPreview = () => {
    if (drawingPoints.length === 0) return null;
    
    if (activeTool === 'click') {
      const p = drawingPoints[0];
      const pointSize = Math.max(4, brushSize);
      const halfSize = pointSize / 2;
      return (
        <Line
          points={[
            (p.x - halfSize) * viewScale, (p.y - halfSize) * viewScale,
            (p.x + halfSize) * viewScale, (p.y - halfSize) * viewScale,
            (p.x + halfSize) * viewScale, (p.y + halfSize) * viewScale,
            (p.x - halfSize) * viewScale, (p.y + halfSize) * viewScale
          ]}
          closed
          stroke={selectedColor}
          strokeWidth={2}
          fill={`${selectedColor}20`}
        />
      );
    } else if (activeTool === 'rect' && drawingPoints.length > 1) {
      const p1 = drawingPoints[0];
      const p2 = drawingPoints[1];
      const x = Math.min(p1.x, p2.x);
      const y = Math.min(p1.y, p2.y);
      const width = Math.abs(p2.x - p1.x);
      const height = Math.abs(p2.y - p1.y);
      return (
        <Line
          points={[
            x * viewScale, y * viewScale,
            (x + width) * viewScale, y * viewScale,
            (x + width) * viewScale, (y + height) * viewScale,
            x * viewScale, (y + height) * viewScale
          ]}
          closed
          stroke={selectedColor}
          strokeWidth={2}
          fill={`${selectedColor}20`}
        />
      );
    } else if (activeTool === 'circle' && drawingPoints.length > 1) {
      const p1 = drawingPoints[0];
      const p2 = drawingPoints[1];
      const radius = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
      const circlePoints: number[] = [];
      for (let i = 0; i <= 32; i++) {
        const angle = (i / 32) * Math.PI * 2;
        const x = p1.x + radius * Math.cos(angle);
        const y = p1.y + radius * Math.sin(angle);
        circlePoints.push(x * viewScale, y * viewScale);
      }
      return (
        <Line
          points={circlePoints}
          closed
          stroke={selectedColor}
          strokeWidth={2}
          fill={`${selectedColor}20`}
        />
      );
    }
    return null;
  };
  
  // State for error handling
  const [imageLoadError, setImageLoadError] = useState(false);

  // Handle image load error
  const handleImageError = () => {
    setImageLoadError(true);
  };

  // Reset image load error when imageSrc changes
  useEffect(() => {
    setImageLoadError(false);
  }, [imageSrc]);

  return (
    <div 
      ref={canvasContainerRef}
      className="flex-1 bg-[#F4F5F7] rounded-16 border relative overflow-hidden group"
      style={{ touchAction: 'none', userSelect: 'none' }}
    >
      {imageSrc ? (
        <div className="flex items-center justify-center h-full w-full">
          {!imageRef.current || imageLoadError ? (
            /* Image loading or error state */
            <div 
                className="flex flex-col items-center justify-center cursor-pointer p-10 transition-transform border rounded-12 bg-card p-16 w-full max-w-md"
              onClick={onUpload}
            >
              <div className="mb-4 text-[#EF4444]">
                <Upload className="w-16 h-16" />
              </div>
              <h3 className="text-xl font-medium text-[#333] mb-2">图片加载失败</h3>
              <p className="text-sm text-[#666] mb-4">请重新上传图片</p>
              <button 
                className="px-4 py-2 bg-[#6C4CF0] text-white rounded-lg hover:bg-[#5B3BC8] transition-colors"
                onClick={onUpload}
              >
                重新上传
              </button>
            </div>
          ) : (
            /* Normal image display with Konva */
            <Stage
              ref={stageRef}
              width={imageMeta.width * viewScale}
              height={imageMeta.height * viewScale}
              draggable={false}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseLeave}
            >
              <Layer>
                {/* Base Image */}
                <KonvaImage
                  image={imageRef.current}
                  x={0}
                  y={0}
                  scaleX={viewScale}
                  scaleY={viewScale}
                  draggable={false}
                  listening={false}
                />
                
                {/* Render existing shapes */}
                {shapes.map(renderShape)}
                
                {/* Render current drawing preview */}
                {renderDrawingPreview()}
              </Layer>
            </Stage>
          )}
        </div>
      ) : (
        /* No image upload prompt */
        <div className="flex items-center justify-center h-full w-full">
          <div 
            className="flex flex-col items-center justify-center cursor-pointer p-10 transition-transform border rounded-12 bg-card p-16 w-full max-w-md "
            onClick={onUpload}
          >
            <div className="mb-4 text-[#9CA3AF]">
              <Upload className="w-16 h-16" />
            </div>
            <h3 className="text-xl font-medium text-[#333] mb-2">点击上传底图</h3>
            <p className="text-sm text-[#666]">支持 JPG、PNG 格式，滚轮缩放画布</p>
          </div>
        </div>
      )}
    </div>
  );
};
