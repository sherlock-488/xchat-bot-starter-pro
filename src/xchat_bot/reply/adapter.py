"""
ReplyAdapter protocol — the interface for sending DM replies.

Implementations:
  - XApiReplyAdapter: sends replies via X API
  - NullReplyAdapter: discards replies (useful for read-only bots and testing)
  - LoggingReplyAdapter: logs replies without sending (useful for development)

Reply modes (XApiReplyAdapter):
  - dm-v2 (default): documented DM Manage v2 endpoint, body {"text": "..."}
  - chat-api: documented Chat encrypted message endpoint — requires already-encrypted
      payload fields produced by chat-xdk (pending stable public release)
  - xchat-observed: EXPERIMENTAL observed XChat reply extras
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ReplyResult(BaseModel):
    """Result from a ReplyAdapter.send_reply() call."""

    success: bool = False
    event_id: str | None = None
    error: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None


class EncryptedReplyPayload(BaseModel):
    """Already-encrypted payload for chat-api reply mode.

    All fields must be produced by chat-xdk before passing to send_encrypted_reply().
    This starter does NOT implement encryption — chat-xdk is pending stable public release.

    Fields correspond to the POST /2/chat/conversations/{id}/messages body.
    """

    message_id: str
    encoded_message_create_event: str
    encoded_message_event_signature: str
    conversation_token: str | None = None


@runtime_checkable
class ReplyAdapter(Protocol):
    """Protocol for DM reply adapters.

    Implementations must be safe to call from async context.
    Never raises — use ReplyResult.error for error context.
    """

    async def send_reply(
        self,
        conversation_id: str,
        text: str,
        *,
        reply_to_event_id: str | None = None,
        conversation_token: str | None = None,
    ) -> ReplyResult:
        """Send a reply to a DM conversation.

        Args:
            conversation_id: The conversation to reply in.
            text: Message text to send.
            reply_to_event_id: ID of the event to reply to (optional).
            conversation_token: EXPERIMENTAL: opaque token for reply API.

        Returns:
            ReplyResult indicating success/failure.
        """
        ...


class NullReplyAdapter:
    """Discards all replies silently. Useful for read-only bots."""

    async def send_reply(
        self,
        conversation_id: str,
        text: str,
        *,
        reply_to_event_id: str | None = None,
        conversation_token: str | None = None,
    ) -> ReplyResult:
        return ReplyResult(success=True, event_id=None)


class LoggingReplyAdapter:
    """Logs replies without sending them. Useful for development."""

    def __init__(self) -> None:
        import structlog

        self._log = structlog.get_logger(__name__)

    async def send_reply(
        self,
        conversation_id: str,
        text: str,
        *,
        reply_to_event_id: str | None = None,
        conversation_token: str | None = None,
    ) -> ReplyResult:
        self._log.info(
            "reply_would_send",
            conversation_id=conversation_id,
            text_preview=text[:80],
            reply_to_event_id=reply_to_event_id,
        )
        return ReplyResult(success=True, event_id="[logging-adapter]")
