"""
HandoffBot — escalates conversations to human agents on trigger words.

Problem it solves:
  Automated bots can't handle every situation. HandoffBot detects when a
  conversation needs human attention and escalates it — notifying a human
  agent and sending the user a confirmation message.

When to use it:
  - Customer support: "I need a human", "speak to agent", "urgent"
  - Complex queries the bot can't answer
  - Escalation paths in multi-tier support systems
  - Hybrid human+bot workflows

Credentials needed:
  - Same as EchoBot
  - Optionally: webhook URL or Slack/email integration for human notifications

Assumptions:
  - Trigger phrases are case-insensitive substring matches
  - Escalated conversations are logged to escalations/queue.jsonl
  - Bot sends a confirmation to the user ("Connecting you to a human...")
  - Human notification is a placeholder — extend with Slack/email/webhook
  - Once escalated, further messages from the same conversation are still
    processed (no per-conversation state tracking in this simple version)

Experimental:
  - Reply API (same caveats as EchoBot)
  - conversation_token passed to reply (EXPERIMENTAL field)

Production note:
  For production, add per-conversation state tracking (Redis/DB) to avoid
  sending multiple escalation notifications for the same conversation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from xchat_bot.bot.base import BotBase
from xchat_bot.config.settings import AppSettings
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.reply.adapter import ReplyAdapter

ESCALATIONS_DIR = Path("escalations")
ESCALATION_FILE = ESCALATIONS_DIR / "queue.jsonl"

DEFAULT_TRIGGERS: frozenset[str] = frozenset(
    [
        "human",
        "agent",
        "speak to someone",
        "real person",
        "urgent",
        "emergency",
        "help me",
    ]
)

ESCALATION_REPLY = (
    "I'm connecting you with a human team member who will follow up shortly. "
    "Thank you for your patience."
)


class HandoffBot(BotBase):
    """Escalates conversations to human agents on trigger words.

    Usage::

        xchat run --bot bots.handoff_bot:HandoffBot

    To customize triggers::

        bot = HandoffBot(settings, reply, triggers={"urgent", "human", "help"})
    """

    def __init__(
        self,
        settings: AppSettings,
        reply: ReplyAdapter,
        *,
        triggers: frozenset[str] | set[str] | None = None,
    ) -> None:
        super().__init__(settings, reply)
        self._triggers = frozenset(t.lower() for t in (triggers or DEFAULT_TRIGGERS))
        ESCALATIONS_DIR.mkdir(parents=True, exist_ok=True)

    async def handle(self, event: NormalizedEvent) -> None:
        if not event.is_incoming or not event.plaintext:
            return

        text_lower = event.plaintext.lower()
        matched = [t for t in self._triggers if t in text_lower]

        if matched:
            await self._escalate(event, matched)
        else:
            # Normal message — echo back (replace with your bot logic)
            await self.reply_to(event, f"Got it: {event.plaintext!r}. How can I help?")

    async def _escalate(self, event: NormalizedEvent, triggers: list[str]) -> None:
        """Record escalation and notify the user."""
        escalation = {
            "escalated_at": datetime.now(UTC).isoformat(),
            "event_id": event.event_id,
            "conversation_id": event.conversation_id,
            "sender_id": event.sender_id,
            "plaintext": event.plaintext,
            "triggers": triggers,
            "status": "pending",
        }

        with ESCALATION_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(escalation, ensure_ascii=False) + "\n")

        self.log.warning(
            "handoff_escalated",
            event_id=event.event_id,
            sender_id=event.sender_id,
            triggers=triggers,
            escalation_file=str(ESCALATION_FILE),
        )

        # Notify human (placeholder — extend with Slack/email/webhook)
        await self._notify_human(escalation)

        # Confirm to user
        result = await self.reply_to(event, ESCALATION_REPLY)
        if result.success:
            self.log.info("handoff_confirmation_sent", event_id=event.event_id)
        else:
            self.log.warning("handoff_confirmation_failed", error=result.error)

    async def _notify_human(self, escalation: dict[str, object]) -> None:
        """Notify a human agent about the escalation.

        PLACEHOLDER: Extend this with your notification system:
          - Slack: POST to incoming webhook
          - Email: send via SMTP/SES
          - PagerDuty: trigger an incident
          - Internal webhook: POST to your support system
        """
        self.log.info(
            "handoff_human_notify_placeholder",
            conversation_id=escalation.get("conversation_id"),
            message=(
                "Human notification is a placeholder. "
                "Extend _notify_human() with your notification system."
            ),
        )
