import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Row } from '@/components/ui';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  required: number;
  current: number;
  onRecharge?: () => void;
  onReduce?: () => void;
  // 新增可选字段：生成图片数量、每张消耗、总计消耗（用于在不足提示中展示）
  imagesCount?: number;
  perImageCost?: number;
  totalPointsCost?: number;
}

export const PointsInsufficientDialog: React.FC<Props> = ({ open, onOpenChange, required, current, onRecharge, imagesCount, perImageCost, totalPointsCost }) => {
  const need = Math.max(0, required - current);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="积分不足提示" className="border-0">
        <DialogHeader>
          <DialogTitle>积分余额不足</DialogTitle>
          <DialogDescription>积分余额不足，请联系管理员充值或调整任务以继续</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="bg-card border rounded-md p-4 space-y-2">
            <Row label="生成图片数量" value={<><strong>{imagesCount ?? 0}</strong> 张</>} labelWidth="w-30" />
            <Row label="每张消耗" value={<><strong>{perImageCost ?? 0}</strong> 积分</>} labelWidth="w-30" />
            <Row label="总计消耗" value={<><strong>{required ?? 0}</strong> 积分</>} labelWidth="w-30" />
          </div>
          <div className="bg-card border rounded-md p-4 space-y-2">
            <Row label="您当前拥有" value={<><strong>{current}</strong> 积分</>} labelWidth="w-30" />
            <Row label="还需要充值" value={<><strong>{need}</strong> 积分</>} labelWidth="w-30" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button disabled onClick={() => { onRecharge?.(); onOpenChange(false); }}>立即充值</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PointsInsufficientDialog;
