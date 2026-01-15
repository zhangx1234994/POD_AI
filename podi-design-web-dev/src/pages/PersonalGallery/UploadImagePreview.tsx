import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ZoomableImage } from './ZoomableImage';
import { Button } from '@/components/ui/button';
import { Download, Trash2 } from 'lucide-react';
import { http } from '@/utils/http';
import { GALLERY_TAG_DISPLAY_PRIORITY } from '@/constants/gallery';
import { GeneratedImageInfo } from './GeneratedImageInfo';
import { GalleryImage } from '@/types/galleryImage';

// 标签映射与优先级（文件级共享）
const TAG_NAME_CN_TO_EN: Record<string, string> = {
  '主色': 'main_color',
  '核心元素': 'core_elements',
  '风格关键词': 'style_keywords',
  '人物信息': 'person_info',
  '人物出处': 'person_source',
};

interface OssImageInfo {
  ImageHeight: number;
  ImageWidth: number;
  FileSize: number;
  Format: string;
  ColorModel: string;
}

export function UploadImagePreview({ 
  open, 
  onOpenChange, 
  image, 
  onDownload, 
  onDelete, 
  onUpdate 
}: { 
  open: boolean; 
  onOpenChange: (open: boolean) => void; 
  image: GalleryImage | null; 
  onDownload?: (imageId: string) => void;
  onDelete?: (imageId: string) => void;
  onUpdate?: (imageId: string, updates: { name?: string; tags?: string[] }) => void;
}) {
  // OSS图片信息状态
  const [loadingOssInfo, setLoadingOssInfo] = useState(false);
  const [ossImageInfo, setOssImageInfo] = useState<OssImageInfo | null>(null);
  
  // 编辑功能状态
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [originalName, setOriginalName] = useState('');
  const [isEditingTags, setIsEditingTags] = useState(false);
  const [editedTags, setEditedTags] = useState<Record<string, any>>({});
  const [originalTags, setOriginalTags] = useState<string>('{}');
  const [hasChanges, setHasChanges] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // 删除二次确认状态
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // 初始化编辑状态
  useEffect(() => {
    if (image) {
      setIsEditingTags(false);
      setIsEditingName(false);
      setHasChanges(false);
      setOriginalName(image.name);
      setEditedName(image.name);

      try {
        const originalTagData = image as any;
        let structuredTags: Record<string, any> = {};
        
        // 初始化所有标签类型，确保每个key都存在
        GALLERY_TAG_DISPLAY_PRIORITY.forEach(key => {
          structuredTags[key] = '';
        });

        if (originalTagData.originalTags) {
          setOriginalTags(originalTagData.originalTags);
          let parsedTags = JSON.parse(originalTagData.originalTags);

          if (parsedTags.tags && typeof parsedTags.tags === 'object') {
            parsedTags = parsedTags.tags;
          } else if (parsedTags.data && typeof parsedTags.data === 'object') {
            parsedTags = parsedTags.data;
          }
          
          // 合并解析的数据到初始化的标签对象中
          Object.entries(parsedTags).forEach(([key, value]) => {
            structuredTags[key] = value;
          });
        } else {
          const t = image.tags;
          
          if (Array.isArray(t)) {
            t.forEach((tag: string) => {
              const colonIndex = tag.indexOf('：');
              if (colonIndex > -1) {
                const tagName = tag.substring(0, colonIndex).trim();
                const tagValue = tag.substring(colonIndex + 1).trim();
                const englishKey = TAG_NAME_CN_TO_EN[tagName] || tagName;
                structuredTags[englishKey] = tagValue;
              }
            });
          } else if (typeof t === 'object') {
            // 合并直接对象格式的标签
            Object.entries(t).forEach(([key, value]) => {
              structuredTags[key] = value;
            });
          }

          setOriginalTags(JSON.stringify(structuredTags));
        }

        setEditedTags(structuredTags);
      } catch (error) {
        console.error('解析标签数据失败:', error);
        // 初始化默认标签
        const defaultTags = {
          main_color: '',
          core_elements: '',
          style_keywords: '',
          person_info: '',
          person_source: ''
        };
        setOriginalTags(JSON.stringify(defaultTags));
        setEditedTags(defaultTags);
      }
    }
  }, [image]);


  // 获取OSS图片信息
  useEffect(() => {
    const fetchOssInfo = async () => {
      if (!image?.url) return;
      
      // 简单判断是否为有效URL
      if (!image.url.startsWith('http')) return;

      setLoadingOssInfo(true);
      try {
        const infoUrl = `${image.url}?x-oss-process=image/info`;
        const response = await fetch(infoUrl);
        if (response.ok) {
          const data = await response.json();
          
          // 解析OSS返回的数据结构
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

  // 处理保存更新
  const handleSave = async () => {
    if (!image) return;
    
    setIsSubmitting(true);
    try {
      const params: any = { img_id: image.imgId };
      
      // 检查文件名是否有变化
      if (editedName !== originalName) {
        params.img_name = editedName;
      }
      
      // 检查标签是否有变化
      const originalTagsObj = JSON.parse(originalTags);
      const tagsChanged = JSON.stringify(editedTags) !== JSON.stringify(originalTagsObj);
      if (tagsChanged) {
        params.tags = editedTags;
      }
      
      // 直接调用API保存，与生成图片保持一致
      const response = await http.post('/img/update', params);
      
      if (response.data?.success) {
        // 保存成功，更新本地状态
        setOriginalName(editedName);
        setOriginalTags(JSON.stringify(editedTags));
        setHasChanges(false);
        setIsEditingName(false);
        setIsEditingTags(false);
        
        // 调用更新回调，通知父组件
        if (onUpdate) {
          // 转换标签格式：对象 -> 数组，格式为 "标签名：标签值"
          const tagNames: Record<string, string> = {
            main_color: '主色',
            core_elements: '核心元素',
            style_keywords: '风格关键词',
            person_info: '人物信息',
            person_source: '人物出处',
          };
          
          const tagArray = Object.entries(editedTags)
            .filter(([_, value]) => value && value !== '')
            .map(([key, value]) => {
              const displayKey = tagNames[key] || key.replace(/_/g, ' ');
              return `${displayKey}：${value}`;
            });
          
          onUpdate(image.id, {
            name: editedName,
            tags: tagArray
          });
        }
      } else {
        console.error('保存失败：', response.data?.message || '未知错误');
      }
    } catch (error) {
      console.error('保存失败:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 取消编辑
  const handleCancel = () => {
    setEditedName(originalName);
    setEditedTags(JSON.parse(originalTags));
    setHasChanges(false);
    setIsEditingName(false);
    setIsEditingTags(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-auto max-w-[30vw] max-h-[90vh] flex flex-col p-0 gap-0">
        <div className="p-6 pb-2">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="font-medium">上传的图片</span>
            </DialogTitle>
          </DialogHeader>
        </div>
        {image && (
          <>
            <div className="flex-1 overflow-y-auto p-6 pt-0 space-y-4">
              {/* 图片预览 */}
              <div className="relative w-full aspect-square rounded-lg overflow-hidden border-2 bg-muted/10">
                <ZoomableImage src={image.url} alt={image.name} />
              </div>

              {/* 图片信息: use generated/shared component */}
              <div className="grid grid-cols-1">
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
                  handleSaveChanges={handleSave}
                  handleCancelEdit={handleCancel}
                />
              </div>
            </div>

            {/* 操作按钮：左侧仅删除，右侧为下载 + 编辑相关操作 */}
            <div className="p-4 border-t bg-background rounded-b-lg">
              <div className="flex items-center justify-between gap-2">
                <div className="flex gap-2">
                  {onDelete && (
                    <Button
                      variant="outline"
                      className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                      onClick={() => setShowDeleteConfirm(true)}
                      disabled={isSubmitting}
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      删除
                    </Button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {/* 编辑状态下显示取消修改和提交修改按钮 */}
                  {(isEditingName || isEditingTags || hasChanges) && (
                    <>
                      <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={isSubmitting}
                      >
                        取消修改
                      </Button>
                      <Button
                        onClick={handleSave}
                        disabled={!hasChanges || isSubmitting}
                      >
                        {isSubmitting ? '保存中...' : '提交修改'}
                      </Button>
                    </>
                  )}

                  {onDownload && (
                    <Button
                      variant="outline"
                      onClick={() => {
                        onDownload(image.id);
                      }}
                      disabled={isSubmitting}
                    >
                      <Download className="w-4 h-4 mr-2" />
                      下载
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
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
                if (image && onDelete) onDelete(image.id);
                setShowDeleteConfirm(false);
                onOpenChange(false);
              }}
            >
              确认
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
};

export default UploadImagePreview;
