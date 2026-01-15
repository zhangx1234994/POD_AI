import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PATTERN_MODE_OPTIONS, IMAGE_GENERATION_SIZE_OPTIONS } from '@/constants/options';
import { OptionSceneModeSelector } from './OptionSceneModeSelector';
import { OptionImageOptimizationSelector } from './OptionImageOptimizationSelector';
import { FeatureDescription } from './FeatureDescription';

interface Props {
  imageSize: string;
  setImageSize: (s: string) => void;
  patternType?: string;
  setPatternType?: (t: string) => void;
  // optional: first image dims to prefill custom inputs
  firstImage?: { width?: number; height?: number } | null;
  // callback when custom width/height change
  onCustomSizeChange?: (width: number | undefined, height: number | undefined) => void;
};

export function SeamlessTool({ imageSize, setImageSize, patternType, setPatternType, firstImage, onCustomSizeChange }: Props) {
  const [internalPattern, setInternalPattern] = useState<string>(patternType ?? 'four');

  useEffect(() => {
    if (patternType !== undefined) setInternalPattern(patternType);
    if (imageSize !== undefined) setImageSize(imageSize);
  }, [patternType, imageSize]);

  const currentPattern = patternType ?? internalPattern;
  const selectedOption = PATTERN_MODE_OPTIONS.find((p) => p.key === currentPattern);

  const handlePatternClick = (key: string) => {
    if (setPatternType) setPatternType(key);
    else setInternalPattern(key);
  };

  const handleImageSizeClick = (key: string) => {
    if (imageSize) setImageSize(key);
    else setImageSize(key);
  };

  return (
    <div>
      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">图案类型</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <OptionSceneModeSelector options={PATTERN_MODE_OPTIONS as any} value={currentPattern} onChange={handlePatternClick} columns={2} />
          {/* <OptionImageOptimizationSelector options={PATTERN_MODE_OPTIONS as any} value={currentPattern} onChange={handlePatternClick} columns={1} /> */}
          <div className="mt-6">
            <FeatureDescription info={selectedOption?.info} desc={selectedOption?.desc} />
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">生图大小</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <OptionImageOptimizationSelector
            options={IMAGE_GENERATION_SIZE_OPTIONS}
            value={imageSize}
            onChange={handleImageSizeClick}
            columns={2}
            firstImage={firstImage ?? null}
            onCustomSizeChange={onCustomSizeChange}
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default SeamlessTool;
