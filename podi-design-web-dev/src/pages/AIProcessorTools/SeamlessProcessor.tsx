import { useState, useCallback, useEffect } from 'react';
import type { ImageItem } from '@/types/upload';
import { Grid2X2 } from 'lucide-react';
import { SubmitProcessorTask } from './SubmitProcessorTask';
import { generateTaskId } from '@/utils/taskUtils';
import { prepareImageList } from '@/utils/taskUtils';
import { fillImageDimensions, resolveImageSize } from '@/utils/imageUtils';
import { getUserId } from '@/utils/http';
import { AIProcessorTitle } from './AIProcessorTitle';
import { ImageUploadPanel } from './ImageUploadPanel';
import { SeamlessTool } from './SeamlessTool';
import { MAX_UPLOAD_IMAGE_COUNT } from '@/constants/upload';
import { useTaskSubmission } from '@/hooks/useTaskSubmission';
import { SubmitSuccessDialog } from './SubmitSuccessDialog';
import { triggerRefreshTaskListDebounced } from '@/utils/debounce';
import usePointsPrecheck from '@/hooks/usePointsPrecheck';

export function SeamlessProcessor({ action = 'seamless' }: { action?: string }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [description, setDescription] = useState('');
  const [imageSize, setImageSize] = useState<string>('1:1');
  const [patternType, setPatternType] = useState<string>('seamless');
  const [customWidth, setCustomWidth] = useState<number | undefined>(undefined);
  const [customHeight, setCustomHeight] = useState<number | undefined>(undefined);
  const [processing, setProcessing] = useState(false);
  const [showSuccessDialog, setShowSuccessDialog] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState<number>(0);

  const { submitTask, isSubmitting } = useTaskSubmission();
  const { precheckAndSubmit, dialogs: precheckDialogs } = usePointsPrecheck();

  const handleImagesChange = useCallback((imgs: ImageItem[]) => {
    setImages(imgs);
    const first = imgs[0] ?? null;
    if (first && (first as any).width) setCustomWidth((first as any).width);
    else setCustomWidth(undefined);
    if (first && (first as any).height) setCustomHeight((first as any).height);
    else setCustomHeight(undefined);
  }, []);

  const handleSubmitTask = async (): Promise<void> => {
    if (images.length === 0) {
      return;
    }

    // 检查是否有超限图片（只检查本地上传的图片）
    if (images.some(img => img.source === 'upload' && img.isOversized)) {
      return;
    }

    setProcessing(true);
    try {
      const imagesWithDimensions = await fillImageDimensions(images);
      const userId = await getUserId();
      const taskId = generateTaskId();
      setCurrentTaskId(taskId);

      const imageList = await prepareImageList(imagesWithDimensions, { filenamePrefix: taskId });

      // compute width/height from imageSize
      const first = imagesWithDimensions[0] ?? null;
      const { width, height } = resolveImageSize(imageSize, { customWidth, customHeight, firstImage: first });

      const seamlessParams: Record<string, any> = {
        action: action,
        userId,
        taskId,
        prompt: description || '',
        patternType: patternType,
        imageList,
        model: 'comfy',
        width,
        height,
        resolution: imageSize, // 将生图大小选择的值封装到resolution字段
      };

      try {
        await precheckAndSubmit({
          action,
          imagesCount: imageList.length,
          taskId,
          submitFn: async () => {
            await submitTask({
              action: action,
              toolType: action,
              params: seamlessParams,
              userId,
              taskId,
              showSuccessDialog: () => setShowSuccessDialog(true),
              onSuccess: (tid: string) => {
                setCurrentTaskId(tid);

                // 立即触发带taskId的刷新事件，同时传递action、userId和分页信息
                triggerRefreshTaskListDebounced(taskId, {
                  action: seamlessParams.action, // 使用与提交任务时完全相同的action参数，确保监控系统能够正确识别
                  user_id: seamlessParams.user_id, // 修改为user_id，与DashboardTaskList组件一致
                  page: 0, // 默认从第0页开始
                  size: 5, // 修改为5，与DashboardTaskList组件一致
                  forceRefresh: true, // 强制刷新，确保新任务正确显示在列表顶部
                });
                handleReset();
              },
              onError: (err: any) => {
                console.error('连续图案提交失败', err);
              },
            });
          },
        });
      } catch (e: any) {
        console.error('积分校验或提交异常:', e);
        setShowSuccessDialog(false);
      } finally {
        setProcessing(false);
      }
    } catch (err) {
      console.error('连续图案提交流程异常:', err);
      setShowSuccessDialog(false);
    } finally {
      setProcessing(false);
    }
  };

  const handleReset = () => {
    setImages([]);
    setDescription('');
    setImageSize('1:1');
    setResetKey((v) => v + 1);
  };

  const canSubmit = images.length > 0 && !isSubmitting && !processing && !images.some(img => img.source === 'upload' && img.isOversized);

  return (
    <div className="px-6 py-4 space-y-6 h-full bg-gradient-to-br from-background via-background to-muted/20">
      <AIProcessorTitle toolIcon={<Grid2X2 className="w-5 h-5 text-white" />} toolName="四方连续" />

      <div className="max-w-5xl mx-auto space-y-4 pb-8">
        <div className="lg:col-span-2 space-y-4">
          <ImageUploadPanel
            images={images}
            onImagesChange={handleImagesChange}
            maxImages={MAX_UPLOAD_IMAGE_COUNT}
            allowMultiple={true}
            numbered={true}
            refreshKey={resetKey}
            zebraConnected={true}
            hummingbirdConnected={true}
            title="选择图片"
          />

          <SeamlessTool
            imageSize={imageSize}
            setImageSize={setImageSize}
            patternType={patternType}
            setPatternType={setPatternType}
            firstImage={images[0] ?? null}
            onCustomSizeChange={(w, h) => { setCustomWidth(w); setCustomHeight(h); }}
          />

          <SubmitProcessorTask
            onSubmit={handleSubmitTask}
            onReset={handleReset}
            canSubmit={canSubmit}
            isSubmitting={isSubmitting}
            setUploadedImages={setImages}
            setDescription={setDescription}
            setCategory={() => {}}
            setImageSize={setImageSize}
            action={action}
          />
        </div>
      </div>

      <SubmitSuccessDialog
        open={showSuccessDialog}
        taskId={currentTaskId ?? undefined}
        toolName="连续图案"
        onOpenChange={(open: boolean) => setShowSuccessDialog(open)}
        onViewTask={(taskId?: string) => {
          setShowSuccessDialog(false);
          triggerRefreshTaskListDebounced(taskId);
        }}
        onContinue={() => {
          setShowSuccessDialog(false);
          handleReset();
          triggerRefreshTaskListDebounced(currentTaskId ?? undefined);
        }}
      />
      {precheckDialogs}
    </div>
  );
};

export default SeamlessProcessor;
