import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { 
  Columns2, 
  SlidersHorizontal, 
  Layers, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Minimize,
  LayoutGrid,
} from 'lucide-react';
import { cn } from '@/components/ui/utils';
import { Input } from '@/components/ui/input';
import React, { useState, useEffect } from 'react';

export type ViewMode = 'split' | 'slider' | 'overlay' | 'seamless';

interface ToolbarProps {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetZoom: () => void;
  onClose: () => void;
  onScaleChange?: (newScale: number) => void;
  className?: string;
  isSeamless?: boolean;
}

export function Toolbar({
  mode,
  onModeChange,
  scale,
  onZoomIn,
  onZoomOut,
  onResetZoom,
  onClose,
  onScaleChange,
  className,
  isSeamless = false,
}: ToolbarProps) {
  const [inputValue, setInputValue] = useState(Math.round(scale * 100).toString());

  useEffect(() => {
    setInputValue(Math.round(scale * 100).toString());
  }, [scale]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleInputBlur = () => {
    let value = parseInt(inputValue, 10);
    if (isNaN(value)) {
      setInputValue(Math.round(scale * 100).toString());
      return;
    }
    // Clamp between 10 and 500
    value = Math.min(Math.max(value, 10), 500);
    
    if (onScaleChange) {
      onScaleChange(value / 100);
    } else {
      setInputValue(Math.round(scale * 100).toString());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <div className={cn(
      "absolute top-0 left-0 right-0 z-50 flex items-center justify-between pb-3 bg-background/95 backdrop-blur border-b border-border/10 shadow-sm",
      className
    )}>
      {/* Left: Mode Switcher */}
      <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg">
        <Button
          variant={mode === 'split' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onModeChange('split')}
          className="h-8 px-3"
        >
          <Columns2 className="w-4 h-4 mr-2" />
          分屏
        </Button>
        <Button
          variant={mode === 'slider' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onModeChange('slider')}
          className="h-8 px-3"
        >
          <SlidersHorizontal className="w-4 h-4 mr-2" />
          滑块
        </Button>
        <Button
          variant={mode === 'overlay' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => onModeChange('overlay')}
          className="h-8 px-3"
        >
          <Layers className="w-4 h-4 mr-2" />
          叠加
        </Button>
        {isSeamless && (
          <Button
            variant={mode === 'seamless' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => onModeChange('seamless')}
            className="h-8 px-3"
          >
            <LayoutGrid className="w-4 h-4 mr-2" />
            连续拼接
          </Button>
        )}
      </div>

      {/* Center: Zoom Controls */}
      <div className="flex items-center gap-2 bg-muted/50 p-1 rounded-lg">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomOut}>
          <ZoomOut className="w-4 h-4" />
        </Button>
        
        <div className="relative flex items-center">
          <Input
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onBlur={handleInputBlur}
            onKeyDown={handleKeyDown}
            className="h-8 w-16 text-center pr-4 border-none shadow-none bg-background focus-visible:ring-1"
          />
          <span className="absolute right-2 text-xs text-muted-foreground pointer-events-none">%</span>
        </div>

        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomIn}>
          <ZoomIn className="w-4 h-4" />
        </Button>
        <Separator orientation="vertical" className="h-4 mx-1" />
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onResetZoom} title="重置">
          <RotateCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Right: Close */}
      <Button 
        variant="ghost" 
        size="icon" 
        onClick={onClose}
        className="h-10 w-10 rounded-full hover:bg-destructive/10 hover:text-destructive"
      >
        <Minimize className="w-5 h-5" />
      </Button>
    </div>
  );
};

export default Toolbar;
