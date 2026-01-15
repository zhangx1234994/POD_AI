import React from 'react';
import { AtSign } from 'lucide-react';

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
  label?: string;
  description?: string;
}

interface EditorFooterProps {
  annotationCount: number;
  shapes: Shape[];
  onHighlightShape?: (shapeId: string | null) => void;
  onShapeDelete: (shapeId: string) => void;
}

export const EditorFooter: React.FC<EditorFooterProps> = ({ annotationCount, shapes, onHighlightShape, onShapeDelete }) => {
  // State for filtering annotation types
  const [selectedFilter, setSelectedFilter] = React.useState<ShapeType | 'all'>('all');
  
  // Generate coordinate tag for shape
  const generateCoordinateTag = (shape: Shape): string => {
    let tag = '';
    if (shape.type === 'point') {
      // Point: @point(x,y)
      tag = `@point(${Math.round(shape.x)},${Math.round(shape.y)})`;
    } else if (shape.type === 'rect') {
      // Rectangle: @rect(x,y,width,height)
      const x = Math.round(shape.x);
      const y = Math.round(shape.y);
      const width = Math.round(shape.width || 0);
      const height = Math.round(shape.height || 0);
      tag = `@rect(${x},${y},${width},${height})`;
    } else if (shape.type === 'circle') {
      // Circle: @circle(cx,cy,radius)
      const cx = Math.round(shape.x);
      const cy = Math.round(shape.y);
      const radius = Math.round(shape.radius || 0);
      tag = `@circle(${cx},${cy},${radius})`;
    }
    return tag;
  };

  return (
    <div className="rounded-t-xl border-t border-l border-r border-[#EDEEF0] p-4 mt-4 h-auto min-h-[160px] w-full">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AtSign className="w-4 h-4 text-[#333]" />
            <span className="text-sm font-medium text-[#333]">标注区域</span>
            
            {/* Filter Buttons */}
            <div className="flex items-center whitespace-nowrap ml-4">
              <button
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  transition: 'all 0.2s ease',
                  color: selectedFilter === 'all' ? '#6C4CF0' : '#333333',
                  textDecoration: selectedFilter === 'all' ? 'underline' : 'none',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedFilter('all')}
              >
                全部
              </button>
              <span className="mx-1 text-[#9CA3AF]">｜</span>
              <button
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  transition: 'all 0.2s ease',
                  color: selectedFilter === 'point' ? '#6C4CF0' : '#333333',
                  textDecoration: selectedFilter === 'point' ? 'underline' : 'none',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedFilter('point')}
              >
                点选
              </button>
              <span className="mx-1 text-[#9CA3AF]">｜</span>
              <button
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  transition: 'all 0.2s ease',
                  color: selectedFilter === 'rect' ? '#6C4CF0' : '#333333',
                  textDecoration: selectedFilter === 'rect' ? 'underline' : 'none',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedFilter('rect')}
              >
                矩形
              </button>
              <span className="mx-1 text-[#9CA3AF]">｜</span>
              <button
                style={{
                  fontSize: '12px',
                  padding: '2px 8px',
                  transition: 'all 0.2s ease',
                  color: selectedFilter === 'circle' ? '#6C4CF0' : '#333333',
                  textDecoration: selectedFilter === 'circle' ? 'underline' : 'none',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                }}
                onClick={() => setSelectedFilter('circle')}
              >
                圆形
              </button>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="h-6 min-w-[24px] px-1.5 rounded-full border border-[#E5E7EB] flex items-center justify-center text-xs text-[#333] bg-[#F4F5F7]">
              {annotationCount}
            </div>
          </div>
        </div>
        
        {/* Filtered Annotation List */}
        {(() => {
          const filteredShapes = selectedFilter === 'all' 
            ? shapes 
            : shapes.filter(shape => shape.type === selectedFilter);
          
          return filteredShapes.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-8">
              <div className="text-xs text-gray-600">暂无标注区域</div>
              <div className="text-xs text-gray-600">使用工具在画布上标注</div>
            </div>
          ) : (
            <div className="flex flex-wrap items-start gap-2 pb-2">
              {filteredShapes.map((shape, index) => {
                const coordinateTag = generateCoordinateTag(shape);
                return (
                  <div 
                      key={shape.id} 
                      className="flex flex-col p-2 border rounded-lg cursor-pointer transition-colors duration-150 ease-in-out hover:border-primary/50"
                      onMouseEnter={() => onHighlightShape?.(shape.id)}
                      onMouseLeave={() => onHighlightShape?.(null)}
                    >
                      <div className="flex items-center gap-2 w-full">
                        <div 
                          className={`w-3 h-3 rounded-full flex-shrink-0`}
                          style={{ backgroundColor: shape.color }}
                        />
                        <p className="text-xs text-foreground truncate flex-1 text-left m-0 p-0">
                          {shape.label || `标注 ${index + 1}`}
                        </p>
                        <button
                          className="p-1 text-gray-600 hover:text-red-500 size-9 rounded-md h-5 w-5 transition-colors flex-shrink-0"
                          onClick={(e) => {
                            e.stopPropagation(); // Prevent triggering the card click event
                            onShapeDelete(shape.id);
                          }}
                          aria-label="删除标注"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18"></path>
                            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                          </svg>
                        </button>
                      </div>
                      <div className="flex items-center gap-2 mt-1 w-full">
                        <p className="text-xs text-muted-foreground truncate text-left m-0 p-0 flex-shrink-0">
                          {shape.type === 'point' ? '点' : shape.type === 'rect' ? '矩形' : '圆形'}
                        </p>
                        <p className="text-xs text-[#6C4CF0] truncate text-left m-0 p-0 flex-1">
                          {coordinateTag}
                        </p>
                      </div>
                    </div>
                );
              })}
            </div>
          );
        })()}
    </div>
  );
};