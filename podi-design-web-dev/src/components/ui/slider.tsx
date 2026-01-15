'use client';

import * as React from 'react';
import * as SliderPrimitive from '@radix-ui/react-slider';

import { cn } from './utils';

function Slider({
  className,
  defaultValue,
  value,
  min = 0,
  max = 100,
  trackClassName,
  rangeClassName,
  thumbClassName,
  style,
  trackStyle,
  rangeStyle,
  thumbStyle,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root> & {
  trackClassName?: string;
  rangeClassName?: string;
  thumbClassName?: string;
  style?: React.CSSProperties;
  trackStyle?: React.CSSProperties;
  rangeStyle?: React.CSSProperties;
  thumbStyle?: React.CSSProperties;
}) {
  const _values = React.useMemo(
    () => (Array.isArray(value) ? value : Array.isArray(defaultValue) ? defaultValue : [min, max]),
    [value, defaultValue, min, max]
  );

  return (
    <SliderPrimitive.Root
      data-slot="slider"
      defaultValue={defaultValue}
      value={value}
      min={min}
      max={max}
      className={cn(
        'relative flex w-full touch-none items-center select-none data-[disabled]:opacity-50 data-[orientation=vertical]:h-full data-[orientation=vertical]:min-h-44 data-[orientation=vertical]:w-auto data-[orientation=vertical]:flex-col',
        className
      )}
      style={style}
      {...props}
    >
      <SliderPrimitive.Track
        data-slot="slider-track"
        className={cn(
          'relative grow overflow-hidden rounded-full data-[orientation=horizontal]:h-4 data-[orientation=horizontal]:w-full data-[orientation=vertical]:h-full data-[orientation=vertical]:w-1.5 slider-track-fission',
          trackClassName
        )}
        style={{
          backgroundColor: '#F3F4F6',
          background: '#F3F4F6',
          backgroundImage: 'none',
          ...trackStyle,
        }}
      >
        <SliderPrimitive.Range
          data-slot="slider-range"
          className={cn(
            'absolute data-[orientation=horizontal]:h-full data-[orientation=vertical]:w-full',
            rangeClassName
          )}
          style={{
            backgroundColor: '#6366F1',
            ...rangeStyle,
          }}
        />
      </SliderPrimitive.Track>
      {Array.from({ length: _values.length }, (_, index) => (
        <SliderPrimitive.Thumb
          data-slot="slider-thumb"
          key={`slider-thumb-${index}-${_values[index]}`}
          className={cn(
            'block size-4 shrink-0 rounded-full border shadow-sm transition-[color,box-shadow] hover:ring-4 focus-visible:ring-4 focus-visible:outline-hidden disabled:pointer-events-none disabled:opacity-50',
            thumbClassName
          )}
          style={{
            backgroundColor: '#FFFFFF',
            borderColor: '#6366F1',
            boxShadow: '0 0 0 1px rgba(99,102,241,0.25), 0 2px 6px rgba(0,0,0,0.08)',
            ...thumbStyle,
          }}
        />
      ))}
    </SliderPrimitive.Root>
  );
}

export { Slider };
