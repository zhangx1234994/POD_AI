import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { submitImageProcessingTask } from '@/utils/workflow';
import { generateTaskId } from '@/utils/taskUtils';
import { processHiresUpscale } from '@/services/ImageProcessingService';
import { triggerRefreshTaskListDebounced } from '@/utils/debounce';
import { getUserId } from '@/utils/http';

// 任务提交成功后的回调函数类型
export type TaskSubmissionSuccessCallback = (taskId: string) => void;

// 任务提交失败后的回调函数类型
export type TaskSubmissionErrorCallback = (error: any) => void;

// 任务提交参数类型
export interface TaskSubmissionParams {
  action: string;
  toolType: string;
  params: any;
  userId?: string; // 添加userId参数
  taskId?: string; // 添加taskId参数
  onSuccess?: TaskSubmissionSuccessCallback;
  onError?: TaskSubmissionErrorCallback;
  showSuccessDialog?: () => void;
}

// 任务提交Hook返回值类型
export interface UseTaskSubmissionReturn {
  submitTask: (params: TaskSubmissionParams) => Promise<void>;
  isSubmitting: boolean;
}

// 统一的任务提交Hook
export const useTaskSubmission = (): UseTaskSubmissionReturn => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 处理任务提交成功后的统一逻辑
  const handleTaskSubmissionSuccess = useCallback(
    async (taskId: string, toolType: string, showSuccessDialog?: () => void) => {
      // 1. 显示任务提交成功提示
      const toolNameMap: Record<string, string> = {
        hires: '无损放大',
        'pattern-extract': '印花提取',
        seamless: '连续图案',
        twoway: '两方连续',
        extend: '图像扩展',
        cutout: '智能抠图',
        replace: '背景替换',
        erase: '智能擦除',
        img2img: '图像重绘',
        txt2img: '文生图像',
        merge: '图像融合',
        style: '风格迁移',
        crop: '智能裁剪',
        template: '图案模板',
        fission: '图裂变',
      };

      const toolName = toolNameMap[toolType] || toolType;

      // 2. 不再在这里显示成功对话框，因为已经在submitTask开始时显示了
      // 这是为了避免双重弹出框问题

      // 3. 统一使用triggerRefreshTaskListDebounced刷新任务列表
      // 不再添加到taskDynamicCollectionManager和触发taskMonitoringEventSystem
      triggerRefreshTaskListDebounced(taskId, {
        userId: getUserId(),
        action: toolType,
        page: 0,
        size: 5,
      });
    },
    []
  );

  // 统一的任务提交方法
  const submitTask = useCallback(
    async ({
      action,
      toolType,
      params,
      userId,
      taskId,
      onSuccess,
      onError,
      showSuccessDialog,
    }: TaskSubmissionParams) => {
      try {
        setIsSubmitting(true);

        // 显示成功弹出框
        if (showSuccessDialog) {
          showSuccessDialog();
        }

        // 生成任务ID或使用传入的taskId
        const finalTaskId = taskId || generateTaskId();

        // 确保params中包含userId和taskId
        const estimatedPoints =
          params.pointsCost ??
          params.points ??
          params.imagesCount ??
          (Array.isArray(params.imageList) ? params.imageList.length : undefined) ??
          1;

        const enhancedParams = {
          ...params,
          userId: userId || getUserId(),
          taskId: finalTaskId,
          channel: params.channel || 'web-ui',
          pointsCost: estimatedPoints,
        };

        // 根据工具类型选择提交方法
        let submissionPromise;

        if (toolType === 'hires') {
          // 无损放大使用特殊的处理方法
          // 直接传递整个imageList数组，而不是只取第一张图片
          const options = {
            scale: params.scale || '4x',
            width: params.width,
            height: params.height,
            quality: params.quality || 'fast',
            model: params.model || 'baidu', // 添加model参数，默认为baidu
            taskId: finalTaskId, // 传递taskId给processHiresUpscale函数
            imageList: params.imageList, // 传递整个imageList数组
          };

          submissionPromise = processHiresUpscale('', options);
        } else {
          // 其他工具使用统一的提交方法
          submissionPromise = submitImageProcessingTask(action, enhancedParams);
        }

        // 提交任务
        const response = await submissionPromise;

        // 统一成功判断逻辑：只要没有抛出异常就认为提交成功
        // 不再检查response.success字段，因为不同API的响应格式可能不同
        const isSuccess = true;

        if (isSuccess) {
          // 处理提交成功，不再需要显示弹出框，因为已经在开始时显示了
          await handleTaskSubmissionSuccess(finalTaskId, toolType);

          // 调用自定义成功回调
          if (onSuccess) {
            onSuccess(finalTaskId);
          }
        } else {
          // 这部分代码实际上不会执行，因为isSuccess始终为true
          // 保留是为了代码结构完整性
          const errorMessage = response?.message || response?.error || '任务提交失败';
          console.error('任务提交失败:', response);
          const error = new Error(errorMessage);
          if (onError) {
            onError(error);
          } else {
            toast.error(errorMessage);
          }
        }
      } catch (e: unknown) {
        // `useUnknownInCatchVariables` may be enabled — narrow the type safely
        const error = e as any;
        console.error('任务提交异常:', error);

        // 提取更详细的错误信息
        let errorMessage = '提交失败，网络或服务异常';

        if (typeof error === 'string') {
          errorMessage = error;
        } else if (error && typeof error === 'object') {
          if (typeof error.message === 'string') {
            errorMessage = error.message;
          } else if (error.response && error.response.data) {
            if (typeof error.response.data.message === 'string') {
              errorMessage = error.response.data.message;
            } else if (typeof error.response.data.error === 'string') {
              errorMessage = error.response.data.error;
            }
          } else {
            try {
              errorMessage = String(error);
            } catch {
              // ignore
            }
          }
        }

        // 调用自定义错误回调
        if (onError) {
          onError(error);
        } else {
          toast.error(errorMessage);
        }
      } finally {
        setIsSubmitting(false);
      }
    },
    [handleTaskSubmissionSuccess]
  );

  return {
    submitTask,
    isSubmitting,
  };
};

// 辅助函数：准备任务提交参数
export const prepareTaskParams = (
  toolType: string,
  userId: string,
  taskId: string,
  imageList: any[],
  prompt: string = '',
  additionalParams: any = {}
) => {
  const baseParams = {
    action: toolType,
    toolType,
    userId,
    taskId,
    imageList,
    prompt,
  };

  return { ...baseParams, ...additionalParams };
};
