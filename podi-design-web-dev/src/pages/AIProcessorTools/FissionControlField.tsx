import React from 'react';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { HelpCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export type FissionFieldConfig = {
  label?: string;
  min: number;
  max: number;
  step: number;
  preview?: string;
  previewDesc?: string;
  lowLabel?: string;
  highLabel?: string;
  unit?: string;
};

interface Props {
  id: string;
  label: React.ReactNode;
  value: number;
  onChange: (v: number) => void;
  config: FissionFieldConfig;
  isInteger?: boolean;
  display?: (v: number) => string;
}

export const FissionControlField: React.FC<Props> = ({ id, label, value, onChange, config, isInteger = false, display }) => {
  const format = (v: number) => {
    if (display) return display(v);
    if (isInteger) return `${Math.round(v)}${config.unit ? ' ' + config.unit : ''}`;
    return v.toFixed(2) + (config.unit ? ' ' + config.unit : '');
  };

  return (
    <div className="space-y-3 w-full" data-field-id={id}>
      <div className="w-full flex items-center justify-between">
        <div className="flex items-center">
          <Label>{label}</Label>
          {config.preview ? (
            <HoverCard>
              <HoverCardTrigger asChild>
                <button aria-label={`${id}-help`} className="ml-2 w-6 h-6 text-muted-foreground hover:text-foreground focus:outline-none" title="查看示例">
                  <HelpCircle className="w-4 h-4" />
                </button>
              </HoverCardTrigger>
              <HoverCardContent
                className="p-2"
                sideOffset={8}
                align="center"
                side="top"
                style={{ width: 400, minHeight: 200 }}
              >
                <div className="flex flex-col items-center gap-2">
                  <img src={config.preview} alt="示例" className="w-full max-h-40 object-contain rounded" />
                  {config.previewDesc ? (
                    <div className="mt-2 px-4 pb-2">
                      <div className="text-sm font-medium">{config.label}</div>
                      <div className="text-xs text-muted-foreground">{config.previewDesc}</div>
                    </div>
                  ) : null}
                </div>
              </HoverCardContent>
            </HoverCard>
          ) : null}
        </div>

        <Badge variant="outline" className="text-xs bg-muted rounded-full">
          {format(value)}
        </Badge>
      </div>

      <Slider
        className="w-full"
        value={[value]}
        onValueChange={(v: number[]) => {
          const raw = v[0];
          const next = isInteger ? Math.round(raw) : Number(raw.toFixed(2));
          onChange(next);
        }}
        min={config.min}
        max={config.max}
        step={config.step}
      />

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{config.lowLabel ?? ''}</span>
        <span>{config.highLabel ?? ''}</span>
      </div>
    </div>
  );
};

export default FissionControlField;
