import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { CheckCircle, RotateCcw } from 'lucide-react';

interface SuccessDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  taskId?: string;
  autoCloseDelay?: number; // 默认3秒自动关闭
  showContinueButton?: boolean;
  onContinue?: () => void;
  onDownload?: () => void;
  showDownloadButton?: boolean;
}

export const SuccessDialog: React.FC<SuccessDialogProps> = ({
  open,
  onOpenChange,
  title = '任务已提交',
  description = '您的任务已成功提交，正在处理中，请稍候...',
  taskId,
  autoCloseDelay = 3000,
  showContinueButton = true,
  onContinue,
  onDownload,
  showDownloadButton = false,
}) => {
  const [countdown, setCountdown] = useState<number>(Math.floor(autoCloseDelay / 1000));
  const [autoCloseEnabled, setAutoCloseEnabled] = useState<boolean>(true);

  useEffect(() => {
    if (!open || !autoCloseEnabled) {
      setCountdown(Math.floor(autoCloseDelay / 1000));
      return;
    }

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          onOpenChange(false);
          return Math.floor(autoCloseDelay / 1000);
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [open, autoCloseDelay, autoCloseEnabled, onOpenChange]);

  const handleContinue = () => {
    if (onContinue) {
      onContinue();
    }
    onOpenChange(false);
  };

  const handleDownload = () => {
    if (onDownload) {
      onDownload();
    }
  };

  const handleManualClose = () => {
    setAutoCloseEnabled(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleManualClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            {title}
          </DialogTitle>
          <DialogDescription>
            {taskId ? `任务ID: ${taskId}，${description}` : description}
          </DialogDescription>
        </DialogHeader>

        {autoCloseEnabled && (
          <div className="text-center text-sm text-muted-foreground">{countdown}秒后自动关闭</div>
        )}

        <div className="flex gap-2 mt-4">
          {showDownloadButton && (
            <Button onClick={handleDownload} className="flex-1">
              下载结果
            </Button>
          )}
          {showContinueButton && (
            <Button onClick={handleContinue} variant="outline" className="flex-1">
              <RotateCcw className="w-4 h-4 mr-1" />
              继续提交
            </Button>
          )}
          <Button onClick={handleManualClose} variant="outline">
            关闭
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default SuccessDialog;
