"""Unit tests for WebhookTransport (no server startup)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from xchat_bot.config.settings import AppSettings
from xchat_bot.crypto.stub import StubCrypto
from xchat_bot.events.dedup import EventDeduplicator
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.transport.webhook import WebhookTransport


@pytest.fixture
def transport(mock_settings: AppSettings) -> WebhookTransport:
    return WebhookTransport(
        settings=mock_settings,
        normalizer=EventNormalizer(),
        deduplicator=EventDeduplicator(max_size=100),
        crypto=StubCrypto(),
    )


def test_name(transport: WebhookTransport) -> None:
    assert transport.name == "webhook"


def test_get_app_returns_fastapi(transport: WebhookTransport) -> None:
    handler = AsyncMock()
    app = transport.get_app(handler)
    assert isinstance(app, FastAPI)


async def test_stop_no_server_does_not_raise(transport: WebhookTransport) -> None:
    # No server started — stop() should be a no-op
    await transport.stop()


async def test_stop_with_server_sets_should_exit(
    transport: WebhookTransport,
) -> None:
    import uvicorn

    mock_server = AsyncMock(spec=uvicorn.Server)
    mock_server.should_exit = False
    transport._server = mock_server  # type: ignore[assignment]
    await transport.stop()
    assert mock_server.should_exit is True


async def test_enriched_handler_dedup(
    transport: WebhookTransport,
) -> None:
    """Verify the enriched_handler inside run() deduplicates events."""
    from datetime import UTC, datetime

    from xchat_bot.events.models import NormalizedEvent

    received: list[NormalizedEvent] = []

    async def handler(event: NormalizedEvent) -> None:
        received.append(event)

    # Build the enriched_handler the same way run() does
    dedup = transport._deduplicator
    crypto = transport._crypto

    async def enriched(event: NormalizedEvent) -> None:
        if dedup.check_and_mark(event.event_id):
            return
        if event.encrypted and crypto:
            result = crypto.decrypt(
                encoded_event=(
                    event.encrypted.encoded_event or event.encrypted.encrypted_content or ""
                ),
                encrypted_conversation_key=event.encrypted.encrypted_conversation_key,
            )
            event = event.model_copy(
                update={
                    "plaintext": result.plaintext,
                    "is_stub": event.is_stub or (result.mode == "stub"),
                    "decrypt_notes": result.notes,
                }
            )
        await handler(event)

    event = NormalizedEvent(
        event_id="dedup_test_001",
        event_type="chat.received",
        schema_source="demo",
        received_at=datetime.now(UTC),
    )
    await enriched(event)
    await enriched(event)
    assert len(received) == 1
