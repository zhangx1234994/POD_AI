import { useState, useCallback, useEffect } from 'react';
import type { ImageItem } from '@/types/upload';
import { Maximize2 } from 'lucide-react';
import { SubmitProcessorTask } from './SubmitProcessorTask';
import { generateTaskId } from '@/utils/taskUtils';
import { prepareImageList } from '@/utils/taskUtils';
import { fillImageDimensions } from '@/utils/imageUtils';
import { getUserId } from '@/utils/http';
import { FissionTool, FissionSettings } from './FissionTool';
import { MAX_UPLOAD_IMAGE_COUNT } from '@/constants/upload';
import { AIProcessorTitle } from './AIProcessorTitle';
import { ImageUploadPanel } from './ImageUploadPanel';
import { useTaskSubmission } from '@/hooks/useTaskSubmission';
import { SubmitSuccessDialog } from './SubmitSuccessDialog';
import { triggerRefreshTaskListDebounced } from '@/utils/debounce';
import usePointsPrecheck from '@/hooks/usePointsPrecheck';

export function FissionProcessor({ action = 'fission' }: { action?: string }): JSX.Element {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [description, setDescription] = useState('');
  const [settings, setSettings] = useState<FissionSettings>({ count: 1, reference: 0.7, creative: 0.5, enhanced: false });
  const [processing, setProcessing] = useState(false);
  const [showSuccessDialog, setShowSuccessDialog] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState<number>(0);

  const { submitTask, isSubmitting } = useTaskSubmission();
  const { precheckAndSubmit, dialogs: precheckDialogs } = usePointsPrecheck();

  const handleImagesChange = useCallback((imgs: ImageItem[]) => {
    setImages(imgs);
  }, []);

  const handleSubmitTask = async (): Promise<void> => {
    if (!images.length) {
      return;
    }

    if (!settings) {
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

      const { reference, creative, count, enhanced } = settings;

      const fessionParams: Record<string, any> = {
        action: action,
        toolType: action,
        user_id: taskId,
        taskId,
        imageList,
        prompt: description || '',
        model: 'comfy',
        reference_strength: Number(reference || 0.5),
        creative_strength: Number(creative || 0.5),
        count: Math.min(4, Math.max(1, Number(count || 1))),
        enhanced, // 文字加强开关
      };

      try {
        await precheckAndSubmit({
          action,
          // imagesCount should reflect total images after splitting by settings.count
          imagesCount: imageList.length * Number(count || 1),
          taskId,
          submitFn: async () => {
            await submitTask({
              action: action,
              toolType: action,
              params: fessionParams,
              userId,
              taskId,
              showSuccessDialog: () => setShowSuccessDialog(true),
              onSuccess: (tid: string) => {
                setCurrentTaskId(tid);

                // 立即触发带taskId的刷新事件，同时传递action、userId和分页信息
                triggerRefreshTaskListDebounced(taskId, {
                  action: fessionParams.action, // 使用与提交任务时完全相同的action参数，确保监控系统能够正确识别
                  user_id: fessionParams.user_id, // 修改为user_id，与DashboardTaskList组件一致
                  page: 0, // 默认从第0页开始
                  size: 5, // 修改为5，与DashboardTaskList组件一致
                  forceRefresh: true, // 强制刷新，确保新任务正确显示在列表顶部
                });
                handleReset();
              },
              onError: (err: any) => {
                console.error('提交失败', err);
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
      console.error('图片裂变提交流程异常:', err);
      setShowSuccessDialog(false);
    } finally {
      setProcessing(false);
    }
  };

  const handleReset = () => {
    setImages([]);
    setDescription('');
    setSettings({ count: 1, reference: 0.7, creative: 0.5, enhanced: false });
    setResetKey((v) => v + 1);
  };

  const canSubmit = images.length > 0 && !isSubmitting && !processing && !images.some(img => img.source === 'upload' && img.isOversized);

  return (
    <div className="px-6 py-4 space-y-6 h-full bg-gradient-to-br from-background via-background to-muted/20">
      <AIProcessorTitle toolIcon={<Maximize2 className="w-5 h-5 text-white" />} toolName="图裂变" />

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

          <FissionTool settings={settings} setSettings={setSettings} />

          <SubmitProcessorTask
            onSubmit={handleSubmitTask}
            onReset={handleReset}
            canSubmit={canSubmit}
            isSubmitting={isSubmitting}
            setUploadedImages={setImages}
            setDescription={setDescription}
            setCategory={() => {}}
            setImageSize={() => {}}
            action={action}
          />
        </div>
      </div>

      <SubmitSuccessDialog
        open={showSuccessDialog}
        taskId={currentTaskId ?? undefined}
        toolName="图裂变"
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

export default FissionProcessor;
