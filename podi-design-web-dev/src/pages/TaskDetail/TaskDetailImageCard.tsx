import React from 'react';
import { Button } from '@/components/ui/button';
import { Eye, ImageIcon, Hourglass, XCircle, Clock } from 'lucide-react';
import { ImageWithFallback } from '@/components/ImageWithFallback';

export interface TaskDetailImageCardProps {
  title?: string;
  src?: string; // full size URL
  thumbnailSrc?: string; // thumbnail URL used for img src
  width?: string | number;
  height?: string | number;
  showCheckbox?: boolean;
  checked?: boolean;
  onCheckboxChange?: (checked: boolean) => void;
  onPreview?: () => void;
  onDownload?: () => void;
  onViewDetails?: (src?: string) => void;
  footerActions?: React.ReactNode;
  placeholder?: React.ReactNode;
  currentStatusConfig?: { bg?: string; icon?: React.ComponentType<any>; color?: string; };
  currentStatus?: string | 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
};

export const TaskDetailImageCard: React.FC<TaskDetailImageCardProps> = ({
  title,
  src,
  thumbnailSrc,
  width = 200,
  height = 200,
  showCheckbox = false,
  checked = false,
  onCheckboxChange,
  onPreview,
  onDownload,
  onViewDetails,
  currentStatusConfig,
  currentStatus,
  placeholder,
}) => {
  const parsePx = (v: string | number | undefined, fallback = 200) => {
    if (typeof v === 'number') return v;
    if (!v) return fallback;
    const s = String(v).trim();
    if (s.endsWith('px')) return parseInt(s.slice(0, -2), 10) || fallback;
    const n = parseInt(s, 10);
    return Number.isFinite(n) ? n : fallback;
  };

  const widthPx = parsePx(width, 200);
  const heightPx = parsePx(height, 200);
  const hasImage = Boolean(thumbnailSrc || src);

  const StatusIcon = (currentStatusConfig?.icon as any) ?? Hourglass;
  const statusColor = currentStatusConfig?.color ?? '';

  const renderStatusContent = () => {
    const s = String(currentStatus || '').toUpperCase();
    if (s === 'RUNNING' || s === 'PROCESSING') {
      return (
        <>
          <StatusIcon className={`w-8 h-8 mb-1 animate-spin motion-safe:animate-bounce ${statusColor}`} />
          <div className={`text-sm text-muted-foreground pt-3`}>正在处理</div>
        </>
      );
    }
    if (s === 'FAILED') {
      return (
        <>
          <XCircle className={`w-8 h-8 mb-1 ${statusColor}`} />
          <div className={`text-sm text-muted-foreground pt-3`}>处理失败</div>
        </>
      );
    }
    if (s === 'PENDING' || s === 'QUEUED') {
      return (
        <>
          <Clock className={`w-8 h-8 mb-1 ${statusColor}`} />
          <div className={`text-sm text-muted-foreground pt-3`}>排队等待中</div>
        </>
      );
    }
    return (
      <>
        <ImageIcon className={`w-8 h-8 mb-1 ${statusColor}`} />
        <div className={`text-sm text-muted-foreground pt-3`}>{placeholder || null}</div>
      </>
    );
  };

  if (!hasImage) {
    return (
      <div className="shrink-0 h-full">
        <div style={{ width: `${widthPx}px` }} className={`h-[260px] bg-white rounded-lg overflow-hidden border border-border flex items-center justify-center`}>
          <div className="flex flex-col items-center justify-center text-center px-2">
            {renderStatusContent()}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="shrink-0 h-full group cursor-pointer hover:shadow-around transition-shadow rounded-md">
      <div
        className={`bg-muted rounded-lg overflow-hidden border border-border relative group cursor-pointer hover:shadow-around transition-shadow h-full flex flex-col`}
        onClick={() => onPreview?.()}
      >
        <div className="w-full relative overflow-hidden" style={{ height: `${heightPx}px` }}>
          <div className="w-full h-full flex items-center justify-center relative overflow-hidden">
            <ImageWithFallback
              src={thumbnailSrc || src!}
              alt={title || 'Image'}
              className="block object-contain transition-transform duration-300 group-hover:scale-105 object-contain max-w-full max-h-full"
              style={{ maxWidth: `${widthPx}px`, height: `${heightPx}px` }}
              overlay={(
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="absolute inset-0 bg-black/50 dark:bg-black/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity rounded z-5" />
                  <div className="relative text-center text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-auto px-2 z-5">
                    <div className="w-10 h-10 rounded-full bg-white/10 dark:bg-white/10 flex items-center justify-center mx-auto">
                      <Eye className="w-8 h-8" />
                    </div>
                    <div className="font-medium text-sm">点击查看图片</div>
                  </div>
                </div>
              )}
            />

            {showCheckbox && (
              <div className="absolute top-2 left-2 bg-white/50 group-hover:opacity-100 z-8" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-offset-card"
                  checked={checked}
                  onChange={(e) => onCheckboxChange?.(e.target.checked)}
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
            )}
          </div>
        </div>

        {src || thumbnailSrc ? (
          <div className="w-full h-14 flex items-center justify-between px-2 py-2 border-t border-border bg-card flex-none">
            <div>
              {
                onDownload ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="border border-border px-3"
                    onClick={(e: React.MouseEvent) => { e.stopPropagation(); onDownload?.(); }}
                  >
                    下载
                  </Button>
                ) : null
              }
            </div>
            <div className="ml-2">
              <Button
                size="sm"
                variant="ghost"
                className="border border-border px-3"
                onClick={(e: React.MouseEvent) => { e.stopPropagation(); onViewDetails?.(src); }}
              >
                查看详情
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default TaskDetailImageCard;
