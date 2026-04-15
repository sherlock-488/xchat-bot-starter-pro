"""Unit tests for EventDeduplicator."""

from __future__ import annotations

import pytest

from xchat_bot.events.dedup import EventDeduplicator


def test_new_event_not_duplicate() -> None:
    dedup = EventDeduplicator()
    assert dedup.is_duplicate("event_001") is False


def test_seen_event_is_duplicate() -> None:
    dedup = EventDeduplicator()
    dedup.mark_seen("event_001")
    assert dedup.is_duplicate("event_001") is True


def test_check_and_mark_first_time() -> None:
    dedup = EventDeduplicator()
    assert dedup.check_and_mark("event_001") is False  # new, not duplicate
    assert dedup.is_duplicate("event_001") is True  # now seen


def test_check_and_mark_second_time() -> None:
    dedup = EventDeduplicator()
    dedup.check_and_mark("event_001")
    assert dedup.check_and_mark("event_001") is True  # duplicate


def test_lru_eviction() -> None:
    dedup = EventDeduplicator(max_size=3)
    dedup.mark_seen("a")
    dedup.mark_seen("b")
    dedup.mark_seen("c")
    assert dedup.size == 3

    # Adding a 4th evicts the oldest ("a")
    dedup.mark_seen("d")
    assert dedup.size == 3
    assert not dedup.is_duplicate("a")  # evicted
    assert dedup.is_duplicate("b")
    assert dedup.is_duplicate("c")
    assert dedup.is_duplicate("d")


def test_clear() -> None:
    dedup = EventDeduplicator()
    dedup.mark_seen("event_001")
    dedup.mark_seen("event_002")
    dedup.clear()
    assert dedup.size == 0
    assert not dedup.is_duplicate("event_001")


def test_max_size_property() -> None:
    dedup = EventDeduplicator(max_size=500)
    assert dedup.max_size == 500


def test_invalid_max_size() -> None:
    with pytest.raises(ValueError):
        EventDeduplicator(max_size=0)


def test_different_events_independent() -> None:
    dedup = EventDeduplicator()
    dedup.mark_seen("event_001")
    assert not dedup.is_duplicate("event_002")
    assert dedup.is_duplicate("event_001")
