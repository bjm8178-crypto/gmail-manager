/**
 * ProgressBar.jsx — Animated Progress Bar Component (Light Design System)
 * Used during bulk email analysis to show progress.
 * Props: current (int), total (int), label (string)
 */

import React from 'react';

function ProgressBar({ current = 0, total = 0, label = '' }) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className="w-full">
      {/* Label + Counter */}
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          {label || `Analyzing ${current} of ${total}...`}
        </span>
        <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          {percentage}%
        </span>
      </div>

      {/* Bar Track */}
      <div
        className="w-full h-2.5 rounded-full overflow-hidden"
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* Animated Fill */}
        <div
          className="h-full rounded-full transition-all duration-500 ease-out relative"
          style={{
            width: `${percentage}%`,
            background: 'var(--color-primary)',
          }}
        >
          {/* Subtle shimmer effect */}
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)',
              animation: 'shimmer 2s infinite',
            }}
          ></div>
        </div>
      </div>

      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}

export default ProgressBar;
