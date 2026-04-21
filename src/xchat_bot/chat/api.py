"""
ChatApiClient — documented Chat API routes from the XChat migration guide.

Documented endpoints (reference: docs.x.com XChat migration guide):
  GET  /2/users/{id}/public_keys
  GET  /2/chat/conversations
  GET  /2/chat/conversations/{conversation_id}
  POST /2/chat/conversations/{conversation_id}/messages

Authentication
--------------
All Chat API endpoints require the OAuth 2.0 user access token
(``XCHAT_USER_ACCESS_TOKEN``), obtained via ``xchat auth login``.
App-only Bearer Token is not supported.

Encryption boundary
-------------------
XChat messages are end-to-end encrypted. This client does NOT encrypt
or decrypt anything. ``send_encrypted_message`` accepts an already-encrypted
payload that must be produced by chat-xdk (pending stable public release).

Do NOT pass plaintext to ``send_encrypted_message``. If you want to send a
plain DM, use ``XApiReplyAdapter`` with ``reply_mode="dm-v2"`` instead.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from xchat_bot.config.settings import AppSettings

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.x.com"
_PUBLIC_KEYS_TEMPLATE = _BASE_URL + "/2/users/{user_id}/public_keys"
_CONVERSATIONS_URL = _BASE_URL + "/2/chat/conversations"
_CONVERSATION_TEMPLATE = _BASE_URL + "/2/chat/conversations/{conversation_id}"
_MESSAGES_TEMPLATE = _BASE_URL + "/2/chat/conversations/{conversation_id}/messages"


class ChatApiClient:
    """Client for documented Chat API routes.

    Uses the OAuth 2.0 user access token for all requests.
    Does NOT perform encryption or decryption.

    Args:
        settings: Application settings (provides user_access_token and http_timeout).
    """

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._token: str | None = (
            settings.user_access_token.get_secret_value() if settings.user_access_token else None
        )

    # ── Public key lookup ────────────────────────────────────────────────────

    async def get_public_keys(self, user_id: str) -> dict[str, Any]:
        """GET /2/users/{user_id}/public_keys

        Returns the public key material for a user. Required by chat-xdk to
        encrypt a message for a specific recipient. This client does not perform
        encryption — pass the result to chat-xdk.

        Args:
            user_id: X user ID of the target user.

        Returns:
            Parsed JSON response from the API.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
            RuntimeError: if no user_access_token is configured.
        """
        self._require_token()
        url = _PUBLIC_KEYS_TEMPLATE.format(user_id=user_id)
        log = logger.bind(endpoint="get_public_keys", user_id=user_id)
        async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
            resp = await client.get(url, headers=self._auth_headers())
        log.debug("chat_api_response", status_code=resp.status_code)
        resp.raise_for_status()
        return resp.json()

    # ── Conversation listing ─────────────────────────────────────────────────

    async def list_conversations(self) -> dict[str, Any]:
        """GET /2/chat/conversations

        Returns the list of conversations for the authenticated user.

        Returns:
            Parsed JSON response from the API.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
            RuntimeError: if no user_access_token is configured.
        """
        self._require_token()
        log = logger.bind(endpoint="list_conversations")
        async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
            resp = await client.get(_CONVERSATIONS_URL, headers=self._auth_headers())
        log.debug("chat_api_response", status_code=resp.status_code)
        resp.raise_for_status()
        return resp.json()

    # ── Single conversation ──────────────────────────────────────────────────

    async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        """GET /2/chat/conversations/{conversation_id}

        Returns metadata for a single conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Parsed JSON response from the API.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
            RuntimeError: if no user_access_token is configured.
        """
        self._require_token()
        url = _CONVERSATION_TEMPLATE.format(conversation_id=conversation_id)
        log = logger.bind(endpoint="get_conversation", conversation_id=conversation_id)
        async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
            resp = await client.get(url, headers=self._auth_headers())
        log.debug("chat_api_response", status_code=resp.status_code)
        resp.raise_for_status()
        return resp.json()

    # ── Send encrypted message ───────────────────────────────────────────────

    async def send_encrypted_message(
        self,
        conversation_id: str,
        *,
        message_id: str,
        encoded_message_create_event: str,
        encoded_message_event_signature: str,
        conversation_token: str | None = None,
    ) -> dict[str, Any]:
        """POST /2/chat/conversations/{conversation_id}/messages

        Send an already-encrypted message to a conversation.

        This method does NOT accept plaintext. All encrypted fields must be
        produced by chat-xdk before calling this method. chat-xdk is pending
        stable public release — see docs/known-caveats.md.

        Args:
            conversation_id: The conversation to post into.
            message_id: Stable ID for this message (produced by chat-xdk).
            encoded_message_create_event: Base64-encoded encrypted message event
                (produced by chat-xdk).
            encoded_message_event_signature: Signature over the encrypted event
                (produced by chat-xdk).
            conversation_token: Optional opaque conversation token from the event
                payload (data.payload.conversation_token).

        Returns:
            Parsed JSON response from the API.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
            RuntimeError: if no user_access_token is configured.
        """
        self._require_token()
        url = _MESSAGES_TEMPLATE.format(conversation_id=conversation_id)
        body: dict[str, str] = {
            "message_id": message_id,
            "encoded_message_create_event": encoded_message_create_event,
            "encoded_message_event_signature": encoded_message_event_signature,
        }
        if conversation_token is not None:
            body["conversation_token"] = conversation_token

        log = logger.bind(
            endpoint="send_encrypted_message",
            conversation_id=conversation_id,
            message_id=message_id,
        )
        async with httpx.AsyncClient(timeout=self._settings.http_timeout) as client:
            resp = await client.post(url, headers=self._auth_headers(), json=body)
        log.debug("chat_api_response", status_code=resp.status_code)
        resp.raise_for_status()
        return resp.json()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _require_token(self) -> None:
        if not self._token:
            raise RuntimeError(
                "No user_access_token configured. "
                "Run `xchat auth login` to obtain an OAuth 2.0 user token. "
                "Chat API endpoints require user-context auth."
            )
