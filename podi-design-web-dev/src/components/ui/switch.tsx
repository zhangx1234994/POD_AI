// src/components/ui/Switch.tsx
import * as React from 'react';
import * as SwitchPrimitives from '@radix-ui/react-switch';
import { cva, type VariantProps } from 'class-variance-authority';

// 使用 class-variance-authority 定义变体（可选，也可直接写 className）
const switchThumbVariants = cva(
  'block rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out transform',
  {
    variants: {
      size: {
        default: 'h-6 w-6 data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0',
        sm: 'h-4 w-4 data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0',
        lg: 'h-8 w-8 data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0',
      },
    },
    defaultVariants: {
      size: 'default',
    },
  }
);

const switchTrackVariants = cva(
  'peer inline-flex shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
  {
    variants: {
      size: {
        default: 'h-8 w-14',
        sm: 'h-6 w-10',
        lg: 'h-10 w-14',
      },
    },
    defaultVariants: {
      size: 'default',
    },
  }
);

export interface SwitchProps
  extends React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>,
    VariantProps<typeof switchTrackVariants> {
  /**
   * 是否显示右侧标签
   */
  label?: string;
  /**
   * 标签位置（默认右侧）
   */
  labelPosition?: 'left' | 'right';
  /**
   * 可选的描述文本，显示在 `label` 下方
   */
  description?: React.ReactNode;
}

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  SwitchProps
>(({ className, size, label, labelPosition = 'right', description, ...props }, ref) => {
  const uid = React.useId();
  const descId = description ? `${uid}-switch-desc` : undefined;
  const labelJsx = label ? (
    <div className="flex flex-col">
      <span className="text-sm text-foreground">{label}</span>
      {description ? (
        <span id={descId} className="text-xs text-muted-foreground mt-0.5">{description}</span>
      ) : null}
    </div>
  ) : null;

  return (
    <div className="flex items-start gap-2">
      {label && labelPosition === 'left' && labelJsx}
      <SwitchPrimitives.Root
        className={`${switchTrackVariants({ size, className })} ${size ? `size-${size}` : ''}`}
        aria-describedby={descId}
        {...props}
        ref={ref}
      >
        <SwitchPrimitives.Thumb
          className={switchThumbVariants({ size })}
        />
      </SwitchPrimitives.Root>
      {label && labelPosition === 'right' && labelJsx}
    </div>
  );
});

Switch.displayName = 'Switch';

export { Switch };