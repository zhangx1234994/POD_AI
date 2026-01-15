import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ImageWithFallback } from '@/components/ImageWithFallback';
import { ZoomIn, ZoomOut, RotateCcw, Download } from 'lucide-react';

interface SeamlessPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  task: any; // 任务对象
  onDownload?: (task: any) => void;
  onRegenerate?: (task: any) => void;
}

export const SeamlessPreviewDialog: React.FC<SeamlessPreviewDialogProps> = ({
  open,
  onOpenChange,
  task,
  onDownload,
  onRegenerate,
}) => {
  const [zoom, setZoom] = useState(1);
  const [showGrid, setShowGrid] = useState(true);

  // 获取第一张结果图
  const getResultImage = () => {
    if (!task) return '';

    // 尝试从不同字段获取图片URL
    const imagesArr = Array.isArray(task?.images) ? task.images : [];
    if (imagesArr.length > 0) {
      return imagesArr[0]; // 取第一张图
    }

    return task?.imageUrl || task?.thumbnail || task?.imgUrl || task?.url || '';
  };

  const resultImage = getResultImage();

  // 创建九宫格数据
  const createGridImages = () => {
    if (!resultImage) return [];

    // 创建九宫格，中心是原图，周围8个是同一张图
    return Array.from({ length: 9 }, (_, index) => ({
      id: index,
      url: resultImage,
      isCenter: index === 4, // 中心位置
    }));
  };

  const gridImages = createGridImages();

  // 处理缩放
  const handleZoomIn = () => {
    setZoom((prev) => Math.min(3, prev + 0.25));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(0.5, prev - 0.25));
  };

  const handleResetZoom = () => {
    setZoom(1);
  };

  // 获取操作类型的中文名称
  const getActionName = (action?: string) => {
    switch (action) {
      case 'seamless':
        return '连续图案';
      case 'twoway':
        return '两方连续';
      default:
        return action || '';
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-h-[90vh] overflow-y-auto" style={{ maxWidth: '800px' }}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>拼接结果预览</span>
            <Badge variant="outline">{getActionName(task?.action)}</Badge>
          </DialogTitle>
          <DialogDescription>
            查看连续图案的无缝拼接效果，可以缩放和切换网格线显示
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 说明文字 */}
          <div className="bg-blue-50 dark:bg-slate-800 p-4 rounded-lg">
            <h3 className="font-medium text-blue-900 dark:text-blue-200 mb-2">
              {task?.action === 'seamless' ? '四方连续图拼接说明' : '两方连续图拼接说明'}
            </h3>
            <p className="text-sm text-blue-800 dark:text-blue-100">
              {task?.action === 'seamless'
                ? '该图案可在上下左右四个方向无缝拼接，适用于包装纸、墙纸、纺织品等需要大面积铺满的设计'
                : '该图案可在指定方向上无缝拼接，适用于边框、装饰带等需要连续图案的设计'}
            </p>
          </div>

          {/* 缩放控制 */}
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={handleZoomOut}>
              <ZoomOut className="w-4 h-4 mr-1" />
              缩小
            </Button>
            <div className="flex items-center gap-2 px-3">
              <span className="text-sm font-medium">{Math.round(zoom * 100)}%</span>
              <input
                type="range"
                min="50"
                max="300"
                step="25"
                value={zoom * 100}
                onChange={(e) => setZoom(Number(e.target.value) / 100)}
                className="w-32"
              />
            </div>
            <Button size="sm" variant="outline" onClick={handleZoomIn}>
              <ZoomIn className="w-4 h-4 mr-1" />
              放大
            </Button>
            <Button size="sm" variant="outline" onClick={handleResetZoom}>
              <RotateCcw className="w-4 h-4 mr-1" />
              重置
            </Button>
            <Button
              size="sm"
              variant={showGrid ? 'default' : 'outline'}
              onClick={() => setShowGrid(!showGrid)}
            >
              {showGrid ? '隐藏网格' : '显示网格'}
            </Button>
          </div>

          {/* 九宫格展示 */}
          <div
            className="border rounded-lg overflow-hidden bg-gray-50 p-2 mx-auto"
            style={{
              width: `${Math.min(350, zoom * 350) + 16}px`,
              height: `${Math.min(350, zoom * 350) + 16}px`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <div
              className="grid grid-cols-3 gap-0"
              style={{
                width: `${Math.min(350, zoom * 350)}px`,
                height: `${Math.min(350, zoom * 350)}px`,
                transform: `scale(${zoom})`,
                transformOrigin: 'center',
              }}
            >
              {gridImages.map((item) => (
                <div
                  key={item.id}
                  className={`relative overflow-hidden ${showGrid ? 'border border-gray-300' : ''}`}
                  style={{ aspectRatio: '1/1' }}
                >
                  <ImageWithFallback
                    src={item.url}
                    alt={`拼接图 ${item.id + 1}`}
                    className="w-full h-full object-cover"
                  />
                  {showGrid && (
                    <div className="absolute top-1 left-1 w-5 h-5 bg-purple-500 bg-opacity-70 text-white text-xs font-medium flex items-center justify-center">
                      {item.id + 1}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 提示信息 */}
          <div className="bg-amber-50 p-3 rounded-lg">
            <p className="text-sm text-amber-800">💡 提示: 拖动滚动条或使用缩放按钮查看细节</p>
          </div>

          {/* 操作按钮 */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            {onRegenerate && (
              <Button variant="outline" onClick={() => onRegenerate(task)}>
                <RotateCcw className="w-4 h-4 mr-2" />
                重绘
              </Button>
            )}
            {onDownload && (
              <Button onClick={() => onDownload(task)}>
                <Download className="w-4 h-4 mr-2" />
                下载结果
              </Button>
            )}
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              关闭
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SeamlessPreviewDialog;
