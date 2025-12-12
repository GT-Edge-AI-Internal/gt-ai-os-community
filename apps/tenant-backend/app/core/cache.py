"""
Simple in-memory cache with TTL support for Gen Two performance optimization.

This module provides a thread-safe caching layer for expensive database queries
and API calls. Each Uvicorn worker maintains its own cache instance.

Key features:
- TTL-based expiration (configurable per-key)
- LRU eviction when cache reaches max size
- Thread-safe for concurrent request handling
- Pattern-based deletion for cache invalidation

Usage:
    from app.core.cache import get_cache

    cache = get_cache()

    # Get cached value with 60-second TTL
    cached_data = cache.get("agents_minimal_user123", ttl=60)
    if not cached_data:
        data = await fetch_from_db()
        cache.set("agents_minimal_user123", data)
"""

from typing import Any, Optional, Dict, Tuple
from datetime import datetime, timedelta
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Thread-safe TTL cache for API responses and database query results.

    This cache is per-worker (each Uvicorn worker maintains separate cache).
    Cache keys should include tenant_domain or user_id for proper isolation.

    Attributes:
        max_entries: Maximum number of cache entries before LRU eviction
        _cache: Internal cache storage (key -> (timestamp, data))
        _lock: Thread lock for safe concurrent access
    """

    def __init__(self, max_entries: int = 1000):
        """
        Initialize cache with maximum entry limit.

        Args:
            max_entries: Maximum cache entries (default 1000)
                        Typical: 200KB per agent list × 1000 = 200MB per worker
        """
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._lock = Lock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
        logger.info(f"SimpleCache initialized with max_entries={max_entries}")

    def get(self, key: str, ttl: int = 60) -> Optional[Any]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key (should include tenant/user for isolation)
            ttl: Time-to-live in seconds (default 60)

        Returns:
            Cached data if found and not expired, None otherwise

        Example:
            data = cache.get("agents_minimal_user123", ttl=60)
            if data is None:
                # Cache miss - fetch from database
                data = await fetch_from_db()
                cache.set("agents_minimal_user123", data)
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                logger.debug(f"Cache miss: {key}")
                return None

            timestamp, data = self._cache[key]
            age = (datetime.utcnow() - timestamp).total_seconds()

            if age > ttl:
                # Expired - remove and return None
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache expired: {key} (age={age:.1f}s, ttl={ttl}s)")
                return None

            self._hits += 1
            logger.debug(f"Cache hit: {key} (age={age:.1f}s, ttl={ttl}s)")
            return data

    def set(self, key: str, data: Any) -> None:
        """
        Set cache value with current timestamp.

        Args:
            key: Cache key
            data: Data to cache (should be JSON-serializable)

        Note:
            If cache is full, oldest entry is evicted (LRU)
        """
        with self._lock:
            # LRU eviction if cache full
            if len(self._cache) >= self._max_entries:
                oldest_key = min(self._cache.items(), key=lambda x: x[1][0])[0]
                del self._cache[oldest_key]
                logger.warning(
                    f"Cache full ({self._max_entries} entries), "
                    f"evicted oldest key: {oldest_key}"
                )

            self._cache[key] = (datetime.utcnow(), data)
            logger.debug(f"Cache set: {key} (total entries: {len(self._cache)})")

    def delete(self, pattern: str) -> int:
        """
        Delete all keys matching pattern (prefix match).

        Args:
            pattern: Key prefix to match (e.g., "agents_minimal_")

        Returns:
            Number of keys deleted

        Example:
            # Delete all agent cache entries for a user
            count = cache.delete(f"agents_minimal_{user_id}")
            count += cache.delete(f"agents_summary_{user_id}")
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for k in keys_to_delete:
                del self._cache[k]

            if keys_to_delete:
                logger.info(f"Cache invalidated {len(keys_to_delete)} entries matching '{pattern}'")

            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear entire cache (use with caution)."""
        with self._lock:
            entry_count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.warning(f"Cache cleared (removed {entry_count} entries)")

    def size(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with size, hits, misses, hit_rate
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_entries": self._max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 2),
        }


# Singleton cache instance per worker
_cache: Optional[SimpleCache] = None


def get_cache() -> SimpleCache:
    """
    Get or create singleton cache instance.

    Each Uvicorn worker creates its own cache instance (isolated per-process).

    Returns:
        SimpleCache instance
    """
    global _cache
    if _cache is None:
        _cache = SimpleCache(max_entries=1000)
    return _cache


def clear_cache() -> None:
    """Clear global cache (for testing or emergency use)."""
    cache = get_cache()
    cache.clear()
