import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import type { PointsRecord } from '@/types/points';
import { Button } from '@/components/ui/button';
import { Row } from '@/components/ui';
import { OPERATOR_LABELS, POINT_CHANGE_LABELS, POINT_TYPE_LABELS } from '@/constants/points';
import { formatSigned } from '@/utils/points';

interface Props {
  open: boolean;
  item?: PointsRecord | null;
  onClose: () => void;
}

export const PointsRecordDetail: React.FC<Props> = ({ open, item, onClose }) => {
  if (!item) return null;

  const operatorId = item.operatorId ?? item.operator_id;
  const operatorLabel = operatorId ? (OPERATOR_LABELS[String(operatorId)] ?? item.operatorName ?? String(operatorId)) : (item.operatorName ?? null);

  const changeKey = String(item.changeType ?? item.change_type ?? '');
  const changeTypeText = POINT_CHANGE_LABELS[changeKey]?.text ?? (changeKey || undefined);
  const pointsKey = String(item.pointsType ?? item.point_type ?? '');
  const pointsTypeText = POINT_TYPE_LABELS[pointsKey]?.text ?? (pointsKey || undefined);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>积分记录详情</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">

          <div className="pt-2 space-y-2">
            <Row label="交易ID" value={item.transactionId ?? item.transaction_id} />
            <Row label="创建时间" value={item.createdTime ?? item.created_time ?? item.time ?? item.created_at} />
            <Row label="交易类型" value={changeTypeText} />
            <Row label="积分类型" value={pointsTypeText} />
            <Row label="变动原因" value={item.remarks ?? item.changeReason ?? item.note ?? undefined} />
            <Row label="任务" value={item.taskId ?? item.task_id ?? item.task_name ?? undefined} />
            <Row label="关联子任务ID" value={item.subTaskId ?? item.sub_task_id ?? undefined} />

            <Row label="临时积分变化量" value={formatSigned(item.tempChange ?? item.temp_change)} />
            <Row label="变化前临时积分" value={formatSigned(item.beforeTempPoints ?? item.before_temp_points)} />
            <Row label="变化后临时积分" value={formatSigned(item.afterTempPoints ?? item.after_temp_points)} />

            <Row label="充值积分变化量" value={formatSigned(item.rechargeChange ?? item.recharge_change)} />
            <Row label="变化前充值积分" value={formatSigned(item.beforeRechargePoints ?? item.before_recharge_points)} />
            <Row label="变化后充值积分" value={formatSigned(item.afterRechargePoints ?? item.after_recharge_points)} />

            <Row label="操作员" value={operatorLabel ?? undefined} />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={onClose}>关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PointsRecordDetail;
