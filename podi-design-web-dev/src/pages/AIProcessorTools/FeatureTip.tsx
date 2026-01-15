import { Info } from 'lucide-react';

interface Props {
  tip: string;
  className?: string;
};

export function FeatureTip({ tip, className }: Props) {
  return (
    <div
      className={`flex items-center rounded-lg border px-4 py-3 text-card-foreground border-blue-200 bg-blue-50 dark:bg-blue-950/20 gap-3 text-sm text-blue-700 mb-4 ${className ?? ''}`}
      role="alert"
    >
      <Info className="w-4 h-4 flex-shrink-0" />
      <div className="text-sm text-blue-600 dark:text-blue-400">{tip}</div>
    </div>
  );
};

export default FeatureTip;
