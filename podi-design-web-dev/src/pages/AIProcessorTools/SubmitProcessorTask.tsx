import { Button } from '@/components/ui/button';
import { Sparkles, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import type { ImageItem } from '@/types/upload';
import { useState } from 'react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { ACTION_TO_SUBMIT_LABEL } from '@/constants/task';

interface Props {
  onSubmit?: () => Promise<void> | void;
  onReset?: () => void;
  canSubmit: boolean;
  isSubmitting: boolean;
  /** Action id for this task (e.g. 'hires', 'fission', 'pattern-extract', 'seamless', 'extend' or localized names).
   * SubmitProcessorTask will map this action to a human-friendly submit label.
   */
  action: string;
  // setters used by the presentational component for a minimal fallback reset
  setUploadedImages: (imgs: ImageItem[]) => void;
  setDescription?: (v: string) => void;
  setCategory?: (c: string) => void;
  setImageSize?: (s: string) => void;
}

export function SubmitProcessorTask(props: Props) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  const doReset = () => {
    if (props.onReset) {
      props.onReset();
      return;
    }

    // fallback minimal reset behavior
    props.setUploadedImages([]);
    props.setDescription?.('');
    props.setCategory?.('');
    props.setImageSize?.('');
    toast.success('页面已重置');
  };

  const handleResetClick = () => {
    // open confirmation dialog
    setConfirmOpen(true);
  };

  const handleConfirm = () => {
    doReset();
    setConfirmOpen(false);
  };

  const internalHandleSubmit = async () => {
    // Minimal fallback: show an error asking page to provide handler
    toast.error('请在页面层提供 onSubmit 处理函数以提交任务');
  };

  const getSubmitLabel = () => {
    const input = props.action?.toString().trim();
    if (!input) return '提交任务';
    return ACTION_TO_SUBMIT_LABEL[input] ?? input;
  };


  return (
    <div className="flex gap-2">
      <Button
        className="h-12 flex-1 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 shadow-md"
        onClick={() => (props.onSubmit ? void props.onSubmit() : void internalHandleSubmit())}
        disabled={!props.canSubmit || props.isSubmitting}
      >
        <Sparkles className="w-4 h-4 mr-2" />
        {getSubmitLabel()}
      </Button>

      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            className="h-12"
            variant="outline"
            onClick={handleResetClick}
          >
            <RotateCcw className="w-4 h-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent
          className="bg-white border-gray-200 p-2 shadow-md overflow-auto"
          showArrow={false}
          sideOffset={8}
        >
            清空当前页面内容并重置
        </TooltipContent>
      </Tooltip>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent aria-label="确认重置">
          <DialogHeader>
            <DialogTitle>确认重置</DialogTitle>
            <div className="mt-4 text-sm text-muted-foreground">确定要清空当前页面内容并重置吗？此操作无法撤销。</div>
          </DialogHeader>
          <DialogFooter>
            <div className="flex gap-2 justify-end w-full">
              <Button variant="outline" onClick={() => setConfirmOpen(false)}>取消</Button>
              <Button className="ml-2" onClick={handleConfirm}>重置</Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SubmitProcessorTask;
