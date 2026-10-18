/**
 * AnalysisContext.jsx — Global Analysis State (Part 2)
 * Holds bulk analysis progress state at the app level so it persists
 * across tab navigation (component mount/unmount cycles).
 *
 * The SSE connection is stored in a ref to survive re-renders and is
 * only closed when analysis completes or the provider unmounts.
 */

import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { apiRequest } from '../lib/api';

const AnalysisContext = createContext(null);

export function useAnalysis() {
  const ctx = useContext(AnalysisContext);
  if (!ctx) {
    throw new Error('useAnalysis must be used within an AnalysisProvider');
  }
  return ctx;
}

export function AnalysisProvider({ children }) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [total, setTotal] = useState(0);
  const [results, setResults] = useState([]);
  const [stats, setStats] = useState(null);
  const [currentEmail, setCurrentEmail] = useState('');

  const [error, setError] = useState(null);

  // Store the reader ref so the SSE stream survives re-renders
  const readerRef = useRef(null);
  const abortRef = useRef(null);

  // Background pre-fetch coordination
  const isPrefetchingRef = useRef(false);
  const activePrefetchPromiseRef = useRef(null);
  const isAnalyzingRef = useRef(isAnalyzing);
  isAnalyzingRef.current = isAnalyzing;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (readerRef.current) {
        try { readerRef.current.cancel(); } catch { /* ignore */ }
      }
      if (abortRef.current) {
        try { abortRef.current.abort(); } catch { /* ignore */ }
      }
    };
  }, []);

  const prefetchEmails = useCallback(async (limit = 25) => {
    // If active analysis or another prefetch is already running, skip quietly
    if (isAnalyzingRef.current || isPrefetchingRef.current) {
      return;
    }

    isPrefetchingRef.current = true;
    const controller = new AbortController();

    const task = (async () => {
      try {
        const res = await apiRequest(`/emails/fetch-only?limit=${limit}&prefetch=true`, {
          method: 'POST',
          signal: controller.signal,
        });
        if (res.ok) {
          const data = await res.json();
          return data;
        }
      } catch {
        // Silently catch - prefetch should never disrupt the UI
      } finally {
        isPrefetchingRef.current = false;
        activePrefetchPromiseRef.current = null;
      }
    })();

    activePrefetchPromiseRef.current = task;
    return task;
  }, []);

  const startAnalysis = useCallback(async (limit) => {
    if (isAnalyzing) return;

    setIsInitializing(true);
    setIsAnalyzing(true);
    setProgress(0);
    setTotal(0);
    setResults([]);
    setStats(null);
    setError(null);
    setCurrentEmail('');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // CONCURRENCY SHIELD:
      // If a background prefetch is actively in-flight, await its completion
      // instead of issuing a duplicate request or conflicting with it!
      if (isPrefetchingRef.current && activePrefetchPromiseRef.current) {
        setCurrentEmail('Finalizing email download...');
        try {
          await activePrefetchPromiseRef.current;
        } catch {
          // If prefetch failed, normal fetch below will handle it
        }
      }

      setCurrentEmail('Fetching emails from Gmail...');

      const fetchResponse = await apiRequest(`/emails/fetch-only?limit=${limit}`, {
        method: 'POST',
        signal: controller.signal,
      });

      if (!fetchResponse.ok) {
        const errorData = await fetchResponse.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.error || 'Failed to fetch emails');
      }

      const fetchData = await fetchResponse.json();
      setCurrentEmail(`Fetched ${fetchData.fetched || 0} emails. Starting analysis...`);

      setCurrentEmail('Running AI analysis...');

      const labelResponse = await apiRequest(`/emails/label-only?limit=${limit}`, {
        method: 'POST',
        signal: controller.signal,
      });

      if (!labelResponse.ok) {
        const errorData = await labelResponse.json().catch(() => ({}));
        throw new Error(errorData.message || errorData.error || 'Failed to analyze emails');
      }

      const labelData = await labelResponse.json();

      setIsInitializing(false);
      setStats({
        analyzed: labelData.analyzed || 0,
        skipped: labelData.skipped || 0,
        failed: labelData.failed || 0,
        retried: 0,
      });
      setResults(labelData.results || []);
      setProgress(labelData.analyzed || 0);
      setTotal(labelData.analyzed || 0);
      setCurrentEmail('Analysis complete');
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('[AnalysisContext] Analysis error:', err);
        setCurrentEmail('Analysis failed');
        setError(err.message || 'Analysis failed');
      }
    } finally {
      setIsAnalyzing(false);
      setIsInitializing(false);
      readerRef.current = null;
      abortRef.current = null;
    }
  }, [isAnalyzing]);

  // Allow consumers to acknowledge/clear stats so notifications don't re-fire
  const clearStats = useCallback(() => {
    setStats(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value = {
    isAnalyzing,
    isInitializing,
    progress,
    total,
    results,
    stats,
    error,
    currentEmail,
    startAnalysis,
    prefetchEmails,
    clearStats,
    clearError,
  };

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  );
}

export default AnalysisContext;
