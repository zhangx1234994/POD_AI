import React from 'react';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Grid3x3, Download, XCircle } from 'lucide-react';

interface TaskDetailHeaderProps {
  task?: any | null;
  items?: any | null;
  id?: string | undefined;
  isGlobalBatchMode?: boolean;
  onEnterBatch?: () => void;
  onExitBatch?: () => void;
  onTriggerGlobalDownload?: () => void;
  onBack?: () => void;
  right?: React.ReactNode;
}

export function TaskDetailHeader({ task, items, isGlobalBatchMode, onEnterBatch, onExitBatch, onTriggerGlobalDownload, onBack, right }: TaskDetailHeaderProps) {
  const totalGenerated = Array.isArray(items)
    ? items.reduce((acc: number, it: any) => acc + (Array.isArray(it?.generatedImages) ? it.generatedImages.length : 0), 0)
    : 0;
  const hasGenerated = totalGenerated > 0;

  return (
    <div className="flex items-center justify-between mx-auto w-full h-20">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="lg" className="h-12 w-12 text-muted-foreground [&_svg:not([class*='size-'])]:size-6 svg:not([class*='size-'])" onClick={onBack}>
          <ArrowLeft className="!h-8 !w-8 text-muted-foreground" />
        </Button>
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-semibold text-foreground">{task?.taskName || '任务详情'}</h3>
          </div>
          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
            <span>{task?.actionLabel ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {isGlobalBatchMode ? (
          <div className="flex items-center gap-2">
            <Button variant="default" size="sm" onClick={onTriggerGlobalDownload} disabled={!hasGenerated}>
              <Download className="mr-2 h-4 w-4 text-primary-foreground" />确认下载
            </Button>
            <Button variant="outline" size="sm" onClick={onExitBatch}>
              <XCircle className="mr-2 h-4 w-4 text-muted-foreground" />取消
            </Button>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={onEnterBatch} disabled={!hasGenerated}>
            <Grid3x3 className="mr-2 h-4 w-4 text-muted-foreground" />批量下载
          </Button>
        )}

        {right}
      </div>
    </div>
  );
}

export default TaskDetailHeader;
