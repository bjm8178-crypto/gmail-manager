/**
 * ScamAlerts.jsx — Scam Alerts Page (Phase 6)
 * Lists all emails with scam_score > 30, sorted by score descending.
 * Filter bar: All / Moderate / High / Danger
 * Re-analyze button per email.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import EmailCard from '../components/EmailCard';
import ScamBadge from '../components/ScamBadge';
import { useToast } from '../components/ToastNotification';
import { apiGet, apiRequest } from '../lib/api';

const RISK_FILTERS = [
  { label: 'All Alerts', value: 'all', minScore: 30 },
  { label: 'Moderate', value: 'moderate', minScore: 31, maxScore: 60 },
  { label: 'High Risk', value: 'high', minScore: 61, maxScore: 80 },
  { label: 'Danger', value: 'danger', minScore: 81, maxScore: 100 },
];

function ScamAlerts() {
  const navigate = useNavigate();
  const toast = useToast();

  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState('all');
  const [reanalyzing, setReanalyzing] = useState({});

  useEffect(() => {
    fetchAlerts();
  }, []);

  async function fetchAlerts() {
    try {
      const authRes = await apiGet('/auth/status');
      const authData = await authRes.json();
      if (!authData.logged_in) { navigate('/login'); return; }

      const res = await apiGet('/scam/alerts?min_score=30');
      const data = await res.json();
      setEmails(data.emails || []);
    } catch (err) {
      console.error('[SCAM] Failed to fetch alerts:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleReanalyze(emailId) {
    setReanalyzing((prev) => ({ ...prev, [emailId]: true }));
    try {
      const res = await apiRequest(`/scam/reanalyze/${emailId}`, {
        method: 'POST',
      });
      const data = await res.json();

      if (res.ok) {
        // Update the email in the list with new score
        setEmails((prev) =>
          prev.map((e) =>
            e.email_id === emailId
              ? { ...e, scam_score: data.scam_score, scam_reason: data.reason, scam_indicators: JSON.stringify(data.indicators) }
              : e
          )
        );
        toast.success('Re-analysis complete', `New scam score: ${data.scam_score} (via ${data.provider_used})`);
      } else {
        toast.error('Re-analysis failed', data.error || 'Unknown error');
      }
    } catch (err) {
      toast.error('Re-analysis failed', err.message);
    } finally {
      setReanalyzing((prev) => ({ ...prev, [emailId]: false }));
    }
  }

  // Apply client-side risk filter
  const filteredEmails = emails.filter((email) => {
    const filter = RISK_FILTERS.find((f) => f.value === activeFilter);
    if (!filter || activeFilter === 'all') return true;
    if (filter.maxScore) return email.scam_score >= filter.minScore && email.scam_score <= filter.maxScore;
    return email.scam_score >= filter.minScore;
  });

  // Count per risk level
  const counts = {
    all: emails.length,
    moderate: emails.filter((e) => e.scam_score >= 31 && e.scam_score <= 60).length,
    high: emails.filter((e) => e.scam_score >= 61 && e.scam_score <= 80).length,
    danger: emails.filter((e) => e.scam_score >= 81).length,
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 md:px-6 py-4 pt-16 md:pt-4 flex-shrink-0" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>Scam Alerts</h1>
        <p className="text-sm text-gray">
          Emails flagged by AI with elevated scam probability scores.
        </p>

        {/* Risk Level Filter Tabs */}
        <div className="flex flex-wrap gap-2 mt-4">
          {RISK_FILTERS.map((filter) => (
            <button
              key={filter.value}
              onClick={() => setActiveFilter(filter.value)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 min-w-[85px] flex items-center justify-center gap-1"
              style={{
                background: activeFilter === filter.value ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: activeFilter === filter.value ? 'var(--color-info)' : 'var(--color-text-muted)',
                border: `1px solid ${activeFilter === filter.value ? 'rgba(59, 130, 246, 0.3)' : 'var(--color-border)'}`,
              }}
            >
              {filter.label}
              <span className="ml-1.5 text-xs opacity-70">({counts[filter.value]})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      <div className="px-4 py-6 md:px-6 flex-1 overflow-y-auto" style={{ WebkitOverflowScrolling: 'touch' }}>
        {loading && (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <div className="w-10 h-10 rounded-full animate-spin" style={{ borderWidth: '3px', borderStyle: 'solid', borderColor: 'var(--color-primary)', borderTopColor: 'transparent' }}></div>
            <p className="text-gray">Loading scam alerts...</p>
          </div>
        )}

        {!loading && filteredEmails.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <div className="text-5xl opacity-30">🛡️</div>
            <p className="text-gray">
              {emails.length === 0 ? 'No scam alerts found. Your inbox looks clean!' : 'No emails match this risk level.'}
            </p>
          </div>
        )}

        <div className="space-y-2">
          {filteredEmails.map((email) => (
            <EmailCard
              key={email.email_id}
              email={email}
              showScamBadge={true}
              actions={
                <button
                  onClick={() => handleReanalyze(email.email_id)}
                  disabled={reanalyzing[email.email_id]}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray
                             transition-all duration-200 hover: hover:bg-surface
                             disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ color: 'var(--color-text-primary)', border: '1px solid var(--border-default)' }}
                >
                  {reanalyzing[email.email_id] ? (
                    <span className="flex items-center gap-1.5">
                      <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Re-analyzing...
                    </span>
                  ) : '🔄 Re-analyze'}
                </button>
              }
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default ScamAlerts;
