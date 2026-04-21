"""Unit tests for XApiReplyAdapter reply modes: dm-v2, chat-api, xchat-observed."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xchat_bot.config.settings import AppSettings
from xchat_bot.reply.adapter import EncryptedReplyPayload
from xchat_bot.reply.x_api import XApiReplyAdapter


@pytest.fixture
def settings_with_token() -> AppSettings:
    from pydantic import SecretStr

    from tests.conftest import make_isolated_settings

    s = make_isolated_settings(
        consumer_key="k",
        consumer_secret="s",
        transport_mode="stream",
        crypto_mode="stub",
    )
    return s.model_copy(update={"user_access_token": SecretStr("fake_oauth2_token")})


def _mock_post_success() -> AsyncMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.is_success = True
    mock_resp.headers = {}
    mock_resp.json.return_value = {"data": {"dm_event_id": "evt_1"}}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


# ── dm-v2 ─────────────────────────────────────────────────────────────────────


async def test_dm_v2_sends_only_text(settings_with_token: AppSettings) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="dm-v2")
        result = await adapter.send_reply(
            "conv_001",
            "hello",
            reply_to_event_id="evt_prev",
            conversation_token="tok_123",
        )

    assert result.success is True
    body = mock_client.post.call_args.kwargs["json"]
    assert body == {"text": "hello"}, "dm-v2 must only send {'text': ...}"


async def test_dm_v2_does_not_include_conversation_token(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="dm-v2")
        await adapter.send_reply("conv_001", "hello", conversation_token="tok_xyz")

    body = mock_client.post.call_args.kwargs["json"]
    assert "conversation_token" not in body


async def test_dm_v2_does_not_include_reply_to_dm_event_id(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="dm-v2")
        await adapter.send_reply("conv_001", "hello", reply_to_event_id="evt_prev")

    body = mock_client.post.call_args.kwargs["json"]
    assert "reply_to_dm_event_id" not in body


# ── chat-api ──────────────────────────────────────────────────────────────────


async def test_chat_api_rejects_plaintext_send_reply(settings_with_token: AppSettings) -> None:
    adapter = XApiReplyAdapter(settings_with_token, reply_mode="chat-api")
    result = await adapter.send_reply("conv_001", "hello plaintext")

    assert result.success is False
    assert result.error is not None
    assert "chat-xdk" in result.error
    assert "already-encrypted" in result.error or "EncryptedReplyPayload" in result.error


async def test_chat_api_plaintext_error_mentions_send_encrypted_reply(
    settings_with_token: AppSettings,
) -> None:
    adapter = XApiReplyAdapter(settings_with_token, reply_mode="chat-api")
    result = await adapter.send_reply("conv_001", "hello")

    assert result.error is not None
    assert "send_encrypted_reply" in result.error


async def test_chat_api_send_encrypted_reply_posts_correct_body(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="chat-api")
        payload = EncryptedReplyPayload(
            message_id="msg_abc",
            encoded_message_create_event="enc_event_b64",
            encoded_message_event_signature="sig_b64",
            conversation_token="tok_xyz",
        )
        result = await adapter.send_encrypted_reply("conv_001", payload)

    assert result.success is True
    body = mock_client.post.call_args.kwargs["json"]
    assert body["message_id"] == "msg_abc"
    assert body["encoded_message_create_event"] == "enc_event_b64"
    assert body["encoded_message_event_signature"] == "sig_b64"
    assert body["conversation_token"] == "tok_xyz"
    assert "text" not in body


async def test_chat_api_send_encrypted_reply_omits_conversation_token_when_none(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="chat-api")
        payload = EncryptedReplyPayload(
            message_id="msg_abc",
            encoded_message_create_event="enc_event_b64",
            encoded_message_event_signature="sig_b64",
            conversation_token=None,
        )
        await adapter.send_encrypted_reply("conv_001", payload)

    body = mock_client.post.call_args.kwargs["json"]
    assert "conversation_token" not in body


async def test_chat_api_send_encrypted_reply_uses_chat_conversations_url(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="chat-api")
        payload = EncryptedReplyPayload(
            message_id="msg_abc",
            encoded_message_create_event="enc",
            encoded_message_event_signature="sig",
        )
        await adapter.send_encrypted_reply("conv_xyz", payload)

    actual_url = mock_client.post.call_args.args[0]
    assert "/2/chat/conversations/conv_xyz/messages" in actual_url
    assert "/2/dm_conversations/" not in actual_url


# ── xchat-observed ────────────────────────────────────────────────────────────


async def test_xchat_observed_includes_experimental_fields(
    settings_with_token: AppSettings,
) -> None:
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="xchat-observed")
        result = await adapter.send_reply(
            "conv_001",
            "hello",
            reply_to_event_id="evt_prev",
            conversation_token="tok_123",
        )

    assert result.success is True
    body = mock_client.post.call_args.kwargs["json"]
    assert body["text"] == "hello"
    assert body["reply_to_dm_event_id"] == "evt_prev"
    assert body["conversation_token"] == "tok_123"


async def test_xchat_observed_is_still_experimental_dm_endpoint(
    settings_with_token: AppSettings,
) -> None:
    """xchat-observed must use the dm_conversations endpoint, not chat/conversations."""
    mock_client = _mock_post_success()
    with patch("xchat_bot.reply.x_api.httpx.AsyncClient", return_value=mock_client):
        adapter = XApiReplyAdapter(settings_with_token, reply_mode="xchat-observed")
        await adapter.send_reply("conv_001", "hello")

    actual_url = mock_client.post.call_args.args[0]
    assert "/2/dm_conversations/" in actual_url
