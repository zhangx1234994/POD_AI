import React from 'react';
import type { ImageItem } from '@/types/upload';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EnhancedImageUpload } from '@/components/EnhancedImageUpload';

interface ImageUploadPanelProps {
  images: ImageItem[];
  onImagesChange: (images: ImageItem[]) => void;
  maxImages?: number;
  allowMultiple?: boolean;
  numbered?: boolean;
  refreshKey?: number;
  zebraConnected?: boolean;
  hummingbirdConnected?: boolean;
  imageLabels?: string[];
  title?: string;
  description?: string;
  supportText?: string;
}

export const ImageUploadPanel: React.FC<ImageUploadPanelProps> = ({
  images,
  onImagesChange,
  maxImages = 1,
  allowMultiple = false,
  numbered = false,
  refreshKey = 0,
  zebraConnected = true,
  hummingbirdConnected = true,
  imageLabels = [],
  title = '',
  description = '',
  supportText = '',
}) => {
  return (
    <Card className="shadow-sm mb-4 gap-6 hover:shadow-md transition-shadow">
      <CardHeader className="pb-0 gap-0">
        <div className="flex items-center justify-between">
          <CardTitle className="text-md font-medium">{title}</CardTitle>
          <div className="flex gap-1">
            {allowMultiple && maxImages && maxImages > 1 && (
              <Badge variant="outline" className="text-xs rounded-md">
                支持 PNG, JPG, JPEG, BMP格式，单张最大5M，最多{maxImages}张
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-6 pb-6 gap-6">
        <EnhancedImageUpload
          key={refreshKey}
          title=""
          description={imageLabels.length > 0 ? imageLabels.join('，') : description}
          supportText={supportText}
          maxImages={maxImages}
          allowMultiple={allowMultiple}
          numbered={numbered}
          onImagesChange={onImagesChange}
          zebraConnected={zebraConnected}
          hummingbirdConnected={hummingbirdConnected}
          images={images}
        />
      </CardContent>
    </Card>
  );
};

export default ImageUploadPanel;
