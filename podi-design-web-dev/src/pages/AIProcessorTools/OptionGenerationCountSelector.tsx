import { HoverCard, HoverCardTrigger, HoverCardContent } from '@/components/ui/hover-card';
import { Badge } from '@/components/ui/badge';
import { HelpCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';

export type OptionItem = {
  key: string;
  // support both shapes used across tools
  value?: string | number;
  label?: string;
  title?: string;
  desc?: string;
  badge?: string;
  disabled?: boolean;
  preview?: string;
  hasInput?: boolean;
};

interface Props {
  options: OptionItem[];
  value: string | number;
  onChange: (value: string | number) => void;
  columns?: number;
  className?: string;
};

/**
 * OptionGenerationCountSelector
 * - Cards with large touch targets, title over description, optional badge
 * - Selected state shows a colored border and a small check marker at top-left
 * - Supports disabled state and optional hover preview using project's HoverCard
 */
export function OptionGenerationCountSelector({ options, value, onChange, columns = 2, className = '' }: Props) {
  const maxCols = Math.max(1, Math.min(columns, 6));
  return (
    <div
      className={`${className} grid items-stretch gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-${maxCols}`}
      style={{ gridAutoRows: '1fr' }}
    >
      {options.map((opt) => {
        const label = opt.label ?? opt.title ?? '';
        const desc = opt.desc ?? '';
        const optionValue = opt.value ?? (opt as any).value ?? opt.key;
        const presetMatches = options.some((o) => !o.hasInput && String((o.value ?? (o as any).value ?? o.key)) === String(value));
        const selected = opt.hasInput ? !presetMatches : String(value) === String(optionValue);
        const disabled = Boolean((opt as any).disabled);

        if (opt.hasInput) {
          return (
            <div
              key={opt.key}
              className={`w-full flex items-center justify-center transition-all h-full p-3 rounded-lg border
                ${selected ? 'border-primary shadow-sm' : 'border-border bg-card'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-text hover:shadow-md'}
                focus-within:border-primary focus-within:bg-primary/5`}
            >
              <Input
                type="number"
                placeholder="请输入"
                value={String(value)}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => {
                  e.stopPropagation();
                  const num = parseInt(e.target.value || '0', 10) || 0;
                  onChange(num);
                }}
                className="w-full h-full px-1 py-0 text-sm bg-transparent border-0 outline-none appearance-none"
              />
              <span className="ml-1 text-sm text-muted-foreground">%</span>
            </div>
          );
        }

        return (
          <button
            key={opt.key}
            role="button"
            aria-pressed={selected}
            aria-disabled={disabled}
            className={`p-3 border rounded-lg transition-all h-full flex flex-col items-center justify-center
              ${selected ? 'border-primary bg-primary/5 shadow-sm' : 'border-border bg-card'}
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:shadow-md'}`}
            onClick={() => { if (!disabled) onChange(optionValue); }}
            tabIndex={disabled ? -1 : 0}
            onKeyDown={(e) => {
              if (disabled) return;
              if (e.key === 'Enter' || e.key === ' ') onChange(optionValue);
            }}
          >
            <div className="flex items-center justify-center gap-3 w-full">
              <div className={`flex-shrink-0 w-4 h-4 rounded-full border-2 relative ${selected ? 'border-primary bg-primary' : 'border-muted-foreground'}`}> 
                <div className="w-full h-full rounded-full bg-white dark:bg-slate-500 scale-50 flex items-center justify-center pointer-events-none">
                  <span className={`${selected ? 'w-2 h-2 rounded-full bg-primary dark:bg-primary' : 'w-2 h-2 rounded-full bg-transparent dark:bg-transparent'}`} />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="text-sm font-medium truncate">{label}</div>
                {opt.badge && (
                  <Badge variant={opt.badge === '推荐' ? 'secondary' : 'outline'} className="text-xs ml-2">
                    {opt.badge}
                  </Badge>
                )}
              </div>
            </div>

            {desc || opt.preview ? (
              <div className={`w-full ${(desc || opt.preview) ? 'mt-2' : ''} flex flex-col items-center`}>
                <div className="flex flex-col items-center justify-center text-center">
                  {desc && <div className="text-xs text-muted-foreground mt-1 whitespace-normal">{desc}</div>}

                  {opt.preview && (
                    <HoverCard>
                      <HoverCardTrigger asChild>
                        <div
                          role="button"
                          tabIndex={0}
                          className="mt-1 w-6 h-6 rounded-full text-xs flex items-center justify-center"
                          aria-label={`preview ${label}`}
                          onClick={(e) => e.stopPropagation()}
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
            ) : null}
          </button>
        );
      })}
    </div>
  );
};

export default OptionGenerationCountSelector;
