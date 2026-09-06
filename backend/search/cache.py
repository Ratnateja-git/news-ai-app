"""Small in-process TTL + LRU cache for search results.

Deliberately not Redis/memcached — Priya runs as a single local process
(same assumption session.py already makes for conversation state), so an
in-memory dict is the right amount of complexity. If Priya ever runs as
multiple worker processes, swap this module's storage for Redis without
touching pipeline.py, which only calls get()/set().
"""

import time
from collections import OrderedDict
from threading import Lock

DEFAULT_TTL_SECONDS = 900  # 15 minutes — search results go stale slowly.
MAX_ENTRIES = 256

_store: "OrderedDict[str, tuple[float, object]]" = OrderedDict()
_lock = Lock()


def make_key(*parts: object) -> str:
    """Build a stable cache key from arbitrary hashable-ish parts."""
    return "|".join(str(part).strip().lower() for part in parts)


def get(key: str) -> object | None:
    """Return the cached value, or None if missing/expired.

    A hit moves the entry to the end (most-recently-used) under the lock.
    """
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del _store[key]
            return None

        _store.move_to_end(key)
        return value


def set(key: str, value: object, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Store a value with a TTL, evicting the oldest entry if over capacity."""
    with _lock:
        _store[key] = (time.monotonic() + ttl_seconds, value)
        _store.move_to_end(key)

        while len(_store) > MAX_ENTRIES:
            _store.popitem(last=False)


def clear() -> None:
    """Drop all cached entries. Mainly useful for tests."""
    with _lock:
        _store.clear()