import React from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { CheckSquare, X, Download, Trash2 } from 'lucide-react';

export type BatchToolbarProps = {
  selectedCount: number;
  visibleIds: string[];
  selectedIds: string[];
  onExit: () => void;
  onSelectAllVisible: () => void;
  onBatchDownload: () => void;
  onBatchDelete: () => void;
};

export const BatchToolbar: React.FC<BatchToolbarProps> = ({
  selectedCount,
  visibleIds,
  selectedIds,
  onExit,
  onSelectAllVisible,
  onBatchDownload,
  onBatchDelete,
}) => {
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  return (
    <div className="flex items-center justify-between p-3 bg-primary/10 rounded-lg border border-primary/20 mb-4">
      <div className="flex items-center gap-2">
        <CheckSquare className="w-4 h-4 text-primary" />
        <span className="text-sm font-medium">已选择 {selectedCount} 张图片</span>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={onExit}>
          <X className="w-4 h-4 mr-1" /> 退出
        </Button>
        {allVisibleSelected ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onSelectAllVisible}
            disabled={visibleIds.length === 0}
          >
            取消全选
          </Button>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                onClick={onSelectAllVisible}
                disabled={visibleIds.length === 0}
              >
                全选
              </Button>
            </TooltipTrigger>
            <TooltipContent
              sideOffset={4}
              side="top"
              align="center"
              showArrow={false}
              className="bg-white text-foreground border border-border shadow-sm"
            >
              仅选中当前已加载的可见图片，未加载内容不包括在内
            </TooltipContent>
          </Tooltip>
        )}
        <Button variant="outline" size="sm" onClick={onBatchDownload} disabled={selectedCount === 0}>
          <Download className="w-4 h-4 mr-1" /> 下载
        </Button>
        <Button variant="destructive" size="sm" onClick={onBatchDelete} disabled={selectedCount === 0}>
          <Trash2 className="w-4 h-4 mr-1" /> 删除
        </Button>
      </div>
    </div>
  );
};

export default BatchToolbar;
