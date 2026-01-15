import React from 'react';
import FeatureDescription from './FeatureDescription';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FISSION_CONTROL_SETTINGS, FISSION_GENERATION_COUNT_OPTIONS } from '@/constants/options';
import { FissionControlField } from './FissionControlField';
import { OptionGenerationCountSelector } from './OptionGenerationCountSelector';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

export interface FissionSettings {
  count: string | number;
  reference: number;
  creative: number;
  enhanced: boolean;
}

interface FissionToolProps {
  settings: FissionSettings;
  setSettings: (s: FissionSettings | ((prev: FissionSettings) => FissionSettings)) => void;
}

export const FissionTool: React.FC<FissionToolProps> = ({ settings, setSettings }) => {
  const handleCountChange = (value: string | number) => {
    setSettings(prev => ({ ...(prev as any), count: String(value) }));
  };
  return (
    <div>
      <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
        <CardHeader>
          <CardTitle className="text-md font-medium">参数设置</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6 gap-6">
          {/* 原图参考强度 */}
          <div className="space-y-4 fission-params">
            <input
              type="hidden"
              data-model="comfy"
              data-reference-strength={settings.reference.toFixed(2)}
              data-creative-strength={settings.creative.toFixed(2)}
            />
            <div className="space-y-4">
              {
                // render controls from the config array; keep a safe fallback if config is empty
                Array.isArray(FISSION_CONTROL_SETTINGS) && FISSION_CONTROL_SETTINGS.length > 0 &&
                  (FISSION_CONTROL_SETTINGS as any[]).map((cfg, index) => {
                    if (!cfg || !cfg.key) return null;

                    // destructure once for clarity
                    const {
                      key: cfgKey,
                      label: cfgLabel,
                      min,
                      max,
                      step,
                      preview,
                      previewDesc,
                      lowLabel: cfgLowLabel,
                      highLabel: cfgHighLabel,
                      unit,
                      isInteger,
                    } = cfg as any;

                    const id = cfgKey as string;
                    const label = cfgLabel ?? id;
                    const lowLabel = cfgLowLabel ?? '';
                    const highLabel = cfgHighLabel ?? '';
                    const integer = !!isInteger;

                    // current value from settings; default to 0 if missing
                    const value = (settings as any)[id] as number ?? 0;

                    // memoized display formatter for integer types
                    const display = integer ? ((v: number) => `${Math.round(v)}${unit ? ' ' + unit : ''}`) : undefined;

                    return (
                      <FissionControlField
                        key={id ?? index}
                        id={id}
                        label={<>{label}</>}
                        value={value}
                        onChange={(v: number) => {
                          setSettings((prev) => ({
                            ...prev,
                            [id]: integer ? Math.round(v) : v,
                          } as any));
                        }}
                        isInteger={integer}
                        config={{
                          label,
                          min,
                          max,
                          step,
                          preview,
                          previewDesc,
                          lowLabel,
                          highLabel,
                          unit,
                        }}
                        display={display}
                      />
                    );
                  })
              }
            </div>
          </div>

          {/* 生成数量 */}
          <div className="space-y-4 pt-6 pb-4">
            <div className="flex items-center justify-between">
              <div className="text-md font-medium">生成数量</div>
              <div className="text-md font-medium">
                <Badge variant="outline" className="text-xs bg-muted rounded-full">
                  {settings.count} 张
                </Badge>
              </div>
            </div>
            
            <OptionGenerationCountSelector
              options={FISSION_GENERATION_COUNT_OPTIONS}
              value={settings.count}
              onChange={handleCountChange}
              columns={4}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm mb-4 gap-4 hover:shadow-md transition-shadow">
        <CardHeader className="pb-0 gap-0">
          <CardTitle className="text-md font-medium">高级设置</CardTitle>
        </CardHeader>
        <CardContent className="px-6 pb-6">
          <Switch
            id="fission-enhanced-mode"
            checked={settings.enhanced}
            onCheckedChange={(checked) => setSettings(prev => ({ ...prev, enhanced: checked }))}
            label="文字加强功能"
            description="开启后将针对图片中的文字部分进行细节优化"
          />
        </CardContent>
      </Card>
      
      <div className="mt-3">
        <FeatureDescription
          info={
            '图裂变功能会基于原图生成多张风格相似但细节不同的变体图，适合快速获得多种设计方案。原图参考强度和创意发散强度可以共同调节生成效果。支持批量上传最多50张图片，每张图片将生成4个变体。'
          }
        />
      </div>
    </div>
  );
};

export default FissionTool;
