import * as React from 'react';

/**
 * A visually hidden component that hides content from sighted users but keeps it accessible to screen readers.
 */
const VisuallyHidden: React.FC<React.HTMLAttributes<HTMLSpanElement>> = ({
  children,
  ...props
}) => {
  return (
    <span
      className="
        visually-hidden
        sr-only
        absolute
        w-px
        h-px
        p-0
        m-0
        overflow-hidden
        clip: rect(0, 0, 0, 0)
        white-space: nowrap
        border: 0
      "
      style={{
        position: 'absolute',
        width: '1px',
        height: '1px',
        padding: 0,
        margin: '-1px',
        overflow: 'hidden',
        clip: 'rect(0, 0, 0, 0)',
        whiteSpace: 'nowrap',
        border: 0,
      }}
      {...props}
    >
      {children}
    </span>
  );
};

export { VisuallyHidden };
