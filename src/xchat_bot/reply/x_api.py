"""
XApiReplyAdapter — sends DM replies via X API.

Authentication
--------------
Sending DM replies requires the **OAuth 2.0 user access token** for the bot
account (``XCHAT_USER_ACCESS_TOKEN``), obtained via ``xchat auth login``.
This is different from the app Bearer Token used by the Activity Stream.
App-only (Bearer Token) is not supported for DM sends.

Endpoint
--------
Uses the documented DM Manage v2 endpoint:
  POST /2/dm_conversations/{conversation_id}/messages
  Body: {"text": "..."}

This endpoint is documented in X DM Manage API (docs.x.com/x-api/direct-messages).

EXPERIMENTAL: The ``conversation_token`` field is observed from xchat-bot-python
and is not yet in official docs. It is only included when explicitly passed.

Features:
  - Automatic retry with exponential backoff (tenacity)
  - Rate limit awareness (reads x-rate-limit-* headers)
  - Token refresh on 401 (uses refresh_token from TokenStore if available)
  - Configurable timeout
  - Structured logging for every attempt
"""

from __future__ import annotations

from typing import Literal

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

# X v2 DM conversations endpoint — documented in X DM Manage API.
# POST /2/dm_conversations/{conversation_id}/messages  body: {"text": "..."}
_REPLY_ENDPOINT_TEMPLATE = "https://api.x.com/2/dm_conversations/{conversation_id}/messages"
# One-to-one DM endpoint (by participant ID) — also documented.
_DM_WITH_PARTICIPANT_TEMPLATE = (
    "https://api.x.com/2/dm_conversations/with/{participant_id}/messages"
)
_TOKEN_URL = "https://api.x.com/2/oauth2/token"


class XApiReplyAdapter:
    """Sends DM replies via X API with retry, rate limit handling, and token refresh.

    Uses the OAuth 2.0 user access token (``settings.user_access_token``) to
    send messages on behalf of the bot account. On 401, attempts to refresh
    the access token using the stored refresh_token before giving up.

    reply_mode controls the request body:
      "dm-v2" (default): documented DM Manage v2 — body is {"text": "..."}
          POST /2/dm_conversations/{conversation_id}/messages
      "xchat-observed": adds observed XChat extras (reply_to_dm_event_id,
          conversation_token) — use only when you know the XChat reply path
          is available and you have a valid conversation_token.

    Args:
        settings: Application settings (provides user_access_token and retry config).
        reply_mode: "dm-v2" (default) or "xchat-observed".
    """

    def __init__(
        self,
        settings: AppSettings,
        reply_mode: Literal["dm-v2", "xchat-observed"] = "dm-v2",
    ) -> None:
        self._settings = settings
        self._reply_mode = reply_mode
        # In-memory cache of the current access token (may be refreshed at runtime)
        self._current_token: str | None = (
            settings.user_access_token.get_secret_value() if settings.user_access_token else None
        )

    async def send_reply(
        self,
        conversation_id: str,
        text: str,
        *,
        reply_to_event_id: str | None = None,
        conversation_token: str | None = None,
    ) -> ReplyResult:
        """Send a DM reply using the OAuth 2.0 user access token.

        In "dm-v2" mode (default), sends {"text": text} — the documented
        DM Manage v2 body. reply_to_event_id and conversation_token are ignored.

        In "xchat-observed" mode, also includes reply_to_dm_event_id and
        conversation_token when provided (EXPERIMENTAL fields from xchat-bot-python).

        Args:
            conversation_id: DM conversation ID.
            text: Message text (plaintext, will be encrypted by X).
            reply_to_event_id: Event ID to reply to. Only used in xchat-observed mode.
            conversation_token: EXPERIMENTAL opaque token. Only used in xchat-observed mode.

        Returns:
            ReplyResult with success status and any error details.
        """
        log = logger.bind(
            conversation_id=conversation_id,
            text_length=len(text),
            reply_mode=self._reply_mode,
        )

        if not self._current_token:
            return ReplyResult(
                success=False,
                error=(
                    "No user_access_token configured. "
                    "Run `xchat auth login` to obtain an OAuth 2.0 user token. "
                    "The Activity Stream Bearer Token cannot be used for sending replies."
                ),
            )

        url = _REPLY_ENDPOINT_TEMPLATE.format(conversation_id=conversation_id)

        # dm-v2 (default): documented DM Manage v2 body — only {"text": "..."}
        body: dict[str, object] = {"text": text}
        if self._reply_mode == "xchat-observed":
            # xchat-observed: add experimental XChat fields when provided
            if reply_to_event_id:
                body["reply_to_dm_event_id"] = reply_to_event_id
            if conversation_token:
                body["conversation_token"] = conversation_token  # EXPERIMENTAL

        headers = {
            "Authorization": f"Bearer {self._current_token}",
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
                    # On 401: attempt token refresh once, then retry
                    if result.error and "401" in result.error:
                        refreshed = await self._try_refresh_token()
                        if refreshed:
                            headers["Authorization"] = f"Bearer {self._current_token}"
                            log.info("token_refreshed_retrying")
                            # Retry immediately with new token (don't count as backoff attempt)
                            result = await self._send_once(url, headers, body, log)
                            if result.success:
                                return result
                        log.error(
                            "token_expired_refresh_failed",
                            hint="Run `xchat auth login` to re-authenticate.",
                        )
                        return ReplyResult(
                            success=False,
                            error=(
                                "Access token expired (401) and refresh failed. "
                                "Run `xchat auth login` to re-authenticate."
                            ),
                        )
                    # Don't retry on other 4xx client errors
                    if result.error and (
                        result.rate_limit_remaining == 0  # 429 rate limit
                        or any(code in result.error for code in ("400", "403", "404", "422"))
                    ):
                        return result
        except RetryError as exc:
            return ReplyResult(
                success=False,
                error=f"Max retries ({self._settings.max_retries}) exhausted: {exc}",
            )

        return ReplyResult(success=False, error="Unexpected retry loop exit")

    async def _try_refresh_token(self) -> bool:
        """Attempt to refresh the access token using the stored refresh_token.

        Reads refresh_token from settings or TokenStore. On success, updates
        self._current_token and persists the new tokens to TokenStore.

        Returns:
            True if refresh succeeded and self._current_token was updated.
            False if no refresh_token is available or the refresh request failed.
        """
        # Get refresh token from settings or TokenStore
        refresh_token: str | None = (
            self._settings.user_refresh_token.get_secret_value()
            if self._settings.user_refresh_token
            else None
        )
        if not refresh_token:
            # Try TokenStore as fallback
            from xchat_bot.auth.token_store import TokenStore

            store = TokenStore(self._settings.data_dir)
            stored = store.load()
            if stored:
                refresh_token = stored.get("refresh_token")

        if not refresh_token:
            logger.warning("token_refresh_no_refresh_token")  # type: ignore[attr-defined]
            return False

        if not self._settings.oauth_client_id:
            logger.warning("token_refresh_no_client_id")  # type: ignore[attr-defined]
            return False

        payload: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self._settings.oauth_client_id,
        }
        if self._settings.oauth_client_secret:
            payload["client_secret"] = self._settings.oauth_client_secret.get_secret_value()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    _TOKEN_URL,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.HTTPError as exc:
            logger.warning("token_refresh_request_failed", error=str(exc))  # type: ignore[attr-defined]
            return False

        if not resp.is_success:
            logger.warning(  # type: ignore[attr-defined]
                "token_refresh_api_error",
                status_code=resp.status_code,
                body=resp.text[:200],
            )
            return False

        data = resp.json()
        new_access_token: str | None = data.get("access_token")
        new_refresh_token: str | None = data.get("refresh_token")
        if not new_access_token:
            return False

        self._current_token = new_access_token

        # Persist refreshed tokens to TokenStore
        try:
            from xchat_bot.auth.token_store import TokenStore

            store = TokenStore(self._settings.data_dir)
            existing = store.load() or {}
            store.save(
                access_token=new_access_token,
                refresh_token=new_refresh_token or refresh_token,
                user_id=existing.get("user_id"),
                screen_name=existing.get("screen_name"),
                scope=existing.get("scope"),
            )
        except Exception:  # noqa: BLE001, S110
            pass  # non-fatal — token is updated in memory even if persist fails

        logger.info("token_refresh_success")  # type: ignore[attr-defined]
        return True

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
