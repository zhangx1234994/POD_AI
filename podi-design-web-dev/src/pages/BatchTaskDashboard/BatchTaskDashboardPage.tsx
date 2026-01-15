import { BatchTaskList } from './BatchTaskList';
import { BatchTaskOverview } from './BatchTaskOverview';

export function BatchTaskDashboardPage(): JSX.Element {
  return (
    <div className="p-6 bg-gradient-to-br from-background via-background to-muted/20">
      {/* 页面标题 */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
            批量任务中心
          </h1>
          <p className="text-muted-foreground text-sm mt-1">管理和监控所有批量处理任务</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-1">
        <div className="lg:col-span-2">
          {/* 任务数据看板 */}
          <div className="mb-6">
           <BatchTaskOverview />
          </div>
          {/* 任务列表 */}
          <BatchTaskList />
        </div>
      </div>
    </div>
  );
};

export default BatchTaskDashboardPage;
