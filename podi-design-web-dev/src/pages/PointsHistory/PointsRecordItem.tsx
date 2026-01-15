import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { POINT_CHANGE_LABELS, OPERATOR_LABELS } from '@/constants/points';
import { formatSigned } from '@/utils/points';
import { TrendingDown, TrendingUp } from 'lucide-react';
import type { PointsRecord } from '@/types/points';

export interface PointsRecordItemProps {
  item: PointsRecord;
  onOpen?: (item: PointsRecord) => void;
  className?: string;
}

const PointsRecordItemInner: React.FC<PointsRecordItemProps> = ({ item, onOpen, className }) => {
  const handleClick = () => {
    onOpen?.(item);
  };

  const navigate = useNavigate();

  const handleTaskBadgeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const tid = item.taskId ?? item.task_id;
    if (tid) navigate(`/task-detail/${tid}`);
  };

  // support both old and new field names; normalize changeType to string for label lookup
  const changeKey = String(item.changeType ?? item.change_type ?? '');
  const changeLabel = POINT_CHANGE_LABELS[changeKey] ?? { text: String(item.changeType ?? item.change_type ?? ''), background: 'bg-gray-50' };

  const operatorId = item.operatorId ?? item.operator_id;
  const operatorLabel = operatorId ? (OPERATOR_LABELS[String(operatorId)] ?? item.operatorName ?? String(operatorId)) : (item.operatorName ?? null);

  // prefer `afterTempPoints`/`after_temp_points` and `afterRechargePoints`/`after_recharge_points`;
  const rawTemp = item.afterTempPoints ?? item.after_temp_points ?? item.tempChange ?? item.temp_change;
  const rawRecharge = item.afterRechargePoints ?? item.after_recharge_points ?? item.rechargeChange ?? item.recharge_change;
  const hasTemp = rawTemp != null;
  const hasRecharge = rawRecharge != null;
  const tempChangeNum = hasTemp ? Number(rawTemp) : 0;
  const rechargeChangeNum = hasRecharge ? Number(rawRecharge) : 0;
  const totalChangeNum = (hasTemp || hasRecharge) ? (tempChangeNum + rechargeChangeNum) : null;

  // use shared formatSigned util; pass '-' as missing placeholder for item display
  const formatChange = (val: number | null, present: boolean) => {
    return formatSigned(present ? val : undefined, '-');
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
      className={`flex flex-1 items-center justify-between px-6 py-4 border-b cursor-pointer ${className || ''}`}
    >
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <Badge className={`${changeLabel.background} text-xs`}>
            {changeLabel.text || (changeKey === '1' ? '获得' : changeKey === '2' ? '消耗' : changeKey)}
          </Badge>
          <div className="text-xs text-muted-foreground">{item.createdTime ?? item.created_time ?? item.time ?? item.created_at}</div>

          {(item.taskId ?? item.task_id) && (
            <Badge
              asChild={false}
              variant="outline"
              title={`查看任务 ${item.taskId ?? item.task_id}`}
              role="button"
              tabIndex={0}
              onClick={handleTaskBadgeClick}
              className="bg-card text-xs cursor-pointer px-2 py-0.5 rounded-md hover:bg-primary/90 hover:text-white hover:shadow-md dark:hover:bg-primary/70 dark:hover:text-white dark:hover:shadow-lg transition-colors"
            >{`任务ID: ${item.taskId ?? item.task_id}`}</Badge>
          )}

          {operatorLabel && (
            <Badge variant="outline" className="bg-card text-xs">{operatorLabel}</Badge>
          )}
        </div>

        {(item.remarks || item.changeReason) && (
          <div className="text-sm font-medium mt-2 break-all break-words whitespace-pre-wrap max-w-full">{item.remarks ?? item.changeReason}</div>
        )}

        <div className="text-xs text-muted-foreground mt-2 flex items-center gap-4">
          <span>临时积分：{formatChange(hasTemp ? tempChangeNum : null, hasTemp)}</span>
          <span>充值积分：{formatChange(hasRecharge ? rechargeChangeNum : null, hasRecharge)}</span>
          <span>总计：{totalChangeNum != null ? (totalChangeNum > 0 ? `+${totalChangeNum}` : `${totalChangeNum}`) : '-'}</span>
        </div>
      </div>
      <div className="ml-4 text-right">
          <div className="flex items-center justify-end gap-2">
            {(() => {
              const temp = Number(item.tempChange ?? item.temp_change);
              if (temp < 0) {
                return (
                  <div className="flex items-center text-red-600">
                    <TrendingDown className="w-5 h-5 text-red-600" />
                    <div className="text-lg font-semibold ml-2">{temp}</div>
                  </div>
                );
              }
              return (
                <div className="flex items-center text-green-600">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                  <div className="text-lg font-semibold ml-2">{`+${temp}`}</div>
                </div>
              );
            })()}
          </div>
        </div>
    </div>
  );
};

export const PointsRecordItem = React.memo(PointsRecordItemInner);
export default PointsRecordItem;
