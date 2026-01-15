import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { HelpCircle } from 'lucide-react';
export type OptionItem = {
  key: string;
  // support both shapes used across tools
  label?: string;
  title?: string;
  desc?: string;
  badge?: string;
  disabled?: boolean;
  preview?: string;
};
interface Props {
  options: OptionItem[];
  value: string;
  onChange: (key: string) => void;
  columns?: number;
  className?: string;
  // optional: when showing the custom inputs, prefill with this image's dimensions
  firstImage?: { width?: number; height?: number } | null;
  // callback to send custom width/height back to parent
  onCustomSizeChange?: (width: number | undefined, height: number | undefined) => void;
};
/**
 * OptionImageOptimizationSelector
 * - Cards with large touch targets, title over description, optional badge
 * - Selected state shows a colored border and a small check marker at top-left
 * - Supports disabled state and optional hover preview using project's HoverCard
 */
export function OptionImageOptimizationSelector({ options, value, onChange, className = '', firstImage = null, onCustomSizeChange, }: Props) {
  const [customW, setCustomW] = useState<number | undefined>(firstImage?.width ?? undefined);
  const [customH, setCustomH] = useState<number | undefined>(firstImage?.height ?? undefined);
  // when firstImage changes, sync the inputs (useful when user uploads a new image)
  useEffect(() => {
  if (firstImage?.width) setCustomW(firstImage.width);
  if (firstImage?.height) setCustomH(firstImage.height);
  }, [firstImage?.width, firstImage?.height]);

  // when the selected value changes from parent, reset or set inputs accordingly
  useEffect(() => {
    if (value === 'auto') {
      const w = firstImage?.width ?? undefined;
      const h = firstImage?.height ?? undefined;
      setCustomW(w);
      setCustomH(h);
      if (onCustomSizeChange) onCustomSizeChange(w, h);
    } else {
      // clear custom inputs when selecting other options
      setCustomW(undefined);
      setCustomH(undefined);
      if (onCustomSizeChange) onCustomSizeChange(undefined, undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const handleSelect = (key: string) => {
    if (key === 'auto') {
      const w = firstImage?.width ?? undefined;
      const h = firstImage?.height ?? undefined;
      setCustomW(w);
      setCustomH(h);
      if (onCustomSizeChange) onCustomSizeChange(w, h);
    } else {
      setCustomW(undefined);
      setCustomH(undefined);
      if (onCustomSizeChange) onCustomSizeChange(undefined, undefined);
    }
    onChange(key);
  };
  return (
    <div className={`${className} grid grid-cols-1 lg:grid-cols-2 items-stretch gap-3`}>
      {options.map((opt) => {
        const label = opt.label ?? opt.title ?? '';
        const desc = opt.desc ?? '';
        const selected = String(value) === String(opt.key);
        const disabled = Boolean((opt as any).disabled);
        return (
          <div key={opt.key} className="flex items-stretch gap-2">
            <button
              role="button"
              aria-pressed={selected}
              aria-disabled={disabled}
              className={`p-3 border rounded-lg transition-all h-full flex flex-1 items-center 
                ${selected ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-card'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'}`}
              onClick={() => { if (!disabled) handleSelect(opt.key); }}
              tabIndex={disabled ? -1 : 0}
              onKeyDown={(e) => {
                if (disabled) return;
                if (e.key === 'Enter' || e.key === ' ') handleSelect(opt.key);
              }}
            >
              <div className="flex items-center gap-3 w-full">
                <div className={`flex-shrink-0 w-4 h-4 rounded-full border relative flex items-center justify-center ${selected ? 'border-primary' : 'border-muted-foreground'}`}> 
                  {selected && <div className="w-2 h-2 rounded-full bg-primary" />}
                </div>
                <div className="flex-1 min-w-0 flex items-center">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="text-sm font-medium">{label}</div>
                    {opt.badge && (
                      <Badge variant={opt.badge === '推荐' ? 'secondary' : 'outline'} className="text-xs ml-2">
                        {opt.badge}
                      </Badge>
                    )}
                    {desc && <div className="text-xs text-muted-foreground whitespace-pre-wrap break-words text-center">{desc}</div>}
                    {opt.preview && (
                      <HoverCard>
                        <HoverCardTrigger asChild>
                          <div
                            role="button"
                            tabIndex={0}
                            className="ml-2 w-6 h-6 rounded-full text-xs flex items-center justify-center"
                            aria-label={`preview ${label}`}
                          >
                            <HelpCircle className="w-4 h-4 text-muted-foreground" />
                          </div>
                        </HoverCardTrigger>
                        <HoverCardContent
                          className="p-2"
                          sideOffset={8}
                          align="center"
                          side="top"
                          style={{ width: 400, minHeight: 200 }}
                        >
                          <div className="rounded-md overflow-hidden bg-muted/5">
                            <img
                              src={opt.preview}
                              alt={`${opt.key} preview`}
                              style={{ width: '100%', height: 'auto', maxHeight: 360, objectFit: 'contain' }}
                            />
                          </div>
                          <div className="mt-2 px-4 pb-2">
                            <div className="text-sm font-medium">{label}</div>
                            {(opt as any).previewDesc && <div className="text-xs text-muted-foreground mt-1">{(opt as any).previewDesc}</div>}
                          </div>
                        </HoverCardContent>
                      </HoverCard>
                    )}
                  </div>
                </div>
              </div>
            </button>
          </div>
        );
      })}

      {/* Render custom inputs outside the button so they visually align with the button height */}
      {String(value) === 'auto' && (
        <div className="flex items-stretch gap-2 min-w-0 basis-1/3 h-full">
          <div className="flex items-center gap-2 min-w-0 w-full h-full">
            <input
              type="number"
              className="w-full min-w-0 p-3 border rounded-lg text-sm h-full box-border"
              placeholder="宽"
              value={customW ?? ''}
              onChange={(e) => {
                const v = e.target.value === '' ? undefined : parseInt(e.target.value, 10);
                setCustomW(v);
                if (onCustomSizeChange) onCustomSizeChange(v, customH);
              }}
              onBlur={() => {
                if (onCustomSizeChange) onCustomSizeChange(customW, customH);
              }}
            />
            <div className="text-sm">×</div>
          </div>
          <div className="flex items-center gap-2 min-w-0 w-full h-full">
            <input
              type="number"
              className="w-full min-w-0 p-3 border rounded-lg text-sm h-full box-border"
              placeholder="高"
              value={customH ?? ''}
              onChange={(e) => {
                const v = e.target.value === '' ? undefined : parseInt(e.target.value, 10);
                setCustomH(v);
                if (onCustomSizeChange) onCustomSizeChange(customW, v);
              }}
              onBlur={() => {
                if (onCustomSizeChange) onCustomSizeChange(customW, customH);
              }}
            />
            <div className="text-sm text-muted-foreground">px</div>
          </div>
        </div>
      )}
    </div>
  );
};
export default OptionImageOptimizationSelector;
