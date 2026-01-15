import { useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { PATTERN_EXTRACT_CATEGORY_OPTIONS, IMAGE_GENERATION_SIZE_OPTIONS } from '@/constants/options';
import { OptionSceneModeSelector } from './OptionSceneModeSelector';
import { OptionImageOptimizationSelector } from './OptionImageOptimizationSelector';
import { FeatureTip } from './FeatureTip';

interface Props {
  category: string;
  setCategory: (c: string) => void;
  imageSize: string;
  setImageSize: (s: string) => void;
  enhanced: boolean;
  setEnhanced: (e: boolean) => void;
  // optional: pass through the firstImage dimensions so custom inputs can be pre-filled
  firstImage?: { width?: number; height?: number } | null;
  onCustomSizeChange?: (width: number | undefined, height: number | undefined) => void;
};

export function PatternExtractTool({ 
  category, 
  setCategory, 
  imageSize, 
  setImageSize, 
  enhanced,
  setEnhanced,
  firstImage = null, 
  onCustomSizeChange, 
}: Props) {
  useEffect(() => {
    if (category !== undefined) setCategory(category);
    if (imageSize !== undefined) setImageSize(imageSize);
  }, [setCategory, imageSize]);


  const handleImageSizeClick = (key: string) => {
    if (imageSize) setImageSize(key);
    else setImageSize(key);
  };

  const handleCategoryChange = (key: string) => {
    const opt = PATTERN_EXTRACT_CATEGORY_OPTIONS.find((c) => c.key === key);
    if (!opt || opt.disabled) return;
    setCategory(key);
  };

  return (
    <div>
      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-md font-medium">选择品类</CardTitle>
            <Badge variant="outline" className="text-xs bg-muted rounded-full">
              可选
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <p className="text-xs text-muted-foreground pb-4">
            选择印花的应用场景，我们更擅长的提取效果，默认使用通用模式
          </p>
          <OptionSceneModeSelector options={PATTERN_EXTRACT_CATEGORY_OPTIONS as any} value={category} onChange={handleCategoryChange} columns={4} />
        </CardContent>
      </Card>

      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">生图大小</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <OptionImageOptimizationSelector options={IMAGE_GENERATION_SIZE_OPTIONS} value={imageSize} onChange={handleImageSizeClick} firstImage={firstImage} onCustomSizeChange={onCustomSizeChange} />
        </CardContent>
      </Card>

      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">高级设置</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <Switch
            id="fission-enhanced-mode"
            checked={enhanced}
            onCheckedChange={setEnhanced}
            label="文字加强功能"
            description="开启后将针对图片中的文字部分进行细节优化"
          />
        </CardContent>
      </Card>

      <div className="mt-3">
        <FeatureTip
          tip={`印花提取可以智能识别并提取图片中的印花图案，去除背景和干扰元素。支持针对不同产品品类的优化提取。`}
        />
      </div>
    </div>
  );
};

export default PatternExtractTool;
