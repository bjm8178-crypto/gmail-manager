/**
 * BulkActionToolbar.jsx — Phase 3: Bulk Email Operations UI
 * Appears when emails are selected. Provides bulk actions:
 * - Delete (respects user's trash/permanent mode)
 * - Mark Safe (clear quarantine)
 * - Quarantine (flag as scam)
 * - Apply Label (dropdown)
 * - Clear Selection
 */

import React, { useState } from 'react';
import { apiBulkDelete, apiBulkMarkSafe, apiBulkQuarantine, apiBulkLabel } from '../lib/api';
import { useToast } from './ToastNotification';

function BulkActionToolbar({ 
  selectedCount, 
  selectedEmails, 
  onClearSelection, 
  onActionComplete,
  availableLabels = []
}) {
  const toast = useToast();
  const [isProcessing, setIsProcessing] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [showLabelDropdown, setShowLabelDropdown] = useState(false);

  const readBulkResponse = async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || data.message || `Request failed (${response.status})`);
    }
    return data;
  };
  // Chunk array into batches of 100
  const chunkArray = (arr, size) => {
    const chunks = [];
    for (let i = 0; i < arr.length; i += size) {
      chunks.push(arr.slice(i, i + size));
    }
    return chunks;
  };


  const handleBulkDelete = async () => {
    if (selectedEmails.length === 0) return;
    
    setIsProcessing(true);
    try {
      const chunks = chunkArray(selectedEmails, 100);
      let totalDeleted = 0;
      
      for (const chunk of chunks) {
        const res = await apiBulkDelete(chunk);
        const data = await readBulkResponse(res);
        if (data.deleted_count) {
          totalDeleted += data.deleted_count;
        }
      }
      
      toast.success('Bulk delete complete', `${totalDeleted} emails deleted`);
      onClearSelection();
      onActionComplete();
    } catch (error) {
      console.error('Bulk delete failed:', error);
      toast.error('Bulk delete failed', error.message);
    } finally {
      setIsProcessing(false);
      setShowConfirmDelete(false);
    }
  };

  const handleBulkMarkSafe = async () => {
    if (selectedEmails.length === 0) return;
    
    setIsProcessing(true);
    try {
      const chunks = chunkArray(selectedEmails, 100);
      let totalMarked = 0;
      
      for (const chunk of chunks) {
        const res = await apiBulkMarkSafe(chunk);
        const data = await readBulkResponse(res);
        if (data.updated_count) {
          totalMarked += data.updated_count;
        }
      }
      
      toast.success('Bulk mark safe complete', `${totalMarked} emails marked safe`);
      onClearSelection();
      onActionComplete();
    } catch (error) {
      console.error('Bulk mark safe failed:', error);
      toast.error('Operation failed', error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkQuarantine = async () => {
    if (selectedEmails.length === 0) return;
    
    setIsProcessing(true);
    try {
      const chunks = chunkArray(selectedEmails, 100);
      let totalQuarantined = 0;
      
      for (const chunk of chunks) {
        const res = await apiBulkQuarantine(chunk);
        const data = await readBulkResponse(res);
        if (data.updated_count) {
          totalQuarantined += data.updated_count;
        }
      }
      
      toast.success('Bulk quarantine complete', `${totalQuarantined} emails quarantined`);
      onClearSelection();
      onActionComplete();
    } catch (error) {
      console.error('Bulk quarantine failed:', error);
      toast.error('Operation failed', error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleBulkLabel = async (label) => {
    const labelId = Number(label?.label_id);
    if (selectedEmails.length === 0 || !Number.isInteger(labelId) || labelId < 1) return;

    const labelName = label.label_name || String(labelId);
    setIsProcessing(true);
    try {
      const chunks = chunkArray(selectedEmails, 100);
      let totalLabeled = 0;
      
      for (const chunk of chunks) {
        const res = await apiBulkLabel(chunk, labelId);
        const data = await readBulkResponse(res);
        if (data.updated_count) {
          totalLabeled += data.updated_count;
        }
      }
      
      toast.success('Bulk label complete', `${totalLabeled} emails labeled as "${labelName}"`);
      onClearSelection();
      onActionComplete();
    } catch (error) {
      console.error('Bulk label failed:', error);
      toast.error('Operation failed', error.message);
    } finally {
      setIsProcessing(false);
      setShowLabelDropdown(false);
    }
  };

  return (
    <>
      {/* Confirmation modal for delete */}
      {showConfirmDelete && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
          onClick={() => setShowConfirmDelete(false)}
        >
          <div 
            style={{
              backgroundColor: 'var(--color-surface)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '400px',
              width: '90%',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 12px 0', fontSize: '18px', fontWeight: '600' }}>
              Delete {selectedCount} email{selectedCount > 1 ? 's' : ''}?
            </h3>
            <p style={{ margin: '0 0 20px 0', color: 'var(--color-text-secondary)', fontSize: '14px' }}>
              This action cannot be undone. The selected emails will be permanently deleted.
            </p>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowConfirmDelete(false)}
                disabled={isProcessing}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--color-border)',
                  backgroundColor: 'transparent',
                  color: 'var(--color-text)',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleBulkDelete}
                disabled={isProcessing}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: 'var(--color-danger)',
                  color: 'white',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                  opacity: isProcessing ? 0.6 : 1,
                }}
              >
                {isProcessing ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk action toolbar */}
      <div
        style={{
          position: 'sticky',
          top: '0',
          zIndex: 100,
          backgroundColor: 'var(--color-primary)',
          color: 'white',
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
          borderRadius: '12px',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
          <span style={{ fontWeight: '600', fontSize: '14px' }}>
            {selectedCount} selected
          </span>
          
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setShowConfirmDelete(true)}
              disabled={isProcessing}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                color: 'white',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: isProcessing ? 0.6 : 1,
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!isProcessing) {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
              }}
            >
              🗑️ Delete
            </button>

            <button
              onClick={handleBulkMarkSafe}
              disabled={isProcessing}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                color: 'white',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: isProcessing ? 0.6 : 1,
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!isProcessing) {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
              }}
            >
              ✓ Mark Safe
            </button>

            <button
              onClick={handleBulkQuarantine}
              disabled={isProcessing}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                color: 'white',
                cursor: isProcessing ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: '500',
                opacity: isProcessing ? 0.6 : 1,
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!isProcessing) {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
              }}
            >
              ⚠️ Quarantine
            </button>

            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowLabelDropdown(!showLabelDropdown)}
                disabled={isProcessing}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.3)',
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  color: 'white',
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  fontSize: '13px',
                  fontWeight: '500',
                  opacity: isProcessing ? 0.6 : 1,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (!isProcessing) {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)';
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
                }}
              >
                🏷️ Label ▼
              </button>

              {showLabelDropdown && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    marginTop: '4px',
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                    minWidth: '150px',
                    zIndex: 1000,
                  }}
                >
                  {availableLabels.map((label) => (
                    <button
                      key={label.label_id}
                      onClick={() => handleBulkLabel(label)}
                      disabled={isProcessing}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: 'none',
                        backgroundColor: 'transparent',
                        color: 'var(--color-text)',
                        textAlign: 'left',
                        cursor: isProcessing ? 'not-allowed' : 'pointer',
                        fontSize: '13px',
                        borderBottom: '1px solid var(--color-border)',
                      }}
                      onMouseEnter={(e) => {
                        if (!isProcessing) {
                          e.currentTarget.style.backgroundColor = 'var(--color-hover)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <button
          onClick={onClearSelection}
          disabled={isProcessing}
          style={{
            padding: '6px 12px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            backgroundColor: 'transparent',
            color: 'white',
            cursor: isProcessing ? 'not-allowed' : 'pointer',
            fontSize: '13px',
            fontWeight: '500',
            opacity: isProcessing ? 0.6 : 1,
          }}
        >
          Clear
        </button>
      </div>
    </>
  );
}

export default BulkActionToolbar;
