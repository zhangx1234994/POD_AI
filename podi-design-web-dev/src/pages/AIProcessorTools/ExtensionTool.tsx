import { Dispatch, SetStateAction, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ExtensionScaleExpand } from './ExtensionScaleExpand';
import { ExtensionCustomExpand } from './ExtensionCustomExpand';
import { EXTENSION_STYLE_OPTIONS } from '@/constants/options';
import { FeatureDescription } from './FeatureDescription';
import { FeatureTip } from './FeatureTip';
import { Info } from 'lucide-react';
import { OptionImageOptimizationSelector } from './OptionImageOptimizationSelector';
import type { ExtensionSettings } from '@/types/options';
import { EXTENSION_DEFAULTS } from '@/constants/options';
import { toast } from 'sonner';

interface Props {
  extensionStyle: string;
  setExtensionStyle: (s: string) => void;
  extensionSettingsScale: ExtensionSettings;
  setExtensionSettingsScale: Dispatch<SetStateAction<ExtensionSettings>>;
  extensionSettingsCustom: ExtensionSettings;
  setExtensionSettingsCustom: Dispatch<SetStateAction<ExtensionSettings>>;
  extensionTab: 'scale' | 'custom';
  setExtensionTab: (t: 'scale' | 'custom') => void;
  imageDimensions: { width: number; height: number };
  isImageLoaded: boolean;
  imageCount: number;
};

export function ExtensionTool({
  extensionStyle,
  setExtensionStyle,
  extensionSettingsScale,
  setExtensionSettingsScale,
  extensionSettingsCustom,
  setExtensionSettingsCustom,
  extensionTab,
  setExtensionTab,
  imageDimensions,
  isImageLoaded,
  imageCount,
}: Props) {
  const handleExtensionStyleClick = (key: string) => setExtensionStyle(key);
  
  const handleTabChange = (value: string) => {
    const tab = value as 'scale' | 'custom';
    setExtensionTab(tab);
    
    if (tab === 'scale') {
      setExtensionSettingsScale({
        ...EXTENSION_DEFAULTS,
        mode: 'ratio',
        ratioValue: 10,
        direction: 'all',
        topPercent: 10,
        bottomPercent: 10,
        leftPercent: 10,
        rightPercent: 10,
        // Reset pixels to 0 as we use percentages for logic
        top: 0, bottom: 0, left: 0, right: 0
      });
    } else if (tab === 'custom') {
      setExtensionSettingsCustom({
        ...EXTENSION_DEFAULTS,
        mode: 'custom',
        ratioValue: 0,
        topPercent: 0,
        bottomPercent: 0,
        leftPercent: 0,
        rightPercent: 0,
        top: 0, bottom: 0, left: 0, right: 0
      });
    }
  };

  // 实时校验：当扩展设置处于自定义扩图模式时，若上传图片超过1张，立即显示提示
  useEffect(() => {
    if (extensionTab === 'custom' && imageCount > 1) {
      toast.error('自定义扩图设置仅支持单图模式');
    }
  }, [extensionTab, imageCount]);
  
  return (
    <div>
      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-md font-medium">扩展风格</CardTitle>
            <Badge variant="outline" className="text-xs">
              必选
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <OptionImageOptimizationSelector options={EXTENSION_STYLE_OPTIONS as any} value={extensionStyle} onChange={handleExtensionStyleClick} columns={2} />
          <div className="pt-4">
            <FeatureDescription info={EXTENSION_STYLE_OPTIONS.find((p) => p.key === extensionStyle)?.info} />
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-md font-medium">扩展设置</CardTitle>
            {isImageLoaded && (
              <Badge variant="outline" className="text-xs">
                <Info className="w-3 h-3 mr-1" />
                已识别图片尺寸
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={extensionTab} onValueChange={handleTabChange}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="scale" className="flex items-center gap-2">按比例扩图</TabsTrigger>
              <TabsTrigger 
                value="custom" 
                className="flex items-center gap-2"
                disabled={imageCount !== 1}
              >
                自定义扩图
              </TabsTrigger>
            </TabsList>

            <TabsContent value="scale">
              <ExtensionScaleExpand
                originalWidth={imageDimensions.width}
                originalHeight={imageDimensions.height}
                value={extensionSettingsScale as any}
                onChange={(s) => setExtensionSettingsScale(s as any)}
              />
            </TabsContent>

            <TabsContent value="custom">
              <ExtensionCustomExpand
                originalWidth={imageDimensions.width}
                originalHeight={imageDimensions.height}
                value={extensionSettingsCustom as any}
                onChange={(s) => setExtensionSettingsCustom(s as any)}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="mb-3">
        <FeatureTip tip={"支持按比例扩图（全部、左右、上下）和自定义扩图两种模，单向扩展最大支持600px，自定义模式支持像素和百分比两种输入方式且仅支持单图模式。"} />
      </div>
    </div>
  );
};

export default ExtensionTool;
