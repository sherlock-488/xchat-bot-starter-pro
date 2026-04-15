"""
XApiReplyAdapter — sends DM replies via X API.

Authentication
--------------
Sending DM replies requires the **OAuth 2.0 user access token** for the bot
account (``XCHAT_USER_ACCESS_TOKEN``), obtained via ``xchat auth login``.
This is different from the app Bearer Token used by the Activity Stream.

EXPERIMENTAL: The exact endpoint path and ``conversation_token`` field are
observed from xchat-bot-python and may change when fully documented.

Features:
  - Automatic retry with exponential backoff (tenacity)
  - Rate limit awareness (reads x-rate-limit-* headers)
  - Configurable timeout
  - Structured logging for every attempt
"""

from __future__ import annotations

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
from xchat_bot.reply.adapter import ReplyResult

logger = structlog.get_logger(__name__)

# X v2 DM conversations endpoint.
# EXPERIMENTAL: Exact path and body format observed from xchat-bot-python.
_REPLY_ENDPOINT_TEMPLATE = "https://api.x.com/2/dm_conversations/{conversation_id}/messages"


class XApiReplyAdapter:
    """Sends DM replies via X API with retry and rate limit handling.

    Uses the OAuth 2.0 user access token (``settings.user_access_token``) to
    send messages on behalf of the bot account.

    EXPERIMENTAL: Endpoint and ``conversation_token`` field observed from
    xchat-bot-python; will be updated when official reply API is fully documented.

    Args:
        settings: Application settings (provides user_access_token and retry config).
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    async def send_reply(
        self,
        conversation_id: str,
        text: str,
        *,
        reply_to_event_id: str | None = None,
        conversation_token: str | None = None,
    ) -> ReplyResult:
        """Send a DM reply using the OAuth 2.0 user access token.

        EXPERIMENTAL: The request format follows xchat-bot-python observations.

        Args:
            conversation_id: DM conversation ID.
            text: Message text (plaintext, will be encrypted by X).
            reply_to_event_id: Event ID to reply to (optional).
            conversation_token: EXPERIMENTAL: opaque conversation token.

        Returns:
            ReplyResult with success status and any error details.
        """
        log = logger.bind(
            conversation_id=conversation_id,
            text_length=len(text),
            reply_to_event_id=reply_to_event_id,
        )

        user_token = (
            self._settings.user_access_token.get_secret_value()
            if self._settings.user_access_token
            else None
        )
        if not user_token:
            return ReplyResult(
                success=False,
                error=(
                    "No user_access_token configured. "
                    "Run `xchat auth login` to obtain an OAuth 2.0 user token. "
                    "The Activity Stream Bearer Token cannot be used for sending replies."
                ),
            )

        url = _REPLY_ENDPOINT_TEMPLATE.format(conversation_id=conversation_id)

        # EXPERIMENTAL: Request body format observed from xchat-bot-python
        body: dict[str, object] = {"text": text}
        if reply_to_event_id:
            body["reply_to_dm_event_id"] = reply_to_event_id
        # conversation_token usage is EXPERIMENTAL — may be required for E2EE replies
        if conversation_token:
            body["conversation_token"] = conversation_token  # EXPERIMENTAL

        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
        }

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout)),
                wait=wait_exponential(
                    multiplier=self._settings.retry_backoff_base,
                    max=self._settings.retry_backoff_max,
                ),
                stop=stop_after_attempt(self._settings.max_retries),
            ):
                with attempt:
                    result = await self._send_once(url, headers, body, log)
                    if result.success:
                        return result
                    # Don't retry on 4xx client errors (only retry on 5xx / network errors)
                    if result.error and (
                        result.rate_limit_remaining == 0  # 429 rate limit
                        or (
                            "400" in result.error
                            or "401" in result.error
                            or "403" in result.error
                            or "404" in result.error
                            or "422" in result.error
                        )
                    ):
                        return result
        except RetryError as exc:
            return ReplyResult(
                success=False,
                error=f"Max retries ({self._settings.max_retries}) exhausted: {exc}",
            )

        return ReplyResult(success=False, error="Unexpected retry loop exit")

    async def _send_once(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, object],
        log: object,
    ) -> ReplyResult:
        """Perform a single POST attempt."""
        async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
            try:
                resp = await client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                return ReplyResult(success=False, error=str(exc))

        rate_remaining = _parse_int_header(resp.headers.get("x-rate-limit-remaining"))
        rate_reset = _parse_int_header(resp.headers.get("x-rate-limit-reset"))

        if resp.status_code == 429:
            logger.warning(  # type: ignore[attr-defined]
                "reply_rate_limited",
                rate_limit_reset=rate_reset,
            )
            return ReplyResult(
                success=False,
                error=f"Rate limited (429). Reset at {rate_reset}.",
                rate_limit_remaining=0,
                rate_limit_reset=rate_reset,
            )

        if not resp.is_success:
            logger.warning(  # type: ignore[attr-defined]
                "reply_api_error",
                status_code=resp.status_code,
                body_preview=resp.text[:200],
            )
            return ReplyResult(
                success=False,
                error=f"API error {resp.status_code}: {resp.text[:200]}",
                rate_limit_remaining=rate_remaining,
            )

        try:
            data = resp.json()
            event_id = data.get("data", {}).get("dm_event_id") or data.get("id")
        except Exception:
            event_id = None

        logger.info(  # type: ignore[attr-defined]
            "reply_sent",
            event_id=event_id,
            rate_limit_remaining=rate_remaining,
        )
        return ReplyResult(
            success=True,
            event_id=event_id,
            rate_limit_remaining=rate_remaining,
            rate_limit_reset=rate_reset,
        )


def _parse_int_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
