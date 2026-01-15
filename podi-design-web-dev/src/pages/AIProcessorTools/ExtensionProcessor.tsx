import { useState, useEffect, useCallback } from 'react';
import type { ImageItem } from '@/types/upload';
import type { ExtensionSettings } from '@/types/options';
import { EXTENSION_DEFAULTS } from '@/constants/options';
import { Maximize2 } from 'lucide-react';
import { SubmitProcessorTask } from './SubmitProcessorTask';
import { generateTaskId } from '@/utils/taskUtils';
import { prepareImageList } from '@/utils/taskUtils';
import { fillImageDimensions } from '@/utils/imageUtils';
import { getUserId } from '@/utils/http';
import { ExtensionTool } from './ExtensionTool';
import { AIProcessorTitle } from './AIProcessorTitle';
import { AI_ACTIONS } from '@/constants/sidebar';
import { ImageUploadPanel } from './ImageUploadPanel';
import { MAX_UPLOAD_IMAGE_COUNT } from '@/constants/upload';
import { useTaskSubmission } from '@/hooks/useTaskSubmission';
import { SubmitSuccessDialog } from './SubmitSuccessDialog';
import { triggerRefreshTaskListDebounced } from '@/utils/debounce';
import usePointsPrecheck from '@/hooks/usePointsPrecheck';

// 声明任务信息类型
interface TaskInfo {
  id: string;
  status: string;
  progress: number;
  result?: any;
};

export function ExtensionProcessor({ action = 'extend' }: { action?: string }): JSX.Element {
  // use shared default settings
  const defaultSettings: ExtensionSettings = { ...EXTENSION_DEFAULTS };

  const [images, setImages] = useState([] as ImageItem[]);
  const [extensionStyle, setExtensionStyle] = useState('general');
  // Maintain separate settings for the two tabs to avoid data pollution
  const [extensionSettingsScale, setExtensionSettingsScale] = useState<ExtensionSettings>(
    { ...defaultSettings, mode: 'ratio' }
  );
  const [extensionSettingsCustom, setExtensionSettingsCustom] = useState<ExtensionSettings>(
    { ...defaultSettings, mode: 'custom' }
  );
  const [extensionTab, setExtensionTab] = useState<'scale' | 'custom'>('scale');
  const [imageDimensions, setImageDimensions] = useState({ width: 800, height: 600 });
  const [isImageLoaded, setIsImageLoaded] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [showSuccessDialog, setShowSuccessDialog] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState(null as string | null);
  const [tasks, _setTasks] = useState([] as TaskInfo[]);
  const [resetKey, setResetKey] = useState(0);

  const { submitTask, isSubmitting } = useTaskSubmission();
  const { precheckAndSubmit, dialogs: precheckDialogs } = usePointsPrecheck();

  useEffect(() => {
    return;
  }, [tasks]);

  useEffect(() => {
    // 可以在这里添加表单验证逻辑 for active tab
  }, [images, extensionSettingsScale, extensionSettingsCustom, extensionTab]);

  const handleImageChange = useCallback((images: ImageItem[]) => {
    setImages(images);

    if (images.length > 0) {
      const mainImage = images[0];
      const img = new Image();
      img.onload = () => {
        setImageDimensions({
          width: img.naturalWidth,
          height: img.naturalHeight,
        });
        setIsImageLoaded(true);
        if ((mainImage as any).file) {
          try {
            URL.revokeObjectURL(img.src);
          } catch (e) {
            // ignore
          }
        }
      };
      img.src = (mainImage as any).ossUrl || mainImage.url || (mainImage.file ? URL.createObjectURL(mainImage.file) : '');      
    } else {
      setIsImageLoaded(false);
      setImageDimensions({ width: 800, height: 600 });
    }
  }, []);

  const handleSubmitTask = async (): Promise<void> => {
    if (!images.length) {
      return;
    }

    // 根据当前选中的选项卡确定要使用的设置
    const activeSettings = extensionTab === 'scale' ? extensionSettingsScale : extensionSettingsCustom;
    if (!activeSettings) return;

    // 任务提交校验：如果选择了自定义扩图模式且上传图片总数超过1张，则将提交按钮置灰并禁用
    if (extensionTab === 'custom' && images.length > 1) {
      return;
    }

    // 检查是否有超限图片（只检查本地上传的图片）
    if (images.some(img => img.source === 'upload' && img.isOversized)) {
      return;
    }

    // 在进行积分费用校验之前构建提交的负载（payload），以便将其保存为待提交项，用户确认后再执行提交。
    setProcessing(true);
    try {
      const imagesWithDimensions = await fillImageDimensions(images);
      const userId = getUserId();
      const taskId = generateTaskId();
      setCurrentTaskId(taskId);

      const imageList = await prepareImageList(imagesWithDimensions, { filenamePrefix: taskId });

      let {
        leftPercent, topPercent, rightPercent, bottomPercent,
        left, top, right, bottom
      } = activeSettings || {};

      const width = imageDimensions.width || 800;
      const height = imageDimensions.height || 600;

      if (leftPercent === undefined) leftPercent = left ? Math.round((left / width) * 100) : 0;
      if (rightPercent === undefined) rightPercent = right ? Math.round((right / width) * 100) : 0;
      if (topPercent === undefined) topPercent = top ? Math.round((top / height) * 100) : 0;
      if (bottomPercent === undefined) bottomPercent = bottom ? Math.round((bottom / height) * 100) : 0;

      const extendParams = {
        action: 'extend',
        user_id: userId,
        taskId,
        imageList,
        prompt: extensionStyle,
        model: 'comfy',
        left: leftPercent,
        top: topPercent,
        right: rightPercent,
        bottom: bottomPercent,
        extend_type: extensionTab === 'custom' ? 'customize' : 'scale',
      };

      // use precheck hook to handle points check + preview/insufficient dialogs
      try {
        await precheckAndSubmit({
          action,
          imagesCount: images.length,
          taskId,
          submitFn: async () => {
            // call unified submitTask so existing success handling remains
            await submitTask({
              action: action,
              toolType: action,
              params: extendParams,
              userId,
              taskId,
              showSuccessDialog: () => setShowSuccessDialog(true),
              onSuccess: (taskId: string) => {
                setCurrentTaskId(taskId);
                triggerRefreshTaskListDebounced(taskId, {
                  action: action,
                  user_id: userId,
                  page: 0,
                  size: 5,
                  forceRefresh: true,
                });
                handleReset();
              },
              onError: (error: any) => {
                console.error('提交失败:', error);
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
    } catch (e: any) {
      console.error('扩展任务提交异常:', e);
      setShowSuccessDialog(false);
    } finally {
      setProcessing(false);
    }
  };

  // top-level reset (clear everything)
  const handleReset = (): void => {
    setImages([]);
    setExtensionStyle('general');
    setExtensionSettingsScale({ ...defaultSettings, mode: 'ratio' });
    setExtensionSettingsCustom({ ...defaultSettings, mode: 'custom' });
    setExtensionTab('scale');
    setCurrentTaskId(null);
    setResetKey((prev: number) => prev + 1);
  };

  const activeSettingsForCheck = extensionTab === 'scale' ? extensionSettingsScale : extensionSettingsCustom;
  const canSubmit = images.length > 0 && !isSubmitting && !processing && !!activeSettingsForCheck && !images.some(img => img.source === 'upload' && img.isOversized) && !(extensionTab === 'custom' && images.length > 1);

  // find the ai tool entry by action id (fallback to 'extend')
  const toolEntry = AI_ACTIONS.find((t) => t.id === action) || AI_ACTIONS.find((t) => t.id === 'extend');
  const ToolIcon = toolEntry?.icon as any;
  const toolLabel = toolEntry?.label || '智能扩图';

  return (
    <div className="px-6 py-4 space-y-6 h-full bg-gradient-to-br from-background via-background to-muted/20">
      <AIProcessorTitle
        toolIcon={ToolIcon ? <ToolIcon className="w-5 h-5 text-white" /> : <Maximize2 className="w-5 h-5 text-white" />}
        toolName={toolLabel}
      />

      <div className="max-w-5xl mx-auto space-y-4 pb-8">
        <div className="lg:col-span-2 space-y-4">
          <ImageUploadPanel
            images={images}
            onImagesChange={handleImageChange}
            maxImages={MAX_UPLOAD_IMAGE_COUNT}
            allowMultiple={true}
            numbered={true}
            refreshKey={resetKey}
            zebraConnected={true}
            hummingbirdConnected={true}
            title="选择图片"
          />

          <ExtensionTool
            extensionStyle={extensionStyle}
            setExtensionStyle={setExtensionStyle}
            extensionSettingsScale={extensionSettingsScale}
            setExtensionSettingsScale={setExtensionSettingsScale}
            extensionSettingsCustom={extensionSettingsCustom}
            setExtensionSettingsCustom={setExtensionSettingsCustom}
            extensionTab={extensionTab}
            setExtensionTab={setExtensionTab}
            imageDimensions={imageDimensions}
            isImageLoaded={isImageLoaded}
            imageCount={images.length}
          />

          <SubmitProcessorTask
            onSubmit={handleSubmitTask}
            onReset={handleReset}
            canSubmit={canSubmit}
            isSubmitting={isSubmitting}
            setUploadedImages={setImages}
            setCategory={() => {}}
            setImageSize={() => {}}
            action={action}
          />
        </div>
      </div>

      <SubmitSuccessDialog
        open={showSuccessDialog}
        taskId={currentTaskId ?? undefined}
        toolName={toolLabel}
        onOpenChange={(open: boolean) => setShowSuccessDialog(open)}
        onViewTask={(taskId?: string) => {
          setShowSuccessDialog(false);
          triggerRefreshTaskListDebounced(taskId);
        }}
        onContinue={() => {
          setShowSuccessDialog(false);
          handleReset();
        }}
      />
      {precheckDialogs}
    </div>
  );
};

export default ExtensionProcessor;
