"""Retrieval Cache Layer.

Provides an abstract RetrievalCache interface and a high-performance in-memory LRU
cache implementation with TTL expiration. Designed to be easily replaced by Redis
or distributed caches without application code modification.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger
from app.retrieval.models import SearchFilters, SearchOptions

logger = get_logger(__name__)


class RetrievalCache(ABC):
    """Abstract interface defining cache operations for query retrieval results."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key.

        Args:
            key: Cache lookup key.

        Returns:
            Cached item or None if expired/not found.
        """
        ...

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store an item in the cache with optional TTL.

        Args:
            key: Cache key.
            value: Item to store.
            ttl_seconds: Expiration lifetime in seconds.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Args:
            key: Cache key to delete.

        Returns:
            bool: True if key was present and removed, False otherwise.
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Purge all entries from the cache."""
        ...

    @staticmethod
    def build_cache_key(
        normalized_query: str,
        filters: SearchFilters | None = None,
        options: SearchOptions | None = None,
        prefix: str = "retrieval",
    ) -> str:
        """Generate a deterministic, collision-resistant cache key.

        Args:
            normalized_query: Preprocessed query text.
            filters: Active search filters.
            options: Active search execution options.
            prefix: Key namespace prefix.

        Returns:
            str: Deterministic hash key.
        """
        key_payload: dict[str, Any] = {
            "query": normalized_query,
            "filters": filters.model_dump(mode="json") if filters else {},
            "options": (
                {
                    "top_k": options.top_k,
                    "dense_weight": options.dense_weight,
                    "sparse_weight": options.sparse_weight,
                    "rrf_k": options.rrf_k,
                    "min_score": options.min_score_threshold,
                    "dense_enabled": options.enabled_dense,
                    "sparse_enabled": options.enabled_sparse,
                    "fusion": options.fusion_strategy,
                    "collection": options.collection_name,
                }
                if options
                else {}
            ),
        }
        serialized = json.dumps(key_payload, sort_keys=True)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"


class _CacheEntry:
    """Internal container for cached item and expiration timestamp."""

    __slots__ = ("expires_at", "last_accessed", "value")

    def __init__(self, value: Any, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at
        self.last_accessed = time.monotonic()


class InMemoryRetrievalCache(RetrievalCache):
    """In-memory thread-safe LRU cache with per-item TTL expiration."""

    def __init__(
        self,
        default_ttl_seconds: int = 300,
        max_size: int = 1000,
    ) -> None:
        """Initialize InMemoryRetrievalCache.

        Args:
            default_ttl_seconds: Default time-to-live in seconds.
            max_size: Maximum entries before LRU eviction.
        """
        self._default_ttl_seconds = default_ttl_seconds
        self._max_size = max_size
        self._store: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Retrieve cached value if not expired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            now = time.monotonic()
            if now > entry.expires_at:
                del self._store[key]
                return None

            entry.last_accessed = now
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store value with TTL, evicting oldest if max_size is reached."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        expires_at = time.monotonic() + ttl

        async with self._lock:
            # If at max size and key is new, evict expired or oldest accessed entry
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_one()

            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> bool:
        """Remove key from store."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        """Purge all entries."""
        async with self._lock:
            self._store.clear()

    def _evict_one(self) -> None:
        """Evict either an expired item or the least recently accessed item."""
        now = time.monotonic()
        # First check for expired entries
        for k, v in list(self._store.items()):
            if now > v.expires_at:
                del self._store[k]
                return

        # Otherwise evict least recently accessed entry
        if self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k].last_accessed)
            del self._store[oldest_key]
