import React from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ImageWithFallback } from '@/components/ImageWithFallback';
import { Eye, Layers, Image as ImageIcon, Download, RotateCcw, EllipsisVertical } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';

import { getStatusConfig, mapActionToChinese, } from '@/utils/taskUtils';
import { Progress } from '@/components/ui/progress';
import { TaskSummaryItem } from '@/types/task';
import { downloadZip } from '@/utils/downloadUtils';

interface BatchTaskCardProps {
  task: TaskSummaryItem;
  onClick: (task: TaskSummaryItem) => void;
  onRegenerate: (task: TaskSummaryItem) => void;
  onDownload: (url: string, filename?: string) => void;
}

export const BatchTaskCard: React.FC<BatchTaskCardProps> = ({ task, onClick, onRegenerate, onDownload }) => {
  const statusConfig = getStatusConfig(task?.status ?? '');
  const StatusIcon = statusConfig.icon as any ?? '';
  const statusBgClass = statusConfig?.bg ?? '';

  const originals: string[] = task.originalImages || [];
  const results: string[] = task.subTaskImages && task.subTaskImages.length > 0 ? task.subTaskImages : [];
  const displayImages: Array<{ type: 'original' | 'result'; src: string }> = [];
  if (originals.length > 0) displayImages.push({ type: 'original', src: originals[originals.length - 1] });
  if (results.length > 0) displayImages.push({ type: 'result', src: results[0] });

  const subCount = Number(task.subTaskCount ?? 0);
  const displaySubCount = task.subTaskImages ? task.subTaskImages.length : 0;
  const succCount = Number(task.successCount ?? 0);
  const failCount = Number(task.failedCount ?? 0);

  const isRunning = task?.status === 'RUNNING';
  const isPending = task?.status === 'PENDING';
  const isFailed = task?.status === 'FAILED';

  const runningPercent = subCount > 0 ? Math.round((succCount / subCount) * 100) : 0;

  return (
    <Card
      key={task?.subTaskId}
      className="relative group cursor-pointer hover:shadow-around transition-shadow gap-4 rounded-md"
      style={{ minWidth: '200px' }}
      onClick={() => onClick(task)}
    >
      <CardHeader className="flex items-start justify-between mb-4 cursor-pointer mb-0 px-5 pt-5">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {StatusIcon ? (
            <div className="w-10 h-10 rounded-full bg-orange-500 flex items-center justify-center flex-shrink-0-2">
            
              <div className={`${statusBgClass || 'bg-gray-200'} w-10 h-10 rounded-full flex items-center justify-center`}>
                <StatusIcon className="w-6 h-6 text-white" />
              </div>
            </div>
          ) : null}
          <div className="flex-1 min-w-0">
            <CardTitle className="font-medium text-sm truncate" title={task?.name || task?.taskId}>
              {task?.name}
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              {mapActionToChinese(task.action)}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 flex-shrink-0 ml-4">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Layers className="w-3.5 h-3.5"/>
            <span>子任务: {subCount}</span>
          </div>
          <span className="text-xs text-muted-foreground">{task?.createTime}</span>
        </div>
      </CardHeader>

      <CardContent className="px-5 pb-0 space-y-0">
        <div className="w-full relative p-2 flex gap-1 rounded-md overflow-hidden border bg-white/5" style={{ height: '260px' }}>
          {displayImages.length > 0 ? (
            displayImages.map((item, i) => (
              <div key={i} className={`flex-1 h-full overflow-hidden relative`}>
                {item?.src ? (
                  <ImageWithFallback src={item?.src} alt={`${item?.type} ${i + 1}`} className="w-full h-full object-cover transform transition-transform duration-300 group-hover:scale-105" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    <ImageIcon className="w-10 h-10" />
                  </div>
                )}

                <span className={`absolute left-1 top-1 px-2 py-0.5 text-xs font-medium rounded-full ${item?.type === 'original' ? 'border-transparent bg-secondary text-secondary-foreground dark:bg-white/10 dark:text-white' : 'bg-primary text-primary-foreground dark:bg-primary/80 dark:text-black'}`}>
                  {item?.type === 'original' ? '原图' : '结果'}
                </span>
                {item?.type === 'result' && displaySubCount > 0 && (
                  <span className="absolute right-2 bottom-2 inline-flex items-center justify-center bg-primary text-primary-foreground text-xs font-medium px-2 py-0.5 rounded-full shadow-md dark:bg-primary/80 dark:text-black">
                    {displaySubCount}
                  </span>
                )}
              </div>
            ))
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              <ImageIcon className="w-10 h-10" />
            </div>
          )}
        </div>
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="absolute inset-0 bg-black/20 dark:bg-black/60 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity rounded-md" />
          <div className="relative text-center text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-auto px-4">
            <div className="w-12 h-12 rounded-full bg-white/10 dark:bg-white/10 flex items-center justify-center mx-auto">
              <Eye className="w-8 h-8" />
            </div>
            <div className="font-medium text-sm">点击查看任务</div>
          </div>
        </div>
      </CardContent>

      <CardFooter className="px-5 pb-5 space-y-0 relative">
        <div className="w-full text-sm">
          <div className="flex items-center gap-3">
            {/* Footer: show running progress, waiting or failed messages, or action buttons */}
            {isRunning ? (
              <div className="flex-1">
                <div className="text-xs text-muted-foreground mb-2">处理进度 {succCount}/{subCount}</div>
                <Progress value={runningPercent} className="h-2" />
              </div>
            ) : isPending ? (
              <div className="flex-1 text-sm text-muted-foreground">正在排队等待中...</div>
            ) : isFailed ? (
              <div className="flex-1 text-sm text-red-600">处理失败</div>
            ) : null}

            <div className="flex-1 flex items-center justify-end gap-2">
              <div className="flex items-center gap-2 ml-auto">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); }}
                    className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium text-accent-foreground transition-all disabled:pointer-events-none hover:text-accent-foreground dark:hover:bg-accent/50 gap-1.5 h-8 px-2 rounded-md bg-muted hover:bg-muted/80"
                    >
                    <EllipsisVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>

                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onClick(task);
                    }}
                    >
                    <Eye className="mr-2 h-4 w-4" />查看详情
                    </DropdownMenuItem>
                    {(subCount === (succCount + failCount)) && (
                        <DropdownMenuItem
                        onClick={(e) => {
                            e.stopPropagation();
                            const subTaskImages = task.subTaskImages || [];
                            if (subTaskImages.length === 1) {
                                onDownload(subTaskImages[0], `${task?.taskId}.jpg`);
                            } else if (subTaskImages.length > 1) {
                                downloadZip(subTaskImages, `downloaded-${task.taskId}`);
                            }
                        }}
                        >
                        <Download className="mr-2 h-4 w-4" /> 下载
                        </DropdownMenuItem>
                    )}

                    {(subCount === 1 && subCount === succCount) && (
                        <DropdownMenuItem
                        onClick={(e) => {
                            e.stopPropagation();
                            onRegenerate(task);
                        }}
                        >
                        <RotateCcw className="mr-2 h-4 w-4" /> 重绘
                        </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </div>
      </CardFooter>
    </Card>
  );
};

export default BatchTaskCard;
