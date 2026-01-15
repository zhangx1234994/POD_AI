import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Row } from '@/components/ui';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  imagesCount: number;
  perImageCost: number;
  currentPoints: number;
  totalPointsCost: number;
  onConfirm?: () => void;
}

export const PointsPreviewDialog: React.FC<Props> = ({ open, onOpenChange, imagesCount, perImageCost, currentPoints, totalPointsCost, onConfirm }) => {
  const remaining = currentPoints - totalPointsCost;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="提交前预览" className="border-0">
        <DialogHeader>
          <DialogTitle>本次任务</DialogTitle>
          <DialogDescription>请确认任务消耗与剩余积分</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="bg-card border rounded-md p-4 space-y-2">
            <Row label="生成图片数量" value={<><strong>{imagesCount}</strong> 张</>} labelWidth="w-30" />
            <Row label="每张消耗" value={<><strong>{perImageCost}</strong> 积分</>} labelWidth="w-30" />
            <Row label="总计消耗" value={<><strong>{totalPointsCost}</strong> 积分</>} labelWidth="w-30" />
          </div>

          <div className="bg-card border rounded-md p-4 space-y-2">
            <Row label="您当前拥有" value={<><strong>{currentPoints}</strong> 积分</>} labelWidth="w-30" />
            <Row label="消耗后剩余" value={<><strong>{remaining}</strong> 积分</>} labelWidth="w-30" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button className="ml-2" onClick={() => { onConfirm?.(); onOpenChange(false); }}>开始处理</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PointsPreviewDialog;
