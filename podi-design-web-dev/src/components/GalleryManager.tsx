import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import {
  Image,
  Folder,
  Search,
  Filter,
  Grid3X3,
  List,
  Upload,
  Download,
  Star,
  Clock,
  Tag,
  Edit,
  Trash2,
  Eye,
  Copy,
  MoreHorizontal,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { http } from '../utils/http';
import { getUserId } from '../utils/http';

export function GalleryManager() {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedImages, setSelectedImages] = useState<number[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [previewImage, setPreviewImage] = useState<any>(null);
  const [images, setImages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // 获取图片库数据
  const fetchImages = async () => {
    try {
      setLoading(true);
      const userId = getUserId();
      const response = await http.get('/gallery/all', {
        params: {
          user_id: userId,
          page: 0,
          size: 100,
        },
      });

      if (response.data && response.data.items) {
        // 转换API返回的数据格式为组件需要的格式
        const formattedImages = response.data.items.map((item: any) => ({
          id: item.img_id || item.id, // 优先使用img_id字段
          name: item.img_name || item.imgName,
          category: item.type === 'UPLOADED' ? '上传图片' : '生成图片',
          size: '1024x1024', // API没有返回尺寸信息，使用默认值
          created: new Date(
            item.createTime || item.create_time || item.uploadTime || item.upload_time
          ).toLocaleDateString(),
          tags: item.tags || [], // 使用API返回的标签信息
          starred: false, // API没有返回收藏状态，使用默认值
          type: item.imgUrl.split('.').pop()?.toUpperCase() || 'JPG',
          url: item.imgUrl,
        }));
        setImages(formattedImages);
      }
    } catch (error) {
      console.error('获取图片库数据失败:', error);
      // 如果API调用失败，保留原有的mock数据作为后备
    } finally {
      setLoading(false);
    }
  };

  // 组件加载时获取图片库数据
  useEffect(() => {
    fetchImages();
  }, []);

  // 模拟图库数据
  const categories = [
    { id: 1, name: '无损放大', count: 156, color: 'bg-blue-500' },
    { id: 2, name: '抠图结果', count: 89, color: 'bg-green-500' },
    { id: 3, name: '印花提取', count: 234, color: 'bg-purple-500' },
    { id: 4, name: '四方连续', count: 67, color: 'bg-orange-500' },
    { id: 5, name: '未归类', count: 45, color: 'bg-gray-500' },
  ];

  const toggleImageSelection = (imageId: number) => {
    setSelectedImages((prev) =>
      prev.includes(imageId) ? prev.filter((id) => id !== imageId) : [...prev, imageId]
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">图库管理</h1>
          <p className="text-muted-foreground">管理和组织您的图片资源</p>
        </div>
        <div className="flex gap-2">
          <Button>
            <Upload className="w-4 h-4 mr-2" />
            上传图片
          </Button>
          <Button variant="outline">
            <Folder className="w-4 h-4 mr-2" />
            新建分类
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* 左侧分类面板 */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>分类管理</CardTitle>
              <CardDescription>按分类组织图片</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {categories.map((category) => (
                  <div
                    key={category.id}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${category.color}`}></div>
                      <span className="font-medium">{category.name}</span>
                    </div>
                    <Badge variant="secondary">{category.count}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>标签</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">T恤</Badge>
                <Badge variant="outline">咖啡杯</Badge>
                <Badge variant="outline">手机壳</Badge>
                <Badge variant="outline">印花</Badge>
                <Badge variant="outline">抠图</Badge>
                <Badge variant="outline">无缝</Badge>
                <Badge variant="outline">复古</Badge>
                <Badge variant="outline">波西米亚</Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 右侧主内容区 */}
        <div className="lg:col-span-3 space-y-6">
          {/* 工具栏 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input placeholder="搜索图片..." className="pl-10 w-64" />
              </div>
              <Button variant="outline" size="sm">
                <Filter className="w-4 h-4 mr-2" />
                筛选
              </Button>
              <Button variant="outline" size="sm">
                <Tag className="w-4 h-4 mr-2" />
                标签
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {selectedImages.length > 0 && `已选择 ${selectedImages.length} 个`}
              </span>
              <div className="flex border rounded-lg">
                <Button
                  variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('grid')}
                >
                  <Grid3X3 className="w-4 h-4" />
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('list')}
                >
                  <List className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>

          {/* 批量操作工具栏 */}
          {selectedImages.length > 0 && (
            <div className="flex items-center gap-3 p-4 bg-muted rounded-lg">
              <span className="font-medium">批量操作:</span>
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                下载
              </Button>
              <Button variant="outline" size="sm">
                <Tag className="w-4 h-4 mr-2" />
                添加标签
              </Button>
              <Button variant="outline" size="sm">
                <Folder className="w-4 h-4 mr-2" />
                移动到
              </Button>
              <Button variant="outline" size="sm">
                <Trash2 className="w-4 h-4 mr-2" />
                删除
              </Button>
            </div>
          )}

          {/* 图片展示区 */}
          <Tabs defaultValue="all" className="w-full">
            <TabsList>
              <TabsTrigger value="all">全部图片</TabsTrigger>
              <TabsTrigger value="recent">最近添加</TabsTrigger>
              <TabsTrigger value="starred">收藏</TabsTrigger>
              <TabsTrigger value="uncategorized">未归类</TabsTrigger>
            </TabsList>

            <TabsContent value="all" className="mt-6">
              {loading ? (
                <div className="flex justify-center py-12">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
                    <p className="text-muted-foreground">加载图片库中...</p>
                  </div>
                </div>
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                  {images.map((image) => (
                    <Card
                      key={image.id}
                      className={`group cursor-pointer transition-all hover:shadow-md ${
                        selectedImages.includes(image.id) ? 'ring-2 ring-primary' : ''
                      }`}
                    >
                      <CardContent className="p-0">
                        <div
                          className="relative aspect-square bg-muted rounded-t-lg overflow-hidden"
                          onClick={() => toggleImageSelection(image.id)}
                        >
                          <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                            <Image className="w-12 h-12 text-white opacity-50" />
                          </div>

                          {/* 选择状态 */}
                          <div className="absolute top-2 left-2">
                            <div
                              className={`w-4 h-4 rounded border-2 ${
                                selectedImages.includes(image.id)
                                  ? 'bg-primary border-primary'
                                  : 'bg-white border-gray-300'
                              }`}
                            >
                              {selectedImages.includes(image.id) && (
                                <div className="w-full h-full flex items-center justify-center">
                                  <div className="w-2 h-2 bg-white rounded-full"></div>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* 收藏状态 */}
                          {image.starred && (
                            <div className="absolute top-2 right-2">
                              <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                            </div>
                          )}

                          {/* 操作按钮 */}
                          <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="secondary" size="sm">
                                  <MoreHorizontal className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent>
                                <DropdownMenuItem>
                                  <Eye className="mr-2 h-4 w-4" />
                                  预览
                                </DropdownMenuItem>
                                <DropdownMenuItem>
                                  <Download className="mr-2 h-4 w-4" />
                                  下载
                                </DropdownMenuItem>
                                <DropdownMenuItem>
                                  <Copy className="mr-2 h-4 w-4" />
                                  复制
                                </DropdownMenuItem>
                                <DropdownMenuItem>
                                  <Edit className="mr-2 h-4 w-4" />
                                  编辑
                                </DropdownMenuItem>
                                <DropdownMenuItem className="text-red-600">
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  删除
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>

                        <div className="p-3">
                          <h4 className="font-medium text-sm truncate">{image.name}</h4>
                          <div className="flex items-center justify-between mt-2">
                            <Badge variant="outline" className="text-xs">
                              {image.category}
                            </Badge>
                            <span className="text-xs text-muted-foreground">{image.size}</span>
                          </div>
                          <div className="flex items-center gap-2 mt-2">
                            <Clock className="w-3 h-3 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">{image.created}</span>
                          </div>
                          <div className="flex flex-wrap gap-1 mt-2">
                            {image?.tags?.map((tag: string) => (
                              <Badge
                                key={tag}
                                variant="secondary"
                                className="text-xs whitespace-normal break-words max-w-full"
                              >
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {images.map((image) => (
                    <Card
                      key={image.id}
                      className={`cursor-pointer transition-all hover:shadow-sm ${
                        selectedImages.includes(image.id) ? 'ring-2 ring-primary' : ''
                      }`}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-center gap-4">
                          <div
                            className="w-4 h-4 rounded border-2 cursor-pointer"
                            onClick={() => toggleImageSelection(image.id)}
                          >
                            {selectedImages.includes(image.id) && (
                              <div className="w-full h-full bg-primary rounded-sm"></div>
                            )}
                          </div>

                          <div className="w-12 h-12 bg-muted rounded flex items-center justify-center">
                            <Image className="w-6 h-6 text-muted-foreground" />
                          </div>

                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium truncate">{image.name}</h4>
                            <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                              <span>{image.size}</span>
                              <span>{image.created}</span>
                              <Badge variant="outline" className="text-xs">
                                {image.category}
                              </Badge>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {image.starred && (
                              <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                            )}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm">
                                  <MoreHorizontal className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent>
                                <DropdownMenuItem>
                                  <Eye className="mr-2 h-4 w-4" />
                                  预览
                                </DropdownMenuItem>
                                <DropdownMenuItem>
                                  <Download className="mr-2 h-4 w-4" />
                                  下载
                                </DropdownMenuItem>
                                <DropdownMenuItem>
                                  <Edit className="mr-2 h-4 w-4" />
                                  编辑信息
                                </DropdownMenuItem>
                                <DropdownMenuItem className="text-red-600">
                                  <Trash2 className="mr-2 h-4 w-4" />
                                  删除
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="recent">
              <div className="text-center py-12">
                <Clock className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-medium mb-2">最近添加的图片</h3>
                <p className="text-muted-foreground">显示最近7天内添加的图片</p>
              </div>
            </TabsContent>

            <TabsContent value="starred">
              <div className="text-center py-12">
                <Star className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-medium mb-2">收藏的图片</h3>
                <p className="text-muted-foreground">显示您标记为收藏的图片</p>
              </div>
            </TabsContent>

            <TabsContent value="uncategorized">
              <div className="text-center py-12">
                <Folder className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                <h3 className="text-lg font-medium mb-2">未归类图片</h3>
                <p className="text-muted-foreground">需要分类整理的图片</p>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* 图片预览对话框 */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{previewImage?.name}</DialogTitle>
            <DialogDescription>查看图片详情和相关信息</DialogDescription>
          </DialogHeader>
          {previewImage && (
            <div className="space-y-4">
              <div className="relative w-full aspect-square rounded-lg overflow-hidden border bg-muted">
                {previewImage.url ? (
                  <img
                    src={previewImage.url}
                    alt={previewImage.name}
                    className="w-full h-full object-contain"
                  />
                ) : (
                  <div className="w-full h-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                    <Image className="w-24 h-24 text-white opacity-50" />
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">尺寸</p>
                  <p className="font-medium">{previewImage.size}</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">创建时间</p>
                  <p className="font-medium">{previewImage.created}</p>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">分类</p>
                  <Badge>{previewImage.category}</Badge>
                </div>
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">格式</p>
                  <p className="font-medium">{previewImage.type}</p>
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">标签</p>
                <div className="flex flex-wrap gap-2">
                  {previewImage.tags.map((tag: string) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className="whitespace-normal break-words max-w-full"
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <Button className="flex-1">
                  <Download className="w-4 h-4 mr-2" />
                  下载
                </Button>
                <Button variant="outline" className="flex-1">
                  <Edit className="w-4 h-4 mr-2" />
                  编辑信息
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
