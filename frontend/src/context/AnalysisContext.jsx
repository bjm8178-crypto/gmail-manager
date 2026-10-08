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

  // Store the reader ref so the SSE stream survives re-renders
  const readerRef = useRef(null);
  const abortRef = useRef(null);

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

  const startAnalysis = useCallback(async (limit) => {
    if (isAnalyzing) return;

    setIsInitializing(true);
    setIsAnalyzing(true);
    setProgress(0);
    setTotal(0);
    setResults([]);
    setStats(null);
    setCurrentEmail('');

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      setCurrentEmail('Fetching emails from Gmail...');

      const fetchResponse = await apiRequest(`/emails/fetch-only?limit=${limit}`, {
        method: 'POST',
        signal: controller.signal,
      });

      if (!fetchResponse.ok) {
        const errorData = await fetchResponse.json();
        throw new Error(errorData.error || 'Failed to fetch emails');
      }

      const fetchData = await fetchResponse.json();
      setCurrentEmail(`Fetched ${fetchData.fetched || 0} emails. Starting analysis...`);

      setCurrentEmail('Running AI analysis...');

      const labelResponse = await apiRequest(`/emails/label-only?limit=${limit}`, {
        method: 'POST',
        signal: controller.signal,
      });

      if (!labelResponse.ok) {
        const errorData = await labelResponse.json();
        throw new Error(errorData.error || 'Failed to analyze emails');
      }

      const labelData = await labelResponse.json();

      if (labelData.analyzed > 0 || labelData.failed > 0) {
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
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('[AnalysisContext] Analysis error:', err);
        setCurrentEmail('Analysis failed');
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

  const value = {
    isAnalyzing,
    isInitializing,
    progress,
    total,
    results,
    stats,
    currentEmail,
    startAnalysis,
    clearStats,
  };

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  );
}

export default AnalysisContext;
