import { useState, useEffect, useRef, useCallback, ChangeEvent, DragEvent } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from './ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Progress } from './ui/progress';
import { ImageWithFallback } from './ImageWithFallback';
import { ImagePreview } from './ImagePreview';
import { IMAGE_FILE_EXTENSIONS } from '@/constants/upload';
import { MAX_UPLOAD_IMAGE_COUNT } from '@/constants';
import {
  Upload,
  Search,
  Check,
  X,
  AlertCircle,
  FolderOpen,
  Loader2,
  Eye,
} from 'lucide-react';
import { http, getUserId } from '@/utils/http';
import { usePlatform } from '@/hooks/usePlatform';
import { getSourceOptions } from '@/utils/sourceOptions';
import { extractPreviewImageUrl, generateImageFilename } from '../utils/imageUtils';
import { formatDateTime } from '@/utils/timeUtils';
import { uploadFilesToOss } from '@/utils/ossUploader';
import { fetchOssImageInfo, formatFileSize, validateImage } from '../utils/imageUtils';

import type { ImageItem } from '@/types/upload';

interface PersonalGalleryImage {
  id: string;
  name: string;
  url: string;
  type: 'uploaded' | 'generated';
  size: string;
  dimensions: string;
  uploadDate: string;
  tags: string[];
  aiTool?: string;
}

interface EnhancedImageUploadProps {
  title?: string;
  description?: string;
  supportText?: string;
  maxImages?: number;
  onImagesChange: (images: ImageItem[]) => void;
  allowMultiple?: boolean;
  numbered?: boolean;
  zebraConnected?: boolean;
  hummingbirdConnected?: boolean;
  images?: ImageItem[]; // 外部传入的图片列表
}

export function EnhancedImageUpload({
  title: _title = '选择图片',
  description,
  maxImages = MAX_UPLOAD_IMAGE_COUNT,
  supportText = '支持 PNG, JPG, JPEG, BMP',
  onImagesChange,
  allowMultiple = true,
  numbered = false,
  zebraConnected: _zebraConnected = true,
  hummingbirdConnected: _hummingbirdConnected = true,
  images: externalImages,
}: EnhancedImageUploadProps) {
  const [images, setImages] = useState<ImageItem[]>(externalImages || []);
  const [showGalleryDialog, setShowGalleryDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const { isEmbedded } = usePlatform();

  // tempSelectedImages 仅用于个人图库弹窗的选择状态
  const [tempSelectedImages, setTempSelectedImages] = useState<ImageItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  
  // 筛选条件状态
  const [filterSourceType, setFilterSourceType] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('podi-gallery-filter-source') || 'all';
    }
    return 'all';
  });
  
  const [filterType, setFilterType] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('podi-gallery-filter-type') || 'all';
    }
    return 'all';
  });

  // 持久化筛选条件到 localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('podi-gallery-filter-source', filterSourceType);
    }
  }, [filterSourceType]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('podi-gallery-filter-type', filterType);
    }
  }, [filterType]);

  // 上传进度相关状态
  const [uploadProgress, setUploadProgress] = useState<{
    isUploading: boolean;
    currentFileIndex: number;
    totalFiles: number;
    currentFilename: string;
    percent: number;
  }>({
    isUploading: false,
    currentFileIndex: 0,
    totalFiles: 0,
    currentFilename: '',
    percent: 0,
  });

  // 个人图库相关状态
  const [personalGalleryImages, setPersonalGalleryImages] = useState<PersonalGalleryImage[]>([]);
  const [personalGalleryPage, setPersonalGalleryPage] = useState(0);
  const [personalGallerySize] = useState(20);
  const [personalGalleryTotal, setPersonalGalleryTotal] = useState(0);
  const [personalGalleryLoading, setPersonalGalleryLoading] = useState(false);
  const [personalGalleryInitialized, setPersonalGalleryInitialized] = useState(false);

  // 滚动加载相关状态和引用
  const personalGalleryScrollRef = useRef<HTMLDivElement>(null);
  const [isScrollLoading, setIsScrollLoading] = useState(false);

  // 图片预览状态
  const [previewImages, setPreviewImages] = useState<string[]>([]);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [showPreview, setShowPreview] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const [confirmRemoveOpen, setConfirmRemoveOpen] = useState(false);
  const [imageToRemove, setImageToRemove] = useState<ImageItem | null>(null);

  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 当外部传入的图片列表变化时，同步更新内部状态
  useEffect(() => {
    if (externalImages !== undefined) {
      setImages([...externalImages]);
    }
  }, [externalImages]);

  // 统一转换为 GalleryImage
  async function mapToGalleryImage(t: any): Promise<PersonalGalleryImage | null> {
    const src = extractPreviewImageUrl(t) || t.ossUrl || t.oss_url || '';
    if (!src) return null;
    const uploadDate = t.createTime || t.create_time || t.uploadTime || t.upload_time || '';
    const name = (t.img_name ||
      t.imgName ||
      t.ossKey ||
      t.oss_key ||
      generateImageFilename('图片.png', undefined, true)) as string;
    const tt = String(t.type || '').toUpperCase();
    const mappedType: 'uploaded' | 'generated' = tt === 'UPLOADED' ? 'uploaded' : 'generated';
    
    // 从API响应中提取size和dimensions字段
    const sizeStr = String(t.size || t.fileSize || t.file_size || '');
    const dimensions = String(t.dimensions || t.size_desc || '');
    
    return {
      id: String(t.img_id || t.id),
      name,
      url: src,
      type: mappedType,
      size: sizeStr,
      dimensions,
      uploadDate: formatDateTime(uploadDate || Date.now()),
      tags: mappedType === 'uploaded' ? ['上传'] : ['AI生成'],
    } as PersonalGalleryImage;
  }

  // 获取个人图库数据
  const fetchPersonalGallery = useCallback(
    async (pageOverride?: number, reset?: boolean) => {
      try {
        const userId = getUserId();
        const pageToFetch = typeof pageOverride === 'number' ? pageOverride : personalGalleryPage;
        setPersonalGalleryLoading(true);
        
        let url = `/gallery/all?user_id=${userId}&page=${pageToFetch}&size=${personalGallerySize}`;
        
        if (searchQuery) {
          url += `&name=${encodeURIComponent(searchQuery)}`;
        }
        if (filterSourceType && filterSourceType !== 'all') {
          url += `&source_type=${filterSourceType}`;
        }
        if (filterType && filterType !== 'all') {
          url += `&type=${filterType}`;
        }

        const resp = await http.get(url);
        const payload: any = resp.data || {};
        const items = Array.isArray(payload) ? payload : payload.items || [];
        const totalCount = payload.total ?? items.length;
        setPersonalGalleryTotal(Number(totalCount) || 0);

        const galleryImages: PersonalGalleryImage[] = (
          await Promise.all(items.map(mapToGalleryImage))
        ).filter(Boolean) as PersonalGalleryImage[];
        setPersonalGalleryImages((prev) => {
          const merged = reset ? galleryImages : [...prev, ...galleryImages];
          const seen = new Set<string>();
          return merged.filter((img) => {
            const key = `${img.type}-${img.id}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
        });
        setPersonalGalleryInitialized(true);
      } catch (e) {
        console.error('加载个人图库失败', e);
      } finally {
        setPersonalGalleryLoading(false);
        if (pageOverride !== undefined && pageOverride > 0) {
          setIsScrollLoading(false);
        }
      }
    },
    [personalGalleryPage, personalGallerySize, searchQuery, filterSourceType, filterType]
  );

  // 监听筛选条件变化
  useEffect(() => {
    if (showGalleryDialog) {
      const timer = setTimeout(() => {
        fetchPersonalGallery(0, true);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [searchQuery, filterSourceType, filterType]);

  // 打开图库弹窗时初始化数据
  useEffect(() => {
    if (showGalleryDialog && !personalGalleryInitialized) {
      fetchPersonalGallery(0, true);
    }
  }, [showGalleryDialog, personalGalleryInitialized]); 
  
  // 将PersonalGalleryImage转换为ImageItem，并从OSS获取图片详细信息
  const convertToUploadedImage = async (image: PersonalGalleryImage): Promise<ImageItem> => {
    let width: number | undefined;
    let height: number | undefined;
    let size: string = image.size || '未知大小';
    
    // 首先尝试从dimensions字段解析
    if (image.dimensions) {
      // 匹配常见的尺寸格式：1920x1080, 1920 × 1080, 1920px x 1080px等
      const dimensionMatch = image.dimensions.match(/(\d+)\s*[x×]\s*(\d+)/);
      if (dimensionMatch) {
        width = parseInt(dimensionMatch[1], 10);
        height = parseInt(dimensionMatch[2], 10);
      }
    }
    
    // 如果从dimensions字段没有获取到有效信息，或者size为空，则从OSS获取
    if ((!width || !height || size === '未知大小') && image.url) {
      try {
        const ossInfo = await fetchOssImageInfo(image.url);
        if (ossInfo) {
          width = ossInfo.width;
          height = ossInfo.height;
          size = formatFileSize(Number(ossInfo.fileSize) || 0);
        }
      } catch (error) {
        console.error('Error fetching image info from OSS:', error);
      }
    }
    
    return {
      id: `personal_${image.id}`,
      preview: image.url,
      name: image.name,
      size,
      source: 'personal',
      ossUrl: image.url,
      width,
      height,
      isOversized: false, // 个人图库图片默认不超限
    };
  };

  // 获取过滤后的图片列表（用于渲染，使用同步转换）
  const getFilteredImages = () => {
    // 同步转换，用于渲染，后续会在确认选择时更新详细信息
    const gallery: ImageItem[] = personalGalleryImages.map((image) => {
      // 解析dimensions字符串为width和height
      let width: number | undefined;
      let height: number | undefined;
      
      if (image.dimensions) {
        // 匹配常见的尺寸格式：1920x1080, 1920 × 1080, 1920px x 1080px等
        const dimensionMatch = image.dimensions.match(/(\d+)\s*[x×]\s*(\d+)/);
        if (dimensionMatch) {
          width = parseInt(dimensionMatch[1], 10);
          height = parseInt(dimensionMatch[2], 10);
        }
      }
      
      return {
        id: `personal_${image.id}`,
        preview: image.url,
        name: image.name,
        size: image.size || '未知大小',
        source: 'personal',
        ossUrl: image.url,
        width,
        height,
        isOversized: false, // 个人图库图片默认不超限
      };
    });
    
    if (!searchQuery) return gallery;
    // return gallery.filter((img) => (img.name || '').toLowerCase().includes(searchQuery.toLowerCase()));
    // 服务端已处理筛选，此处直接返回
    return gallery;
  };

  // 处理拖拽上传的辅助函数
  const processFiles = async (files: File[]) => {
    if (files.length === 0) return;

    setError(null);
    const filesToProcess = allowMultiple
      ? Array.from(files).slice(0, maxImages - images.length)
      : [files[0]];

    // 验证所有文件
    const validFiles: File[] = [];
    const oversizedFiles: { file: File; validation: any }[] = [];

    for (const file of filesToProcess) {
      if (!file || !file.type.startsWith('image/')) {
        setError(`文件 ${file?.name || ''} 不是有效的图片格式`);
        continue;
      }

      try {
        const validation = await validateImage(file);
        if (!validation.isValid) {
          if (validation.isOversized) {
            oversizedFiles.push({ file, validation });
          } else {
            setError(validation.error || `文件 ${file.name} 验证失败`);
          }
          continue;
        }
        validFiles.push(file);
      } catch (error) {
        console.error('图片验证失败:', error);
        setError(`文件 ${file.name} 验证过程中出错`);
      }
    }

    // 处理正常大小的文件
    const newImages: ImageItem[] = [];
    if (validFiles.length > 0) {
      try {
        setUploadProgress({
          isUploading: true,
          currentFileIndex: 0,
          totalFiles: validFiles.length,
          currentFilename: validFiles[0].name,
          percent: 0,
        });

        const uploadResults = await uploadFilesToOss(
          validFiles,
          getUserId(),
          (completed: number, total: number, currentFile?: string) => {
            const percent = Math.round((completed / total) * 100);
            setUploadProgress((prev) => ({
              ...prev,
              currentFileIndex: completed,
              currentFilename: currentFile || '',
              percent,
            }));
          }
        );

        for (let i = 0; i < uploadResults.length; i++) {
          const result = uploadResults[i];
          const file = validFiles[i];
          const validation = await validateImage(file);

          const reader = new FileReader();
          const imagePromise = new Promise<void>((resolve) => {
            reader.onload = (event: ProgressEvent<FileReader>) => {
              const image: ImageItem = {
                id: `upload_${Date.now()}_${i}`,
                file,
                preview: event.target?.result as string,
                name: result.name,
                size: (result.size / 1024 / 1024).toFixed(2) + ' MB',
                source: 'upload',
                width: validation.width,
                height: validation.height,
                ossUrl: result.url,
                isOversized: false,
              };
              newImages.push(image);
              resolve();
            };
          });

          reader.readAsDataURL(file);
          await imagePromise;
        }

        // 批量记录图片信息到数据库
        if (uploadResults.length > 0) {
          const imagesToRecord = uploadResults.map((result) => ({
            ossUrl: result.url,
            imgName: result.name,
            type: 'UPLOADED',
            sourceType: 'UPLOAD',
          }));

          try {
            await http.post('/img/record', {
              userId: getUserId(),
              images: imagesToRecord,
            });
            console.log('图片信息已成功记录到数据库');
          } catch (error) {
            console.error('记录图片信息失败:', error);
            // 记录失败不影响用户体验，仅在控制台输出错误
          }
        }
      } catch (error) {
        console.error('上传到OSS失败:', error);
        setError(`上传失败: ${error instanceof Error ? error.message : '未知错误'}`);
      } finally {
        setUploadProgress((prev) => ({
          ...prev,
          isUploading: false,
        }));
      }
    }

    // 处理超大文件
    const oversizedImages: ImageItem[] = [];
    if (oversizedFiles.length > 0) {
      for (let i = 0; i < oversizedFiles.length; i++) {
        const { file, validation } = oversizedFiles[i];

        const reader = new FileReader();
        const imagePromise = new Promise<void>((resolve) => {
          reader.onload = (event: ProgressEvent<FileReader>) => {
            const image: ImageItem = {
              id: `oversized_${Date.now()}_${i}`,
              file,
              preview: event.target?.result as string,
              name: file.name,
              size: validation.sizeText || (file.size / 1024 / 1024).toFixed(2) + ' MB',
              source: 'upload',
              width: validation.width,
              height: validation.height,
              isOversized: true,
            };
            oversizedImages.push(image);
            resolve();
          };
        });

        reader.readAsDataURL(file);
        await imagePromise;
      }
    }

    // 更新图片列表
    const allImages = [...newImages, ...oversizedImages];
    if (allImages.length > 0) {
      const updatedImages = allowMultiple
        ? [...images, ...allImages] // 这里是基于当前的 images 状态
        : allImages;

      setImages(updatedImages);
      onImagesChange(updatedImages);
    }
  };

  // 文件选择处理
  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    await processFiles(Array.from(files) as File[]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 拖拽事件处理
  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files).filter((file) =>
      file.type.startsWith('image/')
    ) as File[];

    if (files.length > 0) {
      await processFiles(files);
    }
  };

  // 个人图库图片选择处理
  const toggleGalleryImageSelection = (image: ImageItem) => {
    // 检查是否已经在已确认的列表中（避免重复选择）
    const isAlreadyAdded = images.some((img) => img.id === image.id);
    if (isAlreadyAdded) return;

    setTempSelectedImages((prev) => {
      const exists = prev.find((img) => img.id === image.id);

      if (exists) {
        return prev.filter((img) => img.id !== image.id);
      } else {
        if (allowMultiple) {
          // 注意：这里需要考虑当前已选的图片数量
          if (images.length + prev.length >= maxImages) {
            return prev;
          }
          return [...prev, image];
        } else {
          return [image];
        }
      }
    });
  };

  const isGalleryImageSelected = (imageId: string) => {
    return tempSelectedImages.some((img) => img.id === imageId);
  };

  // 确认选择个人图库图片
  const handleConfirmGallerySelection = async () => {
    // 过滤掉已经在 images 中的图片，避免重复 key
    const uniqueSelectedImages = tempSelectedImages.filter(
      (newImg) => !images.some((existingImg) => existingImg.id === newImg.id)
    );
    
    // 找到对应的PersonalGalleryImage对象
    const personalImages = uniqueSelectedImages.map(selectedImg => {
      const imageId = selectedImg.id.replace('personal_', '');
      return personalGalleryImages.find(img => img.id === imageId) || null;
    }).filter(Boolean) as PersonalGalleryImage[];
    
    // 异步获取每个图片的详细信息
    const updatedImages: ImageItem[] = await Promise.all(
      personalImages.map(convertToUploadedImage)
    );
    
    let finalImages: ImageItem[];
    
    if (allowMultiple) {
      finalImages = [...images, ...updatedImages];
    } else {
      finalImages = updatedImages;
    }

    setImages(finalImages);
    onImagesChange(finalImages);
    setShowGalleryDialog(false);
    setTempSelectedImages([]);
    setSearchQuery('');
  };

  const handleCancelGallerySelection = () => {
    setShowGalleryDialog(false);
    setTempSelectedImages([]);
    setSearchQuery('');
  };

  const removeImage = (id: string) => {
    const updatedImages = images.filter((img) => img.id !== id);
    setImages(updatedImages);
    onImagesChange(updatedImages);
  };

  const clearAll = () => {
    // open confirmation dialog
    setConfirmClearOpen(true);
  };

  const doClear = () => {
    setImages([]);
    onImagesChange([]);
    setConfirmClearOpen(false);
  };

  const getSourceLabel = (source?: string) => {
    switch (source) {
      case 'upload':
        return '本地上传';
      case 'personal':
        return '个人图库';
      case 'zebra':
        return '斑马';
      case 'hummingbird':
        return '蜂鸟';
      default:
        return '未知';
    }
  };

  // 处理图片预览
  const handleImagePreview = (image: ImageItem) => {
    const src = image.preview || image.ossUrl || image.url;
    if (!src) return;
    setPreviewImages([src]);
    setPreviewIndex(0);
    setShowPreview(true);
  };

  // 关闭图片预览
  const closePreview = () => {
    setShowPreview(false);
    setPreviewImages([]);
    setPreviewIndex(0);
  };

  // 格式化文件名以便显示：保留扩展名，超长时在中间用省略号显示前后两端
  // 参数 `displayMax` 是目标显示的最大字符数（不包括 title/tooltip），默认 50
  const formatFilenameForDisplay = (filename: string, displayMax = 50) => {
    if (!filename) return '';
    // 如果文件名总长度较短，直接返回
    if (filename.length <= displayMax) return filename;

    const lastDot = filename.lastIndexOf('.');
    let base = filename;
    let ext = '';
    if (lastDot > 0) {
      base = filename.slice(0, lastDot);
      ext = filename.slice(lastDot); // 包含点
    }

    // 如果 even base + ext is short enough
    if (base.length + ext.length <= displayMax) return base + ext;

    // Reserve space for ellipsis (3 chars) and extension
    const extLen = ext.length;
    const avail = Math.max(displayMax - extLen - 3, 0);

    if (avail <= 0) {
      // Not enough room for base; just show truncated start + ... + ext
      return base.slice(0, Math.max(0, displayMax - 3)) + '...' + ext;
    }

    // Split available chars between head and tail (prefer showing the head if odd)
    const headLen = Math.ceil(avail / 2);
    const tailLen = Math.floor(avail / 2);

    const head = base.slice(0, headLen);
    const tail = tailLen > 0 ? base.slice(-tailLen) : '';

    return `${head}...${tail}${ext}`;
  };

  // 渲染图库网格
  const renderImageGrid = () => {
    const filteredImages = getFilteredImages();
    const isLoading = personalGalleryLoading;
    const scrollLoading = isScrollLoading;

    if (filteredImages.length === 0 && !isLoading) {
      return (
        <div className="text-center py-12">
          <FolderOpen className="w-16 h-16 mx-auto text-muted-foreground opacity-20 mb-3" />
          <p className="text-sm text-muted-foreground">
            {searchQuery ? '未找到匹配的图片' : '暂无图片'}
          </p>
        </div>
      );
    }

    const reachedMax = images.length + tempSelectedImages.length >= maxImages;

    return (
      <div className="flex flex-col h-full">
        <div
          ref={personalGalleryScrollRef}
          className="grid grid-cols-3 gap-3 overflow-y-auto p-1"
          style={{ height: '100%', maxHeight: '400px' }}
        >
          {filteredImages.map((image) => {
            const isSelected = isGalleryImageSelected(image.id);
            const isAlreadyAdded = images.some((img) => img.id === image.id);
            const disabledByLimit = !isSelected && !isAlreadyAdded && reachedMax;

            return (
              <div
                key={image.id}
                className={`relative aspect-square rounded-lg overflow-hidden transition-all border-2 group ${
                  isSelected
                    ? 'border-primary shadow-lg scale-95 cursor-pointer'
                    : isAlreadyAdded
                    ? 'border-muted opacity-60 cursor-not-allowed'
                    : disabledByLimit
                    ? 'border-transparent bg-gray-100 opacity-60 cursor-not-allowed'
                    : 'border-transparent hover:border-muted-foreground/30 cursor-pointer'
                }`}
                onClick={() => !isAlreadyAdded && !disabledByLimit && toggleGalleryImageSelection(image)}
              >
                <ImageWithFallback
                  src={image.preview}
                  alt={image.name}
                  className="w-full h-full object-cover"
                />
                {(isSelected || isAlreadyAdded) && (
                  <div
                    className={`absolute inset-0 flex items-center justify-center pointer-events-none ${
                      isAlreadyAdded ? 'bg-black/40' : 'bg-primary/20'
                    }`}
                  >
                    {isSelected && (
                      <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                        <Check className="w-5 h-5 text-primary-foreground" />
                      </div>
                    )}
                    {isAlreadyAdded && (
                      <div className="px-2 py-1 bg-black/60 rounded text-xs text-white">已添加</div>
                    )}
                  </div>
                )}
                {/* 图片预览悬停按钮 - 仅在未添加且未被禁用时显示选择按钮 */}
                <div
                  className={`absolute inset-0 transition-colors flex items-center justify-center opacity-0 pointer-events-none ${
                    !isAlreadyAdded && !disabledByLimit
                      ? 'bg-black/0 group-hover:bg-black/40 group-hover:opacity-100 group-hover:pointer-events-auto'
                      : ''
                  }`}
                >
                  {!isAlreadyAdded && !disabledByLimit && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleGalleryImageSelection(image);
                      }}
                      className="text-white hover:bg-white/20 p-1 rounded-full transition-colors"
                    >
                      <Check className="h-5 w-5" />
                    </button>
                  )}
                </div>
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                  <p className="text-xs text-white truncate">{image.name}</p>
                </div>
              </div>
            );
          })}

          {isLoading && (
            <div className="col-span-3 flex justify-center py-4">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>

        {scrollLoading && (
          <div className="p-2 border-t flex justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mr-2" />
            <span className="text-sm text-muted-foreground">正在加载...</span>
          </div>
        )}
      </div>
    );
  };

  // 滚动事件处理函数
  const handleScroll = useCallback(() => {
    if (!personalGalleryScrollRef.current || isScrollLoading || personalGalleryLoading) {
      return;
    }

    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    scrollTimeoutRef.current = setTimeout(() => {
      const { scrollTop, scrollHeight, clientHeight } = personalGalleryScrollRef.current!;

      if (scrollHeight - scrollTop - clientHeight < 200) {
        if (personalGalleryImages.length < personalGalleryTotal) {
          setIsScrollLoading(true);
          const nextPage = personalGalleryPage + 1;
          setPersonalGalleryPage(nextPage);
          fetchPersonalGallery(nextPage);
        }
      }
    }, 200);
  }, [
    isScrollLoading,
    personalGalleryLoading,
    personalGalleryPage,
    fetchPersonalGallery,
    personalGalleryImages.length,
    personalGalleryTotal,
  ]);

  useEffect(() => {
    const scrollElement = personalGalleryScrollRef.current;
    if (!scrollElement) return;

    scrollElement.addEventListener('scroll', handleScroll);
    return () => {
      scrollElement.removeEventListener('scroll', handleScroll);
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, [handleScroll, showGalleryDialog]); // 依赖 showGalleryDialog 确保弹窗打开后绑定事件

  return (
    <div className="space-y-3">
      <div
        className="border-2 border-dashed rounded-lg p-3 bg-background"
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {images.length > 0 && (
              <Badge variant="outline" className="text-xs">
                {images.length}/{maxImages}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs border-dashed"
              onClick={() => fileInputRef.current?.click()}
              disabled={
                uploadProgress.isUploading ||
                (!allowMultiple && images.length >= 1) ||
                (allowMultiple && images.length >= maxImages)
              }
            >
              {uploadProgress.isUploading ? (
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
              ) : (
                <Upload className="w-3 h-3 mr-1" />
              )}
              上传
            </Button>

            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs border-dashed"
              onClick={() => setShowGalleryDialog(true)}
              disabled={
                (!allowMultiple && images.length >= 1) ||
                (allowMultiple && images.length >= maxImages)
              }
            >
              <FolderOpen className="w-3 h-3 mr-1" />
              图库
            </Button>

            {images.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={clearAll}
                className="h-7 px-2 text-xs text-muted-foreground border-dashed hover:text-destructive"
              >
                清空
              </Button>
            )}
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <Alert variant="destructive" className="mb-3 py-2 flex items-start gap-2 w-full">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <AlertDescription className="text-xs whitespace-normal break-words word-break-all flex-1 min-w-0 max-w-full">{error}</AlertDescription>
          </Alert>
        )}

        {/* 拖拽覆盖层 */}
        {isDragging && (
          <div className="absolute inset-0 z-50 bg-primary/10 border-2 border-primary border-dashed rounded-lg flex items-center justify-center backdrop-blur-sm pointer-events-none">
            <div className="text-center">
              <Upload className="w-10 h-10 mx-auto text-primary mb-2" />
              <p className="text-primary font-medium">释放以上传图片</p>
            </div>
          </div>
        )}

        {/* 已选图片列表 */}
        {images.length > 0 && (
          <div className="space-y-2 mb-3">
            {images.map((image, index) => (
              <div
                key={image.id}
                className={`flex items-center gap-2 p-2 rounded text-xs transition-all duration-200 ${
                  image.isOversized
                    ? 'bg-red-50 border-2 border-red-500 shadow-[0_0_10px_rgba(239,68,68,0.2)] hover:bg-red-100 hover:shadow-lg'
                    : 'bg-muted/30 border border-transparent hover:bg-muted/40 hover:shadow-sm'
                }`}
              >
                {numbered && (
                  <div className="flex-shrink-0 w-5 h-5 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-xs">
                    {index + 1}
                  </div>
                )}

                <div className="w-10 h-10 bg-muted rounded overflow-hidden flex-shrink-0 relative group">
                  <ImageWithFallback
                    src={image.preview}
                    alt={image.name}
                    className="w-full h-full object-cover"
                  />
                  {/* 图片预览悬停按钮 */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleImagePreview(image);
                      }}
                      className="text-white hover:bg-white/20 p-1 rounded-full transition-colors"
                    >
                      <Eye className="h-5 w-5" />
                    </button>
                  </div>
                  {/* 如果是当前正在上传的图片（根据某种逻辑判断，这里简化处理），可以覆盖Loading */}
                </div>

                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium">{image.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Badge variant="outline" className="text-xs px-1 py-0">
                      {getSourceLabel(image?.source)}
                    </Badge>
                    <span
                      className={`${
                        image.isOversized ? 'text-red-600 font-medium' : 'text-muted-foreground'
                      }`}
                    >
                      {image.size}
                    </span>
                    {image.isOversized && (
                      <Badge
                        variant="destructive"
                        className="text-xs px-2 py-0.5 animate-pulse font-bold"
                      >
                        该图片超限大小限制，最大允许5M，请删除
                      </Badge>
                    )}
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setImageToRemove(image);
                    setConfirmRemoveOpen(true);
                  }}
                  className={`p-0 bg-red-100 hover:bg-red-200 text-red-600 transition-all ${
                    image.isOversized ? 'h-8 w-8 shadow-sm' : 'h-6 w-6'
                  }`}
                >
                  <X className={`${image.isOversized ? 'w-5 h-5 stroke-[3]' : 'w-3 h-3'}`} />
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* 空状态提示 */}
        {images.length === 0 && (
          <div
            className="flex flex-col items-center justify-center py-8 text-muted-foreground cursor-pointer hover:bg-muted/50 transition-colors rounded-md"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="p-3 bg-muted rounded-full mb-3">
              <Upload className="w-6 h-6 opacity-50" />
            </div>
            <p className="text-xs font-medium">点击或拖拽图片到此处</p>
            <p className="text-[10px] opacity-70 mt-1">{supportText}</p>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={IMAGE_FILE_EXTENSIONS.join(',')}
          multiple={allowMultiple}
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {description && !images.length && (
        <p className="text-xs text-muted-foreground px-1">{description}</p>
      )}

      {/* 上传进度条 - 内嵌式展示 (如果需要) 或者保持弹出框 */}
      {/* 既然要求结果展示在Card中，这里我们可以做一个简单的全局进度遮罩，或者更优雅地在Card上方显示进度 */}
      <Dialog open={uploadProgress.isUploading} onOpenChange={() => {}}>
        <DialogContent className="w-full max-w-md min-w-0">
          <DialogHeader className="w-full min-w-0">
            <DialogTitle className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              图片上传中
            </DialogTitle>
            <DialogDescription>
              正在上传 {uploadProgress.currentFileIndex} / {uploadProgress.totalFiles} 张图片
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 w-full min-w-0">
            <div className="space-y-2 w-full min-w-0">
              <p
                className="text-sm text-gray-600 truncate w-full"
                aria-label={uploadProgress.currentFilename}
                title={uploadProgress.currentFilename}
              >
                {formatFilenameForDisplay(uploadProgress.currentFilename, 50)}
              </p>
              <Progress value={uploadProgress.percent} className="h-2" />
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* 清空确认对话框 */}
      <Dialog open={confirmClearOpen} onOpenChange={setConfirmClearOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader className="w-full min-w-0">
            <DialogTitle>确认清空已选图片</DialogTitle>
            <DialogDescription className="mt-4 whitespace-normal break-words">此操作会清空当前已选择的所有图片，且不可恢复，是否继续？</DialogDescription>
          </DialogHeader>
          <DialogFooter className="w-full min-w-0">
            <div className="flex justify-end gap-2 w-full">
              <Button variant="outline" onClick={() => setConfirmClearOpen(false)}>
                取消
              </Button>
              <Button className="ml-2" onClick={doClear}>
                清空
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 单张图片删除确认对话框 */}
      <Dialog open={confirmRemoveOpen} onOpenChange={(open) => {
        setConfirmRemoveOpen(open);
        if (!open) setImageToRemove(null);
      }}>
        <DialogContent className="max-w-sm">
          <DialogHeader className="w-full min-w-0">
            <DialogTitle>{imageToRemove?.isOversized ? '删除超限图片' : '确认删除图片'}</DialogTitle>
              <DialogDescription className="mt-4 whitespace-normal break-words word-break-all">
                该图片将从已选列表中移除，是否继续？
              </DialogDescription>
          </DialogHeader>
          <DialogFooter className="w-full min-w-0">
            <div className="flex justify-end gap-2 w-full">
              <Button variant="outline" onClick={() => { setConfirmRemoveOpen(false); setImageToRemove(null); }}>
                取消
              </Button>
              <Button className="ml-2" onClick={() => {
                if (imageToRemove) {
                  removeImage(imageToRemove.id);
                }
                setConfirmRemoveOpen(false);
                setImageToRemove(null);
              }}>
                删除
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 个人图库选择对话框 */}
      <Dialog open={showGalleryDialog} onOpenChange={handleCancelGallerySelection}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>选择个人图库图片</DialogTitle>
            <DialogDescription>从已生成的图片或历史上传中选择</DialogDescription>
          </DialogHeader>

          <div className="flex-1 flex flex-col min-h-0 overflow-hidden space-y-3">
            <div className="flex items-center gap-4 flex-shrink-0">
              <div className="relative w-[70%]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  ref={searchInputRef}
                  placeholder="搜索图片..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-10 w-full"
                />
                {searchQuery && (
                  <button
                    type="button"
                    aria-label="清除搜索"
                    onClick={() => {
                      setSearchQuery('');
                      try {
                        searchInputRef.current?.focus();
                      } catch (e) {
                        // ignore
                      }
                    }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground p-1 rounded hover:bg-muted/10"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <div className="flex gap-2 flex-1">
                <Select value={filterSourceType} onValueChange={setFilterSourceType}>
                  <SelectTrigger className="w-full h-9">
                    <SelectValue placeholder="来源" />
                  </SelectTrigger>
                  <SelectContent>
                    {getSourceOptions(isEmbedded).map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-full h-9">
                    <SelectValue placeholder="类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部类型</SelectItem>
                    <SelectItem value="hires">无损放大</SelectItem>
                    <SelectItem value="pattern-extract">印花提取</SelectItem>
                    <SelectItem value="seamless">连续图案</SelectItem>
                    <SelectItem value="fission">图片裂变</SelectItem>
                    <SelectItem value="extend">智能扩展</SelectItem>
                    <SelectItem value="edit">AI图片编辑器</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex-1 min-h-0 overflow-hidden border rounded-md">
              {renderImageGrid()}
            </div>
          </div>

          <DialogFooter className="mt-4">
            <div className="flex items-center justify-between w-full">
              <div className="text-sm text-muted-foreground">
                已选择 {images.length + tempSelectedImages.length} 张图片
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleCancelGallerySelection}>
                  取消
                </Button>
                <Button
                  onClick={handleConfirmGallerySelection}
                  disabled={tempSelectedImages.length === 0}
                >
                  确认选择
                </Button>
              </div>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 图片预览组件 */}
      <ImagePreview
        open={showPreview}
        onClose={closePreview}
        images={previewImages}
        initialIndex={previewIndex}
        title="图片预览"
      />
    </div>
  );
}
