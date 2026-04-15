"""
ModerationBot — content moderation: flag or block messages matching rules.

Problem it solves:
  Bots exposed to public users need to handle abusive, spammy, or inappropriate
  content. ModerationBot provides a simple rule-based filter that flags messages
  and optionally refuses to reply.

When to use it:
  - Public-facing bots that need basic content filtering
  - Compliance requirements (block certain topics or keywords)
  - Rate limiting abusive users
  - As a first layer before more sophisticated ML-based moderation

Credentials needed:
  - Same as EchoBot

Assumptions:
  - Blocklist is a simple set of lowercase substrings
  - Flagged messages are logged but not replied to (silent drop)
  - Clean messages are passed to the inner bot for normal handling
  - No persistent block list — in-memory only (extend for production)

Experimental:
  - Reply API (same caveats as EchoBot)

Production note:
  This is a starting point, not a complete moderation solution.
  For production, integrate with a dedicated moderation API or ML model.
"""

from __future__ import annotations

from xchat_bot.bot.base import BotBase
from xchat_bot.config.settings import AppSettings
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.reply.adapter import ReplyAdapter

# Default blocklist — extend for your use case
DEFAULT_BLOCKLIST: frozenset[str] = frozenset([
    "spam",
    "phishing",
    "click here",
])


class ModerationBot(BotBase):
    """Filters messages against a blocklist before processing.

    Usage::

        xchat run --bot bots.moderation_bot:ModerationBot

    To customize the blocklist::

        bot = ModerationBot(settings, reply, blocklist={"badword", "spam"})
    """

    def __init__(
        self,
        settings: AppSettings,
        reply: ReplyAdapter,
        *,
        blocklist: frozenset[str] | set[str] | None = None,
    ) -> None:
        super().__init__(settings, reply)
        self._blocklist = frozenset(w.lower() for w in (blocklist or DEFAULT_BLOCKLIST))
        self._flagged_count = 0

    async def handle(self, event: NormalizedEvent) -> None:
        if not event.is_incoming or not event.plaintext:
            return

        text_lower = event.plaintext.lower()
        matched = [word for word in self._blocklist if word in text_lower]

        if matched:
            self._flagged_count += 1
            self.log.warning(
                "moderation_flagged",
                event_id=event.event_id,
                sender_id=event.sender_id,
                matched_words=matched,
                flagged_total=self._flagged_count,
            )
            # Silent drop — do not reply to flagged messages
            # For production: consider sending to a moderation queue,
            # alerting a human reviewer, or blocking the sender via X API
            return

        # Message is clean — log and pass through
        # In a real bot, you'd call your inner bot's handle() here
        self.log.info(
            "moderation_clean",
            event_id=event.event_id,
            sender_id=event.sender_id,
        )
        # Default: echo clean messages back (replace with your bot logic)
        await self.reply_to(event, f"[moderation passed] {event.plaintext}")

    @property
    def flagged_count(self) -> int:
        """Number of messages flagged since startup."""
        return self._flagged_count
