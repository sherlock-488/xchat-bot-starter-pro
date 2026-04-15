"""
DraftReplyBot — human-in-the-loop: queue messages for human review before replying.

Problem it solves:
  Some bots should not reply automatically — a human needs to review and approve
  each reply before it's sent. DraftReplyBot queues incoming messages to a local
  file and lets a human review/edit/approve them.

When to use it:
  - Customer support bots where replies need human approval
  - High-stakes interactions (legal, medical, financial)
  - Supervised learning: collect human-approved replies as training data
  - Gradual automation: start with human review, automate as confidence grows

Credentials needed:
  - XCHAT_CONSUMER_KEY + XCHAT_CONSUMER_SECRET
  - XCHAT_ACCESS_TOKEN for sending approved replies

Assumptions:
  - Queue is a JSONL file (drafts/queue.jsonl) — simple, inspectable
  - Drafts are not automatically sent — a human runs `xchat replay run` or
    a separate approval script to send them
  - Bot sends an acknowledgment ("Got your message, reviewing...") immediately

Experimental:
  - Reply API (same caveats as EchoBot)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from xchat_bot.bot.base import BotBase
from xchat_bot.config.settings import AppSettings
from xchat_bot.events.models import NormalizedEvent
from xchat_bot.reply.adapter import ReplyAdapter

DRAFTS_DIR = Path("drafts")
QUEUE_FILE = DRAFTS_DIR / "queue.jsonl"
ACK_MESSAGE = "Got your message — a team member will review and reply shortly."


class DraftReplyBot(BotBase):
    """Queues incoming messages for human review before replying.

    Usage::

        xchat run --bot bots.draft_reply_bot:DraftReplyBot

    To review and send drafts:
        cat drafts/queue.jsonl  # inspect pending drafts
        # Edit drafts/queue.jsonl to add your reply text
        # Then use xchat replay to send approved replies
    """

    def __init__(self, settings: AppSettings, reply: ReplyAdapter) -> None:
        super().__init__(settings, reply)
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    async def handle(self, event: NormalizedEvent) -> None:
        if not event.is_incoming or not event.plaintext:
            return

        # Queue the message for human review
        draft = {
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "event_id": event.event_id,
            "conversation_id": event.conversation_id,
            "sender_id": event.sender_id,
            "plaintext": event.plaintext,
            "conversation_token": event.conversation_token,  # EXPERIMENTAL
            "status": "pending",
            "draft_reply": "",  # human fills this in
        }

        with QUEUE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(draft, ensure_ascii=False) + "\n")

        self.log.info(
            "draft_queued",
            event_id=event.event_id,
            queue_file=str(QUEUE_FILE),
        )

        # Send immediate acknowledgment
        result = await self.reply_to(event, ACK_MESSAGE)
        if result.success:
            self.log.info("draft_ack_sent", event_id=event.event_id)
        else:
            self.log.warning("draft_ack_failed", error=result.error)

    async def on_start(self) -> None:
        await super().on_start()
        pending = self._count_pending()
        if pending > 0:
            self.log.info("draft_pending_on_start", count=pending, queue_file=str(QUEUE_FILE))

    def _count_pending(self) -> int:
        if not QUEUE_FILE.exists():
            return 0
        count = 0
        for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    if item.get("status") == "pending":
                        count += 1
                except json.JSONDecodeError:
                    pass
        return count
