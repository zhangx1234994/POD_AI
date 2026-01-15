import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ImageSourceSelector } from './ImageSourceSelector';
import { Alert, AlertDescription } from './ui/alert';
import { Separator } from './ui/separator';
import { ImageWithFallback } from './ImageWithFallback';
import { CheckCircle2, Info, ImageIcon, Sparkles, Link2 } from 'lucide-react';

interface SelectedImage {
  id: string;
  name: string;
  url: string;
  source: 'personal' | 'zebra' | 'hummingbird';
}

export function ImageSourceDemo() {
  const [selectedImages, setSelectedImages] = useState<SelectedImage[]>([]);
  const [showSelector, setShowSelector] = useState(false);

  // 模拟账号绑定状态
  const [zebraConnected] = useState(true);
  const [hummingbirdConnected] = useState(true);

  const handleImagesSelected = (images: SelectedImage[]) => {
    setSelectedImages(images);
    setShowSelector(false);
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'personal':
        return <ImageIcon className="w-3 h-3" />;
      case 'zebra':
      case 'hummingbird':
        return <Link2 className="w-3 h-3" />;
      default:
        return <ImageIcon className="w-3 h-3" />;
    }
  };

  const getSourceLabel = (source: string) => {
    switch (source) {
      case 'personal':
        return '个人图库';
      case 'zebra':
        return '斑马平台';
      case 'hummingbird':
        return '蜂鸟平台';
      default:
        return '未知来源';
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">图片来源选择演示</h1>
        <p className="text-muted-foreground">展示如何在AI工具中集成多来源图片选择功能</p>
      </div>

      <Alert>
        <Info className="w-4 h-4" />
        <AlertDescription>
          <strong>使用说明：</strong>
          用户在使用图片处理功能时，可以从个人图库、斑马图库或蜂鸟图库选择图片，也可以直接上传新图片。
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：选择器 */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>步骤1：选择图片来源</CardTitle>
              <CardDescription>从不同来源选择图片进行处理</CardDescription>
            </CardHeader>
            <CardContent>
              {!showSelector ? (
                <div className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full justify-start h-auto py-4"
                    onClick={() => setShowSelector(true)}
                  >
                    <div className="flex items-start gap-3 w-full">
                      <ImageIcon className="w-5 h-5 mt-0.5 text-muted-foreground" />
                      <div className="flex-1 text-left">
                        <div className="font-medium mb-1">选择图片</div>
                        <div className="text-sm text-muted-foreground">
                          从个人图库、斑马或蜂鸟平台选择，或上传新图片
                        </div>
                      </div>
                    </div>
                  </Button>

                  <div className="grid grid-cols-3 gap-2 text-center pt-2">
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <ImageIcon className="w-6 h-6 mx-auto mb-1 text-blue-500" />
                      <p className="text-xs">个人图库</p>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <Link2 className="w-6 h-6 mx-auto mb-1 text-purple-500" />
                      <p className="text-xs">斑马平台</p>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <Link2 className="w-6 h-6 mx-auto mb-1 text-green-500" />
                      <p className="text-xs">蜂鸟平台</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <ImageSourceSelector
                    onImagesSelected={handleImagesSelected}
                    allowMultiple={true}
                    maxImages={5}
                    zebraConnected={zebraConnected}
                    hummingbirdConnected={hummingbirdConnected}
                    showUploadOption={true}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          {selectedImages.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>步骤2：处理图片</CardTitle>
                <CardDescription>对选中的图片进行AI处理</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
                  <CheckCircle2 className="w-4 h-4 text-green-600" />
                  <AlertDescription className="text-green-600">
                    已选择 {selectedImages.length} 张图片，可以开始处理
                  </AlertDescription>
                </Alert>

                <div className="space-y-3">
                  <h4 className="text-sm font-medium">选中的图片：</h4>
                  <div className="grid grid-cols-3 gap-3">
                    {selectedImages.map((image, index) => (
                      <div key={image.id} className="space-y-2">
                        <div className="relative aspect-square rounded-lg overflow-hidden border">
                          <ImageWithFallback
                            src={image.url}
                            alt={image.name}
                            className="w-full h-full object-cover"
                          />
                          <Badge variant="secondary" className="absolute top-2 left-2 text-xs">
                            #{index + 1}
                          </Badge>
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs truncate">{image.name}</p>
                          <Badge variant="outline" className="text-xs">
                            {getSourceIcon(image.source)}
                            <span className="ml-1">{getSourceLabel(image.source)}</span>
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <Separator />

                <div className="flex gap-2">
                  <Button className="flex-1">
                    <Sparkles className="w-4 h-4 mr-2" />
                    开始处理
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setSelectedImages([]);
                      setShowSelector(false);
                    }}
                  >
                    重新选择
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* 右侧：功能说明 */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>功能特点</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" />
                <div>
                  <strong>多来源支持</strong>
                  <p className="text-muted-foreground text-xs mt-1">
                    支持从个人图库、斑马平台、蜂鸟平台选择图片
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" />
                <div>
                  <strong>直接上传</strong>
                  <p className="text-muted-foreground text-xs mt-1">
                    也可以直接上传本地图片进行处理
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" />
                <div>
                  <strong>批量选择</strong>
                  <p className="text-muted-foreground text-xs mt-1">
                    支持一次选择多张图片进行批量处理
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" />
                <div>
                  <strong>搜索功能</strong>
                  <p className="text-muted-foreground text-xs mt-1">快速搜索和筛选图库中的图片</p>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5" />
                <div>
                  <strong>来源标识</strong>
                  <p className="text-muted-foreground text-xs mt-1">清晰标识每张图片的来源平台</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>平台连接状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center justify-between p-2 bg-muted rounded">
                <span className="text-sm">斑马平台</span>
                <Badge variant={zebraConnected ? 'default' : 'outline'}>
                  {zebraConnected ? '已连接' : '未连接'}
                </Badge>
              </div>
              <div className="flex items-center justify-between p-2 bg-muted rounded">
                <span className="text-sm">蜂鸟平台</span>
                <Badge variant={hummingbirdConnected ? 'default' : 'outline'}>
                  {hummingbirdConnected ? '已连接' : '未连接'}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground pt-2">
                在个人中心可以绑定或解绑第三方平台账号
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>集成示例</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-muted p-3 rounded text-xs font-mono overflow-x-auto">
                <pre>{`<ImageSourceSelector
  onImagesSelected={handleSelect}
  allowMultiple={true}
  maxImages={5}
  zebraConnected={true}
  hummingbirdConnected={true}
/>`}</pre>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
