import { useEffect, useState } from 'react';
import { EXTENSION_DEFAULTS } from '@/constants/options';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RotateCcw, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';

export interface CustomExtensionSettings {
  top: number;
  bottom: number;
  left: number;
  right: number;
  topPercent?: number;
  bottomPercent?: number;
  leftPercent?: number;
  rightPercent?: number;
};

interface Props {
  originalWidth?: number;
  originalHeight?: number;
  value?: CustomExtensionSettings | null;
  onChange?: (s: CustomExtensionSettings) => void;
};

export function ExtensionCustomExpand({
  originalWidth = 800,
  originalHeight = 600,
  value = null,
  onChange,
}: Props) {
  const defaultSettings: CustomExtensionSettings = { ...EXTENSION_DEFAULTS } as any;

  const [settings, setSettings] = useState<CustomExtensionSettings>(value || defaultSettings);

  // Sync incoming `value` prop into internal `settings` only when `value`
  // actually changes. Do not depend on `settings` here to avoid resetting
  // user-entered values while they are editing (which caused inputs to be
  // cleared when switching tabs).
  useEffect(() => {
    if (!value) return;
    
    setSettings((prev) => {
      const next = { ...prev };
      let hasChange = false;

      // Check each direction for percentage changes
      (['top', 'bottom', 'left', 'right'] as const).forEach(dir => {
        const percentKey = `${dir}Percent` as keyof CustomExtensionSettings;
        const incomingPercent = value[percentKey];
        const currentPercent = prev[percentKey];
        
        // Only update if percentage has changed externally (or initial load)
        // This prevents overwriting local pixel values when parent echoes back 0 pixels
        if (incomingPercent !== currentPercent) {
           next[percentKey] = incomingPercent as number;
           hasChange = true;
           
           // If percentage changed, we should also update the pixel value to match
           // If incoming has explicit pixels (non-zero), use them.
           // Otherwise, calculate from percentage to keep UI consistent.
           if (value[dir] && value[dir] !== 0) {
              next[dir] = value[dir];
           } else {
              const isVertical = dir === 'top' || dir === 'bottom';
              const base = isVertical ? originalHeight : originalWidth;
              // Calculate pixels from the new percentage
              next[dir] = Math.round((base * (incomingPercent as number)) / 100);
           }
        }
      });
      
      // If any other fields changed (like reset or new object structure), merge them
      // But we primarily care about the directions.
      // Let's do a safe merge for other properties if needed, but for now just returning next is safe
      // as we cloned prev.
      
      return hasChange ? next : prev;
    });
  }, [value, originalWidth, originalHeight]);

  const handlePixelChange = (direction: 'top' | 'bottom' | 'left' | 'right', v: number) => {
    const isVertical = direction === 'top' || direction === 'bottom';
    const base = isVertical ? originalHeight : originalWidth;
    
    // Calculate max pixels based on 100% limit
    // If base is 0 (e.g. image not loaded yet), fallback to just 600 limit
    const maxPixelsByPercent = base > 0 ? Math.floor(base * 1.0) : 600;
    
    // Dual limit: max 600px AND max 100%
    const finalMaxPixels = Math.min(600, maxPixelsByPercent);
    
    const limited = Math.max(0, Math.min(finalMaxPixels, v));
    
    // Calculate percentage from pixels for display
    const computedPercent = base > 0 ? Math.round((limited / base) * 100) : 0;
    
    // Update local state with exact pixel input and calculated percentage
    // We do NOT back-calculate pixels from the percentage here, to prevent input jumping
    const next = { ...settings, [direction]: limited, [`${direction}Percent`]: computedPercent } as any;
    setSettings(next);

    // Send only percentage to parent (pixels zeroed out for encapsulation)
    const percentOnlyNext = { 
      ...settings, 
      [`${direction}Percent`]: computedPercent,
      left: 0, right: 0, top: 0, bottom: 0
    } as any;
    onChange && onChange(percentOnlyNext);
  };

  const handlePercentChange = (direction: 'top' | 'bottom' | 'left' | 'right', p: number) => {
    const isVertical = direction === 'top' || direction === 'bottom';
    const base = isVertical ? originalHeight : originalWidth;
    
    // Calculate max percent based on 600px limit
    const maxPercentByPixels = base > 0 ? Math.floor((600 / base) * 100) : 100;
    
    // Dual limit: max 100% AND max 600px equivalent
    const finalMaxPercent = Math.min(100, maxPercentByPixels);
    
    const limitedPercent = Math.max(0, Math.min(p, finalMaxPercent));
    
    // Calculate pixels from percentage for display
    const pixels = Math.round((base * limitedPercent) / 100);
    
    const next = { ...settings, [direction]: pixels, [`${direction}Percent`]: limitedPercent } as any;
    setSettings(next);

    // Send only percentage to parent
    const percentOnlyNext = { 
      ...settings, 
      [`${direction}Percent`]: limitedPercent,
      left: 0, right: 0, top: 0, bottom: 0
    } as any;
    onChange && onChange(percentOnlyNext);
  };

  const reset = () => {
    setSettings(defaultSettings);
    // 只传递百分比值给父组件，像素值设为0
    const percentOnlyDefault = { ...defaultSettings, left: 0, right: 0, top: 0, bottom: 0 };
    onChange && onChange(percentOnlyDefault);
  };

  // Fixed visual dimensions for preview
  const VISUAL_BASE_WIDTH = 120;
  const VISUAL_BASE_HEIGHT = 90;
  
  const visualLeftExtension = VISUAL_BASE_WIDTH * ((settings.leftPercent || 0) / 100);
  const visualRightExtension = VISUAL_BASE_WIDTH * ((settings.rightPercent || 0) / 100);
  const visualTopExtension = VISUAL_BASE_HEIGHT * ((settings.topPercent || 0) / 100);
  const visualBottomExtension = VISUAL_BASE_HEIGHT * ((settings.bottomPercent || 0) / 100);

  const visualOriginalWidth = VISUAL_BASE_WIDTH;
  const visualOriginalHeight = VISUAL_BASE_HEIGHT;
  const visualNewWidth = VISUAL_BASE_WIDTH + visualLeftExtension + visualRightExtension;
  const visualNewHeight = VISUAL_BASE_HEIGHT + visualTopExtension + visualBottomExtension;

  const hasTop = (settings.topPercent || 0) > 0;
  const hasBottom = (settings.bottomPercent || 0) > 0;
  const hasLeft = (settings.leftPercent || 0) > 0;
  const hasRight = (settings.rightPercent || 0) > 0;
  
  return (
    <Card className="mb-4 px-0 mb-0 gap-6 rounded-none border-0 shadow-none">
      <CardHeader className="px-0 pb-0 gap-0">
        <CardTitle>
          <div className="text-md font-medium h-9 flex items-center justify-between w-full">自定义扩展</div>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0 [&:last-child]:pb-0 space-y-4">
        <div className="flex justify-center p-4 bg-gradient-to-br from-muted to-muted/50 rounded-lg border">
          <div className="relative inline-block">
            <div
              className="border-2 border-dashed border-primary/30 bg-primary/5 relative rounded"
              style={{ width: `${visualNewWidth}px`, height: `${visualNewHeight}px` }}
            >
              <div
                className="absolute bg-white dark:bg-gray-800 border-2 border-primary shadow-sm rounded"
                style={{
                  width: `${visualOriginalWidth}px`,
                  height: `${visualOriginalHeight}px`,
                  left: `${visualLeftExtension}px`,
                  top: `${visualTopExtension}px`,
                }}
              >
                <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">原图</div>
              </div>
              {settings.topPercent! > 0 && <div className="absolute top-1 left-1/2 transform -translate-x-1/2 text-xs text-primary font-medium bg-white dark:bg-gray-800 px-1 rounded">↑ {settings.topPercent}%</div>}
              {settings.bottomPercent! > 0 && <div className="absolute bottom-1 left-1/2 transform -translate-x-1/2 text-xs text-primary font-medium bg-white dark:bg-gray-800 px-1 rounded">↓ {settings.bottomPercent}%</div>}
              {settings.leftPercent! > 0 && <div className="absolute left-1 top-1/2 transform -translate-y-1/2 text-xs text-primary font-medium bg-white dark:bg-gray-800 px-1 rounded">← {settings.leftPercent}%</div>}
              {settings.rightPercent! > 0 && <div className="absolute right-1 top-1/2 transform -translate-y-1/2 text-xs text-primary font-medium bg-white dark:bg-gray-800 px-1 rounded">→ {settings.rightPercent}%</div>}
            </div>
          </div>
        </div>

        <div className="space-y-2 pt-2">
          <div className="text-xs mb-2">扩展方向与数值</div>
          <div className="grid grid-cols-3 gap-4 pb-2">
            <div></div>
            <div className="space-y-2 -mt-2">
              <div className="flex items-center justify-center gap-1 text-sm text-muted-foreground">
                <ArrowUp className="w-5 h-5" />
                <span className="font-md font-bold text-black">向上</span>
              </div>
              <div className="w-full flex items-center justify-center gap-1 text-sm text-muted-foreground">
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.top || ''}
                    onChange={(e) => handlePixelChange('top', parseInt(e.target.value) || 0)}
                    placeholder="px"
                    min={0}
                    max={600}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">px</span>
                </div>
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.topPercent || ''}
                    onChange={(e) => handlePercentChange('top', parseInt(e.target.value) || 0)}
                    placeholder="0"
                    min={0}
                    max={Math.round((600 / originalHeight) * 100)}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                </div>
              </div>
            </div>
            <div></div>

            <div className="space-y-2">
              <div className="flex items-center justify-end gap-1 text-sm text-muted-foreground">
                <ArrowLeft className="w-5 h-5" />
                <span className="font-md font-bold text-black">向左</span>
              </div>
              <div className="flex items-center justify-end gap-1 text-sm text-muted-foreground">
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.left || ''}
                    onChange={(e) => handlePixelChange('left', parseInt(e.target.value) || 0)}
                    placeholder="px"
                    min={0} max={600}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">px</span>
                </div>
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.leftPercent || ''}
                    onChange={(e) => handlePercentChange('left', parseInt(e.target.value) || 0)}
                    placeholder="0"
                    min={0}
                    max={Math.round((600 / originalWidth) * 100)}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                </div>
              </div>
            </div>

            {/* Reset button row (span full width) */}
            <div className="col-span-1 flex items-end justify-center">
              <Button variant="outline" size="sm" onClick={reset} className="w-full h-9 flex items-center justify-center gap-2">
                <RotateCcw className="w-4 h-4" />
                <span className="text-sm">重置所有参数</span>
              </Button>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-start gap-1 text-sm text-muted-foreground">
                <ArrowRight className="w-5 h-5" />
                <span className="font-md font-bold text-black">向右</span>
              </div>
              <div className="flex items-center justify-start gap-1 text-sm text-muted-foreground">
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.right || ''}
                    onChange={(e) => handlePixelChange('right', parseInt(e.target.value) || 0)}
                    placeholder="px"
                    min={0}
                    max={600}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">px</span>
                </div>
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.rightPercent || ''}
                    onChange={(e) => handlePercentChange('right', parseInt(e.target.value) || 0)}
                    placeholder="0"
                    min={0}
                    max={Math.round((600 / originalWidth) * 100)}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                </div>
              </div>
            </div>

            <div></div>
            <div className="space-y-2">
              <div className="flex items-center justify-center gap-1 text-sm text-muted-foreground">
                <ArrowDown className="w-5 h-5" />
                <span className="font-md font-bold text-black">向下</span>
              </div>
              <div className="flex items-center justify-center gap-1 text-sm text-muted-foreground">
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.bottom || ''}
                    onChange={(e) => handlePixelChange('bottom', parseInt(e.target.value) || 0)}
                    placeholder="px"
                    min={0}
                    max={600}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">px</span>
                </div>
                <div className="relative">
                  <Input
                    type="number"
                    value={settings.bottomPercent || ''}
                    onChange={(e) => handlePercentChange('bottom', parseInt(e.target.value) || 0)}
                    placeholder="0"
                    min={0}
                    max={Math.round((600 / originalHeight) * 100)}
                    className="text-center text-xs h-9 w-full pr-5"
                  />
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                </div>
              </div>
            </div>

            <div></div>
          </div>
          <p className="text-xs text-muted-foreground text-center">左侧输入像素值(px)，右侧输入百分比(%)，最大为600px。</p>
        </div>

        <div className="px-4 py-3 bg-red-50 border border-transparent rounded-md text-sm flex items-start justify-between dark:bg-card dark:border-border">
          <div className="text-red-600">结果图尺寸:</div>
          <div className="text-right text-red-600">
            {hasTop && (
              <div className="text-sm">向上扩展 <span className="font-medium text-red-700 ml-1 underline decoration-red-600 decoration-1">{settings.topPercent}</span> %</div>
            )}
            {hasBottom && (
              <div className="text-sm">向下扩展 <span className="font-medium text-red-700 ml-1 underline decoration-red-600 decoration-1">{settings.bottomPercent}</span> %</div>
            )}
            {hasLeft && (
              <div className="text-sm">向左扩展 <span className="font-medium text-red-700 ml-1 underline decoration-red-600 decoration-1">{settings.leftPercent}</span> %</div>
            )}
            {hasRight && (
              <div className="text-sm">向右扩展 <span className="font-medium text-red-700 ml-1 underline decoration-red-600 decoration-1">{settings.rightPercent}</span> %</div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ExtensionCustomExpand;
