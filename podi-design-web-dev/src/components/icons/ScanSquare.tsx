import React from 'react';
import { Scan, Square } from 'lucide-react';

interface ScanSquareProps {
  size?: number; // px
  outerScale?: number;
  innerScale?: number;
  className?: string;
  strokeWidth?: number;
}

export const ScanSquare: React.FC<ScanSquareProps> = ({
  size = 16,
  outerScale = 1.12,
  innerScale = 0.62,
  className = '',
  strokeWidth = 1.6,
}) => {
  // The icon renders centered inside a square container of `size` px.
  // We position both icons absolutely at 50%/50% and translate to center,
  // then scale them independently to achieve the "scan corners outside, square inside" look.
  const styleOuter: React.CSSProperties = {
    left: '50%',
    top: '50%',
    transform: `translate(-50%, -50%) scale(${outerScale})`,
    transformOrigin: 'center',
  };
  const styleInner: React.CSSProperties = {
    left: '50%',
    top: '50%',
    transform: `translate(-50%, -50%) scale(${innerScale})`,
    transformOrigin: 'center',
  };

  return (
    <div className={className} style={{ width: size, height: size, position: 'relative' }}>
      <Scan className="absolute" strokeWidth={strokeWidth} style={styleOuter} />
      <Square className="absolute" strokeWidth={strokeWidth} style={styleInner} />
    </div>
  );
};

export default ScanSquare;
