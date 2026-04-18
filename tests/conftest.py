"""Shared test fixtures and configuration."""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from xchat_bot.config.settings import AppSettings, reset_settings_cache
from xchat_bot.crypto.stub import StubCrypto
from xchat_bot.events.dedup import EventDeduplicator
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.reply.adapter import LoggingReplyAdapter, ReplyResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def reset_settings() -> None:
    """Clear settings cache before each test."""
    reset_settings_cache()


@pytest.fixture
def mock_settings() -> AppSettings:
    """Valid AppSettings for testing (no real credentials)."""
    return AppSettings(
        consumer_key="test_consumer_key",
        consumer_secret="test_consumer_secret",
        transport_mode="stream",
        crypto_mode="stub",
        log_level="DEBUG",
        log_format="console",
    )


@pytest.fixture
def stub_crypto() -> StubCrypto:
    return StubCrypto()


@pytest.fixture
def normalizer() -> EventNormalizer:
    return EventNormalizer()


@pytest.fixture
def deduplicator() -> EventDeduplicator:
    return EventDeduplicator(max_size=100)


@pytest.fixture
def logging_reply() -> LoggingReplyAdapter:
    return LoggingReplyAdapter()


@pytest.fixture
def mock_reply() -> AsyncMock:
    """Mock reply adapter that records calls."""
    mock = AsyncMock()
    mock.send_reply.return_value = ReplyResult(success=True, event_id="reply_123")
    return mock


@pytest.fixture
def official_event_raw() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "chat_received_observed_xchat.json").read_text())


@pytest.fixture
def demo_event_raw() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "chat_received_demo.json").read_text())


@pytest.fixture
def chat_sent_raw() -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / "chat_sent.json").read_text())


@pytest.fixture
def state_stub_path() -> Path:
    return FIXTURES_DIR / "state_stub.json"


def make_event(
    event_type: str = "chat.received",
    conversation_id: str = "CONV_001",
    sender_id: str = "user123",
    plaintext: str | None = "Hello!",
    event_id: str = "test_event_001",
) -> NormalizedEvent:
    """Factory for NormalizedEvent objects in tests."""
    from datetime import datetime

    return NormalizedEvent(
        event_id=event_id,
        event_type=event_type,
        schema_source="demo",
        received_at=datetime.now(UTC),
        conversation_id=conversation_id,
        sender_id=sender_id,
        plaintext=plaintext,
    )
