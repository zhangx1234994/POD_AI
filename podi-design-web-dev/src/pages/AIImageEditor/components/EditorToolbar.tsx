import React from 'react';
import { Settings, MousePointer2, Square, Circle, ZoomIn, ZoomOut, Upload } from 'lucide-react';
import { ScanSquare } from '@/components/icons/ScanSquare';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { cn } from '@/components/ui/utils';
import { Button } from '@/components/ui/button';

type ToolType = 'select' | 'click' | 'rect' | 'circle';

interface EditorToolbarProps {
  activeTool: ToolType;
  onToolChange: (tool: ToolType) => void;
  brushSize: number;
  onBrushSizeChange: (size: number) => void;
  selectedColor: string;
  onColorChange: (color: string) => void;
  zoomLevel: number;
  onZoomChange: (zoom: number) => void;
  onUpload: () => void;
  hasBaseImage?: boolean;
}

const COLORS = [
  '#F87171', // Red/Pink
  '#22D3EE', // Cyan
  '#34D399', // Green
  '#A78BFA', // Purple
  '#FDE047', // Yellow
  '#F472B6', // Pink
  '#818CF8', // Indigo
  '#60A5FA', // Blue
];

export const EditorToolbar: React.FC<EditorToolbarProps> = ({
  activeTool,
  onToolChange,
  brushSize,
  onBrushSizeChange,
  selectedColor,
  onColorChange,
  zoomLevel,
  onZoomChange,
  onUpload
  , hasBaseImage = false
}) => {
  const handleZoomIn = () => {
    if (!hasBaseImage) return;
    onZoomChange(Math.min(zoomLevel + 10, 200));
  };

  const handleZoomOut = () => {
    if (!hasBaseImage) return;
    onZoomChange(Math.max(zoomLevel - 10, 10));
  };

  const handleFitScreen = () => {
    if (!hasBaseImage) return;
    onZoomChange(100);
  };

  const zoomDisabled = !hasBaseImage;

  return (
    <div className="h-14 px-4 flex items-center rounded-xl shadow-sm border gap-3 ml-auto mr-6">
      {/* Tools Group */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onToolChange('select')}
          className={`h-8 gap-1.5 px-3 inline-flex items-center justify-center whitespace-nowrap text-xs font-medium rounded-md border
            ${activeTool === 'select' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''}`}
        >
          <Settings className="w-4 h-4 mr-1" />
          选择
        </button>
        <button
          onClick={() => onToolChange('click')}
          className={`h-8 gap-1.5 px-3 inline-flex items-center justify-center whitespace-nowrap text-xs font-medium rounded-md border
            ${activeTool === 'click' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''}`}
        >
          <MousePointer2 className="w-4 h-4 mr-1" />
          点选
        </button>
        <button
          onClick={() => onToolChange('rect')}
          className={`h-8 gap-1.5 px-3 inline-flex items-center justify-center whitespace-nowrap text-xs font-medium rounded-md border
            ${activeTool === 'rect' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''}`}
        >
          <Square className="w-4 h-4 mr-1" />
          矩形
        </button>
        <button
          onClick={() => onToolChange('circle')}
          className={`h-8 gap-1.5 px-3 inline-flex items-center justify-center whitespace-nowrap text-xs font-medium rounded-md border
            ${activeTool === 'circle' ? 'bg-primary text-primary-foreground hover:bg-primary/90' : ''}`}
        >
          <Circle className="w-4 h-4 mr-1" />
          圆形
        </button>
      </div>

      <div className="h-5 w-[1px] bg-[#EDEEF0]" />

      {/* Size Control - Only show when click tool is active */}
      {activeTool === 'click' && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#666]">大小</span>
          {/* Slider Container */}
          <div className="flex items-center gap-2">
            <div 
              className="relative w-20 h-4 border rounded-full overflow-hidden"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                const newValue = Math.max(1, Math.min(100, Math.round(percent * 100)));
                onBrushSizeChange(newValue);
              }}
            >
              {/* Track */}
              <div 
                className="absolute top-0 left-0 h-full rounded-full"
                style={{ width: `${brushSize}%`, backgroundColor: '#6C4CF0' }}
              />
              {/* Thumb */}
              <div 
                className="absolute top-1/2 w-4 h-4 bg-card border-2 rounded-full transform -translate-y-1/2 cursor-pointer shadow-sm"
                style={{ left: `calc(${brushSize}% - 8px)`, borderColor: '#6C4CF0' }}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  const sliderRect = e.currentTarget.parentElement!.getBoundingClientRect();
                  
                  const handleMouseMove = (moveEvent: MouseEvent) => {
                    const percent = (moveEvent.clientX - sliderRect.left) / sliderRect.width;
                    const newValue = Math.max(1, Math.min(100, Math.round(percent * 100)));
                    onBrushSizeChange(newValue);
                  };
                  
                  const handleMouseUp = () => {
                    document.removeEventListener('mousemove', handleMouseMove);
                    document.removeEventListener('mouseup', handleMouseUp);
                  };
                  
                  document.addEventListener('mousemove', handleMouseMove);
                  document.addEventListener('mouseup', handleMouseUp);
                }}
              />
            </div>
            <div className="px-2 py-0.5 bg-[#F4F5F7] rounded text-xs text-[#333] min-w-[28px] text-center">
              {brushSize}
            </div>
          </div>
        </div>
      )}

      <div className="h-5 w-[1px] bg-[#EDEEF0]" />

      {/* Color Palette */}
      <div className="flex items-center gap-1.5">
        {COLORS.map((color) => (
          <button
            key={color}
            onClick={() => onColorChange(color)}
            className={cn(
              "w-5 h-5 rounded transition-all",
              selectedColor === color ? "ring-2 ring-offset-1 ring-[#6C4CF0]" : "hover:scale-110"
            )}
            style={{ backgroundColor: color }}
          />
        ))}
      </div>

      {/* Spacer to push zoom controls to the right */}
      <div className="flex-grow"></div>

      {/* Zoom Controls -居右展示 */}
      <div className="flex items-center gap-1 ml-auto">
        {/* Replace Background Button */}
        <Button
          variant="outline"
          className="flex items-center justify-center gap-1 border rounded-lg w-auto h-8 px-2 text-xs whitespace-nowrap"
          onClick={onUpload}
        >
          <Upload className="h-4 w-4" />
          更换底图
        </Button>
        
        <div className="h-5 w-[1px]" />
        
        <Button
          variant="outline"
          className={`flex items-center justify-center border rounded-lg w-8 h-8 text-xs ${zoomDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          onClick={handleZoomOut}
          disabled={zoomDisabled}
          aria-disabled={zoomDisabled}
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <div className="px-2 py-1 border rounded-lg text-xs min-w-[40px] text-center">
          {zoomLevel}%
        </div>
        <Button
          variant="outline"
          className={`flex items-center justify-center border rounded-lg w-8 h-8 text-xs ${zoomDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          onClick={handleZoomIn}
          disabled={zoomDisabled}
          aria-disabled={zoomDisabled}
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              className={`flex items-center justify-center border rounded-lg w-8 h-8 text-xs ${zoomDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={handleFitScreen}
              disabled={zoomDisabled}
              aria-disabled={zoomDisabled}
            >
              <ScanSquare size={16} className="w-4 h-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent sideOffset={6} showArrow={false} className="bg-white text-foreground border border-border shadow-sm">
            适应画布
          </TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
};
