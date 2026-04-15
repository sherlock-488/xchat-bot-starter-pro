"""
ActivityStreamTransport — persistent HTTP stream connection to X Activity API.

Connects to GET /2/activity/stream and reads events line by line.
Handles reconnection with exponential backoff on transient failures.

Authentication
--------------
The Activity Stream uses the **app Bearer Token** (``XCHAT_BEARER_TOKEN``),
not a user access token.  Generate it in X Developer Portal → Keys and tokens.

Reference: https://docs.x.com/x-api/direct-messages/activity-stream

Transport comparison
--------------------
- Stream: you open a persistent GET; X pushes events over it.
  No public URL required. Simpler for dev and single-instance bots.
- Webhook: X POSTs events to your server.
  Requires a public HTTPS URL. Better for multi-replica production.
"""

from __future__ import annotations

import asyncio
import json
import secrets

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from xchat_bot.config.settings import AppSettings
from xchat_bot.crypto.base import CryptoAdapter
from xchat_bot.events.dedup import EventDeduplicator
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.transport.base import AuthError, EventHandler, StreamDisconnected, Transport

logger = structlog.get_logger(__name__)

# Official X Activity API v2 stream endpoint.
# Reference: https://docs.x.com/x-api/direct-messages/activity-stream
_STREAM_ENDPOINT = "https://api.x.com/2/activity/stream"


class ActivityStreamTransport(Transport):
    """Persistent HTTP stream transport for X Activity API.

    Connects to GET /2/activity/stream using the app Bearer Token and processes
    events as they arrive.  Reconnects automatically on transient failures.

    Args:
        settings: Application settings.  ``settings.bearer_token`` must be set.
        normalizer: EventNormalizer instance.
        deduplicator: EventDeduplicator instance.
        crypto: CryptoAdapter for decrypting message payloads.
        stream_url: Override the stream endpoint URL (useful for testing).
    """

    def __init__(
        self,
        settings: AppSettings,
        normalizer: EventNormalizer,
        deduplicator: EventDeduplicator,
        crypto: CryptoAdapter,
        *,
        stream_url: str = _STREAM_ENDPOINT,
    ) -> None:
        self._settings = settings
        self._normalizer = normalizer
        self._deduplicator = deduplicator
        self._crypto = crypto
        self._stream_url = stream_url
        self._stop_event = asyncio.Event()
        self._handler: EventHandler | None = None

    @property
    def name(self) -> str:
        return "stream"

    async def run(self, handler: EventHandler) -> None:
        """Start the stream loop with automatic reconnection.

        Args:
            handler: Async callable that receives NormalizedEvent objects.

        Raises:
            AuthError: If authentication fails (401/403).
            StreamDisconnected: If max retries are exhausted.
        """
        self._handler = handler
        self._stop_event.clear()

        log = logger.bind(transport="stream", stream_url=self._stream_url)
        log.info("stream_starting")

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(
                    (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)
                ),
                wait=wait_exponential(
                    multiplier=self._settings.retry_backoff_base,
                    max=self._settings.retry_backoff_max,
                ),
                stop=stop_after_attempt(self._settings.max_retries),
                reraise=False,
            ):
                with attempt:
                    if self._stop_event.is_set():
                        break
                    await self._connect_and_stream(log)
        except RetryError as exc:
            raise StreamDisconnected(
                f"Stream disconnected after {self._settings.max_retries} retries"
            ) from exc

        log.info("stream_stopped")

    async def stop(self) -> None:
        """Signal the stream to stop after the current event."""
        self._stop_event.set()
        logger.info("stream_stop_requested")

    async def _connect_and_stream(self, log: structlog.BoundLogger) -> None:
        """Open one stream connection and process events until disconnected."""
        connection_id = secrets.token_hex(8)
        log = log.bind(connection_id=connection_id)

        bearer = (
            self._settings.bearer_token.get_secret_value() if self._settings.bearer_token else ""
        )
        if not bearer:
            raise AuthError(
                "XCHAT_BEARER_TOKEN is not set. "
                "The Activity Stream requires the app Bearer Token, not a user token. "
                "Generate it in X Developer Portal → Keys and tokens → Bearer Token."
            )

        headers = {
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
        }

        log.info("stream_connecting")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self._settings.stream_connect_timeout,
                read=None,  # No read timeout for streaming
                write=30.0,
                pool=30.0,
            )
        ) as client:
            async with client.stream("GET", self._stream_url, headers=headers) as response:
                if response.status_code == 401:
                    raise AuthError(
                        "Stream authentication failed (401). "
                        "Check XCHAT_BEARER_TOKEN — the Activity Stream requires the app "
                        "Bearer Token, not an OAuth user token."
                    )
                if response.status_code == 403:
                    raise AuthError(
                        "Stream authorization failed (403). "
                        "Check your app's Activity API permissions in X Developer Portal."
                    )
                if response.status_code != 200:
                    log.warning("stream_unexpected_status", status_code=response.status_code)
                    raise httpx.RemoteProtocolError(
                        f"Unexpected status {response.status_code}",
                        request=response.request,
                    )

                log.info("stream_connected", status_code=response.status_code)

                async for line in response.aiter_lines():
                    if self._stop_event.is_set():
                        return

                    stripped = line.strip()
                    if not stripped:
                        # Heartbeat — X sends empty lines to keep connection alive
                        log.debug("stream_heartbeat")
                        continue

                    await self._process_line(stripped, log)

    async def _process_line(self, line: str, log: structlog.BoundLogger) -> None:
        """Parse and process a single stream line."""
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning("stream_invalid_json", line_preview=line[:100], error=str(exc))
            return

        event = self._normalizer.normalize(raw)

        # Dedup check
        if self._deduplicator.check_and_mark(event.event_id):
            log.debug("stream_duplicate_event", event_id=event.event_id)
            return

        # Decrypt if needed
        if event.encrypted and self._crypto:
            result = self._crypto.decrypt(
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

        log.info(
            "stream_event_received",
            event_type=event.event_type,
            event_id=event.event_id,
            schema_source=event.schema_source,
            has_plaintext=event.plaintext is not None,
        )

        if self._handler is not None:
            try:
                await self._handler(event)
            except Exception as exc:
                log.error(
                    "stream_handler_error",
                    event_id=event.event_id,
                    error=str(exc),
                    exc_info=True,
                )
