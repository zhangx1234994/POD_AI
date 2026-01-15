import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Image as ImageIcon, Sparkles, Download, Clock } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

export interface UsageStatsProps {
  stats: {
    uploadedImages: number;
    generatedImages: number;
    totalProcessed: number;
    todayUsage: number;
    monthlyLimit: number;
    storageUsed: number;
    storageLimit: number;
  };
};

export function UsageStats({ stats }: UsageStatsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">上传图片</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-semibold">{stats.uploadedImages}</div>
                <p className="text-xs text-muted-foreground mt-1">总计上传</p>
              </div>
              <ImageIcon className="w-8 h-8 text-blue-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">生成图片</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-semibold">{stats.generatedImages}</div>
                <p className="text-xs text-muted-foreground mt-1">AI生成</p>
              </div>
              <Sparkles className="w-8 h-8 text-purple-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">处理次数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-semibold">{stats.totalProcessed}</div>
                <p className="text-xs text-muted-foreground mt-1">图片处理</p>
              </div>
              <Download className="w-8 h-8 text-green-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">今日使用</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-semibold">{stats.todayUsage}</div>
              </div>
              <Clock className="w-8 h-8 text-orange-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>存储使用情况</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">已使用</span>
              <span className="font-medium">{stats.storageUsed} GB / {stats.storageLimit} GB</span>
            </div>
            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all" style={{ width: `${Math.min(100, (stats.storageUsed / stats.storageLimit) * 100)}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">您已使用 {((stats.storageUsed / stats.storageLimit) * 100).toFixed(1)}% 的存储空间</p>
          </div> */}

          <Separator data-slot="separator-root" />

          <div className="space-y-2">
            <h4 className="text-sm font-medium">月度使用配额</h4>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">本月已使用</span>
              <span className="font-medium">当前测试阶段不做限制</span>
              {/* <span className="font-medium">{stats.todayUsage} / {stats.monthlyLimit} 次</span> */}
            </div>
            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <div className="bg-gradient-to-r from-green-500 to-emerald-500 h-full transition-all" style={{ width: `${Math.min(100, (0.11/ stats.monthlyLimit) * 100)}%` }} />
              {/* <div className="bg-gradient-to-r from-green-500 to-emerald-500 h-full transition-all" style={{ width: `${Math.min(100, (stats.todayUsage / stats.monthlyLimit) * 100)}%` }} /> */}
            </div>
            {/* <p className="text-xs text-muted-foreground">剩余 {stats.monthlyLimit - stats.todayUsage} 次处理配额</p> */}
            <p className="text-xs text-muted-foreground">当前测试阶段不做限制</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default UsageStats;
