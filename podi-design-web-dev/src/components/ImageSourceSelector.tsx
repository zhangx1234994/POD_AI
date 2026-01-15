import React, { useState } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { ImageWithFallback } from './ImageWithFallback';
import {
  Upload,
  Link2,
  ImageIcon,
  Search,
  Check,
  AlertCircle,
  FolderOpen,
  Sparkles,
  X,
} from 'lucide-react';

interface SelectedImage {
  id: string;
  name: string;
  url: string;
  source: 'personal' | 'zebra' | 'hummingbird';
}

interface ImageSourceSelectorProps {
  onImagesSelected: (images: SelectedImage[]) => void;
  allowMultiple?: boolean;
  maxImages?: number;
  zebraConnected?: boolean;
  hummingbirdConnected?: boolean;
  showUploadOption?: boolean;
}

export function ImageSourceSelector({
  onImagesSelected,
  allowMultiple = true,
  maxImages = 10,
  zebraConnected = false,
  hummingbirdConnected = false,
  showUploadOption = true,
}: ImageSourceSelectorProps) {
  const [selectedImages, setSelectedImages] = useState<SelectedImage[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSource, setActiveSource] = useState<'upload' | 'personal' | 'zebra' | 'hummingbird'>(
    'upload'
  );

  // 模拟个人图库数据
  const personalGallery: SelectedImage[] = [
    {
      id: 'p1',
      name: 'my-design-1.png',
      url: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30',
      source: 'personal',
    },
    {
      id: 'p2',
      name: 'my-design-2.png',
      url: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe',
      source: 'personal',
    },
    {
      id: 'p3',
      name: 'my-product-1.jpg',
      url: 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab',
      source: 'personal',
    },
    {
      id: 'p4',
      name: 'ai-generated-1.png',
      url: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64',
      source: 'personal',
    },
  ];

  // 模拟斑马图库数据
  const zebraGallery: SelectedImage[] = [
    {
      id: 'z1',
      name: 'zebra-pattern-1.png',
      url: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e',
      source: 'zebra',
    },
    {
      id: 'z2',
      name: 'zebra-design-2.png',
      url: 'https://images.unsplash.com/photo-1541701494587-cb58502866ab',
      source: 'zebra',
    },
    {
      id: 'z3',
      name: 'zebra-artwork-3.png',
      url: 'https://images.unsplash.com/photo-1556821840-3a63f95609a7',
      source: 'zebra',
    },
    {
      id: 'z4',
      name: 'zebra-template-4.png',
      url: 'https://images.unsplash.com/photo-1434389677669-e08b4cac3105',
      source: 'zebra',
    },
  ];

  // 模拟蜂鸟图库数据
  const hummingbirdGallery: SelectedImage[] = [
    {
      id: 'h1',
      name: 'hummingbird-design-1.png',
      url: 'https://images.unsplash.com/photo-1572635196237-14b3f281503f',
      source: 'hummingbird',
    },
    {
      id: 'h2',
      name: 'hummingbird-pattern-2.png',
      url: 'https://images.unsplash.com/photo-1564584217132-2271feaeb3c5',
      source: 'hummingbird',
    },
    {
      id: 'h3',
      name: 'hummingbird-art-3.png',
      url: 'https://images.unsplash.com/photo-1591047139829-d91aecb6caea',
      source: 'hummingbird',
    },
    {
      id: 'h4',
      name: 'hummingbird-graphic-4.png',
      url: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f',
      source: 'hummingbird',
    },
  ];

  const getFilteredImages = (source: 'personal' | 'zebra' | 'hummingbird') => {
    let gallery: SelectedImage[] = [];

    switch (source) {
      case 'personal':
        gallery = personalGallery;
        break;
      case 'zebra':
        gallery = zebraGallery;
        break;
      case 'hummingbird':
        gallery = hummingbirdGallery;
        break;
    }

    if (!searchQuery) return gallery;

    return gallery.filter((img) => img.name.toLowerCase().includes(searchQuery.toLowerCase()));
  };

  const toggleImageSelection = (image: SelectedImage) => {
    setSelectedImages((prev) => {
      const exists = prev.find((img) => img.id === image.id);

      if (exists) {
        return prev.filter((img) => img.id !== image.id);
      } else {
        if (allowMultiple) {
          if (prev.length >= maxImages) {
            return prev;
          }
          return [...prev, image];
        } else {
          return [image];
        }
      }
    });
  };

  const isImageSelected = (imageId: string) => {
    return selectedImages.some((img) => img.id === imageId);
  };

  const handleConfirmSelection = () => {
    onImagesSelected(selectedImages);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newImages: SelectedImage[] = [];
    Array.from(files)
      .slice(0, maxImages - selectedImages.length)
      .forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = (event) => {
          const image: SelectedImage = {
            id: `upload_${Date.now()}_${index}`,
            name: file.name,
            url: event.target?.result as string,
            source: 'personal',
          };
          newImages.push(image);

          if (newImages.length === Math.min(files.length, maxImages - selectedImages.length)) {
            setSelectedImages((prev) => (allowMultiple ? [...prev, ...newImages] : newImages));
          }
        };
        reader.readAsDataURL(file);
      });
  };

  const removeSelectedImage = (id: string) => {
    setSelectedImages((prev) => prev.filter((img) => img.id !== id));
  };

  const renderImageGrid = (source: 'personal' | 'zebra' | 'hummingbird') => {
    const images = getFilteredImages(source);

    if (images.length === 0) {
      return (
        <div className="text-center py-12">
          <FolderOpen className="w-16 h-16 mx-auto text-muted-foreground opacity-20 mb-3" />
          <p className="text-sm text-muted-foreground">
            {searchQuery ? '未找到匹配的图片' : '暂无图片'}
          </p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {images.map((image) => (
          <div
            key={image.id}
            className={`relative aspect-square rounded-lg overflow-hidden cursor-pointer transition-all border-2 ${
              isImageSelected(image.id)
                ? 'border-primary shadow-lg scale-95'
                : 'border-transparent hover:border-muted-foreground/30'
            }`}
            onClick={() => toggleImageSelection(image)}
          >
            <ImageWithFallback
              src={image.url}
              alt={image.name}
              className="w-full h-full object-cover"
            />
            {isImageSelected(image.id) && (
              <div className="absolute inset-0 bg-primary/20 flex items-center justify-center pointer-events-none">
                <div className="w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                  <Check className="w-5 h-5 text-primary-foreground" />
                </div>
              </div>
            )}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
              <p className="text-xs text-white truncate">{image.name}</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">选择图片来源</h3>
            <p className="text-sm text-muted-foreground">从个人图库或第三方平台选择图片</p>
          </div>
          {selectedImages.length > 0 && (
            <Badge variant="secondary">
              已选 {selectedImages.length}/{maxImages}
            </Badge>
          )}
        </div>

        <Tabs value={activeSource} onValueChange={(v) => setActiveSource(v as any)}>
          <TabsList className="grid w-full grid-cols-4">
            {showUploadOption && (
              <TabsTrigger value="upload">
                <Upload className="w-4 h-4 mr-2" />
                上传
              </TabsTrigger>
            )}
            <TabsTrigger value="personal">
              <ImageIcon className="w-4 h-4 mr-2" />
              个人图库
            </TabsTrigger>
            {/* <TabsTrigger value="zebra" disabled={!zebraConnected}>
              <Link2 className="w-4 h-4 mr-2" />
              斑马
              {!zebraConnected && <AlertCircle className="w-3 h-3 ml-1 text-muted-foreground" />}
            </TabsTrigger>
            <TabsTrigger value="hummingbird" disabled={!hummingbirdConnected}>
              <Link2 className="w-4 h-4 mr-2" />
              蜂鸟
              {!hummingbirdConnected && <AlertCircle className="w-3 h-3 ml-1 text-muted-foreground" />}
            </TabsTrigger> */}
          </TabsList>

          {/* 上传选项 */}
          {showUploadOption && (
            <TabsContent value="upload" className="space-y-3">
              <div className="border-2 border-dashed rounded-lg p-8 text-center hover:border-muted-foreground/50 transition-colors cursor-pointer">
                <input
                  type="file"
                  accept="image/*"
                  multiple={allowMultiple}
                  onChange={handleFileUpload}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <Upload className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
                  <h4 className="font-medium mb-1">点击上传图片</h4>
                  <p className="text-sm text-muted-foreground">或拖拽图片到此区域</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    支持 JPG、PNG、GIF 格式
                    {allowMultiple && ` · 最多 ${maxImages} 张`}
                  </p>
                </label>
              </div>

              {selectedImages.length > 0 && (
                <Alert>
                  <Sparkles className="w-4 h-4" />
                  <AlertDescription>
                    已选择 {selectedImages.length} 张图片，点击确认使用
                  </AlertDescription>
                </Alert>
              )}
            </TabsContent>
          )}

          {/* 个人图库 */}
          <TabsContent value="personal" className="space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索个人图库..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="max-h-96 overflow-y-auto">{renderImageGrid('personal')}</div>
          </TabsContent>

          {/* 斑马图库 */}
          <TabsContent value="zebra" className="space-y-3">
            {zebraConnected ? (
              <>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索斑马图库..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="max-h-96 overflow-y-auto">{renderImageGrid('zebra')}</div>
              </>
            ) : (
              <Alert>
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>请先在个人中心绑定斑马账号后才能访问斑马图库</AlertDescription>
              </Alert>
            )}
          </TabsContent>

          {/* 蜂鸟图库 */}
          <TabsContent value="hummingbird" className="space-y-3">
            {hummingbirdConnected ? (
              <>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索蜂鸟图库..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="max-h-96 overflow-y-auto">{renderImageGrid('hummingbird')}</div>
              </>
            ) : (
              <Alert>
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>请先在个人中心绑定蜂鸟账号后才能访问蜂鸟图库</AlertDescription>
              </Alert>
            )}
          </TabsContent>
        </Tabs>

        {/* 已选择的图片预览 */}
        {selectedImages.length > 0 && (
          <div className="space-y-2 pt-3 border-t">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">已选择的图片</span>
              <Button variant="ghost" size="sm" onClick={() => setSelectedImages([])}>
                清空
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedImages.map((image) => (
                <div key={image.id} className="relative group">
                  <div className="w-16 h-16 rounded border overflow-hidden">
                    <ImageWithFallback
                      src={image.url}
                      alt={image.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <button
                    onClick={() => removeSelectedImage(image.id)}
                    className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                  <Badge
                    variant="secondary"
                    className="absolute bottom-0 left-0 right-0 text-xs justify-center rounded-t-none"
                  >
                    {image.source === 'personal'
                      ? '个人'
                      : image.source === 'zebra'
                      ? '斑马'
                      : '蜂鸟'}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-2 pt-3 border-t">
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => setSelectedImages([])}
            disabled={selectedImages.length === 0}
          >
            取消
          </Button>
          <Button
            className="flex-1"
            onClick={handleConfirmSelection}
            disabled={selectedImages.length === 0}
          >
            <Check className="w-4 h-4 mr-2" />
            确认选择 ({selectedImages.length})
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
