"""
WebhookTransport — X POSTs events to your server.

Creates and manages a FastAPI webhook server. Events arrive as HTTP POST
requests, are verified, normalized, and dispatched to the EventHandler.

Requirements for webhook mode:
  - A public HTTPS URL (X won't POST to localhost)
  - The URL registered in X Developer Portal
  - Subscription created via `xchat subscribe`

Use `xchat subscribe --url https://your-domain.com` to register your webhook.
"""

from __future__ import annotations

import structlog
import uvicorn
from fastapi import FastAPI

from xchat_bot.config.settings import AppSettings
from xchat_bot.crypto.base import CryptoAdapter
from xchat_bot.events.dedup import EventDeduplicator
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.transport.base import EventHandler, Transport
from xchat_bot.webhook.app import create_app

logger = structlog.get_logger(__name__)


class WebhookTransport(Transport):
    """Webhook transport — runs a FastAPI server to receive X events.

    X sends events as HTTP POST requests to your webhook URL.
    This transport handles CRC challenges, signature verification,
    event normalization, deduplication, and crypto decryption.

    Args:
        settings: Application settings.
        normalizer: EventNormalizer instance.
        deduplicator: EventDeduplicator instance.
        crypto: CryptoAdapter for decrypting message payloads.
    """

    def __init__(
        self,
        settings: AppSettings,
        normalizer: EventNormalizer,
        deduplicator: EventDeduplicator,
        crypto: CryptoAdapter,
    ) -> None:
        self._settings = settings
        self._normalizer = normalizer
        self._deduplicator = deduplicator
        self._crypto = crypto
        self._server: uvicorn.Server | None = None

    @property
    def name(self) -> str:
        return "webhook"

    async def run(self, handler: EventHandler) -> None:
        """Start the webhook server.

        Args:
            handler: Async callable that receives NormalizedEvent objects.
        """
        log = logger.bind(
            transport="webhook",
            host=self._settings.webhook_host,
            port=self._settings.webhook_port,
        )

        # Wrap handler to apply dedup + crypto before dispatching
        async def enriched_handler(event: NormalizedEvent) -> None:
            if self._deduplicator.check_and_mark(event.event_id):
                log.debug("webhook_duplicate_event", event_id=event.event_id)
                return

            if event.encrypted and self._crypto:
                enc = event.encrypted
                result = self._crypto.decrypt(
                    encoded_event=enc.encoded_event or enc.encrypted_content or "",
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

        app = create_app(
            consumer_secret=self._settings.consumer_secret.get_secret_value(),
            handler=enriched_handler,
            normalizer=self._normalizer,
        )

        config = uvicorn.Config(
            app,
            host=self._settings.webhook_host,
            port=self._settings.webhook_port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        log.info("webhook_server_starting")
        await self._server.serve()
        log.info("webhook_server_stopped")

    async def stop(self) -> None:
        """Stop the webhook server gracefully."""
        if self._server:
            self._server.should_exit = True
            logger.info("webhook_stop_requested")

    def get_app(self, handler: EventHandler) -> FastAPI:
        """Return the FastAPI app without starting the server.

        Useful for running with an external ASGI server (gunicorn, etc.)

        Args:
            handler: Async callable that receives NormalizedEvent objects.

        Returns:
            FastAPI application instance.
        """
        return create_app(
            consumer_secret=self._settings.consumer_secret.get_secret_value(),
            handler=handler,
            normalizer=self._normalizer,
        )
