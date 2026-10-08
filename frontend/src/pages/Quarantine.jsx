/**
 * Quarantine.jsx — Quarantined Emails Page (Phase 5)
 * Lists quarantined emails with red warning badges.
 * Actions: "Mark Safe" (removes flag) and "Delete" (moves to Gmail trash).
 * Confirmation modal before any delete action.
 * 
 * Updated: 2026-09-14 — Uses EmailCard for visual consistency with Inbox/ScamAlerts
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import EmailCard from '../components/EmailCard';
import ConfirmModal from '../components/ConfirmModal';
import { useToast } from '../components/ToastNotification';
import { apiGet, apiRequest, apiDelete } from '../lib/api';

function Quarantine() {
  const navigate = useNavigate();
  const toast = useToast();

  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => {
    fetchQuarantined();
  }, []);

  async function fetchQuarantined() {
    try {
      const authRes = await apiGet('/auth/status');
      const authData = await authRes.json();
      if (!authData.logged_in) { navigate('/login'); return; }

      const res = await apiGet('/quarantine');
      const data = await res.json();
      setEmails(data.emails || []);
    } catch (err) {
      console.error('[QUARANTINE] Failed to fetch:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkSafe(emailId) {
    try {
      const res = await apiRequest(`/quarantine/${emailId}/safe`, {
        method: 'POST',
      });
      if (res.ok) {
        setEmails((prev) => prev.filter((e) => e.email_id !== emailId));
        toast.success('Email marked as safe', 'Removed from quarantine.');
      }
    } catch (err) {
      toast.error('Failed to mark as safe', err.message);
    }
  }

  async function handleDelete(emailId) {
    try {
      const res = await apiRequest(`/quarantine/${emailId}`, { method: 'DELETE' });
      if (res.ok) {
        setEmails((prev) => prev.filter((e) => e.email_id !== emailId));
        toast.success('Email moved to trash', 'Email was not permanently deleted.');
      } else {
        toast.error('Failed to delete email');
      }
    } catch (err) {
      toast.error('Failed to delete email', err.message);
    } finally {
      setDeleteTarget(null);
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 md:px-6 py-4 pt-16 md:pt-4 flex-shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ background: 'rgba(239, 68, 68, 0.15)' }}>
            <svg className="w-5 h-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Quarantine</h1>
            <p className="text-sm text-gray">
              {emails.length} email{emails.length !== 1 ? 's' : ''} flagged as suspicious
            </p>
          </div>
        </div>
      </div>

      {/* Email List — flex-1 instead of calc() */}
      <div className="flex-1 px-4 py-6 md:px-6 overflow-y-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
        {loading && (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <div className="w-10 h-10 rounded-full animate-spin" style={{ borderWidth: '3px', borderStyle: 'solid', borderColor: 'var(--color-danger)', borderTopColor: 'transparent' }}></div>
            <p className="text-gray">Loading quarantined emails...</p>
          </div>
        )}

        {!loading && emails.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <div className="text-5xl opacity-30">✅</div>
            <p className="text-gray text-lg font-medium">Quarantine is empty</p>
            <p className="text-gray text-sm">No suspicious emails detected. You're safe!</p>
          </div>
        )}

        <div className="space-y-2">
          {emails.map((email) => (
            <EmailCard
              key={email.email_id}
              email={email}
              showScamBadge={true}
              actions={
                <div className="flex gap-2">
                  <button
                    onClick={() => handleMarkSafe(email.email_id)}
                    className="px-4 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 active:scale-95"
                    style={{
                      border: '1px solid rgba(34, 197, 94, 0.3)',
                      background: 'rgba(34, 197, 94, 0.08)',
                      color: 'var(--color-success)',
                      minHeight: '44px',
                    }}
                  >
                    ✓ Mark Safe
                  </button>
                  <button
                    onClick={() => setDeleteTarget(email)}
                    className="px-4 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 active:scale-95"
                    style={{
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      background: 'rgba(239, 68, 68, 0.08)',
                      color: 'var(--color-danger)',
                      minHeight: '44px',
                    }}
                  >
                    🗑 Delete
                  </button>
                </div>
              }
            />
          ))}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <ConfirmModal
          title="Move to Trash?"
          message={`This will move "${deleteTarget.subject || 'this email'}" to Gmail Trash. It will NOT be permanently deleted.`}
          confirmText="Move to Trash"
          isDangerous={true}
          onConfirm={() => handleDelete(deleteTarget.email_id)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

export default Quarantine;
