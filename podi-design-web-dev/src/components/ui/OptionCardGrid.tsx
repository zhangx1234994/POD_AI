import React from 'react';
import { Badge } from '../../components/ui/badge';
import { HoverCard, HoverCardTrigger, HoverCardContent } from '../../components/ui/hover-card';
import { Check, HelpCircle } from 'lucide-react';

export type OptionItem = {
  key: string;
  label?: string;
  title?: string;
  desc?: string;
  badge?: string;
  disabled?: boolean;
  preview?: string;
  previewDesc?: string;
};

interface Props {
  options: OptionItem[];
  value: string;
  onChange: (key: string) => void;
  columns?: number;
  className?: string;
}

/**
 * OptionCardGrid
 * - Cards with large touch targets, title over description, optional badge
 * - Selected state shows a colored border and a small check marker at top-left
 * - Supports disabled state and optional hover preview using project's HoverCard
 */
export function OptionCardGrid({ options, value, onChange, columns = 4, className = '' }: Props) {
  const gridCols = Math.max(1, columns);
  return (
    <div
      className={`${className} grid gap-4 items-stretch`}
      style={{ gridTemplateColumns: `repeat(${gridCols}, minmax(0,1fr))` }}
    >
      {options.map((opt) => {
        const title = opt.title ?? opt.label ?? '';
        const desc = opt.desc ?? '';
        const selected = String(value) === String(opt.key);
        const disabled = Boolean(opt.disabled);

        return (
          <button
            key={opt.key}
            type="button"
            onClick={() => { if (!disabled) onChange(opt.key); }}
            disabled={disabled}
            aria-pressed={selected}
            aria-disabled={disabled}
            className={`relative text-left w-full rounded-lg transition-all p-6 border h-full flex flex-col items-start justify-between
              ${selected ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-card'}
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'}`}
          >
            {selected && (
              <span className="absolute -top-3 -left-3 w-8 h-8 rotate-45 bg-primary rounded-sm flex items-center justify-center shadow-md">
                <Check className="w-4 h-4 text-white -rotate-45" />
              </span>
            )}

            <div className="flex items-center gap-3 w-full">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <div className="text-base font-semibold truncate">{title}</div>
                  {opt.badge && (
                    <Badge variant={opt.badge === '推荐' ? 'secondary' : 'outline'} className="text-xs">
                      {opt.badge}
                    </Badge>
                  )}
                </div>
                {desc && <div className="text-sm text-muted-foreground mt-2 truncate">{desc}</div>}
              </div>

              {opt.preview && (
                <HoverCard>
                  <HoverCardTrigger asChild>
                    <button
                      type="button"
                      className="ml-2 w-8 h-8 rounded-full text-xs flex items-center justify-center"
                      aria-label={`preview ${title}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <HelpCircle className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </HoverCardTrigger>
                  <HoverCardContent side="top" align="center" sideOffset={8} className="p-2" style={{ width: 400 }}>
                    <div className="rounded-md overflow-hidden bg-muted/5">
                      <img src={opt.preview} alt={`${opt.key} preview`} style={{ width: '100%', height: 'auto', objectFit: 'contain' }} />
                    </div>
                    <div className="mt-2 px-4 pb-2">
                      <div className="text-sm font-medium">{title}</div>
                      {opt.previewDesc && <div className="text-xs text-muted-foreground mt-1">{opt.previewDesc}</div>}
                    </div>
                  </HoverCardContent>
                </HoverCard>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

export default OptionCardGrid;
