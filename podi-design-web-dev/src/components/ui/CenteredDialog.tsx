'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { XIcon } from 'lucide-react';
import { cn } from './utils';
import { VisuallyHidden } from './visually-hidden';

export type CenteredDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children?: React.ReactNode;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  allowOutsideClick?: boolean; // clicking overlay to close
  showCloseButton?: boolean;
  width?: string; // css width, default '200px'
  height?: string; // css height, default '200px'
};

export function CenteredDialog({
  open,
  onOpenChange,
  children,
  header,
  footer,
  className,
  allowOutsideClick = true,
  showCloseButton = true,
  width = '200px',
  height = '200px',
}: CenteredDialogProps) {
  const headerHeight = '48px';
  const footerHeight = '48px';

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn('fixed inset-0 z-50 bg-black/50')}
        />

        <DialogPrimitive.Content
          data-slot="centered-dialog-content"
          // center the panel
          className={cn(
            'fixed top-[50%] left-[50%] z-50 translate-x-[-50%] translate-y-[-50%] bg-background rounded-lg shadow-lg overflow-visible',
            className
          )}
          style={{ width, height }}
          // prevent closing when clicking outside if not allowed
          onPointerDownOutside={(e) => {
            if (!allowOutsideClick) e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (!allowOutsideClick) e.preventDefault();
          }}
        >
          {/* set CSS vars on the content element so children can reference header/footer heights */}
          <div
            className="relative w-full h-full"
            style={{ ['--dialog-header-h' as any]: headerHeight, ['--dialog-footer-h' as any]: footerHeight }}
          >
            {/* Header - fixed inside the panel */}
            <div
              className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 pt-6 z-50"
              style={{ height: headerHeight }}
            >
              <div className="flex-1">
                {header ?? <span className="text-base font-medium">Dialog</span>}
              </div>

              {showCloseButton && (
                <DialogPrimitive.Close className="ml-4 z-50 w-6 h-6 flex items-center justify-center rounded-xs opacity-80 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-offset-2">
                  <XIcon />
                  <span className="sr-only">Close</span>
                </DialogPrimitive.Close>
              )}
            </div>

            {/* Content area: padding and scrollable area that does not move header/footer */}
            <div
              className="px-6"
              style={{ paddingTop: headerHeight, paddingBottom: footerHeight, height: '100%' }}
            >
              <div className="w-full h-full overflow-y-auto ">
                {children}
              </div>
            </div>

            {/* Footer - fixed at bottom inside the panel */}
            <div className="absolute bottom-0 left-0 right-0 px-6 pb-6 z-50" style={{ height: footerHeight }}>
              {footer}
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
};

export default CenteredDialog;
