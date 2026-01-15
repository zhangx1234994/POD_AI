import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { ArrowRight } from 'lucide-react';
import { getThumbnailUrl } from '@/utils/imageUtils';
import { mapStatus, getStatusConfig } from '@/utils/taskUtils';
import TaskDetailImageCard from './TaskDetailImageCard';
import { TaskDetailItem } from '@/types/task';
import { TASK_IMAGE_CARD_WIDTH, TASK_IMAGE_CARD_HEIGHT } from '@/constants/task';

export interface TaskDetailCardProps {
  item: TaskDetailItem;
  selectedImages: Record<string | number, string[]>;
  isGlobalBatchMode?: boolean;
  onImagePreview: (images: string[], index?: number) => void;
  onSeamlessPreview: (item: TaskDetailItem, specificImgUrl?: string) => void;
  onDownload: (url: string) => void;
  onViewDetails?: (src: string, sourceType: string) => void;
  onImageSelect: (subTaskId: string | number, imgUrl: string, checked: boolean) => void;
  onSelectAll: (subTaskId: string | number, images: string[], checked: boolean) => void;
};

export const TaskDetailCard: React.FC<TaskDetailCardProps> = ({
  item,
  selectedImages,
  onImagePreview,
  onDownload,
  onViewDetails,
  onImageSelect,
  onSelectAll,
}) => {
  const currentStatus = item.taskStatus ?? mapStatus(item.status);
  const statusConfig = getStatusConfig(currentStatus);

  const subTaskId = item.id || item.subTaskId;
  const gen = item.generatedImages || [];
  const genCount = gen.length;
  const capped = Math.min(Math.max(genCount, 1), 6); // cap between 1 and 6
  const gridColsClass = {
    1: 'grid grid-cols-1 sm:grid-cols-1 md:grid-cols-1 lg:grid-cols-1',
    2: 'grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2',
    3: 'grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
    5: 'grid grid-cols-1 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5',
  }[capped];

  return (
    <Card
      key={subTaskId}
      className="overflow-hidden bg-card text-foreground border border-border"
    >
      <CardContent className="p-6">
        <div className="flex flex-col gap-2">
          {/* Image Row */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-4">
              {/* Original Image */}
              <div className="flex flex-col items-start">
                <div className="h-8 text-xs text-muted-foreground flex flex-col items-center justify-center">原图</div>
                {item.inputImage ? (
                  <div style={{ width: `${TASK_IMAGE_CARD_WIDTH}px` }}>
                    <TaskDetailImageCard
                      src={item.inputImage}
                      thumbnailSrc={item.inputImage ? getThumbnailUrl(item.inputImage) : undefined}
                      width={TASK_IMAGE_CARD_WIDTH}
                      height={TASK_IMAGE_CARD_HEIGHT}
                      currentStatus={currentStatus}
                      onPreview={() => item.inputImage && onImagePreview([item.inputImage])}
                      onDownload={() => item.inputImage && onDownload(item.inputImage)}
                      onViewDetails={(src) => { if (src) onViewDetails?.(src, 'UPLOAD'); }}
                    />
                  </div>
                ) : (
                  <div style={{ width: `${TASK_IMAGE_CARD_WIDTH}px` }}>
                    <TaskDetailImageCard
                      title={undefined}
                      width={TASK_IMAGE_CARD_WIDTH}
                      height={TASK_IMAGE_CARD_HEIGHT}
                      currentStatus=''
                    />
                  </div>
                )}
              </div>

              {/* Arrow Connector */}
              <div className="shrink-0 flex items-center justify-center w-8 self-center pt-6">
                <ArrowRight className="h-6 w-6 text-muted-foreground" />
              </div>

              {/* Generated Images - max 4 per row */}
              <div className="flex-1 min-w-0">
                <div className="flex flex-col items-start">
                  <div>
                    <div className="w-full h-8 flex items-center justify-end">
                      {gen.length > 0 && (
                        <div
                          className="cursor-pointer select-none rounded-md flex items-center justify-end"
                          role="button"
                          aria-label="下载所有结果图"
                        >
                          <input
                            type="checkbox"
                            className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-offset-card"
                            checked={
                              (selectedImages[subTaskId] || []).length ===
                                (item.generatedImages || []).length &&
                              (item.generatedImages || []).length > 0
                            }
                            onChange={(e) => {
                              e.stopPropagation();
                              onSelectAll(subTaskId, item.generatedImages || [], e.target.checked);
                            }}
                            onClick={(e) => e.stopPropagation()}
                          />
                          <div
                            className="ml-2 text-xs text-primary underline cursor-pointer"
                            onClick={(e) => { e.stopPropagation(); onSelectAll(subTaskId, item.generatedImages || [], true); }}
                          >
                            下载所有结果图
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Results grid — responsive columns chosen from image count (1..6) */}
                    <div className={`${gridColsClass} gap-4`}>
                      {gen.length > 0 ? (
                        gen.map((imgUrl, idx) => {
                          const isSelected = (selectedImages[subTaskId] || []).includes(imgUrl);
                          return (
                            <div key={idx} style={{ width: `${TASK_IMAGE_CARD_WIDTH}px` }}>
                              <TaskDetailImageCard
                                title={undefined}
                                src={imgUrl}
                                thumbnailSrc={getThumbnailUrl(imgUrl)}
                                width={TASK_IMAGE_CARD_WIDTH}
                                height={TASK_IMAGE_CARD_HEIGHT}
                                currentStatus={currentStatus}
                                showCheckbox
                                checked={isSelected}
                                onCheckboxChange={(checked) => onImageSelect(subTaskId, imgUrl, checked)}
                                onPreview={() => onImagePreview(item.generatedImages || [], idx)}
                                onDownload={() => onDownload(imgUrl)}
                                onViewDetails={(src) => { if (src) onViewDetails?.(src, 'GENERATE'); }}
                              />
                            </div>
                          );
                        })
                      ) : (
                        <div style={{ width: `${TASK_IMAGE_CARD_WIDTH}px` }}>
                          <TaskDetailImageCard
                            title={undefined}
                            width={TASK_IMAGE_CARD_WIDTH}
                            height={TASK_IMAGE_CARD_HEIGHT}
                            currentStatusConfig={statusConfig}
                            currentStatus={currentStatus}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-foreground">
            <div className="flex items-center gap-4">
              <span>ID: {item.subTaskId || item.id}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default TaskDetailCard;
