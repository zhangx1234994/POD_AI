import React from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';

export const SubmitTipAlert: React.FC<{ className?: string }> = ({ className }) => {
  return (
    <div className="mt-4">
      <Alert className={`${className || ''} border px-4 py-3 text-sm grid text-card-foreground border-muted bg-muted/20`}>
        <Info className="w-4 h-4 text-muted-foreground mr-2" />
        <AlertDescription className="text-muted-foreground col-start-2 grid justify-items-start gap-1 text-sm">
            💡 提交后可在右下角气泡查看任务进度和结果
        </AlertDescription>
      </Alert>
    </div>
  );
};

export default SubmitTipAlert;
