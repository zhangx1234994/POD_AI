import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CheckCircle2 } from 'lucide-react';
interface Props {
  open: boolean;
  taskId?: string | undefined;
  toolName?: string;
  onOpenChange?: (open: boolean) => void;
  onViewTask?: (taskId?: string) => void;
  onContinue?: () => void;
};

export function SubmitSuccessDialog({ open, taskId, onOpenChange, onViewTask, onContinue }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto" />
        </DialogHeader>
        <div className="space-y-6">
          <div className="text-center">
            <p className="text-xs text-muted-foreground">提交任务后可在左下角任务中心查看进度</p>
          </div>
          <div className="flex gap-4">
            <Button
              className="flex-1"
              variant="outline"
              onClick={() => {
                onOpenChange?.(false);
                // Trigger the left-bottom Task Center hover popup and request a refresh
                window.dispatchEvent(
                  new CustomEvent('openTaskCenterHover', {
                    detail: {
                      taskId,
                    },
                  })
                );
                // Also trigger a refresh so the hover shows up-to-date data
                window.dispatchEvent(
                  new CustomEvent('refreshTaskList', {
                    detail: {
                      useStoredParams: false,
                      forceRefresh: true,
                      taskId,
                    },
                  })
                );
              }}
            >
              查看所有任务
            </Button>
            <Button
              className="flex-1"
              onClick={() => {
                onOpenChange?.(false);
                onContinue?.();
              }}
            >
              继续提交
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SubmitSuccessDialog;
