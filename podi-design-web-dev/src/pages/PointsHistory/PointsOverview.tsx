import React from 'react';
import { usePoints } from '@/contexts/PointsContext';
import { Badge } from '@/components/ui/badge';

export const PointsOverview: React.FC = () => {
  const { pointsStatistics } = usePoints();

  const stats = pointsStatistics?.data ?? pointsStatistics ?? {};
  const consumed = stats?.monthlyConsumption ?? stats?.monthly_consumption ?? 0;
  const gained = stats?.monthlyGain ?? stats?.monthly_gain ?? 0;

  return (
    <div className="bg-card border rounded-md p-6">
      <div className="grid grid-cols-4 gap-4 items-start">
        <div>
          <div className="text-sm text-muted-foreground text-center">当前总积分</div>
          <div className="text-3xl font-bold mt-2 text-center">{stats?.totalPoints ?? stats?.total ?? 0}</div>
        </div>

        <div>
          <div className="text-sm text-muted-foreground text-center">临时积分</div>
          <div className="mt-2 text-center">
            <div className="text-3xl font-semibold text-purple-600">{stats?.tempPoints ?? stats?.temp ?? 0}</div>
              <Badge variant="outline" className="bg-card">次日清零</Badge>
          </div>
        </div>

        <div>
          <div className="text-sm text-muted-foreground text-center">充值积分</div>
          <div className="mt-2 text-center">
            <div className="text-3xl font-semibold text-blue-600">{stats?.rechargePoints ?? stats?.recharge ?? 0}</div>
            <Badge variant="outline" className="bg-card">永久有效</Badge>
          </div>
        </div>

        <div className="flex flex-col items-center">
          <div className="text-sm text-muted-foreground text-center">本月累计</div>
          <div className="mt-2 flex flex-col items-start gap-1 text-sm w-max mx-auto">
            <div className="flex items-center justify-start">
              <div className="text-sm">消耗</div>
              <div className="ml-2 text-sm text-red-600 font-semibold">{consumed}</div>
            </div>
            <div className="flex items-center justify-start">
              <div className="text-sm">获得</div>
              <div className="ml-2 text-sm text-green-600 font-semibold">{gained}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PointsOverview;
