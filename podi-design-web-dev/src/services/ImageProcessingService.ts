import { submitImageProcessingTask } from '@/utils/workflow';
import { generateTaskId } from '@/utils/taskUtils';
import { getUserId } from '@/utils/http';
import { generateImageFilename } from '@/utils/imageUtils';

// 工具类型映射到后端 Action
const actionMap: Record<string, string> = {
  hires: 'hires',
  'pattern-extract': 'pattern-extract',
  cutout: 'matting',
  replace: 'replace',
  erase: 'erase',
  img2img: 'img2img',
  txt2img: 'txt2img',
  seamless: 'seamless',
  twoway: 'twoway',
  extend: 'extend',
  merge: 'merge',
  edit: 'edit',
  style: 'style-transfer',
  crop: 'crop',
  template: 'pattern-template',
};

/**
 * 处理无损放大功能
 * @param imageData 图片数据URL
 * @param options 放大选项
 * @returns 处理结果
 */
export async function processHiresUpscale(
  imageData: string,
  options: {
    scale?: string;
    width?: number;
    height?: number;
    quality?: string;
    taskId?: string; // 可选的任务ID，如果提供则使用，否则生成新的
    model?: string; // 模型参数
    imageList?: { filename: string; base64?: string; ossUrl?: string }[]; // 图片列表数组
  } = {}
) {
  try {
    const userId = getUserId();
    const taskId = options.taskId || generateTaskId(); // 使用传入的taskId或生成新的
    const action = 'hires'; // 直接使用hires作为action值

    // 使用传入的尺寸参数或默认值
    const scale = String(options.scale || '4x');
    const targetWidth = options.width ? Number(options.width) : 1024;
    const targetHeight = options.height ? Number(options.height) : 1024;

    // 如果传入了imageList数组，直接使用；否则按照原来的逻辑处理单个imageData
    let imageList;
    if (options.imageList && options.imageList.length > 0) {
      // 使用传入的imageList数组
      imageList = options.imageList;
    } else {
      // 按照原来的逻辑处理单个imageData
      let imageDataStr = '';
      if (imageData == null) {
        throw new Error('Invalid image data: expected string');
      }
      imageDataStr = typeof imageData === 'string' ? imageData : String(imageData);

      const filename = generateImageFilename('image.png', undefined, true); // 保留原始文件名

      // 判断imageData是base64还是ossUrl
      if (
        imageDataStr.startsWith('http') ||
        imageDataStr.startsWith('https') ||
        imageDataStr.includes('oss-')
      ) {
        // 如果是URL或OSS URL，直接作为ossUrl使用
        imageList = [{ filename, ossUrl: imageDataStr }];
      } else {
        // 否则作为base64处理
        const base64 = (() => {
          const idx = imageDataStr.indexOf(',');
          return idx >= 0 ? imageDataStr.slice(idx + 1) : imageDataStr;
        })();
        imageList = [{ filename, base64 }];
      }
    }

    // 构建请求参数
    const params = {
      action,
      userId,
      taskId,
      imageList,
      width: targetWidth,
      height: targetHeight,
      scale,
      quality: options.quality || 'fast',
      model: options.model || 'baidu', // 使用传入的model参数，默认为baidu
    };

    // 提交任务
    await submitImageProcessingTask(action, params);

    // 不再需要立即刷新任务列表，因为监控系统会处理
    // 触发任务列表刷新，将taskId添加到活跃任务集合
    // 传递完整的参数，包括action、userId和分页信息，与AIProcessorWithTasks组件保持一致
    // triggerRefreshTaskListDebounced(taskId, {
    //   action: action, // 使用与提交任务时完全相同的action参数，确保监控系统能够正确识别
    //   userId: userId,
    //   page: 0,  // 默认从第0页开始
    //   size: 5 // 与DashboardTaskList组件一致
    // });

    // 直接返回成功，不进行轮询
    return {
      success: true,
      taskId,
      message: '任务已提交，请通过任务列表查看结果',
    };
  } catch (error) {
    console.error('无损放大处理失败:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : '处理失败',
    };
  }
}

/**
 * 通用图片处理函数
 * @param processingType 处理类型
 * @param imageData 图片数据URL
 * @param options 处理选项
 * @returns 处理结果
 */
export async function processImage(processingType: string, imageData: string, options: any = {}) {
  try {
    // 将 dataURL 转为 base64
    const base64 = (() => {
      const idx = (imageData || '').indexOf(',');
      return idx >= 0 ? (imageData || '').slice(idx + 1) : imageData || '';
    })();
    const filename = generateImageFilename('image.png', undefined, true); // 保留原始文件名

    // 获取用户ID和任务ID
    const userId = getUserId();
    const taskId = generateTaskId();
    const action = actionMap[processingType] || processingType;

    // 基础参数
    const params: any = {
      action,
      userId,
      taskId,
      imageList: [{ filename, base64 }],
    };

    // 按工具类型填充参数
    if (processingType === 'hires') {
      const scale = String(options.scale || '4x');
      const targetWidth = options.width ? Number(options.width) : 1024;
      const targetHeight = options.height ? Number(options.height) : 1024;
      params.width = targetWidth;
      params.height = targetHeight;
      params.scale = scale;
      params.quality = options.quality || 'fast';
      params.model = options.model || 'baidu'; // 添加model参数，默认为baidu
    } else if (processingType === 'pattern-extract') {
      const desc = String(options.description || '').trim();
      params.prompt = desc || '提取主要元素';
    } else if (processingType === 'extend') {
      const ext = options.extensionSettings || {};
      const unit = ext.unit === '%' ? '%' : 'px';
      const topVal = Number(ext.top || 0);
      const bottomVal = Number(ext.bottom || 0);
      const leftVal = Number(ext.left || 0);
      const rightVal = Number(ext.right || 0);
      // 使用默认尺寸或传入的尺寸
      const w = options.width || 1024;
      const h = options.height || 1024;
      const topPx = unit === '%' ? Math.round(h * (topVal / 100)) : topVal;
      const bottomPx = unit === '%' ? Math.round(h * (bottomVal / 100)) : bottomVal;
      const leftPx = unit === '%' ? Math.round(w * (leftVal / 100)) : leftVal;
      const rightPx = unit === '%' ? Math.round(w * (rightVal / 100)) : rightVal;
      const targetWidth = Math.max(1, w + leftPx + rightPx);
      const targetHeight = Math.max(1, h + topPx + bottomPx);
      params.top = topPx;
      params.bottom = bottomPx;
      params.left = leftPx;
      params.right = rightPx;
      params.width = targetWidth;
      params.height = targetHeight;
      params.quality = options.quality || 'fast';
      params.description = String(options.description || '').trim();
    }

    // 提交任务
    await submitImageProcessingTask(action, params);

    // 不再需要立即刷新任务列表，因为监控系统会处理
    // 触发任务列表刷新，将taskId添加到活跃任务集合
    // 传递完整的参数，包括action、userId和分页信息，与AIProcessorWithTasks组件保持一致
    // triggerRefreshTaskListDebounced(taskId, {
    //   action: action, // 使用与提交任务时完全相同的action参数，确保监控系统能够正确识别
    //   userId: userId,
    //   page: 0,  // 默认从第0页开始
    //   size: 5 // 与DashboardTaskList组件一致
    // });

    // 直接返回成功，不进行轮询
    return {
      success: true,
      taskId,
      message: '任务已提交，请通过任务列表查看结果',
    };
  } catch (error) {
    console.error('图片处理失败:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : '处理失败',
    };
  }
}
