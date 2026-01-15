import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { ImageIcon, Sparkles, Eye, MoreVertical, Download, Trash2, Grid3x3, RefreshCw, AlertCircle, Check } from 'lucide-react';
import { useState } from 'react';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
import { GalleryImage } from '@/types/galleryImage';

export interface ListImageCardProps {
  image: GalleryImage;
  onClick?: (img: GalleryImage) => void;
  onDownload?: (id: string) => void | Promise<void>;
  onDelete?: (id: string) => void | Promise<void>;
  onViewDetails?: (img: GalleryImage) => void;
  onViewSeamless?: (img: GalleryImage) => void;
  selected?: boolean;
  onImageLoad?: () => void;
}

export function ListImageCard({
  image,
  onClick,
  onDownload,
  onDelete,
  onViewDetails,
  onViewSeamless,
  selected = false,
  onImageLoad,
  
}: ListImageCardProps) {
  const [imageError, setImageError] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleImageError = () => {
    setImageError(true);
  };

  const handleRetry = async () => {
    setRetrying(true);
    setImageError(false);
    // Use setTimeout to ensure the error state is reset before reloading
    setTimeout(() => {
      setRetrying(false);
    }, 100);
  };
  

  return (
    <div>
      <Card
        className={`relative overflow-hidden cursor-pointer transition-all hover:shadow-md ${selected ? 'ring-2 border-2 border-primary ring-primary' : ''}`}
        onClick={() => onClick && image && onClick(image)}
      >
        {selected && (
          <div className="absolute inset-0 bg-primary/20 flex items-center justify-center pointer-events-none">
            <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
              <Check className="w-5 h-5 text-primary-foreground" />
            </div>
          </div>
        )}
        <div className="p-4">
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 flex-shrink-0 rounded overflow-hidden bg-muted">
              {imageError ? (
                <div className="w-full h-full flex items-center justify-center">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRetry();
                    }}
                    disabled={retrying}
                    className="w-8 h-8"
                  >
                    {retrying ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-muted-foreground" />
                    )}
                  </Button>
                </div>
              ) : (
                <img
                  src={image.url}
                  alt={image.name}
                  className="w-full h-full object-cover"
                  onLoad={() => {
                    onImageLoad && onImageLoad();
                  }}
                  onError={handleImageError}
                />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium truncate mb-1 text-sm">{image.name}</h4>
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* badge: copy implementation from ImageCard */}
                    {image.sourceType === 'GENERATE' ? (
                      <Badge variant="secondary" className="text-xs">
                        <Sparkles className="w-4 h-4 text-purple-600" />
                        <span className="text-xs text-purple-700 font-medium">AI</span>
                      </Badge>
                    ) : (
                      <Badge className="text-xs bg-primary text-primary-foreground">
                        <ImageIcon className="w-4 h-4 text-white" />
                        <span className="text-xs text-white font-medium">上传</span>
                      </Badge>
                    )}

                    {image.aiTool && (
                      <Badge variant="outline" className="text-xs">
                        {image.aiTool}
                      </Badge>
                    )}
                  </div>
                </div>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={(e) => e.stopPropagation()}>
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onViewDetails) onViewDetails(image);
                      }}
                    >
                      <Eye className="w-4 h-4 mr-2" />查看详情
                    </DropdownMenuItem>
                    {image.originalType && ['twoway', 'seamless'].includes(image.originalType) && (
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation();
                          onViewSeamless && onViewSeamless(image);
                        }}
                      >
                        <Grid3x3 className="w-4 h-4 mr-2" />查看拼接结果
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onDownload) onDownload(image.id);
                      }}
                    >
                      <Download className="w-4 h-4 mr-2" />下载
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="group text-destructive hover:bg-red-600 hover:text-white focus:bg-red-600 focus:text-white"
                      onClick={(e) => {
                        e.stopPropagation();
                        // open confirmation dialog instead of deleting immediately
                        setShowDeleteConfirm(true);
                      }}
                    >
                      <Trash2 className="w-4 h-4 mr-2 group-hover:text-white" />删除
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{image.uploadDate}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
      {/* 删除确认对话框 */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-[28rem]">
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>确定要删除该图片吗？此操作不可撤销。</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>取消</Button>
              <Button
                className="ml-2"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDeleteConfirm(false);
                  if (onDelete) onDelete(image.id);
                }}
              >
                删除
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default ListImageCard;
