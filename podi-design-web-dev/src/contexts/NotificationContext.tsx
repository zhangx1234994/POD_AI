import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { createPortal } from 'react-dom';

type Variant = 'info' | 'success' | 'warning' | 'danger';

type Banner = {
  id: string;
  content: React.ReactNode;
  duration?: number | null; // ms, null = persistent
  variant?: Variant;
};

type NotificationContextValue = {
  showBanner: (b: Omit<Banner, 'id'>) => string;
  hideBanner: (id: string) => void;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

// transition duration (ms) used for fade in/out
const TRANSITION_MS = 220;

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [queue, setQueue] = useState<Banner[]>([]);
  const [current, setCurrent] = useState<Banner | null>(null);
  const [visible, setVisible] = useState(false);

  // show next banner when current becomes null and queue has items
  const showNextFromQueue = useCallback(() => {
    setQueue((q) => {
      if (q.length === 0) return q;
      const [next, ...rest] = q;
      setCurrent(next);
      return rest;
    });
  }, []);

  const showBanner = useCallback((b: Omit<Banner, 'id'>) => {
    const id = String(Date.now()) + Math.random().toString(36).slice(2, 8);
    const banner: Banner = { id, variant: 'info', duration: 4000, ...b } as Banner;
    try { console.log('[Notification] showBanner', banner); } catch (e) { /* ignore */ }
    setQueue((q) => [...q, banner]);
    // if nothing currently displayed, kick the queue
    setTimeout(() => {
      setCurrent((cur) => {
        if (cur) return cur;
        // will be set by showNextFromQueue via setQueue callback
        showNextFromQueue();
        return cur;
      });
    }, 0);
    return id;
  }, [showNextFromQueue]);

  const hideBanner = useCallback((id: string) => {
    // if id matches current, start hide animation
    setQueue((q) => q.filter((b) => b.id !== id));
    setCurrent((cur) => {
      if (cur && cur.id === id) {
        // start hide sequence
        setVisible(false);
        // after transition, remove current and show next
        window.setTimeout(() => {
          setCurrent(null);
          // next in queue
          showNextFromQueue();
        }, TRANSITION_MS + 20);
      }
      return cur;
    });
  }, [showNextFromQueue]);

  // when current changes, show it (trigger fade-in) and schedule auto-hide
  React.useEffect(() => {
    if (!current) {
      setVisible(false);
      return;
    }
    // show with transition after mounting
    const t = window.setTimeout(() => setVisible(true), 10);
    let autoHideTimer: number | undefined;
    if (current.duration && current.duration > 0) {
      autoHideTimer = window.setTimeout(() => {
        // start hide
        setVisible(false);
        window.setTimeout(() => {
          setCurrent(null);
          showNextFromQueue();
        }, TRANSITION_MS + 20);
      }, current.duration);
    }
    return () => {
      clearTimeout(t);
      if (autoHideTimer) clearTimeout(autoHideTimer);
    };
  }, [current, showNextFromQueue]);

  const value = useMemo(() => ({ showBanner, hideBanner }), [showBanner, hideBanner]);

  // variant -> style mapping (Tailwind classes)
  const variantClass = (v?: Variant) => {
    switch (v) {
      case 'success': return 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-900/80';
      case 'warning': return 'border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900/80';
      case 'danger': return 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-900/80';
      case 'info':
      default:
        return 'border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-900/80';
    }
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
      {typeof document !== 'undefined' && createPortal(
        <div className="pointer-events-none fixed left-1/2 top-4 transform -translate-x-1/2 w-full max-w-[1100px] px-4" style={{ zIndex: 2147483647 }}>
          {/* only render current banner (queue displayed one by one) */}
          {current && (
            <div className="flex justify-center">
              <div
                className={`pointer-events-auto max-w-full w-full sm:w-auto transition-all duration-200 ease-out ${variantClass(current.variant)}`}
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(-8px)',
                  transition: `opacity ${TRANSITION_MS}ms ease, transform ${TRANSITION_MS}ms ease`,
                }}
              >
                <div className="rounded-lg border p-3 shadow-lg flex items-center gap-3">
                  <div className="flex-1 text-sm">
                    <Alert>
                      <AlertDescription>
                        {current.content}
                      </AlertDescription>
                    </Alert>
                  </div>
                  <div className="ml-2">
                    <Button variant="ghost" size="sm" onClick={() => hideBanner(current.id)}>我知道了</Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>,
        document.body
      )}
    </NotificationContext.Provider>
  );
};

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error('useNotification must be used within NotificationProvider');
  return ctx;
}

export default NotificationContext;
