import React, { useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ImageIcon, Sparkles, Eye, Check } from 'lucide-react';
import { mapActionToChinese } from '@/utils/taskUtils';
import defaultGrid from '@/assets/images/grid_default.png';
import { GalleryImage } from '@/types/galleryImage';

export interface ImageCardProps {
  image: GalleryImage;
  selected?: boolean;
  batchMode?: boolean;
  onViewDetails: (img: GalleryImage) => void;
  onImageLoad?: () => void;
  onToggleSelect?: (id: string) => void;
}

export function ImageCard({
  image,
  batchMode = false,
  selected = false,
  onViewDetails,
  onImageLoad,
  onToggleSelect,
}: ImageCardProps) {
  const actionLabel = mapActionToChinese(String(image.originalType || ''));
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [showOverlay, setShowOverlay] = useState(false);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (batchMode) {
      onToggleSelect && onToggleSelect(image.id);
    } else {
      onViewDetails(image);
    }
  };

  const handleImageError = () => {
    const el = imgRef.current;
    if (el) {
      // avoid infinite loop if default also fails
      if (!String(el.src).includes('grid_default')) el.src = defaultGrid as unknown as string;
    }
  };

  return (
    <div
      className={`relative bg-muted rounded-lg overflow-hidden group cursor-pointer transition-all hover:shadow-md border border-slate-200 ${selected ? 'border-2 border-primary' : ''}`}
      onMouseEnter={() => setShowOverlay(true)}
      onMouseLeave={() => setShowOverlay(false)}
      onClick={handleClick}
    >
      <div className="relative flex items-center justify-center" style={{ minHeight: 200 }}>
        <img
          ref={imgRef}
          src={image.url || (defaultGrid as unknown as string)}
          alt={image.name}
          loading="lazy"
          decoding="async"
          className="block w-full h-auto object-cover"
          style={{ width: '100%', maxWidth: '100%', height: 'auto', minHeight: 200 }}
          onLoad={() => {
            onImageLoad && onImageLoad();
          }}
          onError={handleImageError}
        />

        {/* left-top: sourceType indicator */}
        <div className="absolute left-2 top-2">
          {image.sourceType === 'GENERATE' ? (
            <Badge variant="secondary" className="text-xs">
              <Sparkles className="w-4 h-4 text-purple-600" />
              <span className="text-xs text-purple-700 font-medium">AI</span>
            </Badge>
          ) : (
            <Badge className="text-xs bg-primary">
              <ImageIcon className="w-4 h-4 text-primary-foreground" />
              <span className="text-xs text-primary-foreground font-medium">上传</span>
            </Badge>
          )}
        </div>

        {/* right-top: type label (mapped to Chinese) */}
        {image.sourceType !== 'UPLOAD' && actionLabel && actionLabel !== '未知任务' && (
          <div className="absolute right-2 top-2">
            <Badge variant="secondary" className="text-xs">{actionLabel}</Badge>
          </div>
        )}

        {selected ? (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="absolute inset-0 bg-primary/10" />
            <div className="relative text-center text-primary pointer-events-auto">
              <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                <Check className="w-5 h-5 text-primary-foreground" />
              </div>
            </div>
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className={`absolute inset-0 bg-black/50 transition-opacity ${showOverlay ? 'opacity-100' : 'opacity-0'}`} />
            <div className={`relative text-center text-white transition-opacity pointer-events-auto px-4 ${showOverlay ? 'opacity-100' : 'opacity-0'}`}>
              <div className="flex items-center justify-center mx-auto">
                <Eye className="w-8 h-8 text-white" />
              </div>
              <div className="font-medium text-sm">点击查看详情</div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4">
        <p className="font-medium truncate text-sm mb-1">{image.name}</p>
        <div className="text-xs text-muted-foreground">{image.uploadDate}</div>
      </div>
    </div>
  );
};

export default ImageCard;
