import type { TaskItem } from '../types';

type Status = TaskItem['status'];

const labelMap: Record<Status, string> = {
  idle: '待开始',
  queued: '排队中',
  running: '处理中',
  success: '已完成',
  failed: '失败',
};

export default function StatusPill({ status }: { status: Status }) {
  return <span className={`client-status client-status--${status}`}>{labelMap[status]}</span>;
}
