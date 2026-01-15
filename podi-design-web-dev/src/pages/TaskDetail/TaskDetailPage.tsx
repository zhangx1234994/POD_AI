import { useState, useEffect, useCallback } from 'react';
import { TASK_DETAIL_PAGE_SIZE } from '@/constants/task';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { buildPrimaryTaskFromDetail } from '@/utils/taskDetailUtils';
import { downloadZip, downloadUrl } from '@/utils/downloadUtils';
import { updateTaskListSeamlessly } from '@/utils/taskUtils';
import { workflowApi } from '@/services/workflowApi';
import { getUserId } from '@/utils/http';
import { TaskDetailItem } from '@/types/task';
import type { BaseTask } from '@/types/task';
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { SeamlessPreviewDialog } from '@/pages/PersonalGallery/SeamlessPreviewDialog';
import { useTaskDetailPolling } from '@/hooks/useTaskDetailPolling';
import { TaskDetailProcessor, quickMapTaskDetail } from './TaskDetailProcessor';
import { TaskDetailInfo } from './TaskDetailInfo';
import { TaskDetailHeader } from './TaskDetailHeader';
import { ImagePreview } from '@/components/ImagePreview';
import { TaskDetailCard } from './TaskDetailCard';
import http from '@/utils/http';
import { GeneratedImagePreview } from '../PersonalGallery/GeneratedImagePreview';
import { UploadImagePreview } from '../PersonalGallery/UploadImagePreview';

export function TaskDetailPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState([] as TaskDetailItem[]);
  const [_loading, setLoading] = useState(false);
  const [page, _setPage] = useState(0);
  const [size, _setSize] = useState(TASK_DETAIL_PAGE_SIZE);
  const [_total, setTotal] = useState(0);
  const [_totalPages, setTotalPages] = useState(0);
  const [_hasNext, setHasNext] = useState(false);
  const [previewImages, setPreviewImages] = useState([] as string[]);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [showPreview, setShowPreview] = useState(false);

  // primaryTask is a packaged summary built from the getTaskDetail response
  const [primaryTask, setPrimaryTask] = useState<any>(null);
  // Raw task status from response.data.taskStatus (used to decide polling)
  const [taskStatus, setTaskStatus] = useState<string | null>(null);

  // Seamless preview state
  const [showSeamlessPreview, setShowSeamlessPreview] = useState(false);
  const [seamlessTask, setSeamlessTask] = useState(null as TaskDetailItem | null);
  const [isGlobalBatchMode, setIsGlobalBatchMode] = useState(false);

  // Task type state
  const [taskAction, setTaskAction] = useState<string>('');

  // 状态管理：跟踪每个子任务的选中状态 (subTaskId may be number or string)
  const [selectedImages, setSelectedImages] = useState({} as Record<string | number, string[]>);
  // 状态管理：控制下载弹框显示
  const [showDownloadDialog, setShowDownloadDialog] = useState(false);
  // 状态管理：当前操作的子任务ID
  const [currentSubTaskId, setCurrentSubTaskId] = useState(null as string | number | null);

  const fetchDetail = useCallback(
    async (isPolling: boolean = false) => {
      if (!taskId) return null;

      if (!isPolling) {
        setLoading(true);
      }
      try {
        const userId = getUserId();
        const response = await workflowApi.getTaskDetail(taskId, userId, page, size);
        if (response.data) {
          // Adapt to potential response structure variations
          const dataItems = response.data.items || response.data || [];
          const rawItems = Array.isArray(dataItems) ? dataItems : [];

          // Map items quickly to allow fast initial render (no heavy image processing)
          const quickItems = rawItems.map(quickMapTaskDetail);
          if (!isPolling) {
            setItems(quickItems);
            if (quickItems.length > 0 && quickItems[0].action) setTaskAction(quickItems[0].action);
          }

          // Hydrate items (resolve any additional image URLs/processing) in background
          const taskDetailItems = await Promise.all(rawItems.map(TaskDetailProcessor));

          // If this was not a polling update, allow the later branch to replace quick items
          if (!isPolling && taskDetailItems.length > 0 && taskDetailItems[0].action) {
            setTaskAction(taskDetailItems[0].action);
          }

          // Build primaryTask summary from response (use processed items to extract timing/workflowParams)
          try {
            const primary = buildPrimaryTaskFromDetail(response.data);
            if (primary) setPrimaryTask(primary);
          } catch (e) {
            // keep previous primaryTask if builder fails
            console.warn('Failed to build primary task summary', e);
          }

            // Save raw task status reported by the API (if present)
            let currentStatus = null;
            try {
              currentStatus = response.data?.task_status ?? null;
              setTaskStatus(currentStatus);
            } catch (e) {
              // ignore if response shape unexpected
              setTaskStatus(null);
            }

          if (isPolling) {
            setItems((prevItems: TaskDetailItem[]) => {
              const { hasChanges, updatedList } = updateTaskListSeamlessly(
                prevItems as unknown as BaseTask[],
                taskDetailItems as unknown as BaseTask[]
              );
              return hasChanges ? (updatedList as TaskDetailItem[]) : prevItems;
            });
          } else {
            setItems(taskDetailItems);
            const totalMatches = response.data.total || 0;
            setTotal(totalMatches);
            setTotalPages(response.data.totalPages || Math.ceil((totalMatches || 0) / (size || 1)));
            const hasNextVal = typeof response.data.hasNext === 'boolean'
              ? response.data.hasNext
              : (totalMatches > (page + 1) * size);
            setHasNext(hasNextVal);
          }

          return currentStatus;
        }
        return null;
      } catch (error) {
        console.error('Failed to fetch task detail:', error);
        return null;
      } finally {
        if (!isPolling) {
          setLoading(false);
        }
      }
    },
    [taskId, page, size]
  );

  const { startPolling, stopPolling } = useTaskDetailPolling({
    taskId: taskId || '',
    fetchDetail,
    pollingEnabled: true,
    checkInterval: 1000,
  });

  useEffect(() => {
    fetchDetail(false).then((status) => {
      if (status && ['pending', 'running'].includes(status.toLowerCase())) {
        setTimeout(() => {
          startPolling();
        }, 1000);
      }
    });
  }, [fetchDetail, startPolling]);

  const handleDownload = async (url: string) => {
    if (!url) return;
    try {
      await downloadUrl(url, undefined);
    } catch (err) {
      console.error('下载失败，使用新窗口打开', err);
      window.open(url, '_blank');
    }
  };

  const handleImagePreview = (images: string[], index: number = 0) => {
    setPreviewImages(images);
    setPreviewIndex(index);
    setShowPreview(true);
  };

  // Preview dialogs for generated/uploaded image details
  const [showGeneratedPreview, setShowGeneratedPreview] = useState(false);
  const [generatedPreviewImage, setGeneratedPreviewImage] = useState(null as any);
  const [showUploadPreview, setShowUploadPreview] = useState(false);
  const [uploadPreviewImage, setUploadPreviewImage] = useState(null as any);

  const handleViewDetails = async (src: string, sourceType: string) => {
    if (!src) return;
    try {
      const parts = src.split('/');
      const last = parts.pop() || '';
      const imgId = last.split('.')[0];
      const response = await http.get(`/img/getOriginal?img_id=${imgId}`);
      const data = response.data || {};

      if (response.data) {
        const workflowParams = response.data.workflow_params || {};
        const imgInfo = response.data.imgInfo || {};
        const imageList = Array.isArray(workflowParams.imageList) ? workflowParams.imageList : [];
        const firstImage = imageList[0] || {};

        // Prefer dimensions from workflow params' imageList.o_size if available
        const width = firstImage?.o_size?.width ?? data?.dimensions?.width ?? undefined;
        const height = firstImage?.o_size?.height ?? data?.dimensions?.height ?? undefined;
        const dimensions = width && height ? `${width}x${height}` : (data.dimensions || '');

        // Parse tags: API may return a JSON string
        let tags: any = data.tags ?? response.data.tags ?? {};
        if (typeof tags === 'string' && tags.trim()) {
          try {
            tags = JSON.parse(tags);
          } catch (e) {
            // keep original string if parse fails
          }
        }

        const image = {
          id: imgId,
          imgId,
          name: imgInfo.imgName || firstImage.imgName ||  '',
          url: src,
          type: sourceType === 'GENERATE' ? 'generated' : 'uploaded',
          sourceType: sourceType as 'UPLOAD' | 'GENERATE',
          size: firstImage?.size || '',
          dimensions,
          uploadDate: imgInfo.createTime || '',
          tags,
          workflowParams: {
            // include the raw workflow params but normalize some common keys
            ...workflowParams,
            top: workflowParams.top ?? null,
            left: workflowParams.left ?? null,
            right: workflowParams.right ?? null,
            bottom: workflowParams.bottom ?? null,
            model: workflowParams.model ?? null,
            action: workflowParams.action ?? null,
            extend_type: workflowParams.extend_type ?? null,
            prompt: workflowParams.prompt ?? null,
            taskId: workflowParams.taskId ?? workflowParams.task_id ?? null,
            userId: workflowParams.userId ?? workflowParams.user_id ?? null,
            imageList,
          },
        } as any;

        if (sourceType === 'GENERATE') {
          setGeneratedPreviewImage(image);
          setShowGeneratedPreview(true);
        } else {
          setUploadPreviewImage(image);
          setShowUploadPreview(true);
        }
      } else {
        console.error('获取图片详情失败', response);
      }
    } catch (error) {
      console.error('获取图片详情失败', error);
    }
  };

  const handleSeamlessPreview = (item: TaskDetailItem, specificImgUrl?: string) => {
    setSeamlessTask({
      ...item,
      images: specificImgUrl ? [specificImgUrl] : item.generatedImages || [],
    });
    setShowSeamlessPreview(true);
  };

  const closePreview = () => {
    setShowPreview(false);
    setPreviewImages([]);
    setPreviewIndex(0);
  };

  // 处理单个图片选择
  const handleImageSelect = (subTaskId: string | number, imgUrl: string, checked: boolean) => {
    setSelectedImages((prev: Record<string, string[]>) => {
      const currentSelected = prev[subTaskId] || [];
      if (checked) {
        return {
          ...prev,
          [subTaskId]: [...currentSelected, imgUrl],
        };
      } else {
        return {
          ...prev,
          [subTaskId]: currentSelected.filter((url: string) => url !== imgUrl),
        };
      }
    });
  };

  // 处理全选/取消全选
  const handleSelectAll = (subTaskId: string | number, images: string[], checked: boolean) => {
    setSelectedImages((prev: Record<string | number, string[]>) => {
      if (checked) {
        return {
          ...prev,
          [subTaskId]: images,
        };
      } else {
        return {
          ...prev,
          [subTaskId]: [],
        };
      }
    });

    // 如果是全选，且不在全局批量模式下，显示下载弹框
    if (checked && !isGlobalBatchMode) {
      setCurrentSubTaskId(subTaskId);
      setShowDownloadDialog(true);
    }
  };

  // 进入全局批量下载模式
  const enterGlobalBatchMode = () => {
    setIsGlobalBatchMode(true);
    const allImages: Record<string | number, string[]> = {};
    items.forEach((item: TaskDetailItem) => {
      const subTaskId = item.id || item.subTaskId;
      if (item.generatedImages && item.generatedImages.length > 0) {
        allImages[subTaskId] = item.generatedImages;
      }
    });
    setSelectedImages(allImages);
  };

  // 退出全局批量下载模式
  const exitGlobalBatchMode = () => {
    setIsGlobalBatchMode(false);
    setSelectedImages({});
    setCurrentSubTaskId(null);
  };

  // 触发全局下载确认
  const triggerGlobalDownload = () => {
    const totalImages = Object.values(selectedImages).flat().length;
    if (totalImages === 0) return;
    setShowDownloadDialog(true);
  };

  // 执行全局批量下载
  const executeGlobalDownload = async () => {
    const allUrls = Object.values(selectedImages).flat() as string[];
    if (allUrls.length === 0) {
      setShowDownloadDialog(false);
      exitGlobalBatchMode();
      return;
    }
    if (allUrls.length === 1) {
      await downloadUrl(allUrls[0]);
    } else {
    await downloadZip(allUrls, `下载所有结果图_${taskId || Date.now()}`);
    }
    setShowDownloadDialog(false);
    exitGlobalBatchMode();
  };

  // 处理批量下载
  const handleBatchDownload = async () => {
    if (isGlobalBatchMode) {
      await executeGlobalDownload();
      return;
    }

    if (!currentSubTaskId) return;

    const imagesToDownload = selectedImages[currentSubTaskId] || [];
    if (imagesToDownload.length === 0) {
      setShowDownloadDialog(false);
      return;
    }

    // 批量下载图片：若多张则打包 ZIP
    if (imagesToDownload.length === 1) {
      await downloadUrl(imagesToDownload[0]);
    } else if (imagesToDownload.length > 1) {
      await downloadZip(imagesToDownload, `下载所有结果图${currentSubTaskId || Date.now()}`);
    }

    // 关闭弹框并清空选中状态
    setShowDownloadDialog(false);
    setSelectedImages((prev: Record<string, string[]>) => ({
      ...prev,
      [currentSubTaskId]: [],
    }));
    setCurrentSubTaskId(null);
  };

  // 取消下载
  const cancelDownload = () => {
    setShowDownloadDialog(false);
    if (!isGlobalBatchMode && currentSubTaskId) {
      setSelectedImages((prev: Record<string, string[]>) => ({
        ...prev,
        [currentSubTaskId]: [],
      }));
      setCurrentSubTaskId(null);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-background via-background to-muted/20">
      <div className="pl-6 pr-8 border-b flex items-center">
        <TaskDetailHeader
          task={primaryTask}
          items={items}
          id={taskId}
          isGlobalBatchMode={isGlobalBatchMode}
          onEnterBatch={enterGlobalBatchMode}
          onExitBatch={exitGlobalBatchMode}
          onTriggerGlobalDownload={triggerGlobalDownload}
          onBack={() => navigate(-1)}
        />
      </div>
    
      <div className="flex-1 space-y-4 pt-4 overflow-auto">
        {primaryTask && (
            <div className="px-6">
            <TaskDetailInfo task={primaryTask} />
          </div>
        )}

        {/* Determine grid layout based on taskAction */}
        <div className="max-w-7xl mx-auto px-6 pb-6 z-5">
          <div className={
            String(taskAction || '').toLowerCase().includes('fission')
              ? 'grid gap-4 grid-cols-1'
              : 'grid gap-4 grid-cols-1 md:grid-cols-1 lg:grid-cols-2'
          }>
            {items.map((item: TaskDetailItem) => {
              const genCount = (item.generatedImages || item.images || []).length;
              // items with more than one generated image should occupy the full row on large screens
              const cellClass = genCount > 1 ? 'lg:col-span-1' : '';
              return (
                <div key={item.id || item.subTaskId} className={cellClass}>
                  <TaskDetailCard
                    item={item}
                    selectedImages={selectedImages}
                    isGlobalBatchMode={isGlobalBatchMode}
                    onImagePreview={handleImagePreview}
                    onSeamlessPreview={handleSeamlessPreview}
                    onDownload={handleDownload}
                    onViewDetails={handleViewDetails}
                    onImageSelect={handleImageSelect}
                    onSelectAll={handleSelectAll}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* 新的图片预览组件 */}
        <ImagePreview
          open={showPreview}
          onClose={closePreview}
          images={previewImages}
          initialIndex={previewIndex}
          title="图片预览"
        />

        {/* Seamless Preview Dialog */}
        <SeamlessPreviewDialog
          open={showSeamlessPreview}
          onOpenChange={setShowSeamlessPreview}
          task={seamlessTask}
        />

        {/* Uploaded image preview dialog (from 图片详情) */}
        <UploadImagePreview
          open={showUploadPreview}
          onOpenChange={(open) => setShowUploadPreview(open)}
          image={uploadPreviewImage}
          onDownload={(_id) => {
            if (uploadPreviewImage?.url) handleDownload(uploadPreviewImage.url);
          }}
          onDelete={(id) => {
            // deletion from task detail page is not implemented here
            console.warn('delete requested for', id);
          }}
        />

        {/* Generated image preview dialog (from 图片详情) */}
        <GeneratedImagePreview
          open={showGeneratedPreview}
          onOpenChange={(open) => setShowGeneratedPreview(open)}
          image={generatedPreviewImage}
          onDownload={(_id) => {
            if (generatedPreviewImage?.url) handleDownload(generatedPreviewImage.url);
          }}
          onDelete={(id) => {
            console.warn('delete requested for', id);
          }}
        />

        {/* 批量下载弹框 */}
        <Dialog open={showDownloadDialog} onOpenChange={cancelDownload}>
          <DialogContent>
            <DialogTitle>批量下载确认</DialogTitle>
            <DialogDescription>您确定要下载选中的图片吗？</DialogDescription>
            <div className="mt-4">
              <p className="text-sm">
                共{' '}
                {isGlobalBatchMode
                  ? Object.values(selectedImages).flat().length
                  : currentSubTaskId
                  ? (selectedImages[currentSubTaskId] || []).length
                  : 0}{' '}
                张图片
              </p>
            </div>
            <DialogFooter>
              <div className="flex gap-2 justify-end w-full">
                <Button variant="outline" onClick={cancelDownload}>
                  取消
                </Button>
                <Button onClick={handleBatchDownload}>下载</Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default TaskDetailPage;
