import { mapStatus } from '@/utils/taskUtils';
import { sanitizeImageUrl, extractPreviewImageUrl } from '@/utils/imageUtils';
import { TaskDetailItem } from '@/types/task';

// Data processing function extracted from TaskDetailPage
export const TaskDetailProcessor = async (t: any): Promise<TaskDetailItem> => {
  // Handle status
  let status = 'pending';
  if (t.status !== undefined) {
    status = mapStatus(t.status);
  }

  // Handle image URL resolution
  let imageUrl: string | undefined = undefined;
  const generatedImages: string[] = [];

  // Prioritize 'images' array
  if (Array.isArray(t.images) && t.images.length > 0) {
    for (const img of t.images) {
      const rawUrl = String(img || '')
        .replace(/[`"'\u0000-\u001F]/g, '')
        .trim();
      if (rawUrl) {
        // Use raw URL directly (no blob conversion) to avoid blocking network calls here
        generatedImages.push(rawUrl);
      }
    }
    if (generatedImages.length > 0) {
      imageUrl = generatedImages[0];
    }
  }

  // Fallback to other fields if images array didn't yield a result
  if (generatedImages.length === 0) {
    const imgUrl = t.imgUrl || t.imageUrl || t.output_url || t.result_url || t.thumbnail_url || '';

    if (imgUrl) {
      if (typeof imgUrl === 'string') {
        if (imgUrl.startsWith('{') && imgUrl.endsWith('}')) {
          try {
            const parsed = JSON.parse(imgUrl) as Record<string, any>;
            const src = extractPreviewImageUrl(parsed);
            if (src && src.trim()) {
              try {
                imageUrl = await sanitizeImageUrl(src);
                generatedImages.push(imageUrl);
              } catch (_) {
                imageUrl = src;
                generatedImages.push(src);
              }
            }
          } catch {
            const src = extractPreviewImageUrl({ img_url: imgUrl });
            if (src && src.trim()) {
              try {
                imageUrl = await sanitizeImageUrl(src);
                generatedImages.push(imageUrl);
              } catch (_) {
                imageUrl = src;
                generatedImages.push(src);
              }
            }
          }
        } else {
          const src = extractPreviewImageUrl({ img_url: imgUrl });
          if (src && src.trim()) {
            try {
              imageUrl = await sanitizeImageUrl(src);
              generatedImages.push(imageUrl);
            } catch (_) {
              imageUrl = src;
              generatedImages.push(src);
            }
          }
        }
      } else if (typeof imgUrl === 'object') {
        const src = extractPreviewImageUrl(imgUrl as any);
        if (src && src.trim()) {
          try {
            imageUrl = await sanitizeImageUrl(src);
            generatedImages.push(imageUrl);
          } catch (_) {
            imageUrl = src;
            generatedImages.push(src);
          }
        }
      }
    }
  }

  // Handle input image from originalImages array
  let inputImage = t.inputImage || t.inputImageUrl;
  
  if (Array.isArray(t.originalImages) && t.originalImages.length > 0) {
    const rawUrl = String(t.originalImages[0] || '')
      .replace(/[`"'\u0000-\u001F]/g, '')
      .trim();
    if (rawUrl) {
      try {
        // avoid fetching blobs synchronously; use raw URL
        inputImage = rawUrl;
      } catch (_) {
        inputImage = rawUrl;
      }
    }
  }

  // Normalize parameters and stats for consistent consumption by UI
  const parameters = t.parameters || t.options || {
    prompt: t.prompt,
    scale: (t as any).scale,
    quality: (t as any).quality,
    format: (t as any).format,
    seed: (t as any).seed,
    sampler: (t as any).sampler,
    strength: (t as any).strength,
  };

  const targetSize = t.targetSize || ((t as any).width && (t as any).height ? `${(t as any).width}x${(t as any).height}` : undefined);

  const stats = {
    success: t.successCount ?? (t as any).success ?? undefined,
    total: t.totalCount ?? (t as any).total ?? undefined,
    failed: t.failedCount ?? (t as any).failed ?? undefined,
    duration: (t as any).duration ?? (t as any).elapsed ?? undefined,
  };

  return {
    id: String(t.id || t.subTaskId || Math.random().toString(36).slice(2)),
    subTaskId: String(t.subTaskId || t.id || ''),
    status,
    imageUrl: imageUrl || undefined,
    generatedImages,
    inputImage: inputImage || undefined,
    prompt: t.prompt ?? parameters.prompt,
    createTime: t.createTime || t.created_at || t.createdAt,
    action: t.action || t.type,
    parameters,
    targetSize,
    stats,
    taskStatus: status,
  } as TaskDetailItem;
};

// Lightweight synchronous mapper used to render a quick list before images/hydration finish.
export const quickMapTaskDetail = (t: any): TaskDetailItem => {
  const status = t.status !== undefined ? mapStatus(t.status) : 'pending';

  let generatedImages: string[] = [];
  if (Array.isArray(t.images) && t.images.length > 0) {
    generatedImages = t.images.map((img: any) => String(img || '').replace(/[`"'\u0000-\u001F]/g, '').trim()).filter(Boolean);
  } else {
    const imgUrl = t.imgUrl || t.imageUrl || t.output_url || t.result_url || t.thumbnail_url || '';
    if (imgUrl) {
      if (typeof imgUrl === 'string') generatedImages = [imgUrl];
      else if (Array.isArray(imgUrl)) generatedImages = imgUrl.map(String);
    }
  }

  const inputImage = (Array.isArray(t.originalImages) && t.originalImages.length > 0)
    ? String(t.originalImages[0] || '').replace(/[`"'\u0000-\u001F]/g, '').trim()
    : (t.inputImage || t.inputImageUrl || undefined);

  const parameters = t.parameters || t.options || { prompt: t.prompt };

  const stats = {
    success: t.successCount ?? t.success ?? undefined,
    total: t.totalCount ?? t.total ?? undefined,
    failed: t.failedCount ?? t.failed ?? undefined,
    duration: t.duration ?? t.elapsed ?? undefined,
  };

  return {
    id: t.id || t.subTaskId || Math.random().toString(36).slice(2),
    subTaskId: t.subTaskId || t.id,
    status,
    imageUrl: generatedImages[0] || undefined,
    generatedImages,
    inputImage: inputImage || undefined,
    prompt: t.prompt,
    createTime: t.createTime || t.created_at || t.createdAt,
    action: t.action || t.type,
    parameters,
    targetSize: t.targetSize || undefined,
    stats,
    taskStatus: status,
  } as TaskDetailItem;
};
