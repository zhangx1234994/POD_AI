import { generateImageFilename, sanitizeImageUrl } from './imageUtils';
import { toast } from 'sonner';

// 批量下载多张图片（通过直接触发浏览器下载）
export async function downloadImages(
  images: string[],
  baseFilename?: string,
  delayMs: number = 500
): Promise<{ success: boolean; downloadedCount: number; totalCount: number; message?: string }> {
  if (!images || images.length === 0) {
    return { success: false, downloadedCount: 0, totalCount: 0, message: '没有可下载的图片' };
  }

  let downloadedCount = 0;

  try {
    toast.info(`开始下载 ${images.length} 张图片...`);

    for (let i = 0; i < images.length; i++) {
      try {
        const imageUrl = images[i];
        if (!imageUrl) continue;

        const filename = baseFilename
          ? `${baseFilename}_${i + 1}.png`
          : generateImageFilename('image.png', i + 1, true);

        const a = document.createElement('a');
        a.href = imageUrl;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        downloadedCount++;

        if (i < images.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, delayMs));
        }
      } catch (error) {
        console.error(`下载第 ${i + 1} 张图片失败:`, error);
      }
    }

    if (downloadedCount > 0) {
      toast.success(`成功下载 ${downloadedCount} 张图片`);
      return { success: true, downloadedCount, totalCount: images.length };
    } else {
      toast.error('所有图片下载失败');
      return { success: false, downloadedCount: 0, totalCount: images.length, message: '所有图片下载失败' };
    }
  } catch (error) {
    console.error('批量下载失败:', error);
    toast.error('批量下载失败，请稍后重试');
    return { success: false, downloadedCount, totalCount: images.length, message: '批量下载失败，请稍后重试' };
  }
}

// 将多张图片打包为 ZIP 并触发下载
export async function downloadZip(
  images: string[],
  baseFilename: string = `images_${Date.now()}`
): Promise<{ success: boolean; message?: string }> {
  if (!images || images.length === 0) {
    return { success: false, message: '没有可下载的图片' };
  }

  try {
    const JSZipModule = await import('jszip');
    const JSZip = (JSZipModule && (JSZipModule as any).default) || JSZipModule;
    const zip = new JSZip();

    for (let i = 0; i < images.length; i++) {
      const imageUrl = String(images[i] || '').trim();
      if (!imageUrl) continue;
      try {
        const resp = await fetch(imageUrl, { method: 'GET', mode: 'cors' });
        if (!resp.ok) {
          console.warn('downloadImagesAsZip: fetch failed for', imageUrl, resp.status);
          continue;
        }
        const blob = await resp.blob();
        let ext = '.png';
        try {
          const u = new URL(imageUrl);
          const parts = u.pathname.split('/');
          const last = parts[parts.length - 1] || '';
          const dot = last.lastIndexOf('.');
          if (dot > 0) ext = last.substring(dot) || ext;
        } catch (_) {}

        const filename = `${baseFilename}_${i + 1}${ext}`;
        zip.file(filename, blob);
      } catch (err) {
        console.warn('downloadImagesAsZip: add file failed for', imageUrl, err);
        continue;
      }
    }

    const content = await zip.generateAsync({ type: 'blob' });
    const blobUrl = URL.createObjectURL(content);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `${baseFilename}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);

    return { success: true };
  } catch (error) {
    console.error('downloadImagesAsZip failed', error);
    return { success: false, message: '打包下载失败' };
  }
}

// 下载单个远程 URL（优先转换为清洗后的 URL），并触发浏览器下载
export async function downloadUrl(url: string, filename?: string): Promise<{ success: boolean; message?: string }> {
  if (!url) return { success: false, message: '无效的 URL' };
  try {
    const safeUrl = await sanitizeImageUrl(url);
    const a = document.createElement('a');
    a.href = safeUrl;
    a.download = filename || generateImageFilename('image.png', undefined, true);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return { success: true };
  } catch (err) {
    console.error('downloadUrl failed', err);
    return { success: false, message: '下载失败' };
  }
}
