'use client';

import { useTheme } from 'next-themes';
import { Toaster as ToasterComponent } from 'sonner';
import type { ComponentProps, CSSProperties } from 'react';

const Toaster = (props: ComponentProps<typeof ToasterComponent>) => {
  const { theme = 'system' } = useTheme();

  return (
    <ToasterComponent
      theme={theme as ComponentProps<typeof ToasterComponent>['theme']}
      className="toaster group"
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
        } as CSSProperties
      }
      {...props}
    />
  );
};

export { Toaster };
