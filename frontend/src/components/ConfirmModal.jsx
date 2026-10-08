/**
 * ConfirmModal.jsx — Confirmation Modal Component (Light Design System)
 * Centered overlay modal with title, message, Cancel + Confirm buttons.
 * Used before destructive actions (e.g., deleting emails, resetting database).
 * 
 * Props:
 *   title (string): Modal title
 *   message (string): Confirmation message
 *   confirmText (string): Confirm button text (default: "Confirm")
 *   isDangerous (bool): Use danger styling for destructive actions
 *   onConfirm (fn): Callback when confirmed
 *   onCancel (fn): Callback when cancelled
 * 
 * Updated: 2026-08-11 - Light design system
 */

import React from 'react';
import { useModalFocus } from '../hooks/useModalFocus';

function ConfirmModal({
  title = 'Confirm Action',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  isDangerous = false,
  onConfirm = () => {},
  onCancel = () => {},
}) {
  const dialogRef = useModalFocus(onCancel);
  return (
<div
  className="modal-overlay fixed inset-0 z-[400] flex items-center justify-center"
  style={{
    background: 'rgba(0, 0, 0, 0.4)',
    backdropFilter: 'blur(4px)',
  }}
        onClick={onCancel}
      >
      <div
        ref={dialogRef} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}
        className="modal-content w-full max-w-md mx-4 animate-fadeIn"
        style={{
          background: 'var(--color-surface)',
          borderRadius: '20px',
          padding: '32px',
          boxShadow: '0 20px 60px -10px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Warning Icon */}
        <div className="flex justify-center mb-4">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center"
            style={{
              background: isDangerous ? 'rgba(224, 90, 103, 0.1)' : 'rgba(229, 162, 60, 0.1)',
              border: `2px solid ${isDangerous ? 'rgba(224, 90, 103, 0.2)' : 'rgba(229, 162, 60, 0.2)'}`,
            }}
          >
            <svg
              className="w-7 h-7"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.8}
              style={{ color: isDangerous ? 'var(--color-danger)' : 'var(--color-warning)' }}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>
        </div>

        {/* Title */}
        <h3
          className="text-lg font-semibold text-center mb-2"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {title}
        </h3>

        {/* Message */}
        <p
          className="text-sm text-center mb-6 leading-relaxed whitespace-pre-line"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {message}
        </p>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="btn-secondary flex-1"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={isDangerous ? 'btn-danger flex-1' : 'btn-primary flex-1'}
          >
            {confirmText}
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.2s ease-out;
        }
      `}</style>
    </div>
  );
}

export default ConfirmModal;
