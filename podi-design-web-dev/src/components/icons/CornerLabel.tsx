interface CornerLabelProps {
  /** 
   * 'result' -> 结果图 (绿色背景, 白色文字)
   * 'original' -> 原图 (灰色背景, 黑色文字)
   */
  variant?: 'result' | 'original';
  /** 可选：覆盖默认文字 */
  text?: string;
  /** 可选：覆盖默认背景色 */
  bg?: string;
  className?: string;
  /** 角标位置: top-left | top-right */
  corner?: 'top-left' | 'top-right';
};

export function CornerLabel({
  variant = 'result',
  text,
  bg,
  className = '',
  corner = 'top-left',
}: CornerLabelProps) {
  // 配置映射
  const config = {
    result: {
      defaultText: '结果图',
      defaultBg: '#4CD964', // Bright green
      textColor: '#FFFFFF',
    },
    original: {
      defaultText: '原图',
      defaultBg: '#B9B9B9', // Gray
      textColor: '#000000',
    },
  } as const;

  const currentConfig = config[variant];
  const contentText = text ?? currentConfig.defaultText;
  const backgroundColor = bg ?? currentConfig.defaultBg;
  const textColor = currentConfig.textColor;

  const isTopLeft = corner === 'top-left';

  return (
    <div 
      className={`absolute top-0 ${isTopLeft ? 'left-0' : 'right-0'} w-[72px] h-[72px] pointer-events-none z-10 overflow-hidden ${className}`}
      aria-label={contentText}
    >
      <svg
        width="72"
        height="72"
        viewBox="0 0 72 72"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* 背景：45度等腰梯形 */}
        {isTopLeft ? (
           <path d="M0 24L24 0H72L0 72V24Z" fill={backgroundColor} />
        ) : (
           <path d="M72 24L48 0H0L72 72V24Z" fill={backgroundColor} />
        )}
        
        {/* 文字：居中旋转 */}
        <text
          x={isTopLeft ? "24" : "48"}
          y="24"
          transform={isTopLeft ? "rotate(-45 24 24)" : "rotate(45 48 24)"}
          fill={textColor}
          fontFamily="Inter, ui-sans-serif, system-ui"
          fontSize="16"
          fontWeight="400"
          textAnchor="middle"
          dominantBaseline="central"
        >
          {contentText}
        </text>
      </svg>
    </div>
  );
};

export default CornerLabel;
