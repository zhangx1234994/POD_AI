import React, { useState, useRef } from 'react';
import { Image as ImageIcon, Hash, X, Sparkles } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { EnhancedImageUpload } from '@/components/EnhancedImageUpload';
import { SubmitSuccessDialog } from '@/pages/AIProcessorTools/SubmitSuccessDialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { ACTION_TO_SUBMIT_LABEL } from '@/constants/task';
import { useTaskSubmission } from '@/hooks/useTaskSubmission';
import { generateTaskId } from '@/utils/taskUtils';
import { getUserId } from '@/utils/http';
import type { ImageItem } from '@/types/upload';
import { triggerRefreshTaskListDebounced } from '@/utils/debounce';
import usePointsPrecheck from '@/hooks/usePointsPrecheck';
import { Badge } from '@/components/ui/badge';

// Define shape types
type ShapeType = 'point' | 'rect' | 'circle';

interface Shape {
  id: string;
  type: ShapeType;
  x: number;
  y: number;
  width?: number;
  height?: number;
  radius?: number;
  color: string;
  size: number;
  label?: string;
  description?: string;
}

interface EditorSidebarProps {
  description: string;
  onDescriptionChange: (val: string) => void;
  outputSize: 'original' | 'custom';
  onOutputSizeChange: (val: 'original' | 'custom') => void;
  shapes: Shape[];
  selectedShapeId: string | null;
  onShapeSelect: (shapeId: string | null) => void;
  onShapeUpdate: (shape: Shape) => void;
  onShapeDelete: (shapeId: string) => void;
  mainImageSrc?: string;
  uploadedImages?: ImageItem[];
  mainImageSource?: 'upload' | 'personal';
  referenceImages?: ImageItem[];
}

interface EditorSidebarProps {
  description: string;
  onDescriptionChange: (val: string) => void;
  outputSize: 'original' | 'custom';
  onOutputSizeChange: (val: 'original' | 'custom') => void;
  shapes: Shape[];
  selectedShapeId: string | null;
  onShapeSelect: (shapeId: string | null) => void;
  onShapeUpdate: (shape: Shape) => void;
  onShapeDelete: (shapeId: string) => void;
  mainImageSrc?: string;
  uploadedImages?: ImageItem[];
  mainImageSource?: 'upload' | 'personal';
  onHighlightShape?: (shapeId: string | null) => void;
  onClearAll?: () => void;
}

export const EditorSidebar: React.FC<EditorSidebarProps> = ({
  description,
  onDescriptionChange,
  outputSize,
  onOutputSizeChange,
  shapes,
  mainImageSrc,
  uploadedImages = [],
  mainImageSource = 'upload',
  onHighlightShape,
  onClearAll,
}) => {
  const allowMultiple = true;
  const maxImages = 5;
  // State for reference images
  const [localReferenceImages, setLocalReferenceImages] = useState<ImageItem[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  // State for delete confirmation of reference images
  const [pendingDeleteIndex, setPendingDeleteIndex] = useState<number | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  // State for editing shape
  const { submitTask } = useTaskSubmission();
  const { precheckAndSubmit, dialogs: precheckDialogs } = usePointsPrecheck();

  // State for custom dimensions
  const [customWidth, setCustomWidth] = useState(1024);
  const [customHeight, setCustomHeight] = useState(1024);
  const [aspectRatio, setAspectRatio] = useState('free');
  const [isRatioLocked, setIsRatioLocked] = useState(false);
  // State for suggestion list
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [suggestionType, setSuggestionType] = useState<'@' | '#' | null>(null);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(0);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  
  // State for image hover zoom preview
  const [hoveredImage, setHoveredImage] = useState<string | null>(null);
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 });
  const imageRefs = useRef<(HTMLImageElement | null)[]>([]);


  // Handle width change
  const handleWidthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newWidth = parseInt(e.target.value) || 0;
    if (isRatioLocked && customHeight > 0) {
      // Maintain aspect ratio when locked
      const ratio = customWidth / customHeight;
      setCustomWidth(newWidth);
      setCustomHeight(Math.round(newWidth / ratio));
    } else {
      setCustomWidth(newWidth);
    }
  };

  // Handle height change
  const handleHeightChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newHeight = parseInt(e.target.value) || 0;
    if (isRatioLocked && customWidth > 0) {
      // Maintain aspect ratio when locked
      const ratio = customWidth / customHeight;
      setCustomHeight(newHeight);
      setCustomWidth(Math.round(newHeight * ratio));
    } else {
      setCustomHeight(newHeight);
    }
  };

  // Handle aspect ratio selection
  const handleRatioSelect = (ratio: string) => {
    setAspectRatio(ratio);
    if (ratio === 'free') {
      setIsRatioLocked(false);
    } else {
      setIsRatioLocked(true);
      // Apply the selected aspect ratio
      if (ratio === '1:1') {
        setCustomHeight(customWidth);
      } else if (ratio === '16:9') {
        setCustomHeight(Math.round(customWidth * 9 / 16));
      } else if (ratio === '4:3') {
        setCustomHeight(Math.round(customWidth * 3 / 4));
      } else if (ratio === '3:2') {
        setCustomHeight(Math.round(customWidth * 2 / 3));
      } else if (ratio === '2:3') {
        setCustomHeight(Math.round(customWidth * 3 / 2));
      }
    }
  };

  // Handle description change with suggestion detection
  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const pos = e.target.selectionStart;
    setCursorPosition(pos);
    onDescriptionChange(value);

    // Detect @ and # symbols
    const textBefore = value.slice(0, pos);
    const lastAt = textBefore.lastIndexOf('@');
    const lastHash = textBefore.lastIndexOf('#');
    const lastSymbolPos = Math.max(lastAt, lastHash);
    
    // Check if the last symbol is not followed by a space
    if (lastSymbolPos !== -1) {
      const afterSymbol = textBefore.slice(lastSymbolPos + 1);
      if (!/\s/.test(afterSymbol)) {
        setSuggestionType(lastAt > lastHash ? '@' : '#');
        setShowSuggestions(true);
        setSelectedSuggestionIndex(0);
        return;
      }
    }
    
    setShowSuggestions(false);
    setSuggestionType(null);
  };

  // Handle suggestion item click
  const handleSuggestionClick = (_item: string, value: string) => {
    // Use the description prop directly instead of the ref's value
    // because React state updates are asynchronous
    const currentValue = description;
    const currentPos = cursorPosition;
    
    const textBefore = currentValue.slice(0, currentPos);
    const textAfter = currentValue.slice(currentPos);
    
    // Find the last symbol position (@ or #)
    const lastAt = textBefore.lastIndexOf('@');
    const lastHash = textBefore.lastIndexOf('#');
    const lastSymbolPos = Math.max(lastAt, lastHash);
    
    if (lastSymbolPos !== -1) {
      // Determine the actual symbol used
      const actualSymbol = lastAt > lastHash ? '@' : '#';
      const newText = textBefore.slice(0, lastSymbolPos) + `${actualSymbol}${value} ` + textAfter;
      onDescriptionChange(newText);
      
      // Hide suggestions
      setShowSuggestions(false);
      
      // Focus back to textarea after the state has been updated
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          // Set cursor position after the inserted text
          const newCursorPos = lastSymbolPos + value.length + 2;
          textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        }
      }, 100); // Wait a bit for the state to update
    }
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!showSuggestions) return;
    
    const suggestions = suggestionType === '@' ? shapes : localReferenceImages;
    
    switch (e.key) {
      case 'ArrowUp':
        e.preventDefault();
        setSelectedSuggestionIndex(prev => 
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case 'ArrowDown':
        e.preventDefault();
        setSelectedSuggestionIndex(prev => 
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'Enter':
      case 'Tab':
        e.preventDefault();
        if (suggestions.length > 0) {
          const selectedItem = suggestions[selectedSuggestionIndex];
          if (suggestionType === '@' && 'type' in selectedItem) {
            // It's a shape
            const shape = selectedItem as Shape;
            let shapeValue = '';
            if (shape.type === 'point') {
              shapeValue = `point(${Math.round(shape.x)},${Math.round(shape.y)})`;
            } else if (shape.type === 'rect') {
              shapeValue = `rect(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.width || 0)},${Math.round(shape.height || 0)})`;
            } else if (shape.type === 'circle') {
              shapeValue = `circle(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.radius || 0)})`;
            }
            // Call the updated handleSuggestionClick function
            handleSuggestionClick(shape.label || shape.id, shapeValue);
          } else if (suggestionType === '#' && 'preview' in selectedItem) {
            // It's a reference image
            const imageIndex = localReferenceImages.indexOf(selectedItem as ImageItem);
            handleSuggestionClick('', `参考图${imageIndex + 1}`);
          }
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        break;
      default:
        break;
    }
  };

  // Handle textarea focus
  const handleTextareaFocus = () => {
    if (description) {
      const lastAt = description.lastIndexOf('@');
      const lastHash = description.lastIndexOf('#');
      const lastSymbolPos = Math.max(lastAt, lastHash);
      
      if (lastSymbolPos !== -1) {
        const textAfter = description.slice(lastSymbolPos + 1);
        if (!/\s/.test(textAfter)) {
          setSuggestionType(lastAt > lastHash ? '@' : '#');
          setShowSuggestions(true);
          setSelectedSuggestionIndex(0);
        }
      }
    }
  };

  // Handle textarea blur
  const handleTextareaBlur = () => {
    // Delay hiding suggestions to allow click events to fire
    setTimeout(() => setShowSuggestions(false), 200);
  };

  // State for task submission
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccessDialog, setShowSuccessDialog] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  // Handle start generate button click with anti-duplicate submission
  const handleStartGenerate = async () => {
    if (!mainImageSrc || !description.trim()) {
      return;
    }

    // Prevent duplicate submissions
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);

    try {
      // Generate task ID
      const taskId = generateTaskId();
      const userId = getUserId();
      setCurrentTaskId(taskId);

      // Prepare processed prompt with annotations
      const processedPrompt = description || '';

      // Get original image dimensions
      const getImageDimensions = (url: string): Promise<{ width: number; height: number }> => {
        return new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => {
            resolve({ width: img.width, height: img.height });
          };
          img.onerror = reject;
          img.src = url;
        });
      };

      const originalDimensions = await getImageDimensions(mainImageSrc);

      // Prepare image lists
      const imageList: { filename: string; ossUrl?: string; source: string }[] = [];
      const aux_imageList: { filename: string; ossUrl?: string; source: string }[] = [];

      // Add main image to imageList
      if (mainImageSrc) {
        // Get the actual main image from uploadedImages if available
        const mainImage = uploadedImages[0];
        
        imageList.push({
          filename: `${taskId}_base.png`,
          ossUrl: mainImage?.ossUrl || mainImageSrc, // Use ossUrl if available, otherwise use preview
          source: mainImageSource || (mainImage?.source as 'upload' | 'personal') || 'upload'
        });
      }

      // Add reference images to aux_imageList
      if (localReferenceImages.length > 0) {
        localReferenceImages.forEach((img, idx) => {
          // Use the source property from the image object, default to 'upload'
          const imgSource = img.source as string || 'upload';
          
          aux_imageList.push({
            filename: img.name || `ref_${idx}.png`,
            ossUrl: img.ossUrl || img.preview, // Use ossUrl if available, otherwise use preview
            source: imgSource
          });
        });
      }

      // Prepare mask elements from shapes
      const maskElements = shapes.map(shape => ({
        id: shape.id,
        type: shape.type === 'rect' ? 'rectangle' : shape.type,
        color: shape.color,
        points: shape.type === 'point' ? [
          { x: shape.x, y: shape.y }
        ] : shape.type === 'rect' ? [
          { x: shape.x, y: shape.y },
          { x: shape.x + (shape.width || 0), y: shape.y + (shape.height || 0) }
        ] : [
          { x: shape.x, y: shape.y },
          { x: shape.x + (shape.radius || 0), y: shape.y + (shape.radius || 0) }
        ],
        brushSize: shape.size,
        name: shape.label || `${shape.type === 'rect' ? '矩形' : shape.type === 'circle' ? '圆形' : '点位'}${shapes.indexOf(shape) + 1}`
      }));

      // Calculate width, height, and output resolution based on selected options
      let width: number;
      let height: number;
      let outputResolution: string;

      if (outputSize === 'original') {
        // Use original image dimensions
        width = originalDimensions.width;
        height = originalDimensions.height;
        outputResolution = 'original'; // Set to 'original' when using original dimensions
      } else {
        // Use custom dimensions
        width = customWidth;
        height = customHeight;
        // Determine output resolution based on aspect ratio
        if (aspectRatio === 'free') {
          outputResolution = 'auto';
        } else {
          outputResolution = aspectRatio;
        }
      }

      // Construct params with o_size
      const params = {
        action: 'edit',
        user_id: userId,
        taskId,
        imageList,
        aux_imageList,
        prompt: processedPrompt,
        maskElements,
        model: 'nano-banana-pro', // Default model
        width,
        height,
        o_size: originalDimensions, // Original image dimensions
        output_resolution: outputResolution,
      };

      // use precheck hook to run points check + dialogs then submit
      try {
        await precheckAndSubmit({
          action: 'edit',
          imagesCount: imageList.length,
          taskId,
          submitFn: async () => {
            await submitTask({
              action: 'edit',
              toolType: 'edit',
              params,
              userId,
              taskId,
              onSuccess: () => {
                setShowSuccessDialog(true);

                // 立即触发带taskId的刷新事件，同时传递action、userId和分页信息
                triggerRefreshTaskListDebounced(taskId, {
                  action: params.action, // 使用与提交任务时完全相同的action参数，确保监控系统能够正确识别
                  user_id: params.user_id, // 修改为user_id，与DashboardTaskList组件一致
                  page: 0, // 默认从第0页开始
                  size: 5, // 修改为5，与DashboardTaskList组件一致
                  forceRefresh: true, // 强制刷新，确保新任务正确显示在列表顶部
                });
              },
              onError: (error) => {
                console.error('提交失败:', error);
              },
              showSuccessDialog: () => {
                // Optionally show UI dialog
              },
            });
          },
        });
      } catch (e: any) {
        console.error('积分校验或提交异常:', e);
        setShowSuccessDialog(false);
      } finally {
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error('任务提交失败:', error);
      setShowSuccessDialog(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle continue submitting new task
  const handleContinueSubmit = () => {
    // Clear current input content
    onDescriptionChange('');
    setLocalReferenceImages([]);
    setShowSuccessDialog(false);
    // Call onClearAll to clear all content including images and annotations
    onClearAll?.();
  };

  // Handle view task
  const handleViewTask = () => {
    setShowSuccessDialog(false);
    // Optionally navigate to task list or refresh task list
  };

  return (
    <div className="flex flex-col gap-4 h-full overflow-y-auto">
      {/* Reference Image Section */}
      <Card className="bg-card text-card-foreground flex flex-col gap-1 rounded-xl border">
        <CardHeader className={`grid auto-rows-min grid-rows-[auto_auto] items-start px-6 ${localReferenceImages.length > 0 ? 'pt-6 pb-2' : 'py-6'}`}>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Hash className="w-4 h-4" aria-hidden="true" />
              参考图
            </CardTitle>
            <Button 
              variant="outline" 
              size="sm"
              className="h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5"
              onClick={() => setShowUploadDialog(true)}
            >
              <ImageIcon className="w-3 h-3 mr-1" aria-hidden="true" />
              添加
            </Button>
          </div>
        </CardHeader>

        {/* Reference Images Display */}
        {localReferenceImages.length > 0 && (
          <CardContent className="p-3 pt-0 [&:last-child]:pb-6">
            <ScrollArea className="max-h-32">
              <div className="space-y-2">
                {localReferenceImages.map((image, index) => (
                  <div key={index} className="flex items-center gap-2 p-2 border rounded-lg relative">
                    <div
                      className="relative group"
                      onMouseEnter={(e) => {
                        setHoveredImage(image.preview || null);
                        const rect = e.currentTarget.getBoundingClientRect();
                        setHoverPosition({ x: rect.left, y: rect.top });
                      }}
                      onMouseMove={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setHoverPosition({ x: e.clientX, y: e.clientY });
                      }}
                      onMouseLeave={() => {
                        setHoveredImage(null);
                      }}
                    >
                      <img 
                        ref={el => imageRefs.current[index] = el}
                        src={image.preview} 
                        alt={`Reference ${index + 1}`} 
                        className="h-8 w-8 object-cover rounded cursor-pointer"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-foreground truncate">参考图{index + 1}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="p-0 bg-red-100 hover:bg-red-200 text-red-600 transition-all"
                      onClick={() => {
                        setPendingDeleteIndex(index);
                        setShowDeleteConfirm(true);
                      }}
                      aria-label={`删除参考图 ${index + 1}`}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </ScrollArea>
            
            {/* Zoom Preview Overlay */}
            {hoveredImage && (
              <div
                className="fixed z-50 w-48 h-48 border-2 border-white rounded-lg shadow-2xl overflow-hidden pointer-events-none bg-white flex items-center justify-center"
                style={{
                  left: `${hoverPosition.x + 15}px`,
                  top: `${hoverPosition.y - 50 - 15}px`, // 向上偏移预览窗口高度加上额外间距
                  zIndex: 9999
                }}
              >
                <img
                  src={hoveredImage}
                  alt="Zoom preview"
                  className="max-w-full max-h-full object-contain"
                />
              </div>
            )}
          </CardContent>
        )}
      </Card>
      
      {/* Image Upload Dialog */}
      <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>上传参考图</DialogTitle>
            <DialogDescription className="text-xs">
              点击上传或从图库选择图片作为参考图
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex-1 py-4">
            <EnhancedImageUpload
              title="选择参考图"
              description="点击上传或从图库选择"
              supportText={`支持 PNG, JPG, JPEG, BMP格式，单张最大5M，最多${maxImages}张`}
              maxImages={maxImages}
              allowMultiple={allowMultiple}
              onImagesChange={(images) => {
                setLocalReferenceImages(images);
                setShowUploadDialog(false);
              }}
              zebraConnected={true}
              hummingbirdConnected={true}
              images={localReferenceImages}
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete reference image confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除参考图</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            {pendingDeleteIndex != null
              ? `确认删除 参考图 ${pendingDeleteIndex + 1}？此操作无法撤销。`
              : '确认删除选中的参考图？此操作无法撤销。'}
          </div>
          <div className="pt-4 flex gap-2 justify-end">
            <Button variant="outline" onClick={() => { setPendingDeleteIndex(null); setShowDeleteConfirm(false); }}>取消</Button>
            <Button
              className="ml-2"
              onClick={() => {
                if (pendingDeleteIndex != null) {
                  const newImages = [...localReferenceImages];
                  newImages.splice(pendingDeleteIndex, 1);
                  setLocalReferenceImages(newImages);
                }
                setPendingDeleteIndex(null);
                setShowDeleteConfirm(false);
              }}
            >
              删除
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Effect Description Section */}
      <div className="bg-card rounded-16 p-6 border flex-1">
        <h3 className="text-sm font-medium text-[#333] mb-3">效果描述</h3>
        
        <div className="bg-[#F4F5F7] rounded-10 p-3 mb-3 h-[198px] flex items-start">
          <p className="text-xs text-[#666] leading-relaxed">
            描述你想要的效果，例如：<br/>
            • 在@天空区域生成梵高星空，参考#星空图的风格<br/>
            • 移除@人物区域的背景，保持边缘自然<br/>
            • 将@建筑区域迁移为#油画图的风格<br/>
            <br/>
            使用 @ 引用标注区域，使用 # 引用参考图
          </p>
        </div>

        <div className="relative w-full">
          <Textarea 
            ref={textareaRef}
            value={description}
            onChange={handleDescriptionChange}
            onKeyDown={handleKeyDown}
            onFocus={handleTextareaFocus}
            onBlur={handleTextareaBlur}
            placeholder="未填写"
            className="min-h-[198px] resize-none border-0 bg-[#F4F5F7] rounded-10 p-3 placeholder:text-[#9CA3AF] focus-visible:ring-0 text-sm text-[#333] whitespace-normal word-wrap:break-word word-break:break-word overflow-hidden"
            style={{ 
              whiteSpace: 'normal', 
              wordBreak: 'break-word', 
              wordWrap: 'break-word',
              width: '100%',
              display: 'block'
            }}
            maxLength={2000}
          />
          
          {/* Character Count */}
          <div className="text-xs text-[#9CA3AF] mt-1 text-right">
            {description.length}/2000
          </div>
          
          {/* Suggestion List */}
          {showSuggestions && suggestionType && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-[#EDEEF0] rounded-lg shadow-lg z-10 max-h-60 overflow-y-auto">
              {suggestionType === '@' ? (
                // Annotation suggestions
                <div className="p-2">
                  {shapes.length > 0 ? (
                    shapes.map((shape, index) => (
                      <div 
                        key={shape.id} 
                        className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${index === selectedSuggestionIndex ? 'bg-[#F4F5F7]' : 'hover:bg-[#F9FAFB]'}`}
                        onClick={() => {
                          let shapeValue = '';
                          if (shape.type === 'point') {
                            shapeValue = `point(${Math.round(shape.x)},${Math.round(shape.y)})`;
                          } else if (shape.type === 'rect') {
                            shapeValue = `rect(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.width || 0)},${Math.round(shape.height || 0)})`;
                          } else if (shape.type === 'circle') {
                            shapeValue = `circle(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.radius || 0)})`;
                          }
                          handleSuggestionClick(shape.label || shape.id, shapeValue);
                        }}
                        onMouseEnter={() => onHighlightShape?.(shape.id)}
                        onMouseLeave={() => onHighlightShape?.(null)}
                      >
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: shape.color }}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-[#333] truncate">{shape.label || `标注 ${shapes.indexOf(shape) + 1}`}</p>
                          <p className="text-xs text-[#666] truncate">{shape.type === 'point' ? '点' : shape.type === 'rect' ? '矩形' : '圆形'}</p>
                          <p className="text-xs text-[#6C4CF0] truncate mt-1">
                            {shape.type === 'point' ? `@point(${Math.round(shape.x)},${Math.round(shape.y)})` : 
                             shape.type === 'rect' ? `@rect(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.width || 0)},${Math.round(shape.height || 0)})` : 
                             `@circle(${Math.round(shape.x)},${Math.round(shape.y)},${Math.round(shape.radius || 0)})`}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-xs text-[#9CA3AF] text-center">
                      暂无标注
                    </div>
                  )}
                </div>
              ) : (
                // Reference image suggestions
                <div className="p-2">
                  {localReferenceImages.length > 0 ? (
                    localReferenceImages.map((image, index) => (
                      <div 
                        key={index} 
                        className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${index === selectedSuggestionIndex ? 'bg-[#F4F5F7]' : 'hover:bg-[#F9FAFB]'}`}
                        onClick={() => handleSuggestionClick('', `参考图${index + 1}`)}
                      >
                        <div
                          className="relative group"
                          onMouseEnter={(e) => {
                            setHoveredImage(image.preview || null);
                            const rect = e.currentTarget.getBoundingClientRect();
                            setHoverPosition({ x: rect.left, y: rect.top });
                          }}
                          onMouseMove={(e) => {
                            setHoverPosition({ x: e.clientX, y: e.clientY });
                          }}
                          onMouseLeave={() => {
                            setHoveredImage(null);
                          }}
                        >
                          <img 
                            src={image.preview} 
                            alt={`参考图 ${index + 1}`} 
                            className="h-8 w-8 object-cover rounded cursor-pointer"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-[#333] truncate">参考图{index + 1}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-xs text-[#9CA3AF] text-center">
                      暂无参考图
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Output Size Section */}
      <Card className="bg-card text-card-foreground flex flex-col gap-2 rounded-xl border mb-4" style={{ width: '100%', maxWidth: '100%' }}>
        <CardHeader className="grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 pt-6 pb-3">
          <CardTitle className="text-sm">输出尺寸</CardTitle>
        </CardHeader>
        <CardContent className="px-6 [&:last-child]:pb-6 space-y-3" style={{ width: '100%', maxWidth: '100%' }}>
          <RadioGroup value={outputSize} onValueChange={(val) => onOutputSizeChange(val as 'original' | 'custom')} className="grid gap-3" style={{ width: '100%', maxWidth: '100%' }}>
            <div
              className={`flex items-center space-x-2 border-2 rounded-lg p-3 cursor-pointer transition-all ${outputSize === 'original' ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}`}
              style={{ width: '100%', maxWidth: '100%' }}
              onClick={() => onOutputSizeChange('original')}
            >
              <RadioGroupItem value="original" id="output-original" className="text-primary" />
              <Label htmlFor="output-original" className="cursor-pointer font-medium text-sm">原图大小</Label>
            </div>
            
            <div
              className={`border-2 rounded-lg p-3 cursor-pointer transition-all ${outputSize === 'custom' ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}`}
              style={{ width: '100%', maxWidth: '100%' }}
              onClick={() => onOutputSizeChange('custom')}
            >
              <div className="flex items-center space-x-2 mb-2">
                <RadioGroupItem value="custom" id="output-custom" className="text-primary" />
                <Label htmlFor="output-custom" className="cursor-pointer font-medium text-sm">自定义尺寸</Label>
              </div>
              {outputSize === 'custom' && (
                <div className="ml-6 space-y-3" style={{ width: '100%', maxWidth: '220px' }}>
                  <div className="flex items-center gap-2" style={{ width: '100%' }}>
                    <input 
                      type="number" 
                      className="border border-[#EDEEF0] rounded-md px-3 py-2 text-sm" 
                      placeholder="宽度" 
                      value={customWidth}
                      onChange={handleWidthChange}
                      style={{ width: '80px', flexShrink: 0 }}
                    />
                    <span className="text-sm">×</span>
                    <input 
                      type="number" 
                      className="border border-[#EDEEF0] rounded-md px-3 py-2 text-sm" 
                      placeholder="高度" 
                      value={customHeight}
                      onChange={handleHeightChange}
                      style={{ width: '80px', flexShrink: 0 }}
                    />
                  </div>
                  <div>
                    <Label className="block text-xs font-medium mb-2">比例锁定</Label>
                    <div className="flex gap-1 flex-wrap" style={{ width: '100%' }}>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === 'free' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('free')}
                        style={{ flexShrink: 0 }}
                      >
                        自由
                      </button>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === '1:1' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('1:1')}
                        style={{ flexShrink: 0 }}
                      >
                        1:1
                      </button>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === '16:9' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('16:9')}
                        style={{ flexShrink: 0 }}
                      >
                        16:9
                      </button>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === '4:3' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('4:3')}
                        style={{ flexShrink: 0 }}
                      >
                        4:3
                      </button>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === '3:2' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('3:2')}
                        style={{ flexShrink: 0 }}
                      >
                        3:2
                      </button>
                      <button 
                        className={`px-3 py-1.5 rounded-md text-xs font-medium ${aspectRatio === '2:3' ? 'bg-primary text-white' : 'bg-white text-[#333] border border-[#EDEEF0]'}`}
                        onClick={() => handleRatioSelect('2:3')}
                        style={{ flexShrink: 0 }}
                      >
                        2:3
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </RadioGroup>
        </CardContent>
      </Card>
      

      
      {/* Start Generate Button at Bottom - Fixed Position */}
      <div className="fixed bottom-4 left-4 right-4 z-30">
        <Button
          variant="default"
          size="sm"
          className="w-full h-10 gap-1.5 px-3 generate-start-btn shadow-md"
          onClick={handleStartGenerate}
          disabled={!mainImageSrc || !description.trim()}
        >
          <Sparkles className="w-4 h-4 mr-2" />{ACTION_TO_SUBMIT_LABEL['edit'] ?? '启动AI图片编辑'}
        </Button>
      </div>
      
      {/* Success Dialog (shared) */}
      <SubmitSuccessDialog
        open={showSuccessDialog}
        taskId={currentTaskId ?? undefined}
        toolName="AI图片编辑"
        onOpenChange={setShowSuccessDialog}
        onViewTask={() => {
          handleViewTask();
        }}
        onContinue={handleContinueSubmit}
      />
      {precheckDialogs}
    </div>
  );
};

export default EditorSidebar;