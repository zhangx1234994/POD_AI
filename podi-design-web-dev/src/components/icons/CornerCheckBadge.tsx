import { Check } from 'lucide-react';

export interface CornerCheckBadgeProps {
  size?: number;
  rounded?: number | string;
  color?: string;
  checkColor?: string;
  className?: string;
  top?: number;
  left?: number;
}

export function CornerCheckBadge({
  size = 36,
  rounded = 0.5,
  color = '#6D28D9',
  checkColor = '#fff',
  className = '',
  top = 0,
  left = 0,
}: CornerCheckBadgeProps) {
  const w = size;
  const h = size;

  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

  function mapTokenToPx(token: string | undefined, totalSize: number) {
    const rem = 16;
    const radius = 0.75 * rem; // 12px
    const radiusXs = 0.125 * rem; // 2px
    if (!token) return Math.floor(radius * 0.5);
    const t = token.replace(/^rounded-?/, '').trim();
    switch (t) {
      case 'none':
        return 0;
      case 'xs':
        return Math.floor(radiusXs);
      case 'sm':
        return Math.max(0, Math.floor(radius - 4));
      case 'md':
        return Math.max(0, Math.floor(radius - 2));
      case 'lg':
      case '':
        return Math.floor(radius);
      case 'xl':
        return Math.floor(radius + 4);
      case '2xl':
        return Math.floor(radius + 8);
      case 'full':
        return Math.floor(totalSize / 2);
      default: {
        const asPx = parseFloat(t.replace('px', ''));
        if (!Number.isNaN(asPx)) return Math.min(Math.floor(asPx), Math.floor(totalSize / 2));
        if (t.endsWith('rem')) {
          const v = parseFloat(t.replace('rem', ''));
          if (!Number.isNaN(v)) return Math.min(Math.floor(v * rem), Math.floor(totalSize / 2));
        }
        return Math.floor(radius * 0.5);
      }
    }
  }

  function numericRoundedPx(input: number | string | undefined, totalSize: number) {
    const half = Math.floor(totalSize / 2);
    if (typeof input === 'number') {
      if (input <= 1) return Math.floor(clamp01(input) * half);
      return Math.min(Math.max(0, Math.floor(input)), half);
    }
    if (typeof input === 'string') return mapTokenToPx(input, totalSize);
    return Math.floor(0.5 * half);
  }

  const roundedPx = Math.max(0, Math.min(Math.floor(numericRoundedPx(rounded, size)), Math.floor(size / 2)));

  const diagStartX = w * 0.78;
  const diagStartY = h * 0.12;
  const diagEndX = w * 0.12;
  const diagEndY = h * 0.78;

  const checkCx = w * 0.34;
  const checkCy = h * 0.28;
  const checkSize = Math.max(10, Math.round(size * 0.5));

  return (
    <div
      aria-hidden
      className={className}
      style={{ position: 'absolute', top: `${top}px`, left: `${left}px`, width: w, height: h, pointerEvents: 'none' }}
    >
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d={`M ${w} 0 L ${roundedPx} 0 A ${roundedPx} ${roundedPx} 0 0 0 0 ${roundedPx} L 0 ${h} Z`} fill={color} />

        <path d={`M ${diagStartX} ${diagStartY} L ${diagEndX} ${diagEndY}`} stroke={color} strokeWidth={Math.max(1, Math.round(size * 0.06))} strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      <div style={{ position: 'absolute', left: checkCx - checkSize / 2, top: checkCy - checkSize / 2, width: checkSize, height: checkSize, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
        <Check size={checkSize} color={checkColor} strokeWidth={2} />
      </div>
    </div>
  );
}

export default CornerCheckBadge;
