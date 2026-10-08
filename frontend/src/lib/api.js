/**
 * api.js - Centralized API Client with JWT Authentication
 * Handles all API requests with automatic JWT token injection
 */

import { apiCache, CACHE_CONFIG } from './apiCache.js';

export const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000';

// Authentication is maintained by HttpOnly cookies set by the backend.
export const getAuthToken = () => null;
export const setAuthToken = () => {};

const getCsrfToken = () => {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
};

let csrfFetchInProgress = false;

const ensureCsrfToken = async () => {
  // Try to read from cookie first
  let token = getCsrfToken();
  if (token) return token;
  
  // Avoid concurrent fetches
  if (csrfFetchInProgress) {
    // Wait a bit and retry
    await new Promise(resolve => setTimeout(resolve, 100));
    token = getCsrfToken();
    if (token) return token;
  }
  
  // Fetch csrf_token from /auth/status
  csrfFetchInProgress = true;
  try {
    const response = await fetch(`${API_BASE}/auth/status`, {
      credentials: 'include',
      headers: { 'Accept': 'application/json' }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch CSRF token: ${response.status}`);
    }
    
    // Cookie should now be set by the backend
    token = getCsrfToken();
    if (!token) {
      throw new Error('CSRF token unavailable, please log in again');
    }
    
    return token;
  } finally {
    csrfFetchInProgress = false;
  }
};

let accountScope = null;
let cacheGeneration = 0;
export const invalidateAccountCache = () => { cacheGeneration++; apiCache.clear(); };

export const clearAuthToken = () => {
  invalidateAccountCache();
  accountScope = null;
};

const invalidateMutationCache = (endpoint, method) => {
  // Map mutations to affected cache keys
  const invalidationRules = {
    // Email mutations affect inbox, alerts, quarantine, stats
    '/emails/mark-safe': ['/emails', '/emails/stats', '/emails/alerts', '/emails/quarantine'],
    '/emails/mark-quarantine': ['/emails', '/emails/stats', '/emails/alerts', '/emails/quarantine'],
    '/emails/delete': ['/emails', '/emails/stats', '/emails/alerts', '/emails/quarantine'],
    '/emails/retry-failed': ['/emails', '/emails/stats'],
    '/emails/bulk-delete': ['/emails', '/emails/stats', '/emails/alerts', '/emails/quarantine'],
    
    // Label mutations affect labels and related emails
    '/labels': ['/labels', '/emails'],
    
    // Settings changes affect everything (rare, so full invalidation acceptable)
    '/settings': ['*'], // Full cache clear
    
    // Auth changes always clear everything
    '/auth/logout': ['*'],
  };

  // Check if endpoint matches any invalidation rule
  for (const [ruleEndpoint, affectedKeys] of Object.entries(invalidationRules)) {
    if (endpoint.startsWith(ruleEndpoint)) {
      if (affectedKeys.includes('*')) {
        // Full cache clear for rare operations
        apiCache.clear();
      } else {
        // Selective invalidation
        apiCache.invalidateMultiple(affectedKeys);
      }
      return;
    }
  }

  // Default: for unknown mutations, invalidate emails and stats (conservative)
  apiCache.invalidateMultiple(['/emails', '/emails/stats']);
};

export const setAuthTokenLegacy = (token) => {
  if (token !== getAuthToken()) invalidateAccountCache();
  if (token) {
    // legacy token storage removed
  } else {
    // legacy token storage removed
  }
};

export const clearAuthTokenLegacy = () => {
  invalidateAccountCache();
  accountScope = null;
  // legacy token storage removed
};

/** Make an authenticated API request using HttpOnly cookies and CSRF protection. */
export const apiRequest = async (endpoint, options = {}) => {
  const token = null;
  if (accountScope !== token) { invalidateAccountCache(); accountScope = token; }
  const generation = cacheGeneration;
  const method = (options.method || 'GET').toUpperCase();
  const isGet = method === 'GET';
  const cacheable = isGet && endpoint !== '/auth/status' && !options.noCache;

  const headers = { ...options.headers };
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
    // Ensure CSRF token is available before making state-changing requests
    const csrfToken = await ensureCsrfToken();
    headers['X-CSRF-Token'] = csrfToken;
  }

  const config = {
    ...options,
    headers,
    credentials: 'include',
  };
  
  // Check cache for GET requests (unless no-cache specified)
  if (isGet) {
      if (cacheable) {
      const cached = apiCache.get(endpoint, options.params || {});
      if (cached !== null) {
        console.log('[API CACHE HIT]', endpoint);
        return { json: async () => cached, ok: true, status: 200 };
      }
    }
  }
  
  if (!endpoint.startsWith('/') || endpoint.startsWith('//')) throw new Error('API endpoint must be a relative path');
  const url = `${API_BASE}${endpoint}`;
  
  try {
    const response = await fetch(url, config);
    
    if (token !== getAuthToken()) throw new Error('Account changed during request');
    // Handle 401 Unauthorized - clear token and redirect to login
    if (response.status === 401) {
      clearAuthToken();
      apiCache.clear(); // Clear cache on logout
      // Only redirect if not already on login page
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
      throw new Error('Unauthorized - please log in');
    }
    
    // Cache successful GET responses
    if (response.ok && cacheable) {
      const clonedResponse = response.clone();
      const data = await clonedResponse.json();
      
      // Get TTL from config or use default
      const cacheConfig = CACHE_CONFIG[endpoint] || {};
      if (generation === cacheGeneration && token === getAuthToken()) apiCache.set(endpoint, options.params || {}, data, cacheConfig.ttl);
      
      // Return a new response with the cached data
      return { json: async () => data, ok: true, status: response.status };
    }
    
    // H2: Selective cache invalidation on mutations (POST, PUT, DELETE)
    // Only invalidate related endpoints, not entire cache
    if (!isGet) {
      invalidateMutationCache(endpoint, method);
    }
    
    return response;
  } catch (error) {
    // On error, only invalidate if mutation was attempted
    if (!isGet) {
      invalidateMutationCache(endpoint, method);
    }
    console.error('[API] Request failed:', error);
    throw error;
  }
};

/**
 * Convenience method for GET requests
 */
export const apiGet = async (endpoint) => {
  return apiRequest(endpoint, { method: 'GET' });
};

/**
 * Convenience method for POST requests
 */
export const apiPost = async (endpoint, body) => {
  return apiRequest(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
};

/**
 * Convenience method for DELETE requests
 */
export const apiDelete = async (endpoint) => {
  return apiRequest(endpoint, { method: 'DELETE' });
};

/**
 * Phase 3: Bulk Email Operations API Methods
 */

export const apiBulkDelete = async (emailIds) => {
  return apiPost('/emails/bulk-delete', { email_ids: emailIds });
};

export const apiBulkMarkSafe = async (emailIds) => {
  return apiPost('/emails/bulk-mark-safe', { email_ids: emailIds });
};

export const apiBulkQuarantine = async (emailIds) => {
  return apiPost('/emails/bulk-quarantine', { email_ids: emailIds });
};

export const apiBulkLabel = async (emailIds, labelId) => {
  return apiPost('/emails/bulk-label', { email_ids: emailIds, label_id: labelId });
};

export default {
  apiRequest,
  apiGet,
  apiPost,
  apiDelete,
  apiBulkDelete,
  apiBulkMarkSafe,
  apiBulkQuarantine,
  apiBulkLabel,
  getAuthToken,
  setAuthToken,
  clearAuthToken,
  API_BASE,
};
