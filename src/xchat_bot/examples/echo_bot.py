"""
EchoBot — reflects every incoming message back to the sender.

Problem it solves:
  The simplest possible bot — useful as a smoke test to verify your
  end-to-end setup is working: credentials, transport, crypto, reply.

When to use it:
  - Validating your setup before building real bot logic
  - Demonstrating that messages are being received and decrypted
  - As a base for testing your transport and reply adapter

Credentials needed:
  - XCHAT_CONSUMER_KEY + XCHAT_CONSUMER_SECRET
  - XCHAT_ACCESS_TOKEN + XCHAT_ACCESS_TOKEN_SECRET (for sending replies)

Assumptions:
  - Ignores chat.sent events (to avoid echo loops)
  - Ignores events with no plaintext (encrypted but not decrypted)
  - Replies in the same conversation

Experimental:
  - Reply API endpoint follows xchat-bot-python observations
  - conversation_token passed to reply adapter (EXPERIMENTAL field)
"""

from __future__ import annotations

from xchat_bot.bot.base import BotBase
from xchat_bot.events.models import NormalizedEvent


class EchoBot(BotBase):
    """Reflects incoming messages back to the sender.

    Usage::

        xchat run --bot bots.echo_bot:EchoBot
    """

    async def handle(self, event: NormalizedEvent) -> None:
        # Only process incoming messages
        if not event.is_incoming:
            self.log.debug("echo_skip_non_incoming", event_type=event.event_type)
            return

        # Skip if no plaintext (decryption failed or not attempted)
        if not event.plaintext:
            self.log.info(
                "echo_skip_no_plaintext",
                event_id=event.event_id,
                decrypt_notes=event.decrypt_notes,
                is_stub=event.is_stub,
            )
            return

        self.log.info(
            "echo_replying",
            event_id=event.event_id,
            sender_id=event.sender_id,
            text_preview=event.plaintext[:50],
        )

        result = await self.reply_to(event, event.plaintext)

        if result.success:
            self.log.info("echo_reply_sent", reply_event_id=result.event_id)
        else:
            self.log.warning("echo_reply_failed", error=result.error)
