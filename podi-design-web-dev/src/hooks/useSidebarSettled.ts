import { useEffect, useRef, useState } from 'react';

/**
 * Waits for the layout to settle after a `sidebar:toggle` event.
 * Returns an incrementing key which updates when the container width
 * has stopped changing for `settleMs` milliseconds.
 *
 * Usage: pass the containerRef (or null) and call updateLayout when key changes.
 */
export function useSidebarSettled(
  containerRef: React.RefObject<HTMLElement | null> | null,
  settleMs = 160,
  // optional trigger (e.g. collapsed boolean from context). If provided,
  // the hook will run settle logic whenever `trigger` changes.
  trigger?: any,
) {
  const [key, setKey] = useState(0);
  const roRef = useRef<ResizeObserver | null>(null);
  const debounceRef = useRef<number | null>(null);
  const lastWidthRef = useRef<number | null>(null);

  useEffect(() => {
    const onToggle = () => {
      const el = (containerRef && containerRef.current) || (typeof document !== 'undefined' ? document.documentElement : null);
      const initialWidth = el ? Math.max(0, el.getBoundingClientRect().width) : (typeof window !== 'undefined' ? window.innerWidth : 0);
      lastWidthRef.current = initialWidth;

      // Clean previous
      try { if (roRef.current) { roRef.current.disconnect(); roRef.current = null; } } catch (e) { /* ignore */ }
      if (debounceRef.current) {
        try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ }
        debounceRef.current = null;
      }

      // create new ResizeObserver to watch until width stabilizes
      if (typeof ResizeObserver !== 'undefined' && el) {
        roRef.current = new ResizeObserver((entries) => {
          for (const entry of entries) {
            const w = Math.max(0, entry.contentRect.width || 0);
            if (w !== lastWidthRef.current) {
              lastWidthRef.current = w;
              if (debounceRef.current) try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ }
              debounceRef.current = window.setTimeout(() => {
                setKey(k => k + 1);
                try { if (roRef.current) { roRef.current.disconnect(); roRef.current = null; } } catch (e) { /* ignore */ }
                if (debounceRef.current) { try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ } debounceRef.current = null; }
              }, settleMs) as unknown as number;
            }
          }
        });
        try { roRef.current.observe(el); } catch (e) { /* ignore */ }
      }

      // Fallback: if ResizeObserver doesn't fire, use double RAF + timeout
      try {
        window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
          if (debounceRef.current) try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ }
          debounceRef.current = window.setTimeout(() => {
            setKey(k => k + 1);
            try { if (roRef.current) { roRef.current.disconnect(); roRef.current = null; } } catch (e) { /* ignore */ }
            if (debounceRef.current) { try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ } debounceRef.current = null; }
          }, settleMs) as unknown as number;
        }));
      } catch (e) {
        // ignore; environment may not support requestAnimationFrame
      }
    };

    // If trigger is undefined, subscribe to legacy window event
    if (typeof trigger === 'undefined') {
      if (typeof window !== 'undefined') window.addEventListener('sidebar:toggle', onToggle as EventListener);
      return () => {
        try { if (typeof window !== 'undefined') window.removeEventListener('sidebar:toggle', onToggle as EventListener); } catch (e) { /* ignore */ }
        try { if (roRef.current) roRef.current.disconnect(); } catch (e) { /* ignore */ }
        if (debounceRef.current) try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ }
      };
    }

    // If a trigger is provided (e.g. collapsed boolean), run once now and whenever it changes
    onToggle();
    return () => {
      try { if (roRef.current) roRef.current.disconnect(); } catch (e) { /* ignore */ }
      if (debounceRef.current) try { window.clearTimeout(debounceRef.current); } catch (e) { /* ignore */ }
    };
  }, [containerRef, settleMs, trigger]);

  return key;
}

export default useSidebarSettled;
