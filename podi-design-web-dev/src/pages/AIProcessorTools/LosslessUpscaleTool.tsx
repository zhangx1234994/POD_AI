import { useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { UPSCALE_FACTOR_OPTIONS } from '@/constants/options';
import { OptionImageOptimizationSelector } from './OptionImageOptimizationSelector';
import { FeatureTip } from './FeatureTip';

interface Props {
  scale: string;
  setScale: (s: string) => void;
};

export function LosslessUpscaleTool({ scale, setScale }: Props) {
  useEffect(() => {
    if (scale !== undefined) setScale(scale);
  }, [scale]);

  const handleScaleClick = (key: string) => {
    if (scale) setScale(key);
    else setScale(key);
  };

  return (
    <div>
      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">放大设置</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          <OptionImageOptimizationSelector options={UPSCALE_FACTOR_OPTIONS} value={scale} onChange={handleScaleClick} columns={4} />
          <div className="pt-6 text-xs text-muted-foreground">倍数越高，处理时间越长，文件体积也会相应增大</div>
        </CardContent>
      </Card>

      <div className="mt-4">
        <FeatureTip
          tip={`无损放大采用AI技术提升图片分辨率，支持批量处理。建议根据实际需求选择合适的放大倍数。`}
        />
      </div>
    </div>
  );
};

export default LosslessUpscaleTool;
