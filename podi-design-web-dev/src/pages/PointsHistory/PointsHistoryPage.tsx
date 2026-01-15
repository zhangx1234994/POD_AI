import React from 'react';
import { PointsOverview } from './PointsOverview';
import { PointsFilterBar } from './PointsFilterBar';
import { PointsSummary } from './PointsSummary';

export const PointsHistoryPage: React.FC = () => {
  return (
    <div className="p-6 space-y-4 min-w-[460px]">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            积分中心
          </h1>
          <p className="text-muted-foreground text-sm mt-1">管理和监控所有积分变动明细</p>
        </div>
      </div>
      <PointsOverview />
      <PointsFilterBar />
      <PointsSummary />
    </div>
  );
};

export default PointsHistoryPage;
