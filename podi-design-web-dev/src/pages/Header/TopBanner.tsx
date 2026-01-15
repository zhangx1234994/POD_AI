import React from 'react';
import { Info, CheckCircle, RefreshCw } from 'lucide-react';

type Variant = 'info' | 'success' | 'refund';

interface TopBannerProps {
  active?: boolean | null;
  children?: React.ReactNode;
  className?: string;
  variant?: Variant;
}

const VARIANT_STYLES: Record<Variant, string> = {
  info: 'bg-blue-600 text-white',
  success: 'bg-emerald-600 text-white',
  refund: 'bg-yellow-400 text-black',
};

export function TopBanner({ active, children, className = '', variant = 'info' }: TopBannerProps) {
  if (!active) return null;

  const style = VARIANT_STYLES[variant];

  const renderIcon = () => {
    if (variant === 'success') return <CheckCircle size={18} className="inline-block mr-2" />;
    if (variant === 'refund') return <RefreshCw size={18} className="inline-block mr-2" />;
    return <Info size={18} className="inline-block mr-2" />;
  };

  return (
    <div className={`fixed top-0 left-0 right-0 z-30 ${style} ${className} midnight-banner`}>
      <div className="midnight-banner-inner flex items-center justify-center">
        {renderIcon()}
        <div>{children}</div>
      </div>
    </div>
  );
};

export default TopBanner;
