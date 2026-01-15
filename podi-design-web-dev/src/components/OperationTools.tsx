import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { http } from '../utils/http';
import {
  Calculator,
  Database,
  Video,
  Download,
  RefreshCw,
  Plus,
  Search,
  Filter,
  ExternalLink,
  TrendingUp,
  DollarSign,
  Package,
  Globe,
} from 'lucide-react';

interface OperationToolsProps {
  activeSection: string;
}

export function OperationTools({ activeSection }: OperationToolsProps) {
  const [profit, setProfit] = useState(0);
  const [collectUrl, setCollectUrl] = useState('');
  const [collectData, setCollectData] = useState<any[]>([]);
  const [collectedProducts, setCollectedProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  // 毛利计算器数据
  const [calculatorData, setCalculatorData] = useState({
    platform: 'amazon',
    productPrice: 25.99,
    cost: 8.5,
    shipping: 3.2,
    platformFee: 15,
    returnRate: 5,
    adCost: 2.0,
  });

  // 获取采集产品数据
  const fetchCollectedProducts = async () => {
    setLoading(true);
    try {
      // 使用模拟API调用获取采集产品数据
      const response = await http.get('/api/collected-products');
      setCollectedProducts(response.data || []);
    } catch (error) {
      console.error('获取采集产品数据失败:', error);
      // 如果API调用失败，使用mock数据作为后备
      setCollectedProducts([
        {
          id: 1,
          title: 'Vintage Sunset T-Shirt',
          price: '$24.99',
          platform: 'Amazon',
          sales: '1.2K',
          rating: '4.8',
          images: 8,
          status: '已采集',
        },
        {
          id: 2,
          title: 'Minimalist Coffee Mug',
          price: '$16.99',
          platform: 'Etsy',
          sales: '856',
          rating: '4.9',
          images: 5,
          status: '已采集',
        },
        {
          id: 3,
          title: 'Boho Style Phone Case',
          price: '$19.99',
          platform: 'Shopify',
          sales: '643',
          rating: '4.7',
          images: 12,
          status: '采集中',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // 组件加载时获取采集产品数据
  useEffect(() => {
    if (activeSection === 'collect') {
      fetchCollectedProducts();
    }
  }, [activeSection]);

  // 计算毛利
  const calculateProfit = () => {
    const { productPrice, cost, shipping, platformFee, returnRate, adCost } = calculatorData;
    const platformFeeAmount = (productPrice * platformFee) / 100;
    const returnCost = (productPrice * returnRate) / 100;
    const totalCost = cost + shipping + platformFeeAmount + returnCost + adCost;
    const finalProfit = productPrice - totalCost;
    setProfit(finalProfit);
  };

  React.useEffect(() => {
    calculateProfit();
  }, [calculatorData]);

  const renderCalculator = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-green-500 flex items-center justify-center">
          <Calculator className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">毛利计算器</h1>
          <p className="text-muted-foreground">精确计算POD产品利润</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧参数设置 */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>基础参数</CardTitle>
              <CardDescription>设置产品和平台相关参数</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>销售平台</Label>
                  <Select
                    value={calculatorData.platform}
                    onValueChange={(value) =>
                      setCalculatorData({ ...calculatorData, platform: value })
                    }
                  >
                    <SelectTrigger className="mt-2">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="amazon">Amazon</SelectItem>
                      <SelectItem value="ebay">eBay</SelectItem>
                      <SelectItem value="shopify">Shopify</SelectItem>
                      <SelectItem value="etsy">Etsy</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>产品售价 ($)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.productPrice}
                    onChange={(e) =>
                      setCalculatorData({
                        ...calculatorData,
                        productPrice: parseFloat(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <Label>产品成本 ($)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.cost}
                    onChange={(e) =>
                      setCalculatorData({ ...calculatorData, cost: parseFloat(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <Label>物流费用 ($)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.shipping}
                    onChange={(e) =>
                      setCalculatorData({ ...calculatorData, shipping: parseFloat(e.target.value) })
                    }
                  />
                </div>
                <div>
                  <Label>平台手续费 (%)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.platformFee}
                    onChange={(e) =>
                      setCalculatorData({
                        ...calculatorData,
                        platformFee: parseFloat(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <Label>退货率 (%)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.returnRate}
                    onChange={(e) =>
                      setCalculatorData({
                        ...calculatorData,
                        returnRate: parseFloat(e.target.value),
                      })
                    }
                  />
                </div>
                <div>
                  <Label>广告成本 ($)</Label>
                  <Input
                    type="number"
                    className="mt-2"
                    value={calculatorData.adCost}
                    onChange={(e) =>
                      setCalculatorData({ ...calculatorData, adCost: parseFloat(e.target.value) })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>成本分析</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span>产品成本:</span>
                  <span>${calculatorData.cost.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>物流费用:</span>
                  <span>${calculatorData.shipping.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>平台手续费:</span>
                  <span>
                    ${((calculatorData.productPrice * calculatorData.platformFee) / 100).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>退货成本:</span>
                  <span>
                    ${((calculatorData.productPrice * calculatorData.returnRate) / 100).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>广告成本:</span>
                  <span>${calculatorData.adCost.toFixed(2)}</span>
                </div>
                <div className="border-t pt-2 flex justify-between font-semibold">
                  <span>总成本:</span>
                  <span>
                    $
                    {(
                      calculatorData.cost +
                      calculatorData.shipping +
                      (calculatorData.productPrice * calculatorData.platformFee) / 100 +
                      (calculatorData.productPrice * calculatorData.returnRate) / 100 +
                      calculatorData.adCost
                    ).toFixed(2)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* 右侧利润显示 */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle>利润分析</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600">${profit.toFixed(2)}</div>
                <p className="text-sm text-muted-foreground">单件毛利润</p>
              </div>

              <div className="text-center">
                <div className="text-xl font-semibold">
                  {((profit / calculatorData.productPrice) * 100).toFixed(1)}%
                </div>
                <p className="text-sm text-muted-foreground">利润率</p>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>日销10件:</span>
                  <span className="font-medium">${(profit * 10).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>月销300件:</span>
                  <span className="font-medium">${(profit * 300).toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>年销3600件:</span>
                  <span className="font-medium">${(profit * 3600).toFixed(2)}</span>
                </div>
              </div>

              <Button className="w-full">
                <Download className="w-4 h-4 mr-2" />
                导出报告
              </Button>
            </CardContent>
          </Card>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>平台对比</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-2 border rounded">
                  <span className="text-sm">Amazon</span>
                  <Badge variant="secondary">15%</Badge>
                </div>
                <div className="flex items-center justify-between p-2 border rounded">
                  <span className="text-sm">eBay</span>
                  <Badge variant="secondary">12%</Badge>
                </div>
                <div className="flex items-center justify-between p-2 border rounded">
                  <span className="text-sm">Shopify</span>
                  <Badge variant="secondary">2.9%</Badge>
                </div>
                <div className="flex items-center justify-between p-2 border rounded">
                  <span className="text-sm">Etsy</span>
                  <Badge variant="secondary">6.5%</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );

  const renderDataCollection = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-blue-500 flex items-center justify-center">
          <Database className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">数据采集</h1>
          <p className="text-muted-foreground">多平台产品数据采集系统</p>
        </div>
      </div>

      <Tabs defaultValue="single" className="w-full">
        <TabsList>
          <TabsTrigger value="single">单品采集</TabsTrigger>
          <TabsTrigger value="store">全店采集</TabsTrigger>
          <TabsTrigger value="library">产品库</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>单品链接采集</CardTitle>
              <CardDescription>输入产品链接，自动解析产品信息</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>产品链接</Label>
                <div className="flex gap-2 mt-2">
                  <Input
                    placeholder="请输入Amazon、eBay、Walmart等平台的产品链接"
                    value={collectUrl}
                    onChange={(e) => setCollectUrl(e.target.value)}
                  />
                  <Button>
                    <Search className="w-4 h-4 mr-2" />
                    采集
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 border rounded-lg">
                  <Globe className="w-8 h-8 mx-auto mb-2 text-blue-500" />
                  <p className="text-sm font-medium">Amazon</p>
                  <p className="text-xs text-muted-foreground">支持</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <Globe className="w-8 h-8 mx-auto mb-2 text-green-500" />
                  <p className="text-sm font-medium">eBay</p>
                  <p className="text-xs text-muted-foreground">支持</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <Globe className="w-8 h-8 mx-auto mb-2 text-purple-500" />
                  <p className="text-sm font-medium">Walmart</p>
                  <p className="text-xs text-muted-foreground">支持</p>
                </div>
                <div className="text-center p-4 border rounded-lg">
                  <Globe className="w-8 h-8 mx-auto mb-2 text-orange-500" />
                  <p className="text-sm font-medium">Temu</p>
                  <p className="text-xs text-muted-foreground">支持</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="store" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>批量店铺采集</CardTitle>
              <CardDescription>采集整个店铺的产品数据</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>店铺链接</Label>
                <Input placeholder="请输入店铺主页链接" className="mt-2" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>采集数量</Label>
                  <Select>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="选择采集数量" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="50">前50个产品</SelectItem>
                      <SelectItem value="100">前100个产品</SelectItem>
                      <SelectItem value="all">全部产品</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>采集模式</Label>
                  <Select>
                    <SelectTrigger className="mt-2">
                      <SelectValue placeholder="选择模式" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fast">快速模式</SelectItem>
                      <SelectItem value="detail">详细模式</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button className="w-full">
                <RefreshCw className="w-4 h-4 mr-2" />
                开始批量采集
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="library" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>采集产品库</CardTitle>
                  <CardDescription>查看已采集的产品数据</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">
                    <Filter className="w-4 h-4 mr-2" />
                    筛选
                  </Button>
                  <Button variant="outline" size="sm">
                    <Download className="w-4 h-4 mr-2" />
                    导出
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex justify-center items-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                  <span className="ml-2">加载中...</span>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>产品标题</TableHead>
                      <TableHead>价格</TableHead>
                      <TableHead>平台</TableHead>
                      <TableHead>销量</TableHead>
                      <TableHead>评分</TableHead>
                      <TableHead>图片数</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {collectedProducts.map((product) => (
                      <TableRow key={product.id}>
                        <TableCell className="font-medium">{product.title}</TableCell>
                        <TableCell>{product.price}</TableCell>
                        <TableCell>{product.platform}</TableCell>
                        <TableCell>{product.sales}</TableCell>
                        <TableCell>{product.rating}</TableCell>
                        <TableCell>{product.images}</TableCell>
                        <TableCell>
                          <Badge variant={product.status === '已采集' ? 'default' : 'secondary'}>
                            {product.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Button variant="outline" size="sm">
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );

  const renderVideoGeneration = () => (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-purple-500 flex items-center justify-center">
          <Video className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">视频生成</h1>
          <p className="text-muted-foreground">AI视频内容生成工具</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>产品展示视频</CardTitle>
            <CardDescription>生成产品360度展示视频</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-video bg-muted rounded-lg mb-4 flex items-center justify-center">
              <Video className="w-12 h-12 text-muted-foreground" />
            </div>
            <Button className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              创建展示视频
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>营销视频</CardTitle>
            <CardDescription>制作产品营销推广视频</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-video bg-muted rounded-lg mb-4 flex items-center justify-center">
              <TrendingUp className="w-12 h-12 text-muted-foreground" />
            </div>
            <Button className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              创建营销视频
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>教程视频</CardTitle>
            <CardDescription>生成产品使用教程视频</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-video bg-muted rounded-lg mb-4 flex items-center justify-center">
              <Package className="w-12 h-12 text-muted-foreground" />
            </div>
            <Button className="w-full">
              <Plus className="w-4 h-4 mr-2" />
              创建教程视频
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  // 根据当前选择的工具渲染对应内容
  switch (activeSection) {
    case 'calculator':
      return renderCalculator();
    case 'collect':
      return renderDataCollection();
    case 'video':
      return renderVideoGeneration();
    default:
      return (
        <div className="p-6 text-center">
          <h2>选择运营工具</h2>
          <p className="text-muted-foreground">请从侧边栏选择一个运营工具</p>
        </div>
      );
  }
}
