"""Unit tests for ActivityStreamTransport (no real HTTP connections)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from xchat_bot.config.settings import AppSettings
from xchat_bot.crypto.stub import StubCrypto
from xchat_bot.events.dedup import EventDeduplicator
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.transport.stream import ActivityStreamTransport


def _make_transport(settings: AppSettings) -> ActivityStreamTransport:
    return ActivityStreamTransport(
        settings=settings,
        normalizer=EventNormalizer(),
        deduplicator=EventDeduplicator(max_size=100),
        crypto=StubCrypto(),
    )


def _make_log() -> MagicMock:
    log = MagicMock()
    log.bind.return_value = log
    return log


@pytest.fixture
def transport(mock_settings: AppSettings) -> ActivityStreamTransport:
    return _make_transport(mock_settings)


async def test_stop_sets_event(transport: ActivityStreamTransport) -> None:
    assert not transport._stop_event.is_set()
    await transport.stop()
    assert transport._stop_event.is_set()


def test_name(transport: ActivityStreamTransport) -> None:
    assert transport.name == "stream"


async def test_process_line_invalid_json_does_not_raise(
    transport: ActivityStreamTransport,
) -> None:
    handler = AsyncMock()
    transport._handler = handler
    log = _make_log()
    await transport._process_line("not valid json {{", log)
    handler.assert_not_called()


async def test_process_line_valid_official_schema(
    transport: ActivityStreamTransport,
) -> None:
    handler = AsyncMock()
    transport._handler = handler
    log = _make_log()

    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {"conversation_id": "CONV_001"},
        }
    }
    await transport._process_line(json.dumps(raw), log)
    handler.assert_called_once()
    event = handler.call_args[0][0]
    assert event.event_type == "chat.received"


async def test_process_line_dedup_skips_second(
    transport: ActivityStreamTransport,
) -> None:
    handler = AsyncMock()
    transport._handler = handler
    log = _make_log()

    raw = json.dumps(
        {"data": {"event_type": "chat.received", "payload": {"conversation_id": "C1"}}}
    )
    await transport._process_line(raw, log)
    await transport._process_line(raw, log)
    assert handler.call_count == 1


async def test_process_line_stub_crypto_sets_is_stub(
    transport: ActivityStreamTransport,
) -> None:
    handler = AsyncMock()
    transport._handler = handler
    log = _make_log()

    from xchat_bot.crypto.stub import StubCrypto
    stub_payload = StubCrypto().encrypt("hello")

    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_STUB",
                "encoded_event": stub_payload,
            },
        }
    }
    await transport._process_line(json.dumps(raw), log)
    handler.assert_called_once()
    event = handler.call_args[0][0]
    assert event.is_stub is True
    assert event.plaintext == "hello"


async def test_process_line_handler_exception_does_not_propagate(
    transport: ActivityStreamTransport,
) -> None:
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    transport._handler = handler
    log = _make_log()

    raw = {"data": {"event_type": "chat.received", "payload": {}}}
    # Should not raise
    await transport._process_line(json.dumps(raw), log)


async def test_connect_and_stream_raises_auth_error_without_bearer(
    mock_settings: AppSettings,
) -> None:
    from xchat_bot.transport.base import AuthError

    transport = _make_transport(mock_settings)
    # mock_settings has no bearer_token
    log = _make_log()
    with pytest.raises(AuthError, match="XCHAT_BEARER_TOKEN"):
        await transport._connect_and_stream(log)
