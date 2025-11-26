"""Lightweight in-memory cache utilities used by the layout pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, Optional


@dataclass
class _CacheEntry:
    value: Any
    expires_at: Optional[float]

    def is_expired(self) -> bool:
        return self.expires_at is not None and time.monotonic() >= self.expires_at


class Cache:
    """Concurrent-safe cache with TTL and size control."""

    def __init__(self, max_size: int = 1024, ttl: int = 3600) -> None:
        self.max_size = max(1, int(max_size))
        self.default_ttl = max(0, int(ttl))
        self._entries: Dict[str, _CacheEntry] = {}
        self._lock = RLock()

    def _prune_expired(self) -> None:
        expired_keys = [key for key, entry in self._entries.items() if entry.is_expired()]
        for key in expired_keys:
            self._entries.pop(key, None)

    def _ensure_capacity(self) -> None:
        if len(self._entries) <= self.max_size:
            return
        # Drop the oldest entries first based on expiry time/insert order
        sorted_items = sorted(
            self._entries.items(),
            key=lambda item: (item[1].expires_at or float("inf")),
        )
        for key, _ in sorted_items[: len(self._entries) - self.max_size]:
            self._entries.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl_to_use = self.default_ttl if ttl is None else max(0, int(ttl))
        expires_at = time.monotonic() + ttl_to_use if ttl_to_use else None
        with self._lock:
            self._prune_expired()
            self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
            self._ensure_capacity()

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._entries.pop(key, None)
                return False
            return True

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl=ttl)
        return value
