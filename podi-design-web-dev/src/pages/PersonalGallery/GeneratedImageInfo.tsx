import React from 'react';
import { Sparkles, Tag as TagIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { formatFileSize } from '@/utils/imageUtils';
import { GALLERY_TAG_KEY_TO_LABEL, GALLERY_TAG_DISPLAY_PRIORITY } from '@/constants/gallery';
import { GalleryImage } from '@/types/galleryImage';

interface OssImageInfo {
  ImageHeight: number;
  ImageWidth: number;
  FileSize: number;
  Format: string;
  ColorModel: string;
}

interface GeneratedImageInfoProps {
  image: GalleryImage;
  loadingOssInfo: boolean;
  ossImageInfo: OssImageInfo | null;

  isEditingName: boolean;
  setIsEditingName: (v: boolean) => void;
  editedName: string;
  setEditedName: (s: string) => void;
  originalName: string;

  isEditingTags: boolean;
  setIsEditingTags: (v: boolean) => void;
  editedTags: any;
  setEditedTags: (t: any) => void;
  originalTags: string;
  setOriginalTags: (s: string) => void;

  hasChanges: boolean;
  setHasChanges: (b: boolean) => void;

  isSubmitting: boolean;
  handleSaveChanges: () => void;
  handleCancelEdit: () => void;
}

function getValueString(val: any) {
  if (val === null || val === undefined) return '';
  if (Array.isArray(val)) return val.join(', ');
  if (typeof val === 'object') {
    const nestedValues = Object.values(val).flat();
    return nestedValues.join(', ');
  }
  return String(val);
}

function setValueFromString(_key: string, strVal: string, originalValue: any) {
  if (Array.isArray(originalValue)) {
    return strVal
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  } else if (typeof originalValue === 'object' && originalValue !== null) {
    return originalValue;
  }
  return strVal || null;
}

function buildProcessedTags(originalTagsStr: string) {
  try {
    const parsedOriginalTags = JSON.parse(originalTagsStr);
    let structuredTags: { [key: string]: any } = {};

    if (parsedOriginalTags.tags && typeof parsedOriginalTags.tags === 'object') {
      structuredTags = parsedOriginalTags.tags;
    } else if (parsedOriginalTags.data && typeof parsedOriginalTags.data === 'object') {
      structuredTags = parsedOriginalTags.data;
    } else {
      structuredTags = parsedOriginalTags;
    }

    const processedTags = GALLERY_TAG_DISPLAY_PRIORITY
      .filter((key) => {
        const value = structuredTags[key];
        if (value === undefined || value === null) return false;
        if (typeof value === 'string' && value.trim().length === 0) return false;
        return true;
      })
      .map((key) => {
        const value = structuredTags[key];
        let displayValue = '';
        if (Array.isArray(value)) {
          displayValue = value.join(', ');
        } else if (typeof value === 'object') {
          const nestedValues = Object.values(value).flat();
          displayValue = nestedValues.join(', ');
        } else {
          displayValue = String(value);
        }
        return {
          key,
          name: GALLERY_TAG_KEY_TO_LABEL[key] || key,
          value: displayValue,
        };
      });

    return processedTags;
  } catch (e) {
    console.error('解析标签失败:', e);
    return [];
  }
}

// Extracted handlers for name input to keep render clean
function handleNameBlur(
  editedName: string,
  setEditedName: (s: string) => void,
  setHasChanges: (b: boolean) => void,
  originalName: string,
  setIsEditingName: (v: boolean) => void,
) {
  const lastDotIndex = editedName.lastIndexOf('.');
  if (lastDotIndex > 0) {
    const extension = editedName.substring(lastDotIndex);
    const nameWithoutExt = editedName.substring(0, lastDotIndex);
    if (nameWithoutExt.length > 30 - extension.length) {
      const limitedName = nameWithoutExt.substring(0, 30 - extension.length);
      setEditedName(limitedName + extension);
      setHasChanges(limitedName + extension !== originalName);
      alert(`图片名称长度不能超过${30 - extension.length}个字符（不含后缀）`);
    }
  } else {
    if (editedName.length > 30) {
      const limitedName = editedName.substring(0, 30);
      setEditedName(limitedName);
      setHasChanges(limitedName !== originalName);
      alert('图片名称长度不能超过30个字符');
    }
  }
  setIsEditingName(false);
}

function handleNameKeyDown(
  e: React.KeyboardEvent<HTMLInputElement>,
  editedName: string,
  setEditedName: (s: string) => void,
  setHasChanges: (b: boolean) => void,
  originalName: string,
  setIsEditingName: (v: boolean) => void,
) {
  if (e.key === 'Enter') {
    const lastDotIndex = editedName.lastIndexOf('.');
    if (lastDotIndex > 0) {
      const extension = editedName.substring(lastDotIndex);
      const nameWithoutExt = editedName.substring(0, lastDotIndex);
      if (nameWithoutExt.length > 30 - extension.length) {
        const limitedName = nameWithoutExt.substring(0, 30 - extension.length);
        setEditedName(limitedName + extension);
        setHasChanges(limitedName + extension !== originalName);
        alert(`图片名称长度不能超过${30 - extension.length}个字符（不含后缀）`);
      }
    } else {
      if (editedName.length > 30) {
        const limitedName = editedName.substring(0, 30);
        setEditedName(limitedName);
        setHasChanges(limitedName !== originalName);
        alert('图片名称长度不能超过30个字符');
      }
    }
    setIsEditingName(false);
  }
}

export function GeneratedImageInfo(props: GeneratedImageInfoProps) {
  const {
    image,
    loadingOssInfo,
    ossImageInfo,
    isEditingName,
    setIsEditingName,
    editedName,
    setEditedName,
    originalName,
    isEditingTags,
    setIsEditingTags,
    editedTags,
    setEditedTags,
    originalTags,
    setHasChanges,
  } = props;

  const processedTags = buildProcessedTags(originalTags);

  return (
    <div className="w-full">
      <div className="p-4 rounded-lg border-4 border-cyan-400">
        <h3 className="text-base font-medium mb-3">图片信息</h3>

        <div className="space-y-3">
          {editedName && (
            <div className="flex items-start gap-4">
              <div className="text-sm text-muted-foreground w-20 text-right pr-2">文件名：</div>
              <div className="flex-1 min-w-0">
                {isEditingName ? (
                  <div className="space-y-1">
                    <Input
                      value={editedName}
                      onChange={(e) => {
                        const newValue = e.target.value;
                        setEditedName(newValue);
                        setHasChanges(newValue !== originalName);
                      }}
                      onBlur={() => handleNameBlur(editedName, setEditedName, setHasChanges, originalName, setIsEditingName)}
                      onKeyDown={(e) => handleNameKeyDown(e as React.KeyboardEvent<HTMLInputElement>, editedName, setEditedName, setHasChanges, originalName, setIsEditingName)}
                      className="w-full bg-white border-gray-200 focus:bg-white focus:border-primary/50 transition-all duration-300 placeholder:text-gray-400"
                      placeholder="输入图片名称"
                    />
                  </div>
                ) : (
                  <div className="flex items-center justify-start gap-2">
                    <p className="font-medium truncate">{editedName}</p>
                    <button
                      onClick={() => setIsEditingName(true)}
                      className="text-xs hover:underline focus:outline-none focus-visible:outline-none focus-visible:ring-0"
                    >
                      ✏️
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
          

          <div className="flex items-center gap-4">
            <div className="text-sm text-muted-foreground w-20 text-right pr-2">文件大小：</div>
            <div className="flex-1">
              <p className="font-medium">
                {loadingOssInfo ? (
                  <span className="text-xs text-muted-foreground">加载中...</span>
                ) : ossImageInfo ? (
                  formatFileSize(Number(ossImageInfo.FileSize) || 0)
                ) : (
                  image.size || '-' 
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-sm text-muted-foreground w-20 text-right pr-2">图片尺寸：</div>
            <div className="flex-1">
              <p className="font-medium">
                {loadingOssInfo ? (
                  <span className="text-xs text-muted-foreground">加载中...</span>
                ) : ossImageInfo ? (
                  `${ossImageInfo.ImageWidth}*${ossImageInfo.ImageHeight} px`
                ) : image.dimensions ? (
                  `${String(image.dimensions).replace('x','*')} px`
                ) : (
                  '-'
                )}
              </p>
            </div>
          </div>

          {image.uploadDate && (
            <div className="flex items-center gap-4">
              <div className="text-sm text-muted-foreground w-20 text-right pr-2">上传日期：</div>
              <div className="flex-1">
                <p className="font-medium">{image.uploadDate}</p>
              </div>
            </div>
          )}

          {image.aiTool && (
            <div className="flex items-center gap-4">
              <div className="text-sm text-muted-foreground w-20 text-right pr-2">AI工具：</div>
              <div className="flex-1">
                <Badge variant="outline" className="mt-1">
                  <Sparkles className="w-3 h-3 mr-1" />
                  {image.aiTool}
                </Badge>
              </div>
            </div>
          )}

          <div className="flex items-start gap-4">
            <div className="text-sm text-muted-foreground w-20 text-right pr-2">标签：</div>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-2">
                {!isEditingTags && (
                  <button
                    onClick={() => setIsEditingTags(true)}
                    className="text-xs hover:underline focus:outline-none focus-visible:outline-none focus-visible:ring-0"
                  >
                    ✏️
                  </button>
                )}
                <div></div>
              </div>

              {isEditingTags ? (
                <div className="space-y-3 p-3 rounded-md border">
                  {GALLERY_TAG_DISPLAY_PRIORITY.map((key) => {
                    const displayKey = GALLERY_TAG_KEY_TO_LABEL[key] || key;
                    return (
                      <div key={key} className="flex items-center gap-2">
                        <span className="text-sm font-medium min-w-[120px]">{displayKey}：</span>
                        <Input
                          value={getValueString(editedTags[key])}
                          onChange={(e) => {
                            const newValue = e.target.value;
                            setEditedTags((prev: any) => {
                              const updated = { ...prev };
                              updated[key] = setValueFromString(key, newValue, prev[key]);
                              return updated;
                            });
                            setHasChanges(true);
                          }}
                          placeholder={`输入${displayKey}`}
                          className="flex-1 bg-white border-gray-200 focus:bg-white focus:border-primary/50 transition-all duration-300 placeholder:text-gray-400"
                        />
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {processedTags.length === 0 ? (
                    <p className="text-sm text-muted-foreground">AI正在解析图片并生成标签中...</p>
                  ) : (
                    processedTags.map((tag) => (
                      <Badge
                        key={`tag-${tag.key}`}
                        variant="secondary"
                        className="inline-flex items-start gap-1 whitespace-normal break-words w-full justify-start p-2"
                      >
                        <TagIcon className="w-4 h-4 mr-2 flex-shrink-0" />
                        <span className="font-medium">{tag.name}：</span>
                        <span className="flex-1">{tag.value}</span>
                      </Badge>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default GeneratedImageInfo;
