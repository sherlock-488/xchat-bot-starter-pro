"""
BotBase — abstract base class for all XChat bots.

Subclass BotBase and implement handle() to create a bot.
BotBase provides:
  - reply_to() convenience method
  - Lifecycle hooks (on_start, on_stop, on_error)
  - Structured logging bound to the bot class name

Usage::

    class MyBot(BotBase):
        async def handle(self, event: NormalizedEvent) -> None:
            if event.is_incoming and event.plaintext:
                await self.reply_to(event, f"You said: {event.plaintext}")

    bot = MyBot(settings=settings, reply=XApiReplyAdapter(settings))
    await transport.run(handler=bot.handle)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from xchat_bot.config.settings import AppSettings
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.reply.adapter import ReplyAdapter, ReplyResult


class BotBase(ABC):
    """Abstract base class for XChat bots.

    Subclasses must implement handle(). All other methods have default
    implementations that can be overridden.

    Args:
        settings: Application settings.
        reply: ReplyAdapter for sending DM replies.
    """

    def __init__(self, settings: AppSettings, reply: ReplyAdapter) -> None:
        self.settings = settings
        self.reply = reply
        self.log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def handle(self, event: NormalizedEvent) -> None:
        """Process an incoming event.

        This is the main entry point for bot logic. Called for every event
        that passes deduplication and decryption.

        Args:
            event: Normalized event from any transport.
        """
        ...

    async def on_start(self) -> None:
        """Called once when the bot is about to start receiving events.

        Override to initialize resources (database connections, caches, etc.)
        """
        self.log.info("bot_starting", bot=self.__class__.__name__)

    async def on_stop(self) -> None:
        """Called once when the bot is shutting down.

        Override to clean up resources.
        """
        self.log.info("bot_stopping", bot=self.__class__.__name__)

    async def on_error(self, event: NormalizedEvent, exc: Exception) -> None:
        """Called when handle() raises an exception.

        Default implementation logs the error and continues.
        Override to add custom error handling (alerting, DLQ, etc.)

        Args:
            event: The event that caused the error.
            exc: The exception that was raised.
        """
        self.log.error(
            "bot_handle_error",
            event_id=event.event_id,
            event_type=event.event_type,
            error=str(exc),
            exc_info=True,
        )

    async def reply_to(
        self,
        event: NormalizedEvent,
        text: str,
    ) -> ReplyResult:
        """Send a reply in the same conversation as the event.

        Convenience wrapper around reply.send_reply().

        Args:
            event: The event to reply to (provides conversation_id).
            text: Reply text.

        Returns:
            ReplyResult from the reply adapter.
        """
        if not event.conversation_id:
            self.log.warning(
                "reply_no_conversation_id",
                event_id=event.event_id,
                event_type=event.event_type,
            )
            from xchat_bot.reply.adapter import ReplyResult
            return ReplyResult(success=False, error="No conversation_id on event")

        return await self.reply.send_reply(
            conversation_id=event.conversation_id,
            text=text,
            reply_to_event_id=event.event_id,
            conversation_token=event.conversation_token,
        )
