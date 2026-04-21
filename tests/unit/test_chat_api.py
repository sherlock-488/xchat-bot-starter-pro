"""Unit tests for ChatApiClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xchat_bot.chat.api import (
    _CONVERSATION_TEMPLATE,
    _CONVERSATIONS_URL,
    _PUBLIC_KEYS_TEMPLATE,
    ChatApiClient,
)
from xchat_bot.chat.api import (
    _MESSAGES_TEMPLATE as _CHAT_MESSAGES_TEMPLATE,
)
from xchat_bot.config.settings import AppSettings


@pytest.fixture
def settings_no_token() -> AppSettings:
    from tests.conftest import make_isolated_settings

    return make_isolated_settings(
        consumer_key="k",
        consumer_secret="s",
        transport_mode="stream",
        crypto_mode="stub",
    )


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
    return s.model_copy(update={"user_access_token": SecretStr("fake_token")})


def _mock_httpx_get(json_body: dict) -> tuple:
    """Return (mock_client_cls, mock_resp) for a successful GET."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_success = True
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    return mock_client, mock_resp


def _mock_httpx_post(json_body: dict) -> tuple:
    """Return (mock_client, mock_resp) for a successful POST."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.is_success = True
    mock_resp.json.return_value = json_body
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    return mock_client, mock_resp


# ── No token ─────────────────────────────────────────────────────────────────


async def test_get_public_keys_raises_when_no_token(settings_no_token: AppSettings) -> None:
    client = ChatApiClient(settings_no_token)
    with pytest.raises(RuntimeError, match="user_access_token"):
        await client.get_public_keys("12345")


async def test_list_conversations_raises_when_no_token(settings_no_token: AppSettings) -> None:
    client = ChatApiClient(settings_no_token)
    with pytest.raises(RuntimeError, match="user_access_token"):
        await client.list_conversations()


async def test_get_conversation_raises_when_no_token(settings_no_token: AppSettings) -> None:
    client = ChatApiClient(settings_no_token)
    with pytest.raises(RuntimeError, match="user_access_token"):
        await client.get_conversation("conv_001")


async def test_send_encrypted_message_raises_when_no_token(
    settings_no_token: AppSettings,
) -> None:
    client = ChatApiClient(settings_no_token)
    with pytest.raises(RuntimeError, match="user_access_token"):
        await client.send_encrypted_message(
            "conv_001",
            message_id="msg_1",
            encoded_message_create_event="enc_event",
            encoded_message_event_signature="sig",
        )


# ── get_public_keys ───────────────────────────────────────────────────────────


async def test_get_public_keys_calls_correct_url(settings_with_token: AppSettings) -> None:
    mock_client, _ = _mock_httpx_get({"data": {"public_key": "pk_abc"}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        result = await client.get_public_keys("user_999")

    expected_url = _PUBLIC_KEYS_TEMPLATE.format(user_id="user_999")
    mock_client.get.assert_called_once()
    actual_url = mock_client.get.call_args.args[0]
    assert actual_url == expected_url
    assert result == {"data": {"public_key": "pk_abc"}}


# ── list_conversations ────────────────────────────────────────────────────────


async def test_list_conversations_calls_correct_url(settings_with_token: AppSettings) -> None:
    mock_client, _ = _mock_httpx_get({"data": []})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        result = await client.list_conversations()

    mock_client.get.assert_called_once()
    actual_url = mock_client.get.call_args.args[0]
    assert actual_url == _CONVERSATIONS_URL
    assert result == {"data": []}


# ── get_conversation ──────────────────────────────────────────────────────────


async def test_get_conversation_calls_correct_url(settings_with_token: AppSettings) -> None:
    mock_client, _ = _mock_httpx_get({"data": {"id": "conv_abc"}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        result = await client.get_conversation("conv_abc")

    expected_url = _CONVERSATION_TEMPLATE.format(conversation_id="conv_abc")
    mock_client.get.assert_called_once()
    actual_url = mock_client.get.call_args.args[0]
    assert actual_url == expected_url
    assert result["data"]["id"] == "conv_abc"


# ── send_encrypted_message ────────────────────────────────────────────────────


async def test_send_encrypted_message_calls_correct_url(
    settings_with_token: AppSettings,
) -> None:
    mock_client, _ = _mock_httpx_post({"data": {"message_id": "msg_1"}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        await client.send_encrypted_message(
            "conv_xyz",
            message_id="msg_1",
            encoded_message_create_event="enc_event_base64",
            encoded_message_event_signature="sig_base64",
        )

    expected_url = _CHAT_MESSAGES_TEMPLATE.format(conversation_id="conv_xyz")
    mock_client.post.assert_called_once()
    actual_url = mock_client.post.call_args.args[0]
    assert actual_url == expected_url


async def test_send_encrypted_message_body_contains_encrypted_fields(
    settings_with_token: AppSettings,
) -> None:
    mock_client, _ = _mock_httpx_post({"data": {}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        await client.send_encrypted_message(
            "conv_xyz",
            message_id="msg_abc",
            encoded_message_create_event="enc_event_base64",
            encoded_message_event_signature="sig_base64",
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["message_id"] == "msg_abc"
    assert body["encoded_message_create_event"] == "enc_event_base64"
    assert body["encoded_message_event_signature"] == "sig_base64"


async def test_send_encrypted_message_body_does_not_contain_plaintext_text(
    settings_with_token: AppSettings,
) -> None:
    mock_client, _ = _mock_httpx_post({"data": {}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        await client.send_encrypted_message(
            "conv_xyz",
            message_id="msg_abc",
            encoded_message_create_event="enc_event_base64",
            encoded_message_event_signature="sig_base64",
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert "text" not in body, "send_encrypted_message must not include a plaintext 'text' field"


async def test_send_encrypted_message_includes_conversation_token_when_provided(
    settings_with_token: AppSettings,
) -> None:
    mock_client, _ = _mock_httpx_post({"data": {}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        await client.send_encrypted_message(
            "conv_xyz",
            message_id="msg_abc",
            encoded_message_create_event="enc",
            encoded_message_event_signature="sig",
            conversation_token="tok_123",
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert body["conversation_token"] == "tok_123"


async def test_send_encrypted_message_omits_conversation_token_when_none(
    settings_with_token: AppSettings,
) -> None:
    mock_client, _ = _mock_httpx_post({"data": {}})
    with patch("xchat_bot.chat.api.httpx.AsyncClient", return_value=mock_client):
        client = ChatApiClient(settings_with_token)
        await client.send_encrypted_message(
            "conv_xyz",
            message_id="msg_abc",
            encoded_message_create_event="enc",
            encoded_message_event_signature="sig",
            conversation_token=None,
        )

    body = mock_client.post.call_args.kwargs["json"]
    assert "conversation_token" not in body
