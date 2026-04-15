"""
RouterBot — routes incoming messages to handlers based on command prefixes.

Problem it solves:
  Most real bots need to respond differently to different inputs.
  RouterBot provides a clean command dispatch pattern: messages starting
  with "/" are routed to registered handlers; others go to a default handler.

When to use it:
  - Building command-driven bots (/help, /status, /subscribe, etc.)
  - Separating concerns: each command has its own handler function
  - As a base class for more complex bots

Credentials needed:
  - Same as EchoBot

Assumptions:
  - Commands are case-insensitive, prefix-matched
  - First word of message is the command (e.g. "/help me" → command="/help")
  - Unknown commands get a default "unknown command" response
  - Only processes chat.received events with plaintext

Experimental:
  - Reply API (same caveats as EchoBot)
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from xchat_bot.bot.base import BotBase
from xchat_bot.config.settings import AppSettings
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.reply.adapter import ReplyAdapter

# Handler type: receives event and returns None
CommandHandler = Callable[[NormalizedEvent], Coroutine[Any, Any, None]]


class RouterBot(BotBase):
    """Routes incoming messages to handlers based on command prefixes.

    Usage::

        bot = RouterBot(settings=settings, reply=reply_adapter)
        bot.register("/help", help_handler)
        bot.register("/ping", ping_handler)

        xchat run --bot bots.router_bot:RouterBot
    """

    def __init__(self, settings: AppSettings, reply: ReplyAdapter) -> None:
        super().__init__(settings, reply)
        self._routes: dict[str, CommandHandler] = {}
        self._default_handler: CommandHandler | None = None

        # Register built-in commands
        self.register("/help", self._handle_help)
        self.register("/ping", self._handle_ping)

    def register(self, command: str, handler: CommandHandler) -> None:
        """Register a handler for a command prefix.

        Args:
            command: Command prefix (e.g. "/help"). Case-insensitive.
            handler: Async callable that receives the NormalizedEvent.
        """
        self._routes[command.lower()] = handler
        self.log.debug("route_registered", command=command)

    def set_default(self, handler: CommandHandler) -> None:
        """Set the handler for unrecognized commands."""
        self._default_handler = handler

    async def handle(self, event: NormalizedEvent) -> None:
        if not event.is_incoming or not event.plaintext:
            return

        text = event.plaintext.strip()
        command = text.split()[0].lower() if text else ""

        handler = self._routes.get(command) or self._default_handler

        if handler:
            self.log.info("route_dispatching", command=command, event_id=event.event_id)
            await handler(event)
        else:
            self.log.info("route_no_handler", command=command)
            await self.reply_to(
                event,
                f"Unknown command: {command!r}. Try /help for a list of commands.",
            )

    # ── Built-in handlers ─────────────────────────────────────────────────

    async def _handle_help(self, event: NormalizedEvent) -> None:
        commands = sorted(self._routes.keys())
        lines = ["Available commands:"] + [f"  {cmd}" for cmd in commands]
        await self.reply_to(event, "\n".join(lines))

    async def _handle_ping(self, event: NormalizedEvent) -> None:
        await self.reply_to(event, "pong")
