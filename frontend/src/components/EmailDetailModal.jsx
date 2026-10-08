/**
 * EmailDetailModal.jsx — Redesigned Email Detail Modal
 * 
 * IMPROVEMENTS (2026-09-14 — Mobile UX Overhaul):
 * - Full-screen sheet on mobile (< md breakpoint)
 * - Reply section inside scroll area (not clipped off bottom)
 * - Touch feedback on all interactive elements
 * - 44px minimum touch targets
 * - Safe area inset support
 * 
 * Previous improvements (2026-09-11):
 * - Single-column layout for better readability
 * - Security indicators with clear visual hierarchy
 * - Collapsible reply section
 * - File attachment support
 */

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import ScamBadge from './ScamBadge';
import { apiRequest } from '../lib/api';
import { useModalFocus } from '../hooks/useModalFocus';
import { useToast } from './ToastNotification';
import EmailBodyFrame from './EmailBodyFrame';

function EmailDetailModal({ email, senderName, senderEmail, decodedSubject, indicators, onClose }) {
  const [replyBody, setReplyBody] = useState('');
  const [sending, setSending] = useState(false);
  const [showReply, setShowReply] = useState(false);
  const [scamExpanded, setScamExpanded] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const fileInputRef = useRef(null);
  const toast = useToast();

  const dialogRef = useModalFocus(onClose);

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    const maxSize = 25 * 1024 * 1024;
    const oversizedFiles = files.filter(f => f.size > maxSize);
    if (oversizedFiles.length > 0) {
      toast.error('File too large', `Maximum file size is 25MB. ${oversizedFiles[0].name} is too large.`);
      return;
    }
    if (attachments.length + files.length > 10) {
      toast.error('Too many files', 'Maximum 10 attachments allowed per email.');
      return;
    }
    setAttachments(prev => [...prev, ...files]);
    e.target.value = '';
  };

  const handleRemoveAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const handleSendReply = async () => {
    if (!replyBody.trim() || sending) return;
    setSending(true);
    try {
      const formData = new FormData();
      formData.append('body', replyBody);
      attachments.forEach((file) => {
        formData.append('attachments', file);
      });
      const response = await apiRequest(`/emails/${encodeURIComponent(email.email_id || email.id)}/reply`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      const result = await response.json();
      if (!response.ok || result.error) {
        toast.error('Failed to send reply', result.error || result.message || 'Please try again.');
      } else {
        toast.success('Reply sent', attachments.length > 0
          ? `Your reply with ${attachments.length} attachment${attachments.length > 1 ? 's' : ''} was sent successfully.`
          : 'Your reply was sent successfully.'
        );
        setReplyBody('');
        setAttachments([]);
        setShowReply(false);
        onClose();
      }
    } catch (err) {
      toast.error('Failed to send reply', err.message || 'Please try again.');
    } finally {
      setSending(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    let timeAgo = '';
    if (diffMins < 60) timeAgo = `${diffMins} min ago`;
    else if (diffHours < 24) timeAgo = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    else if (diffDays < 7) timeAgo = `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

    const formatted = date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });

    return timeAgo ? `${timeAgo}, ${formatted}` : formatted;
  };

  const senderTrust = { level: 'unknown', label: 'Sender identity not verified', color: 'var(--color-text-secondary)' };

  return createPortal(
    <div
      className="fixed inset-0 flex items-end md:items-center md:justify-center md:p-4"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.6)',
        backdropFilter: 'blur(4px)',
        zIndex: 300,
      }}
      onClick={onClose}
    >
      <div
        ref={dialogRef} role="dialog" aria-modal="true" aria-label={decodedSubject || "Email details"} tabIndex={-1}
        className="relative w-full h-full md:h-auto md:max-h-[92vh] md:max-w-4xl overflow-hidden md:rounded-2xl flex flex-col"
        style={{
          backgroundColor: 'var(--color-surface)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Mobile drag handle */}
        <div className="md:hidden flex justify-center pt-2 pb-1 flex-shrink-0">
          <div
            className="w-10 h-1 rounded-full"
            style={{ backgroundColor: 'var(--color-border)' }}
          />
        </div>

        {/* Header with sender info and trust badge */}
        <div
          className="px-4 md:px-6 py-3 md:py-4 flex-shrink-0"
          style={{
            backgroundColor: 'var(--color-surface)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <div className="flex items-start justify-between gap-3 md:gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              {/* Avatar */}
              <div
                className="w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center text-white font-semibold text-base md:text-lg flex-shrink-0"
                style={{
                  backgroundColor: 'var(--color-primary)',
                }}
              >
                {senderName?.charAt(0)?.toUpperCase() || '?'}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <h3
                    className="text-base md:text-lg font-semibold truncate"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {senderName}
                  </h3>

                  {/* Sender trust badge */}
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 flex-shrink-0"
                    style={{
                      backgroundColor: `${senderTrust.color}20`,
                      color: senderTrust.color,
                      border: `1px solid ${senderTrust.color}40`,
                    }}
                  >
                    {senderTrust.level === 'safe' ? (
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                      </svg>
                    )}
                    {senderTrust.label}
                  </span>
                </div>

                <p
                  className="text-sm truncate mb-1"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {senderEmail}
                </p>

                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {formatDate(email.received_at || email.date || email.analyzed_at)}
                </span>
              </div>
            </div>

            {/* Close button — 44px touch target */}
            <button
              onClick={onClose}
              className="w-11 h-11 rounded-full flex items-center justify-center transition-all flex-shrink-0 active:scale-90 active:bg-[var(--color-border)]"
              style={{
                color: 'var(--color-text-secondary)',
                backgroundColor: 'transparent',
              }}
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Scrollable content area — everything scrolls on mobile including reply */}
        <div className="flex-1 overflow-y-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
          {/* Security alert - prominent if high risk */}
          {email.scam_score !== null && email.scam_score !== undefined && email.scam_score >= 40 && (
            <div
              className="mx-4 md:mx-6 mt-4"
              style={{
                backgroundColor: email.scam_score >= 70 ? 'rgba(224, 90, 103, 0.05)' : 'rgba(229, 162, 60, 0.05)',
                border: `1px solid ${email.scam_score >= 70 ? 'var(--color-danger)' : 'var(--color-warning)'}40`,
                borderRadius: '12px',
                padding: '12px 16px',
              }}
            >
              <div className="flex items-start gap-3">
                <svg
                  className="w-5 h-5 flex-shrink-0 mt-0.5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  style={{ color: email.scam_score >= 70 ? 'var(--color-danger)' : 'var(--color-warning)' }}
                >
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    {email.scam_score >= 70 ? '⚠️ High Security Risk Detected' : '⚠️ Suspicious Email'}
                  </p>
                  <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                    This email shows signs of phishing or fraud. Avoid clicking links or providing personal information.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Subject */}
          <div className="px-4 md:px-6 pt-4 md:pt-5 pb-3 md:pb-4">
            <h2
              className="text-lg md:text-xl font-semibold"
              style={{ color: 'var(--color-text-primary)', lineHeight: '1.4' }}
            >
              {decodedSubject || '(No Subject)'}
            </h2>
          </div>

          {/* Scam badge */}
          {(
            <div className="px-4 md:px-6 pb-4">
              <ScamBadge
                email={email} score={email.scam_score}
                reason={email.reasoning || email.scam_reason}
                indicators={indicators}
                expanded={scamExpanded}
                onToggle={() => setScamExpanded(!scamExpanded)}
              />
            </div>
          )}

          {/* Email body */}
          <div
            className="px-4 md:px-6 pb-4 md:pb-6"
            style={{
              borderTop: '1px solid var(--color-border)',
              paddingTop: '1rem',
            }}
          >
            <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
              <EmailBodyFrame
                body={email.body || email.snippet}
                className="text-sm"
                textStyle={{ color: 'var(--color-text-primary)', lineHeight: '1.7' }}
              />
            </div>
          </div>

          {/* Reply section — INSIDE scroll area so it's always reachable on mobile */}
          <div
            className="px-4 md:px-6 py-4 flex-shrink-0"
            style={{
              borderTop: '1px solid var(--color-border)',
              backgroundColor: 'var(--color-background)',
            }}
          >
            {/* Reply toggle */}
            <button
              onClick={() => setShowReply(!showReply)}
              className="px-4 py-2.5 rounded-lg text-sm font-medium transition-all flex items-center gap-2 active:scale-95"
              style={{
                backgroundColor: showReply ? 'var(--color-primary)' : 'var(--color-surface)',
                color: showReply ? '#ffffff' : 'var(--color-text-primary)',
                border: showReply ? 'none' : '1px solid var(--color-border)',
                minHeight: '44px',
              }}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
              </svg>
              {showReply ? 'Hide Reply' : 'Reply'}
            </button>
          </div>

          {/* Collapsible reply form — also inside scroll area */}
          {showReply && (
            <div
              className="px-4 md:px-6 py-4 flex-shrink-0"
              style={{
                backgroundColor: 'var(--color-surface)',
                borderTop: '1px solid var(--color-border)',
                paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))',
              }}
            >
              <div className="mb-3">
                <p className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  <span className="font-medium">To:</span> {senderName} &lt;{senderEmail}&gt;
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  <span className="font-medium">Subject:</span> Re: {decodedSubject}
                </p>
              </div>

              <textarea aria-label="Reply message"
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                placeholder="Write your reply..."
                className="w-full text-sm rounded-lg p-3 resize-none mb-3"
                rows={4}
                style={{
                  backgroundColor: 'var(--color-background)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-primary)',
                  outline: 'none',
                  fontSize: '16px', /* Prevents iOS zoom on focus */
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--color-border)'}
              />

              {/* Attachments display */}
              {attachments.length > 0 && (
                <div className="mb-3 space-y-2">
                  {attachments.map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 p-2 rounded-lg"
                      style={{
                        backgroundColor: 'var(--color-background)',
                        border: '1px solid var(--color-border)',
                      }}
                    >
                      <svg className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--color-text-secondary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                          {file.name}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                      <button
                        onClick={() => handleRemoveAttachment(index)}
                        className="p-2 rounded transition-colors flex-shrink-0 active:scale-90"
                        style={{ color: 'var(--color-text-secondary)', minWidth: '44px', minHeight: '44px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                        title="Remove attachment"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={handleSendReply}
                  disabled={!replyBody.trim() || sending}
                  className="px-4 py-2.5 rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                  style={{
                    backgroundColor: replyBody.trim() && !sending ? 'var(--color-primary)' : 'var(--color-border)',
                    color: '#ffffff',
                    minHeight: '44px',
                  }}
                >
                  {sending ? 'Sending...' : 'Send Reply'}
                </button>

                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={handleFileSelect}
                  style={{ display: 'none' }}
                  accept="*/*"
                />

                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={sending}
                  className="p-2.5 rounded-lg transition-colors disabled:opacity-50 active:scale-90 active:bg-[var(--color-border)]"
                  style={{ color: 'var(--color-text-secondary)', minWidth: '44px', minHeight: '44px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  title="Attach file"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

export default EmailDetailModal;
