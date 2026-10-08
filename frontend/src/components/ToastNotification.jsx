/**
 * ToastNotification.jsx — Toast Notification Component (Light Design System)
 * Top-right corner auto-dismiss toasts with success/warning/error/info types.
 * 
 * Usage: import { ToastProvider, useToast } from './ToastNotification';
 * Wrap app in <ToastProvider>, then call toast.success('message') anywhere.
 */

import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

// Toast context
const ToastContext = createContext(null);

// Toast type configurations
const TOAST_TYPES = {
  success: {
    color: 'var(--color-success)',
    bg: 'var(--color-success-bg)',
    border: 'var(--color-success-border)',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  warning: {
    color: 'var(--color-warning)',
    bg: 'var(--color-warning-bg)',
    border: 'var(--color-warning-border)',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
      </svg>
    ),
  },
  error: {
    color: 'var(--color-danger)',
    bg: 'var(--color-danger-bg)',
    border: 'var(--color-danger-border)',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  info: {
    color: 'var(--color-info)',
    bg: 'var(--color-info-bg)',
    border: 'var(--color-info-border)',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
      </svg>
    ),
  },
};

let toastId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef({});

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (timersRef.current[id]) {
      clearTimeout(timersRef.current[id]);
      delete timersRef.current[id];
    }
  }, []);

  const addToast = useCallback((type, message, subtext = '') => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, message, subtext }]);

    // Auto-dismiss after 4 seconds
    timersRef.current[id] = setTimeout(() => {
      removeToast(id);
    }, 4000);

    return id;
  }, [removeToast]);

  const toast = {
    success: (msg, sub) => addToast('success', msg, sub),
    warning: (msg, sub) => addToast('warning', msg, sub),
    error: (msg, sub) => addToast('error', msg, sub),
    info: (msg, sub) => addToast('info', msg, sub),
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}

      {/* Toast Container */}
      <div className="fixed top-20 md:top-4 right-4 z-[500] space-y-3 pointer-events-none" style={{ width: 'min(380px, calc(100vw - 2rem))' }}>
        {toasts.map((t) => {
          const config = TOAST_TYPES[t.type] || TOAST_TYPES.success;
          return (
            <div
              key={t.id}
              className="pointer-events-auto flex items-start gap-3 p-4 rounded-xl"
              style={{
                background: config.bg,
                border: `1px solid ${config.border}`,
                boxShadow: '0 4px 16px -2px rgba(0, 0, 0, 0.3)',
                animation: 'slideIn 0.3s ease-out',
              }}
            >
              <span style={{ color: config.color }} className="flex-shrink-0 mt-0.5">
                {config.icon}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {t.message}
                </p>
                {t.subtext && (
                  <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>
                    {t.subtext}
                  </p>
                )}
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="flex-shrink-0 transition-colors p-1 rounded active:opacity-50"
                style={{ color: 'var(--color-text-muted)', minWidth: '32px', minHeight: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(40px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

export default ToastProvider;
