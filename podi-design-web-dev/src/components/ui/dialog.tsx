'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { XIcon } from 'lucide-react';

import { cn } from './utils';
import { VisuallyHidden } from './visually-hidden';

function Dialog({ ...props }: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />;
}

const DialogTrigger = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Trigger>
>(({ ...props }, ref) => (
  <DialogPrimitive.Trigger ref={ref} data-slot="dialog-trigger" {...props} />
));
DialogTrigger.displayName = DialogPrimitive.Trigger.displayName;

function DialogPortal({ ...props }: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />;
}

const DialogClose = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Close>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Close>
>(({ ...props }, ref) => <DialogPrimitive.Close ref={ref} data-slot="dialog-close" {...props} />);
DialogClose.displayName = DialogPrimitive.Close.displayName;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    data-slot="dialog-overlay"
    className={cn(
      'data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 fixed inset-0 z-50 bg-black/50',
      className
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

type DialogContentProps = React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  showBorder?: boolean;
  showCloseButton?: boolean;
  /** 当传入 true 时，将在小屏断点处使用 `w-screen` 而不是默认的 `sm:max-w-lg`，用于全屏展示场景 */
  isFullscreen?: boolean;
};

const DialogContent = React.forwardRef((
  { className, children, showBorder = true, showCloseButton = true, isFullscreen = false, ...props }: DialogContentProps,
  ref: React.Ref<any>
) => {
  const childrenArray = React.Children.toArray(children);

  const hasTitle = childrenArray.some((child) => {
    if (!React.isValidElement(child)) return false;
    try {
      if (child.props && child.props['data-slot'] === 'dialog-title') return true;
    } catch (e) {}
    if (child.type === DialogPrimitive.Title) return true;
    // @ts-ignore
    if (child.type && (child.type as any).displayName === DialogPrimitive.Title.displayName) return true;
    return false;
  });

  const hasDescription = childrenArray.some((child) => {
    if (!React.isValidElement(child)) return false;
    try {
      if (child.props && child.props['data-slot'] === 'dialog-description') return true;
    } catch (e) {}
    if (child.type === DialogPrimitive.Description) return true;
    // @ts-ignore
    if (child.type && (child.type as any).displayName === DialogPrimitive.Description.displayName) return true;
    return false;
  });

  return (
    <DialogPortal data-slot="dialog-portal">
      <DialogOverlay ref={undefined} />
      <DialogPrimitive.Content
        ref={ref}
        data-slot="dialog-content"
        className={cn(
          'bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 fixed top-[50%] left-[50%] z-50 grid w-full max-w-[calc(100%-2rem)] translate-x-[-50%] translate-y-[-50%] gap-4 rounded-lg p-6 shadow-lg duration-200',
          showBorder && 'border',
          // 插入断点宽度类：如果父传入 isFullscreen，则使用 w-screen，否则保留 sm:max-w-lg
          isFullscreen ? 'w-screen max-w-none max-h-none rounded-none p-0' : 'sm:max-w-lg',
          className
        )}
        {...props}
      >
        {/* Inject a visually-hidden DialogTitle when none is provided */}
        {!hasTitle && (
          <DialogPrimitive.Title data-slot="dialog-title" className="sr-only">
            <VisuallyHidden>{(props as any)['aria-label'] ?? 'Dialog'}</VisuallyHidden>
          </DialogPrimitive.Title>
        )}

        {/* Inject a visually-hidden DialogDescription when none is provided */}
        {!hasDescription && (
          <DialogPrimitive.Description data-slot="dialog-description" className="sr-only">
            <VisuallyHidden>{(props as any)['aria-describedby'] ?? (props as any)['aria-label'] ?? 'Dialog content'}</VisuallyHidden>
          </DialogPrimitive.Description>
        )}

        {children}
        {showCloseButton && (
          <DialogPrimitive.Close className="ring-offset-background focus:ring-ring data-[state=open]:bg-accent data-[state=open]:text-muted-foreground absolute top-4 right-4 rounded-xs opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-hidden disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-5 w-6 h-6 flex items-center justify-center">
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  );
});
DialogContent.displayName = DialogPrimitive.Content.displayName;

function DialogHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-header"
      className={cn('flex flex-col gap-2 text-center sm:text-left', className)}
      {...props}
    />
  );
}

function DialogFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)}
      {...props}
    />
  );
}

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    data-slot="dialog-title"
    className={cn('text-lg leading-none font-semibold', className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    data-slot="dialog-description"
    className={cn('text-muted-foreground text-sm', className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
