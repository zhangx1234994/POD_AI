import React, { useCallback, useState } from 'react';
import { usePoints } from '@/contexts/PointsContext';
import { Card } from '@/components/ui/card';
import { Calendar } from 'lucide-react';
import { PointsPagination } from './PointsPagination';
import { PointsRecordItem } from './PointsRecordItem';
import { PointsRecordDetail } from './PointsRecordDetail';
import type { PointsRecord } from '@/types/points';

export const PointsSummary: React.FC = () => {
  const {
    transactionsList,
    loadingTransactions,
    total,
    page,
    setPage,
    fetchTransactions,
    changeType,
    pointsType,
    taskId,
    totalPages,
  } = usePoints();
  const displayList = transactionsList || [];

  const [selected, setSelected] = useState<PointsRecord | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const handleOpen = useCallback((item: PointsRecord) => {
    setSelected(item);
    setDetailOpen(true);
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-card border rounded-md">
        <div className="space-y-3">
          {loadingTransactions ? (
            <Card className="p-12 border-0 h-48">
              <div className="text-center h-full flex flex-col justify-center items-center space-y-2">
                <span className="font-medium">加载中...</span>
              </div>
            </Card>
          ) : displayList.length === 0 ? (
            <Card className="p-12 border-0 h-48">
              <div className="text-center h-full flex flex-col justify-center items-center space-y-2">
                <Calendar className="w-16 h-16 mx-auto text-muted-foreground opacity-20" />
                <h3 className="font-medium">暂无积分变动明细</h3>
              </div>
            </Card>
          ) : (
            (displayList.map((record: PointsRecord) => (
              <PointsRecordItem key={record.transactionId} item={record} onOpen={handleOpen} />
            )))
          )}
        </div>

        <PointsPagination
          page={page}
          totalPages={totalPages}
          total={total}
          onPageChange={(p) => {
            setPage(p);
            fetchTransactions({ current: p, changeType, pointsType, taskId });
          }}
        />
      </div>

      <PointsRecordDetail open={detailOpen} item={selected} onClose={() => setDetailOpen(false)} />
    </div>
  );
};

export default PointsSummary;
