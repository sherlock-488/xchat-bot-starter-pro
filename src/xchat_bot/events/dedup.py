"""
EventDeduplicator — prevents processing the same event twice.

Uses an in-memory LRU cache keyed by event_id. Configurable max size.
Thread-safe for asyncio (single-threaded event loop).

For production deployments with multiple replicas, replace with a
Redis-backed implementation that shares state across instances.
"""

from __future__ import annotations

from collections import OrderedDict


class EventDeduplicator:
    """LRU-based event deduplication.

    Args:
        max_size: Maximum number of event IDs to track. When full, the oldest
                  entries are evicted (LRU). Default: 10,000.

    Usage::

        dedup = EventDeduplicator(max_size=10_000)

        if dedup.is_duplicate(event.event_id):
            return  # skip already-processed event

        # process event...
        dedup.mark_seen(event.event_id)
    """

    def __init__(self, max_size: int = 10_000) -> None:
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._max_size = max_size
        self._seen: OrderedDict[str, None] = OrderedDict()

    def is_duplicate(self, event_id: str) -> bool:
        """Return True if this event_id has been seen before."""
        return event_id in self._seen

    def mark_seen(self, event_id: str) -> None:
        """Record an event_id as processed.

        If the cache is full, evicts the oldest entry.
        """
        if event_id in self._seen:
            # Move to end (most recently used)
            self._seen.move_to_end(event_id)
            return

        self._seen[event_id] = None

        if len(self._seen) > self._max_size:
            # Evict oldest (first) entry
            self._seen.popitem(last=False)

    def check_and_mark(self, event_id: str) -> bool:
        """Atomically check for duplicate and mark as seen.

        Returns True if the event was already seen (is a duplicate).
        Returns False and marks as seen if it's new.

        This is the preferred method for bot handlers::

            if dedup.check_and_mark(event.event_id):
                return  # duplicate, skip
        """
        if self.is_duplicate(event_id):
            return True
        self.mark_seen(event_id)
        return False

    def clear(self) -> None:
        """Clear all tracked event IDs."""
        self._seen.clear()

    @property
    def size(self) -> int:
        """Number of event IDs currently tracked."""
        return len(self._seen)

    @property
    def max_size(self) -> int:
        """Maximum capacity."""
        return self._max_size
