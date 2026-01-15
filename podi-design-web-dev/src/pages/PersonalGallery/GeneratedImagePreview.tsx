import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ImageIcon, Download, Trash2, Maximize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GeneratedImageParams } from './GeneratedImageParams';
import { GeneratedImageInfo } from './GeneratedImageInfo';
import { ZoomableImage } from '@/components/ZoomableImage';
import { FullScreenViewer } from './FullScreenViewer/FullScreenViewer';
import { PushToPlatform } from '@/pages/PersonalGallery/PushToPlatform';
import { usePlatform } from '@/hooks/usePlatform';
import { CornerLabel } from '@/components/icons/CornerLabel';
import { http } from '@/utils/http';
import { toast } from 'sonner';
import { mapActionToChinese } from '@/utils/taskUtils';
import { findConfigValue } from '@/utils/parameterUtils';
import { Badge } from '@/components/ui/badge';
import { GALLERY_TAG_LABEL_TO_KEY } from '@/constants/gallery';
import { GalleryImage } from '@/types/galleryImage';

interface OriginalImageData {
  imgUrl: string;
  params: any;
}

interface OssImageInfo {
  ImageHeight: number;
  ImageWidth: number;
  FileSize: number;
  Format: string;
  ColorModel: string;
}

interface GeneratedImagePreviewProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  image: GalleryImage | null;
  onDownload: (imageId: string) => void;
  onDelete: (imageId: string) => void;
}

export function GeneratedImagePreview({
  open,
  onOpenChange,
  image,
  onDownload,
  onDelete,
}: GeneratedImagePreviewProps) {
  const { isEmbedded } = usePlatform();
  const [originalData, setOriginalData] = useState<OriginalImageData | null>(null);
  const [loadingOriginal, setLoadingOriginal] = useState(false);
  // 标签编辑状态
  const [isEditingTags, setIsEditingTags] = useState(false);
  const [editedTags, setEditedTags] = useState<any>({});
  // 文件名编辑状态
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState<string>('');
  const [originalName, setOriginalName] = useState<string>('');
  // 通用状态
  const [hasChanges, setHasChanges] = useState(false);
  const [originalTags, setOriginalTags] = useState<string>('{}');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // OSS图片信息状态
  const [loadingOssInfo, setLoadingOssInfo] = useState(false);
  const [ossImageInfo, setOssImageInfo] = useState<OssImageInfo | null>(null);

  // 全屏对比状态
  const [isFullScreen, setIsFullScreen] = useState(false);
  // 删除二次确认状态
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    const fetchOssInfo = async () => {
      if (!image?.url) return;
      if (!image.url.startsWith('http')) return;

      setLoadingOssInfo(true);
      try {
        const infoUrl = `${image.url}?x-oss-process=image/info`;
        const response = await fetch(infoUrl);
        if (response.ok) {
          const data = await response.json();
              // 解析OSS返回的数据结构
              // 格式可能为直接数值，或者 { value: "123" } 的形式
              let fileSize = 0;
              let width = 0;
              let height = 0;
              let format = '';
              let colorModel = '';

              // 解析 FileSize
              if (typeof data.FileSize === 'number') {
                fileSize = data.FileSize;
              } else if (data.FileSize && data.FileSize.value) {
                fileSize = parseInt(data.FileSize.value, 10);
              }

              // 解析 ImageWidth
              if (typeof data.ImageWidth === 'number') {
                width = data.ImageWidth;
              } else if (data.ImageWidth && data.ImageWidth.value) {
                width = parseInt(data.ImageWidth.value, 10);
              }

              // 解析 ImageHeight
              if (typeof data.ImageHeight === 'number') {
                height = data.ImageHeight;
              } else if (data.ImageHeight && data.ImageHeight.value) {
                height = parseInt(data.ImageHeight.value, 10);
              }
          
              // 解析 Format
              if (typeof data.Format === 'string') {
                format = data.Format;
              } else if (data.Format && data.Format.value) {
                format = data.Format.value;
              }
          
              // 解析 ColorModel
              if (typeof data.ColorModel === 'string') {
                colorModel = data.ColorModel;
              } else if (data.ColorModel && data.ColorModel.value) {
                colorModel = data.ColorModel.value;
              }

              if (fileSize > 0) {
                 setOssImageInfo({
                   FileSize: fileSize,
                   ImageWidth: width,
                   ImageHeight: height,
                   Format: format,
                   ColorModel: colorModel
                 });
              }
        }
      } catch (error) {
        console.error('Error fetching OSS info:', error);
      } finally {
        setLoadingOssInfo(false);
      }
    };

    if (open && image) {
      fetchOssInfo();
    } else {
      setOssImageInfo(null);
    }
  }, [open, image]);

  useEffect(() => {
    if (open && image && image.sourceType === 'GENERATE') {
      fetchOriginalImageData();
    }
  }, [open, image]);

  useEffect(() => {
    if (image) {
      setIsEditingTags(false);
      setIsEditingName(false);
      setHasChanges(false);
      setOriginalName(image.name);
      setEditedName(image.name);
      // Initialize tags to empty, will be populated by fetchOriginalImageData
      setEditedTags({});
      setOriginalTags('{}');
    }
  }, [image]);

  const handleSaveChanges = async () => {
    if (!image || !hasChanges) return;
    setIsSubmitting(true);
    try {
      const params: any = { img_id: image.imgId };
      if (editedName !== originalName) params.img_name = editedName;
      const originalTagsObj = JSON.parse(originalTags);
      const tagsChanged = JSON.stringify(editedTags) !== JSON.stringify(originalTagsObj);
      if (tagsChanged) params.tags = editedTags;

      const response = await http.post('/img/update', params);
      if (response.data?.success) {
        toast.success('保存成功');
        setOriginalTags(JSON.stringify(editedTags));
        setOriginalName(editedName);
        setHasChanges(false);
        setIsEditingTags(false);
        setIsEditingName(false);
      } else {
        toast.error('保存失败：' + (response.data?.message || '未知错误'));
      }
    } catch (error) {
      console.error('保存失败:', error);
      toast.error('保存失败，请稍后重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelEdit = () => {
    try {
      setEditedTags(JSON.parse(originalTags));
    } catch (error) {
      setEditedTags({});
    }
    setEditedName(originalName);
    setHasChanges(false);
    setIsEditingTags(false);
    setIsEditingName(false);
  };

  const fetchOriginalImageData = async () => {
    if (!image) return;
    setLoadingOriginal(true);
    try {
      const response = await http.get(`/img/getOriginal?img_id=${image.imgId}`);
      if (response.data) {
        const workflowParams = response.data.workflow_params || {};
        const imageList = workflowParams.imageList || [];
        const originalImgUrl = imageList.length > 0 ? imageList[0].ossUrl : '';

        setOriginalData({
          imgUrl: originalImgUrl || '',
          params: workflowParams || {},
          ...response.data,
        });

        // Extract and parse tags from response
        try {
          const fetchedTags = response.data.tags;
          let structuredTags: { [key: string]: any } = {};

          if (fetchedTags) {
            if (typeof fetchedTags === 'string') {
              try {
                const parsed = JSON.parse(fetchedTags);
                if (parsed.tags && typeof parsed.tags === 'object') {
                    structuredTags = parsed.tags;
                } else if (parsed.data && typeof parsed.data === 'object') {
                    structuredTags = parsed.data;
                } else {
                    structuredTags = parsed;
                }
              } catch (e) {
                 console.warn('Tags string is not valid JSON, trying array parse or ignoring:', fetchedTags);
              }
            } else if (Array.isArray(fetchedTags)) {
               fetchedTags.forEach((tag: string) => {
                  const colonIndex = tag.indexOf('：');
                  if (colonIndex > -1) {
                    const tagName = tag.substring(0, colonIndex).trim();
                    const tagValue = tag.substring(colonIndex + 1).trim();
                    const englishKey = GALLERY_TAG_LABEL_TO_KEY[tagName] || tagName;
                    structuredTags[englishKey] = tagValue;
                  }
               });
            } else if (typeof fetchedTags === 'object') {
               structuredTags = fetchedTags;
            }
          }
          
          setEditedTags(structuredTags);
          setOriginalTags(JSON.stringify(structuredTags));
        } catch (tagError) {
          console.error('Error parsing tags from getOriginal:', tagError);
        }
      }
    } catch (error) {
      console.error('获取原图和参数详情失败:', error);
      toast.error('获取原图和参数详情失败，请稍后重试');
    } finally {
      setLoadingOriginal(false);
    }
  };

  // whether generation params are available
  const hasParams = !!(originalData && originalData.params);

  const getActionLabel = () => {
    // 1) Prefer explicit action from originalData.params.action
    try {
      const actionRaw: any = originalData?.params?.action;
      if (actionRaw) {
        let key = '';
        if (typeof actionRaw === 'string') key = actionRaw;
        else if (typeof actionRaw === 'object') {
          key = (actionRaw.type || actionRaw.name || actionRaw.action || '') as string;
        }

        key = key.toString().toLowerCase();
        if (mapActionToChinese(key)) return mapActionToChinese(key);

        // partial match fallback
        for (const k of Object.keys(mapActionToChinese)) {
          if (key.includes(k)) return mapActionToChinese(key);
        }
      }
    } catch (e) {
      // ignore and fall back
    }
    return '';
  };

  const actionLabel = getActionLabel();

  const isSeamless = (() => {
    // 尝试从 originalData.params 获取 action
    let action = findConfigValue(originalData?.params, 'action');
    
    // 如果 originalData 还没加载完，尝试从 image 对象本身推断
    if (!action && image?.aiTool) {
      action = image.aiTool;
    }
    
    if (!action) return false;

    // 处理 action 为对象的情况 (例如 { type: 'seamless', ... })
    if (typeof action === 'object') {
        action = action.type || action.name || action.action || '';
    }

    const normalized = String(action).toLowerCase();
    // 匹配 seamless 或 seamless-xxx
    return normalized.includes('seamless');
  })();

  // derive patternType and generatedUrls from workflow params if available
  const patternType = (() => {
    const val = findConfigValue(originalData?.params, 'patternType') || findConfigValue(originalData?.params, 'pattern');
    if (!val) return undefined;
    if (typeof val === 'object') return (val.type || val.name || val.action || '').toString().toLowerCase();
    return String(val).toLowerCase();
  })();

  const generatedUrls = (() => {
    try {
      const imageList = (originalData?.params && originalData.params.imageList) || [];
      if (Array.isArray(imageList) && imageList.length > 0) {
        return imageList.map((it: any) => it.ossUrl || it.url || it.preview || it);
      }
    } catch (e) {
      // ignore
    }
    return image ? [image.url] : [];
  })();

  if (!image) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-w-[80vw] generated-image-dialog max-h-[90vh] flex flex-col p-0 gap-0">
        <div className="p-6 pb-2">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="font-medium">AI生成图片</span>
              {actionLabel ? (
                <>
                  <Badge variant="secondary" className="text-xs">
                    <span className="text-xs text-purple-700 font-medium">{actionLabel}</span>
                  </Badge>
                  <span className="text-xs font-medium text-muted-foreground">鼠标滚轮可放大缩小</span>
                </>
              ) : null}
            </DialogTitle>
          </DialogHeader>
        </div>

        <div className="flex-1 overflow-y-auto p-6 pt-0 space-y-4">
          {/* 图片展示区域 - 横向布局 */}
          <div className="grid grid-cols-2 md:grid-cols-2 border rounded-lg overflow-hidden">
            {/* 生成的图片 */}
            <div className="border-r relative">
              {/* 左上角斜标 - 结果图（绿色） */}
              <CornerLabel variant="result" />
              <div className="relative w-full aspect-square overflow-hidden bg-muted/10 max-h-[400px]">
                <ZoomableImage src={image.url} alt={image.name} />
              </div>
            </div>

            {/* 原图 */}
            <div className="relative">
              {/* 左上角斜标 - 原图（灰色） */}
              <CornerLabel variant="original" />
              <div className="relative w-full aspect-square overflow-hidden bg-muted/10 max-h-[400px]">
                {originalData && originalData.imgUrl ? (
                  <ZoomableImage src={originalData.imgUrl} alt={`${image.name} - 原图`} />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-muted">
                    <ImageIcon className="w-16 h-16 text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">
                      {loadingOriginal ? '加载中...' : '暂无原图'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 图片信息和生成参数 - 左右布局 */}
          <div className={`grid grid-cols-1 ${hasParams ? 'md:grid-cols-2' : 'md:grid-cols-1'} border rounded-lg overflow-hidden`}>
            {/* 左侧：图片信息 */}
            <div className="p-4">
              <GeneratedImageInfo
                image={image}
                loadingOssInfo={loadingOssInfo}
                ossImageInfo={ossImageInfo}

                isEditingName={isEditingName}
                setIsEditingName={setIsEditingName}
                editedName={editedName}
                setEditedName={setEditedName}
                originalName={originalName}

                isEditingTags={isEditingTags}
                setIsEditingTags={setIsEditingTags}
                editedTags={editedTags}
                setEditedTags={setEditedTags}
                originalTags={originalTags}
                setOriginalTags={setOriginalTags}

                hasChanges={hasChanges}
                setHasChanges={setHasChanges}

                isSubmitting={isSubmitting}
                handleSaveChanges={handleSaveChanges}
                handleCancelEdit={handleCancelEdit}
              />
            </div>

            {/* 右侧：生成参数 */}
            {originalData && originalData.params && (
              <div className="p-4">
                <h3 className="text-base font-medium mb-3">生成参数</h3>
                <GeneratedImageParams params={originalData.params} />
              </div>
            )}
          </div>
        </div>

        {/* 操作按钮：删除按钮靠左，其他按钮靠右 */}
        <div className="p-4 border-t bg-background rounded-b-lg">
          <div className="flex items-center justify-between gap-2">
            {/* 左侧：删除按钮 */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                删除
              </Button>
            </div>

            {/* 右侧：其他操作按钮 */}
            <div className="flex items-center gap-2">
              {/* 编辑状态下显示取消修改和提交修改按钮 */}
              {(isEditingName || isEditingTags || hasChanges) && (
                <>
                  <Button
                    variant="outline"
                    onClick={handleCancelEdit}
                    disabled={isSubmitting}
                  >
                    取消修改
                  </Button>
                  <Button
                    onClick={handleSaveChanges}
                    disabled={!hasChanges || isSubmitting}
                  >
                    {isSubmitting ? '保存中...' : '提交修改'}
                  </Button>
                </>
              )}

              {isEmbedded && (
                <PushToPlatform
                  image={image}
                  originalData={originalData}
                />
              )}

              <Button
                variant="outline"
                onClick={() => setIsFullScreen(true)}
              >
                <Maximize2 className="w-4 h-4 mr-2" />
                全屏对比
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  onDownload(image.id);
                }}
              >
                <Download className="w-4 h-4 mr-2" />
                下载结果图
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>

      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-[28rem]">
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
          </DialogHeader>
          <div className="py-2 text-sm text-muted-foreground">确定要删除该图片吗？此操作不可撤销。</div>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>取消</Button>
            <Button
              className="ml-2"
              onClick={() => {
                if (image) {
                  onDelete(image.id);
                }
                setShowDeleteConfirm(false);
                onOpenChange(false);
              }}
            >
              确认
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <FullScreenViewer
        isOpen={isFullScreen}
        onClose={() => setIsFullScreen(false)}
        originalUrl={originalData?.imgUrl || ''}
        generatedUrl={image.url}
        generatedUrls={generatedUrls}
        isFullscreen={true}
        isSeamless={isSeamless}
        patternType={patternType}
      />
    </Dialog>
  );
}

export default GeneratedImagePreview;
