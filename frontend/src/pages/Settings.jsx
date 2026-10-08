/**
 * Settings.jsx — Settings Page (Unified Neumorphic Design)
 * Manages AI provider API keys, custom labels, and app configuration.
 * Uses responsive grid layout with consistent neumorphic cards.
 * 
 * Updated: 2026-08-10 - Unified neumorphic design system
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../components/ToastNotification';
import ConfirmModal from '../components/ConfirmModal';
import InfoTooltip from '../components/InfoTooltip';
import { apiGet, apiRequest, clearAuthToken } from '../lib/api';

// API key field definitions
const API_FIELDS = [
  {
    key: 'GROQ_API_KEY',
    label: 'Groq API Key',
    placeholder: 'gsk_...',
    description: 'Primary AI provider — Groq LLaMA 3',
    role: 'Primary',
    icon: '🟢',
  },
  {
    key: 'GEMINI_API_KEY',
    label: 'Gemini API Key',
    placeholder: 'AIzaSy...',
    description: 'Secondary AI provider — Google Gemini Flash',
    role: 'Secondary',
    icon: '🔵',
  },
  {
    key: 'COHERE_API_KEY',
    label: 'Cohere API Key',
    placeholder: 'R0Uw...',
    description: 'Tertiary AI provider — Cohere Command-R',
    role: 'Tertiary',
    icon: '🟡',
  },
  {
    key: 'NVIDIA_API_KEY',
    label: 'NVIDIA API Key',
    placeholder: 'nvapi-...',
    description: 'Reserved provider (inactive, future use)',
    role: 'Inactive',
    icon: '⚪',
  },
  {
    key: 'GOOGLE_SAFE_BROWSING_KEY',
    label: 'Safe Browsing API Key',
    placeholder: 'AIzaSy...',
    description: 'Google Safe Browsing — URL threat scanner',
    role: 'Security',
    icon: '🛡️',
  },
];

function Settings() {
  const navigate = useNavigate();
  const toast = useToast();

  const [providerStatus, setProviderStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState('');
  
  // Custom Labels State
  const [customLabels, setCustomLabels] = useState([]);
  const [newLabelName, setNewLabelName] = useState('');
  const [labelLoading, setLabelLoading] = useState(false);

  // Delete Mode State
  const [deleteMode, setDeleteMode] = useState('trash');
  const [showDeleteInfo, setShowDeleteInfo] = useState(false);

  // Confirm Modal State
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  useEffect(() => {
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const authRes = await apiGet('/auth/status');
      const authData = await authRes.json();
      if (!authData.logged_in) { navigate('/login'); return; }
      setUserEmail(authData.email || '');

      // Fetch AI provider status
      const aiRes = await apiGet('/ai/status');
      const aiData = await aiRes.json();
      setProviderStatus(aiData.providers || {});

      // Fetch custom labels
      const labelRes = await apiGet('/settings/labels');
      if (labelRes.ok) {
        const labelData = await labelRes.json();
        setCustomLabels(labelData.labels || []);
      }

      // Fetch delete mode
      const dmRes = await apiGet('/settings/delete-mode');
      if (dmRes.ok) {
        const dmData = await dmRes.json();
        setDeleteMode(dmData.delete_mode || 'trash');
      }
    } catch (err) {
      console.error('[SETTINGS] Failed to load:', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    try {
      await apiRequest('/auth/logout', {
        method: 'POST',
      });
      toast.success('Logged out', 'Redirecting to login...');
      clearAuthToken();
      setTimeout(() => navigate('/login'), 500);
    } catch (err) {
      toast.error('Logout failed', err.message);
    }
  }

  async function handleAddLabel() {
    if (!newLabelName.trim()) return;
    setLabelLoading(true);
    try {
      const res = await apiRequest('/settings/labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newLabelName.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to add label');
      
      toast.success('Label added', `${newLabelName} was added successfully.`);
      setNewLabelName('');
      
      // Refresh labels
      const labelRes = await apiGet('/settings/labels');
      if (labelRes.ok) {
        const labelData = await labelRes.json();
        setCustomLabels(labelData.labels || []);
      }
    } catch (err) {
      toast.error('Error adding label', err.message);
    } finally {
      setLabelLoading(false);
    }
  }

  async function handleDeleteLabel(label) {
    setConfirmAction({
      title: 'Delete Label',
      message: `Are you sure you want to delete "${label.label_name}"? This action cannot be undone.`,
      confirmText: 'Delete',
      onConfirm: async () => {
        try {
          const res = await apiRequest(`/settings/labels/${label.label_name}`, {
            method: 'DELETE',
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'Failed to delete label');
          
          toast.success('Label deleted', `${label.label_name} was removed.`);
          setCustomLabels(prev => prev.filter(l => l.label_id !== label.label_id));
        } catch (err) {
          toast.error('Error deleting label', err.message);
        }
        setShowConfirmModal(false);
      },
    });
    setShowConfirmModal(true);
  }

  async function handleResetDatabase() {
    setConfirmAction({
      title: 'Reset Database',
      message: 'WARNING: This will permanently delete all analyzed emails, scan cursors, and failure queues. This action CANNOT be undone. Are you absolutely sure?',
      confirmText: 'Reset Database',
      isDangerous: true,
      onConfirm: async () => {
        try {
          const res = await apiRequest('/settings/reset-database', {
        method: 'POST',
      });
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'Failed to reset database');
          
          toast.success('Database Reset', data.message);
        } catch (err) {
          toast.error('Error resetting database', err.message);
        }
        setShowConfirmModal(false);
      },
    });
    setShowConfirmModal(true);
  }

  async function handleSetDeleteMode(mode) {
    try {
      const res = await apiRequest('/settings/delete-mode', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (!res.ok) throw new Error('Failed to set delete mode');
      
      setDeleteMode(mode);
      toast.success('Setting updated', `Email deletion mode set to ${mode}`);
    } catch (err) {
      toast.error('Error updating setting', err.message);
    }
  }

  function isConfigured(providerKey) {
    const keyMap = {
      'NVIDIA_API_KEY': 'nvidia',
      'GEMINI_API_KEY': 'gemini',
      'COHERE_API_KEY': 'cohere',
      'GROQ_API_KEY': 'groq',
      'GOOGLE_SAFE_BROWSING_KEY': 'safebrowsing',
    };
    const providerName = keyMap[providerKey];
    if (providerName && providerStatus[providerName]) {
      return providerStatus[providerName].configured;
    }
    return false;
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: 'var(--surface)' }}>
        <div className="w-10 h-10 rounded-full animate-spin" style={{ borderWidth: '3px', borderStyle: 'solid', borderColor: 'var(--color-primary)', borderTopColor: 'transparent' }}></div>
      </div>
    );
  }

  return (
    <div className="h-screen overflow-y-auto" style={{ background: 'var(--surface)', WebkitOverflowScrolling: 'touch', paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
      {/* Header */}
      <div className="px-4 md:px-6 py-4 pt-16 md:pt-4" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
        <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Settings</h1>
        <p className="text-sm text-gray mt-0.5">
          Manage AI providers, labels, and account settings.
        </p>
      </div>

      {/* Settings Grid */}
      <div className="settings-grid">
        {/* Account Section */}
        <section className="neu-card p-5">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
            Account
          </h2>

          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>{userEmail || 'Connected Google Account'}</p>
              <p className="text-xs text-gray mt-0.5">OAuth 2.0 — Gmail API access granted</p>
            </div>
            <button
              onClick={handleLogout}
              className="btn-danger"
            >
              Sign Out
            </button>
          </div>
        </section>

        {/* AI Providers Section */}
        <section className="neu-card p-5">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            AI Cascade Providers
          </h2>
          <p className="text-xs text-gray mb-4">
            Providers are tried in order. If one hits a rate limit, the next is used automatically.
          </p>

          <div className="space-y-3">
            {API_FIELDS.map((field) => {
              const configured = isConfigured(field.key);
              const isInactive = field.role === 'Inactive';
              return (
                <div
                  key={field.key}
                  className="neu-card p-3"
                  style={{ opacity: isInactive ? 0.6 : 1 }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span className="text-lg flex-shrink-0" aria-hidden="true">{field.icon}</span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>{field.label}</p>
                        <p className="text-xs text-gray truncate">{field.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span
                        className={`badge ${
                          isInactive
                            ? 'badge-neutral'
                            : configured
                              ? 'badge-success'
                              : 'badge-danger'
                        }`}
                      >
                        {isInactive ? 'Reserved' : configured ? 'Connected' : 'Not Set'}
                      </span>
                      <span className="badge badge-info">
                        {field.role}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 p-3 rounded-lg" style={{ background: 'var(--info-bg)', border: '1px solid var(--info-border)' }}>
            <p className="text-xs text-info">
              ℹ️ API keys are stored securely in your Railway environment variables and never exposed to the frontend.
            </p>
          </div>
        </section>

        {/* Custom Labels Section */}
        <section className="neu-card p-5">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
            </svg>
            Custom Labels
          </h2>

          <div className="flex gap-2 mb-4">
            <label htmlFor="new-label-input" className="sr-only">New label name</label>
            <input
              id="new-label-input"
              type="text"
              aria-label="New label name"
              value={newLabelName}
              onChange={(e) => setNewLabelName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddLabel()}
              placeholder="Enter label name..."
              className="neu-input flex-1"
              disabled={labelLoading}
            />
            <button
              onClick={handleAddLabel}
              disabled={!newLabelName.trim() || labelLoading}
              className="btn-primary"
            >
              {labelLoading ? '...' : '+ Add'}
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {customLabels.length === 0 ? (
              <p className="text-xs text-muted">No custom labels yet. Add one above!</p>
            ) : (
              customLabels.map((label) => (
                <div
                  key={label.label_id}
                  className="badge badge-neutral group transition-all"
                >
                  <span className="text-xs">{label.label_name}</span>
                  <button
                    onClick={() => handleDeleteLabel(label)}
                    aria-label={`Delete label ${label.label_name}`}
                    className="ml-1 text-danger opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Email Deletion Behavior Section */}
        <section className="neu-card p-5">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
            Deletion Method
            <InfoTooltip text="Choose what happens when you delete an email — move it to Gmail's trash (recoverable for 30 days) or permanently delete it (cannot be undone)." />
          </h2>

          <div className="flex items-center gap-4">
            <button
              onClick={() => handleSetDeleteMode('trash')}
              className={deleteMode === 'trash' ? 'btn-primary' : 'btn-secondary'}
            >
              📁 Move to Trash
            </button>
            <button
              onClick={() => handleSetDeleteMode('permanent')}
              className={deleteMode === 'permanent' ? 'btn-danger' : 'btn-secondary'}
            >
              🗑️ Permanent Delete
            </button>
          </div>

          <div className="mt-3 p-3 rounded-lg" style={{ background: 'var(--warning-bg)', border: '1px solid var(--warning-border)' }}>
            <p className="text-xs text-warning">
              {deleteMode === 'trash' 
                ? '📁 Emails moved to trash can be recovered from Gmail trash for 30 days.'
                : '⚠️ Permanent deletion is irreversible. Deleted emails cannot be recovered.'}
            </p>
          </div>
        </section>

        {/* Danger Zone Section */}
        <section className="neu-card p-5" style={{ border: '1px solid var(--danger-border)' }}>
          <h2 className="text-sm font-semibold text-danger mb-3 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            Danger Zone
          </h2>

          <button
            onClick={handleResetDatabase}
            className="btn-danger w-full"
          >
            🗑️ Reset Database
          </button>

          <p className="text-xs text-muted mt-2">
            This will permanently delete all analyzed emails, scan history, and retry queues from the local database.
          </p>
        </section>

        {/* About Section */}
        <section className="neu-card p-5">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            About
          </h2>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted">Version</p>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>2.0.0</p>
            </div>
            <div>
              <p className="text-xs text-muted">Last Updated</p>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>2026-08-10</p>
            </div>
            <div>
              <p className="text-xs text-muted">AI Providers</p>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>4 Active</p>
            </div>
            <div>
              <p className="text-xs text-muted">Database</p>
              <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>PostgreSQL</p>
            </div>
          </div>
        </section>
      </div>

      {/* Confirm Modal */}
      {showConfirmModal && confirmAction && (
        <ConfirmModal
          title={confirmAction.title}
          message={confirmAction.message}
          confirmText={confirmAction.confirmText}
          isDangerous={confirmAction.isDangerous}
          onConfirm={confirmAction.onConfirm}
          onCancel={() => setShowConfirmModal(false)}
        />
      )}
    </div>
  );
}

export default Settings;
