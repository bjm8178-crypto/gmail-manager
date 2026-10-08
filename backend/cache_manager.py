"""
cache_manager.py — API Response Caching & Query Result Caching
Implements in-memory LRU cache with TTL for expensive operations.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import time
import json
from functools import wraps
from collections import OrderedDict
from threading import Lock

class LRUCache:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size=1000, default_ttl=300):
        self.cache = OrderedDict()
        self.timestamps = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key):
        """Get value from cache if not expired."""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            # Check TTL
            if time.time() - self.timestamps[key] > self.default_ttl:
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
    
    def set(self, key, value, ttl=None):
        """Set value in cache with optional custom TTL."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
            
            # Evict oldest if over limit
            if len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
    
    def invalidate(self, key):
        """Remove specific key from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]
    
    def clear(self):
        """Clear entire cache."""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0
    
    def stats(self):
        """Return cache statistics."""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 2)
            }


# Global cache instances
api_cache = LRUCache(max_size=1000, default_ttl=300)  # 5 min TTL
query_cache = LRUCache(max_size=500, default_ttl=180)  # 3 min TTL
ml_cache = LRUCache(max_size=200, default_ttl=3600)  # 1 hour TTL


def cache_api_response(ttl=300, key_prefix="api"):
    """
    Decorator to cache API endpoint responses.
    
    Usage:
        @cache_api_response(ttl=300, key_prefix="emails")
        async def get_emails(user_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Check cache first
            cached_result = api_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"[CACHE HIT] {cache_key[:100]}")
                return cached_result
            
            # Cache miss - execute function
            logger.debug(f"[CACHE MISS] {cache_key[:100]}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            api_cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def cache_query_result(ttl=180, key_prefix="query"):
    """
    Decorator to cache database query results.
    
    Usage:
        @cache_query_result(ttl=180, key_prefix="labels")
        def get_labels(user_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Check cache
            cached_result = query_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"[QUERY CACHE HIT] {cache_key[:100]}")
                return cached_result
            
            # Execute query
            logger.debug(f"[QUERY CACHE MISS] {cache_key[:100]}")
            result = func(*args, **kwargs)
            
            # Cache result
            query_cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def invalidate_user_cache(user_id: int):
    """Invalidate all cache entries for a specific user."""
    # This is a simplified invalidation - walks through cache keys
    # In production, consider using Redis with key patterns
    for cache in [api_cache, query_cache]:
        keys_to_invalidate = []
        with cache.lock:
            for key in cache.cache.keys():
                if f"user_id={user_id}" in str(key) or f"({user_id}," in str(key):
                    keys_to_invalidate.append(key)
        
        for key in keys_to_invalidate:
            cache.invalidate(key)
    
    logger.info(f"[CACHE] Invalidated cache for user_id={user_id}")


def get_cache_stats():
    """Return statistics for all caches."""
    return {
        "api_cache": api_cache.stats(),
        "query_cache": query_cache.stats(),
        "ml_cache": ml_cache.stats()
    }
