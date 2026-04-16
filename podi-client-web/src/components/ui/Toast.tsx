import { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

type ToastItem = {
  id: number;
  type: ToastType;
  message: string;
};

let toastQueue: ToastItem[] = [];
let toastListeners: Array<(items: ToastItem[]) => void> = [];
let nextId = 1;

function notify() {
  toastListeners.forEach((fn) => fn([...toastQueue]));
}

function addToast(type: ToastType, message: string) {
  const id = nextId++;
  toastQueue = [...toastQueue, { id, type, message }];
  notify();
  window.setTimeout(() => {
    toastQueue = toastQueue.filter((t) => t.id !== id);
    notify();
  }, 3000);
}

export const toast = {
  success: (msg: string) => addToast('success', msg),
  error: (msg: string) => addToast('error', msg),
  warning: (msg: string) => addToast('warning', msg),
  info: (msg: string) => addToast('info', msg),
};

const icons: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 size={16} className="text-emerald-500" />,
  error: <AlertCircle size={16} className="text-red-500" />,
  warning: <AlertTriangle size={16} className="text-amber-500" />,
  info: <Info size={16} className="text-blue-500" />,
};

export function ToastContainer() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    toastListeners.push(setItems);
    return () => {
      toastListeners = toastListeners.filter((fn) => fn !== setItems);
    };
  }, []);

  if (!items.length) return null;

  return createPortal(
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {items.map((item) => (
        <div
          key={item.id}
          className="pointer-events-auto flex items-center gap-2 px-4 py-3 bg-white rounded-xl shadow-lg border border-gray-100 animate-fade-in-up text-sm min-w-[240px]"
        >
          {icons[item.type]}
          <span className="text-gray-700">{item.message}</span>
        </div>
      ))}
    </div>,
    document.body,
  );
}
