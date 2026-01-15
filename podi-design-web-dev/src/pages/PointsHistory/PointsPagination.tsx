import React from 'react';
import { Button } from '@/components/ui/button';

interface Props {
  page: number;
  totalPages: number;
  total?: number;
  onPageChange: (p: number) => void;
}

export const PointsPagination: React.FC<Props> = ({ page, totalPages, total = 0, onPageChange }) => {
  const prev = () => onPageChange(Math.max(1, page - 1));
  const next = () => onPageChange(Math.min(totalPages, page + 1));

  return (
    <div className="px-6 py-4 flex flex-1 items-center justify-between">
      <div className="text-sm">共 {total} 条</div>
      <div className="flex items-center gap-3">
        <Button size="sm" variant="outline" disabled={page <= 1} onClick={prev}>
          上一页
        </Button>
        <div className="text-sm">第 {page} / {totalPages} 页</div>
        <Button size="sm" disabled={page >= totalPages} onClick={next}>
          下一页
        </Button>
      </div>
    </div>
  );
};

export default PointsPagination;
