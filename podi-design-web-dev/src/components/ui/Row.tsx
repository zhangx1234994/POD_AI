import React from 'react';

interface RowProps {
  label: string;
  value?: React.ReactNode;
  className?: string;
  /**
   * 可选的标签宽度。可以传入 Tailwind 宽度类（例如 'w-36 md:w-44'），
   * 也可以传入原生 CSS 宽度值（例如 '9rem'）。如果不传，则使用
   * 由 design token 控制的默认宽度（var(--row-label-width)）。
   */
  labelWidth?: string;
  /**
   * 可选的额外类，会应用到标签元素上（用于覆盖字体/对齐等样式）。
   */
  labelClassName?: string;
}

const Row: React.FC<RowProps> = ({ label, value, className = '', labelWidth, labelClassName = '' }) => {
  if (value === undefined || value === null || value === '') return null;

  // 如果 labelWidth 看起来像 Tailwind 宽度类（以 'w-' 开头或包含 ':' 响应式前缀），
  // 则将其作为类名应用到标签上；否则把它当作原生 CSS 宽度值，通过 inline style 设置。
  const labelStyle: React.CSSProperties | undefined = labelWidth && !/^([a-z]+-)?w-/.test(labelWidth) ? { width: labelWidth } : undefined;
  const labelClassFromWidth = labelWidth && /^([a-z]+-)?w-/.test(labelWidth) ? labelWidth : '';

  return (
    <div className={`ui-row ${className}`}>
      <div className={`ui-row-label ${labelClassFromWidth} ${labelClassName}`} style={labelStyle}>{label}：</div>
      <div className="ui-row-value">{value}</div>
    </div>
  );
};

export default Row;
