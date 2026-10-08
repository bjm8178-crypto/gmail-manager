/**
 * Rewriter.jsx — AI Email Rewriter Page (Phase 8)
 * Two-column layout: Original (textarea) → Rewritten (readonly)
 * Preset command buttons + custom instruction field.
 * Copy to clipboard, provider indicator.
 */

import React, { useState } from 'react';
import { useToast } from '../components/ToastNotification';
import { apiRequest } from '../lib/api';

// Preset rewrite commands
const COMMANDS = [
  { label: '💼 Make Professional', instruction: 'Make this email professional and formal' },
  { label: '✂️ Shorten to 3 Sentences', instruction: 'Shorten this email to exactly 3 sentences while keeping the core message' },
  { label: '😊 Make Friendly', instruction: 'Rewrite this email in a warm, friendly tone' },
  { label: '✏️ Fix Grammar', instruction: 'Fix all grammar and spelling mistakes in this email' },
  { label: '🌐 Translate to English', instruction: 'Translate this email to English' },
];

function Rewriter() {
  const toast = useToast();

  const [originalText, setOriginalText] = useState('');
  const [rewrittenText, setRewrittenText] = useState('');
  const [customInstruction, setCustomInstruction] = useState('');
  const [activeCommand, setActiveCommand] = useState(null);
  const [loading, setLoading] = useState(false);
  const [providerUsed, setProviderUsed] = useState('');
  const [charCounts, setCharCounts] = useState({ original: 0, rewritten: 0 });

  // Handle command button click — clears custom instruction
  function handleCommandClick(cmd) {
    setActiveCommand(cmd.label);
    setCustomInstruction('');
    doRewrite(cmd.instruction);
  }

  // Handle custom instruction — clears active command
  function handleCustomSubmit() {
    if (!customInstruction.trim()) return;
    setActiveCommand(null);
    doRewrite(customInstruction.trim());
  }

  // Call the /ai/rewrite endpoint
  async function doRewrite(instruction) {
    if (!originalText.trim()) {
      toast.warning('No text to rewrite', 'Paste or type an email in the left panel first.');
      return;
    }

    setLoading(true);
    setRewrittenText('');
    setProviderUsed('');

    try {
      const res = await apiRequest('/ai/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: originalText, instruction }),
      });

      const data = await res.json();

      if (res.ok) {
        setRewrittenText(data.rewritten);
        setProviderUsed(data.provider_used || 'Unknown');
        setCharCounts({
          original: data.character_count_original || originalText.length,
          rewritten: data.character_count_rewritten || data.rewritten.length,
        });
        toast.success('Rewrite complete!', `Using ${data.provider_used}`);
      } else {
        toast.error('Rewrite failed', data.error || 'All AI providers exhausted.');
      }
    } catch (err) {
      toast.error('Rewrite failed', 'Could not connect to the backend.');
    } finally {
      setLoading(false);
    }
  }

  // Copy rewritten text to clipboard
  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(rewrittenText);
      toast.success('Copied to clipboard!');
    } catch {
      toast.error('Failed to copy');
    }
  }

  return (
    <div className="h-screen overflow-hidden">
      {/* Header */}
      <div className="px-4 md:px-6 py-4 pt-16 md:pt-4" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>AI Email Rewriter</h1>
        <p className="text-sm text-gray">
          Paste an email and let AI transform it. Works independently of Gmail.
        </p>
      </div>

      {/* Two-Column Layout - Desktop Only */}
      <div className="hidden md:flex gap-4 p-6" style={{ height: 'calc(100vh - 90px)' }}>
        {/* LEFT COLUMN — Original (Desktop) */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>Original</h2>
            <span className="text-xs text-gray">{originalText.length} / 5000 chars</span>
          </div>

          <textarea
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value.slice(0, 5000))}
            placeholder="Paste or type your email text here..."
            className="neu-input flex-1 p-4 text-sm resize-none"
            style={{
              minHeight: '200px',
            }}
          />

          {/* Command Buttons - Desktop Only */}
          <div className="mt-4">
            <p className="text-xs text-gray mb-2 font-semibold">Quick Commands:</p>
            <div className="flex flex-wrap gap-2">
              {COMMANDS.map((cmd) => (
                <button
                  key={cmd.label}
                  onClick={() => handleCommandClick(cmd)}
                  disabled={loading}
                  className="px-3.5 py-2 rounded-lg text-xs font-medium transition-all duration-200
                             hover:scale-[1.03] active:scale-[0.97] disabled:opacity-50"
                  style={{
                    background: activeCommand === cmd.label ? 'rgba(59, 130, 246, 0.2)' : 'var(--color-surface)',
                    border: `1px solid ${activeCommand === cmd.label ? 'rgba(59, 130, 246, 0.4)' : 'var(--color-border)'}`,
                    color: activeCommand === cmd.label ? 'var(--color-info)' : 'var(--color-text-muted)',
                  }}
                >
                  {cmd.label}
                </button>
              ))}
            </div>

            {/* Custom Instruction - Desktop Only */}
            <div className="flex gap-2 mt-3">
              <input
                type="text"
                placeholder="Or type your own instruction..."
                value={customInstruction}
                onChange={(e) => {
                  setCustomInstruction(e.target.value);
                  setActiveCommand(null);
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                className="flex-1 px-4 py-2 rounded-lg text-sm placeholder-text-gray
                           outline-none transition-all duration-200 focus:ring-2 focus:ring-primary"
                style={{ color: 'var(--color-text-primary)', background: 'var(--surface)', border: '1px solid var(--border-default)' }}
              />
              <button
                onClick={handleCustomSubmit}
                disabled={loading || !customInstruction.trim()}
                className="btn-primary px-4 py-2 text-sm"
              >
                Rewrite
              </button>
            </div>
          </div>
        </div>

        {/* Divider - Desktop Only */}
        <div className="w-px flex-shrink-0" style={{ background: 'var(--surface)' }}></div>

        {/* RIGHT COLUMN — Rewritten (Desktop) */}
        <div className="flex-1 flex flex-col">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>Rewritten</h2>
            {rewrittenText && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium text-gray
                           transition-all duration-200 hover: hover:bg-surface"
                style={{ color: 'var(--color-text-primary)', border: '1px solid var(--border-default)' }}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                </svg>
                Copy
              </button>
            )}
          </div>

          <div
            className="flex-1 p-4 rounded-xl text-sm overflow-y-auto relative"
            style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              minHeight: '200px',
              maxHeight: '600px',
              boxShadow: 'var(--shadow-neumorphic-sm)',
            }}
          >
            {loading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <div className="w-8 h-8 rounded-full animate-spin" style={{ borderWidth: '2px', borderStyle: 'solid', borderColor: 'var(--color-primary)', borderTopColor: 'transparent' }}></div>
                <p className="text-gray text-sm">AI is rewriting...</p>
              </div>
            ) : rewrittenText ? (
              <p className="whitespace-pre-wrap leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>{rewrittenText}</p>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2 opacity-40">
<svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}
                      style={{ color: 'var(--color-text-primary)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                </svg>
                <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>Rewritten text will appear here</p>
              </div>
            )}
          </div>

          {/* Provider + Char Count */}
          {providerUsed && (
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-gray">
                Provider: <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>{providerUsed}</span>
              </span>
              <span className="text-xs text-gray">
                {charCounts.original} → {charCounts.rewritten} chars
              </span>
            </div>
          )}
        </div>
      </div>

      {/* MOBILE LAYOUT — Chat-Style */}
      <div className="md:hidden flex flex-col" style={{ height: 'calc(100vh - 140px)' }}>
        {/* Chat Messages Area */}
        <div className="flex-1 px-4 pt-4 pb-2 overflow-y-auto" style={{ paddingBottom: 'calc(180px + env(safe-area-inset-bottom, 0px))' }}>
          {/* Original Email Bubble (User) */}
          {originalText && (
            <div className="mb-4 flex justify-end">
              <div
                className="max-w-[85%] p-3 rounded-2xl rounded-tr-sm text-sm"
                style={{
                  background: 'var(--color-primary)',
                  color: '#FFFFFF',
                }}
              >
                <p className="whitespace-pre-wrap break-words">{originalText}</p>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="mb-4 flex justify-start">
              <div
                className="max-w-[85%] p-4 rounded-2xl rounded-tl-sm"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full animate-spin" style={{ borderWidth: '2px', borderStyle: 'solid', borderColor: 'var(--color-primary)', borderTopColor: 'transparent' }}></div>
                  <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>Rewriting...</span>
                </div>
              </div>
            </div>
          )}

          {/* Rewritten Email Bubble (Assistant) */}
          {rewrittenText && (
            <div className="mb-4 flex justify-start">
              <div className="max-w-[85%]">
                <div
                  className="p-3 rounded-2xl rounded-tl-sm text-sm mb-2"
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                  }}
                >
                  <p className="whitespace-pre-wrap break-words" style={{ color: 'var(--color-text-primary)' }}>{rewrittenText}</p>
                </div>
                
                {/* Action Buttons Below Bubble */}
                <div className="flex items-center gap-2 px-2">
                  <button
                    onClick={handleCopy}
                    className="p-1.5 rounded-lg transition-all"
                    style={{
                      background: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                    }}
                    title="Copy"
                  >
                    <svg className="w-4 h-4" style={{ color: 'var(--color-text-secondary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                    </svg>
                  </button>
                  {providerUsed && (
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {providerUsed}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Empty State */}
          {!originalText && !rewrittenText && !loading && (
            <div className="flex flex-col items-center justify-center gap-3 py-20" style={{ opacity: 0.5 }}>
              <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
                    style={{ color: 'var(--color-text-primary)' }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
              </svg>
              <p className="text-sm text-center" style={{ color: 'var(--color-text-primary)' }}>Paste an email below to get started</p>
            </div>
          )}
        </div>

        {/* Bottom Input Bar - Fixed */}
        <div className="fixed bottom-0 left-0 right-0 px-4 pt-3 md:hidden" 
             style={{ 
               background: 'linear-gradient(to top, var(--color-background) 90%, transparent)',
               borderTop: '1px solid var(--color-border)',
               paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))',
             }}>
          {/* Char Counter - Above input bar */}
          <div className="text-center text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
            {originalText.length} / 5000 chars
          </div>

          {/* Multi-line input area */}
          <div className="flex items-end gap-3 px-4 py-3 rounded-2xl shadow-lg" 
               style={{ 
                 background: 'var(--color-surface)', 
                 border: '1px solid var(--color-border)',
                 boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
               }}>
            {/* Textarea for multi-line pasting */}
            <textarea
              value={originalText}
              onChange={(e) => setOriginalText(e.target.value.slice(0, 5000))}
              placeholder="Paste your email..."
              className="flex-1 bg-transparent text-sm placeholder-text-gray outline-none resize-none"
              style={{ color: 'var(--color-text-primary)', fontSize: '16px', maxHeight: '120px', minHeight: '24px' }}
              rows={1}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
            />

            {/* Submit button (up-arrow in circle) */}
            <button
              onClick={() => {
                if (originalText.trim()) {
                  // Trigger rewrite with default instruction (professional tone)
                  setActiveCommand(COMMANDS[0].label);
                  doRewrite(COMMANDS[0].instruction);
                }
              }}
              disabled={loading || !originalText.trim()}
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all duration-200 disabled:opacity-50"
              style={{
                background: originalText.trim() && !loading ? 'linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%)' : 'var(--color-text-muted)',
              }}
            >
              <svg className="w-4 h-4" style={{ color: 'var(--color-text-primary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Rewriter;
