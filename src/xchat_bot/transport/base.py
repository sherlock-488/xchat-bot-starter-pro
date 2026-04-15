"""
Transport abstraction — the interface all transport implementations must satisfy.

Both ActivityStreamTransport and WebhookTransport implement Transport.
Bot logic only ever sees NormalizedEvent — it never knows which transport delivered it.

Usage::

    transport = ActivityStreamTransport(settings, normalizer, deduplicator, crypto)
    await transport.run(handler=my_bot.handle)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any

from xchat_bot.events.models import NormalizedEvent

# EventHandler: receives a NormalizedEvent, returns None (async)
EventHandler = Callable[[NormalizedEvent], Coroutine[Any, Any, None]]


class TransportError(Exception):
    """Base class for transport errors."""


class AuthError(TransportError):
    """Authentication failed (invalid credentials, expired token)."""


class StreamDisconnected(TransportError):
    """Stream connection was lost and could not be re-established."""


class Transport(ABC):
    """Abstract base class for event transports.

    Subclasses must implement run() and stop().
    The transport is responsible for:
      1. Receiving raw payloads (via HTTP stream or webhook POST)
      2. Normalizing them to NormalizedEvent
      3. Deduplicating by event_id
      4. Applying crypto decryption
      5. Calling the registered EventHandler

    The EventHandler is provided at run() time, not construction time,
    so the same transport instance can be reused with different handlers.
    """

    @abstractmethod
    async def run(self, handler: EventHandler) -> None:
        """Start the transport loop.

        Runs until stop() is called or an unrecoverable error occurs.
        Handles reconnection internally for transient failures.

        Args:
            handler: Async callable that receives NormalizedEvent objects.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Signal the transport to stop gracefully."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable transport name (e.g. 'stream', 'webhook')."""
        ...
