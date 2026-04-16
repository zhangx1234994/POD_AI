import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export default function Modal({
  visible,
  title,
  width = 520,
  confirmLabel,
  cancelLabel = '取消',
  onClose,
  onConfirm,
  children,
}: {
  visible: boolean;
  title?: string;
  width?: number;
  confirmLabel?: string | null;
  cancelLabel?: string | false;
  onClose: () => void;
  onConfirm?: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [visible, onClose]);

  if (!visible) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        className="relative bg-white rounded-2xl shadow-2xl max-h-[85vh] flex flex-col"
        style={{ width: Math.min(width, typeof window !== 'undefined' ? window.innerWidth - 32 : width) }}
        onClick={(e) => e.stopPropagation()}
      >
        {title ? (
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
            <h3 className="text-base font-semibold text-gray-900 font-display">{title}</h3>
            <button type="button" className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        ) : null}
        <div className="px-6 py-5 overflow-y-auto flex-1 text-sm text-gray-600 leading-relaxed">{children}</div>
        {confirmLabel !== null || cancelLabel ? (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100">
            {cancelLabel ? (
              <button
                type="button"
                className="px-4 py-2 text-sm rounded-xl text-gray-600 hover:bg-gray-100 transition-colors"
                onClick={onClose}
              >
                {cancelLabel}
              </button>
            ) : null}
            {confirmLabel !== null ? (
              <button
                type="button"
                className="px-5 py-2 text-sm font-medium text-white rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 hover:opacity-90 transition-opacity"
                onClick={onConfirm}
              >
                {confirmLabel ?? '确定'}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
