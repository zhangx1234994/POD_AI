import { useCallback, useEffect, useState } from 'react';
import { EXTENSION_DEFAULTS } from '@/constants/options';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { OptionGenerationCountSelector } from './OptionGenerationCountSelector';
import { EXTENSION_RATIO_OPTIONS } from '@/constants/options';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Maximize2, RotateCcw, ArrowLeftRight, ArrowUpDown } from 'lucide-react';

export interface ExtensionSettings {
  top: number;
  bottom: number;
  left: number;
  right: number;
  mode?: 'ratio' | 'custom';
  ratioValue?: number;
  direction?: 'horizontal' | 'vertical' | 'all';
  topPercent?: number;
  bottomPercent?: number;
  leftPercent?: number;
  rightPercent?: number;
};

interface Props {
  originalWidth?: number;
  originalHeight?: number;
  value?: ExtensionSettings | null;
  onChange?: (s: ExtensionSettings) => void;
};

export function ExtensionScaleExpand({
  originalWidth = 800,
  originalHeight = 600,
  value = null,
  onChange,
}: Props) {
  const defaultSettings: ExtensionSettings = { 
    ...EXTENSION_DEFAULTS, 
    mode: 'ratio',
    // Ensure default 10% ratio is reflected in percents
    topPercent: 10,
    bottomPercent: 10,
    leftPercent: 10,
    rightPercent: 10
  };

  const [settings, setSettings] = useState<ExtensionSettings>(value || defaultSettings);

  // Sync incoming `value` prop into internal `settings` only when `value`
  // actually changes. Do not depend on `settings` here to avoid resetting
  // user-entered values while they are editing (which can cause inputs to
  // be cleared when switching tabs). Merge incoming values to avoid wiping
  // locally controlled fields.
  useEffect(() => {
    if (!value) return;
    try {
      const incoming = JSON.stringify(value);
      const current = JSON.stringify(settings);
      if (incoming !== current) {
        setSettings((prev) => ({ ...prev, ...(value as ExtensionSettings) }));
      }
    } catch (e) {
      setSettings(value as any);
    }
  }, [value]);

  const calculateRatioExtension = useCallback(
    (ratio: number, direction: 'horizontal' | 'vertical' | 'all' = 'all') => {
      const widthExtension = Math.round((originalWidth * ratio) / 100);
      const heightExtension = Math.round((originalHeight * ratio) / 100);

      if (direction === 'horizontal') {
        return { 
          left: widthExtension, right: widthExtension, top: 0, bottom: 0,
          leftPercent: ratio, rightPercent: ratio, topPercent: 0, bottomPercent: 0
        };
      }
      if (direction === 'vertical') {
        return { 
          left: 0, right: 0, top: heightExtension, bottom: heightExtension,
          leftPercent: 0, rightPercent: 0, topPercent: ratio, bottomPercent: ratio
        };
      }
      return { 
        left: widthExtension, right: widthExtension, top: heightExtension, bottom: heightExtension,
        leftPercent: ratio, rightPercent: ratio, topPercent: ratio, bottomPercent: ratio
      };
    },
    [originalWidth, originalHeight]
  );

  const handleDirectionChange = (direction: 'horizontal' | 'vertical' | 'all') => {
    const extensions = calculateRatioExtension(settings.ratioValue || 0, direction);
    const next = { ...settings, ...extensions, direction } as ExtensionSettings;
    setSettings(next);
    onChange && onChange(next);
  };

  const handleRatioChange = (ratio: number) => {
    // Limit ratio to 100% max
    const limitedRatio = Math.min(100, Math.max(0, ratio));
    const extensions = calculateRatioExtension(limitedRatio, settings.direction || 'all');
    const next = { ...settings, ...extensions, ratioValue: limitedRatio, mode: 'ratio' } as ExtensionSettings;
    setSettings(next);
    onChange && onChange(next);
  };

  const reset = () => {
    setSettings(defaultSettings);
    onChange && onChange(defaultSettings);
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

  return (
    <Card className="mb-4 px-0 mb-0 gap-6 rounded-none border-0 shadow-none">
      <CardHeader className="px-0 pb-0 gap-0">
        <div className="flex items-center justify-between w-full">
          <CardTitle className="text-sm">比例扩展</CardTitle>
          <div className="flex-shrink-0">
            <Button variant="outline" onClick={reset} className="text-sm flex items-center gap-3">
              <RotateCcw className="w-4 h-4" />
              重置
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-0 [&:last-child]:pb-0 space-y-4">
        <div className="space-y-2">
          <div className="text-xs mb-2">扩展方向</div>
          <ToggleGroup
            type="single"
            value={settings.direction || 'all'}
            onValueChange={(v) => v && handleDirectionChange(v as any)}
            className="justify-start bg-muted/10 rounded-full bg-muted/50 border border-border overflow-hidden flex"
          >
            <ToggleGroupItem value="all" className="w-30 flex-1 gap-1 border-r border-border last:border-r-0">
              <Maximize2 className="w-4 h-4 mr-2" /> 全部
            </ToggleGroupItem>
            <ToggleGroupItem value="horizontal" className="w-30 flex-1 gap-1 border-r border-border last:border-r-0">
              <ArrowLeftRight className="w-4 h-4 mr-2" /> 左右
            </ToggleGroupItem>
            <ToggleGroupItem value="vertical" className="w-30 flex-1 gap-1">
              <ArrowUpDown className="w-4 h-4 mr-2" /> 上下
            </ToggleGroupItem>
          </ToggleGroup>
        </div>

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
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="text-xs mb-2">扩展比例</div>
              <div>
                <OptionGenerationCountSelector
                  options={EXTENSION_RATIO_OPTIONS as any}
                  value={settings.ratioValue || 0}
                  onChange={(v) => handleRatioChange(Number(v))}
                  columns={5}
                  className="mb-4"
                />
              </div>
              
              <div className="px-4 py-3 bg-red-50 border border-transparent rounded-md text-sm flex items-start justify-between dark:bg-card dark:border-border">
                <div className="text-red-600">结果图尺寸:</div>

                <div className="text-red-600">
                  {settings.direction === 'horizontal' && (
                    <span>左右各扩展 <span className="underline decoration-red-600 decoration-1">{settings.ratioValue || 0}</span> %</span>
                  )}
                  {settings.direction === 'vertical' && (
                    <span>上下各扩展 <span className="underline decoration-red-600 decoration-1">{settings.ratioValue || 0}</span> %</span>
                  )}
                  {(!settings.direction || settings.direction === 'all') && (
                    <span>上下左右各扩展 <span className="underline decoration-red-600 decoration-1">{settings.ratioValue || 0}</span> %</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ExtensionScaleExpand;
