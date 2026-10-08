// apiCache.js - Frontend API response cache with TTL
// Implements in-memory cache for API responses

class APICache {
  constructor(maxSize = 100, defaultTTL = 60000) {
    this.cache = new Map();
    this.maxSize = maxSize;
    this.defaultTTL = defaultTTL; // milliseconds
    this.stats = { hits: 0, misses: 0 };
  }

  /**
   * Generate cache key from endpoint and params
   */
  _generateKey(endpoint, params = {}) {
    const sortedParams = Object.keys(params)
      .sort()
      .map(key => `${key}=${JSON.stringify(params[key])}`)
      .join('&');
    return `${endpoint}?${sortedParams}`;
  }

  /**
   * Get value from cache if not expired
   */
  get(endpoint, params = {}) {
    const key = this._generateKey(endpoint, params);
    const cached = this.cache.get(key);

    if (!cached) {
      this.stats.misses++;
      return null;
    }

    // Check if expired
    if (Date.now() - cached.timestamp > cached.ttl) {
      this.cache.delete(key);
      this.stats.misses++;
      return null;
    }

    this.stats.hits++;
    return cached.data;
  }

  /**
   * Set value in cache with optional custom TTL
   */
  set(endpoint, params = {}, data, ttl = null) {
    const key = this._generateKey(endpoint, params);

    // Evict oldest if at capacity
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTTL
    });
  }

  /**
   * Invalidate specific endpoint or pattern
   */
  invalidate(pattern) {
    if (typeof pattern === 'string') {
      // Exact match
      for (const key of this.cache.keys()) {
        if (key.includes(pattern)) {
          this.cache.delete(key);
        }
      }
    } else if (pattern instanceof RegExp) {
      // Regex match
      for (const key of this.cache.keys()) {
        if (pattern.test(key)) {
          this.cache.delete(key);
        }
      }
    }
  }

  /**
   * Invalidate multiple patterns at once (H2: explicit invalidation)
   * Used after mutations to invalidate related queries without clearing entire cache
   */
  invalidateMultiple(patterns) {
    for (const pattern of patterns) {
      this.invalidate(pattern);
    }
  }

  /**
   * Clear entire cache
   */
  clear() {
    this.cache.clear();
    this.stats = { hits: 0, misses: 0 };
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const total = this.stats.hits + this.stats.misses;
    const hitRate = total > 0 ? (this.stats.hits / total * 100).toFixed(2) : 0;
    
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hits: this.stats.hits,
      misses: this.stats.misses,
      hitRate: `${hitRate}%`
    };
  }
}

// Global cache instance
export const apiCache = new APICache(100, 60000); // 100 items, 60s TTL

// Cache configuration for specific endpoints
export const CACHE_CONFIG = {
  '/emails': { ttl: 30000 },           // 30s - emails change frequently
  '/labels': { ttl: 300000 },          // 5min - labels rarely change
  '/settings': { ttl: 300000 },        // 5min - settings rarely change
  '/emails/stats': { ttl: 60000 },     // 1min - stats update moderately
  '/auth/status': { ttl: 60000 },      // 1min - auth status
};

export default apiCache;
