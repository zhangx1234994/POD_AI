import { Info } from 'lucide-react';

interface Props {
  info?: string | null;
  desc?: string | null;
  className?: string;
  iconClassName?: string;
};

export function FeatureDescription({ info, desc, className, iconClassName }: Props) {
  const content = info ?? desc;
  if (!content) return null;

  return (
    <div className={`bg-muted/50 rounded-lg p-3 text-xs flex items-start gap-2 ${className}`}>
      <Info className={`w-4 h-4 text-muted-foreground shrink-0 ${iconClassName}`} />
      <div className="text-muted-foreground leading-relaxed">{content}</div>
    </div>
  );
};

export default FeatureDescription;
