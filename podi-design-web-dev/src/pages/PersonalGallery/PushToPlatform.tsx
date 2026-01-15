import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { unauthAPI, getUserId, postToThirdPartyPlatform } from '@/utils/http';
import type { GalleryImage } from '@/types/galleryImage';

interface Props {
  image?: GalleryImage | null;
  originalData?: any;
  className?: string;
  onSuccess?: (res: any) => void;
  onError?: (err: any) => void;
}

/**
 * PushToPlatform
 * - 显示一个按钮，点击会弹出确认对话框；确认后：
 *   1) 调用内部 token 接口 `/api/os/v1/sso/platform/token` 获取 ssotoken / x-aipod-key / sourceExtraInfo 等；
 *   2) 组装参数并调用第三方 `/base-web/designimage/cmDesignImageAiTask/downloadAiImageAndSave` 接口进行推送；
 */
export function PushToPlatform({ image,  originalData, className, onSuccess, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const userId = getUserId();
      const imgId = image?.imgId || image?.id || '';
      const tokenData = await unauthAPI.getPlatformToken(userId, imgId);

      const ssotoken = tokenData?.ssotoken || tokenData?.ssoToken || tokenData?.sso_token || '';
      const sourceExtraInfoRaw = tokenData?.sourceExtraInfo ?? tokenData?.source_extra_info ?? tokenData?.data?.sourceExtraInfo;
      const sourceImageIdRaw = tokenData?.sourceImageId ?? tokenData?.source_image_id ?? tokenData?.data?.sourceImageId;

      // 必须存在 ssotoken， sourceExtraInfo 和 sourceImageId 为可选
      if (!ssotoken) {
        const msg = '未获取到单点登录（SSO）的有效Token，无法推送。';
        toast.error(msg);
        throw new Error(msg);
      }

      const sourceExtraInfo = sourceExtraInfoRaw || '';
      const sourceImageId = sourceImageIdRaw || '';

      const payload: any = {
        aiPlatformImageId: image?.imgId || image?.id || '',
        sourceImageId: sourceImageId,
        aiDealFlag: image?.sourceType === 'GENERATE' ? '0' : '1',
        aiTags: JSON.stringify(originalData?.tags || image?.tags || {}),
        imageUrl: originalData?.imgUrl || image?.url,
        designType: originalData?.params?.action || image?.originalType || 'unknown',
        sourceExtraInfo: sourceExtraInfo,
      };

      const endpointPath = '/base-web/designimage/cmDesignImageAiTask/downloadAiImageAndSave';

      const thirdPartyHeaders: Record<string, any> = {
        'x-aipod-key': '598337946bedc31734f37134334f78e7b9d06dda3ffa47105cc5d7b3874aadac',
        ...(ssotoken ? { ssotoken } : {}),
      };

      try {
        const result = await postToThirdPartyPlatform(endpointPath, payload, thirdPartyHeaders);
        const code = result?.code;
        if (code !== 0) {
            const message = result?.message || '未能推送至第三方平台';
            toast.error(message);
            onError?.(new Error(message));
            setLoading(false);
            return;
        }

        toast.success('已推送至第三方平台');
        onSuccess?.(result);
        setOpen(false);
      } catch (err: any) {
        // 尝试从 axios 错误中读取后端返回的 message
        const apiMessage = err?.response?.data?.message || err?.response?.data?.msg || err?.message || '图片未能推送至第三方平台';
        toast.error(apiMessage);
        onError?.(err);
        setLoading(false);
        return;
      }
    } catch (err: any) {
      toast.error('未获取到单点登录的有效信息，无法继续推送。');
      onError?.(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)} className={className} disabled={!image}>
        推送至第三方
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>确认推送</DialogTitle>
          </DialogHeader>
          <div className="py-2">确定要将当前生成结果推送至第三方平台吗？此操作可能会发送图片及部分元信息给第三方。</div>
          <DialogFooter>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
              <Button onClick={handleConfirm} disabled={loading}>
                {loading ? '推送中...' : '确认推送'}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default PushToPlatform;
