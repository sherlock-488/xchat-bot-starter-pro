"""Unit tests for xchat_bot.reply.x_api."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from xchat_bot.config.settings import AppSettings
from xchat_bot.reply.x_api import XApiReplyAdapter, _parse_int_header

# ── _parse_int_header ──────────────────────────────────────────────────────────

def test_parse_int_header_none_returns_none():
    assert _parse_int_header(None) is None


def test_parse_int_header_valid_string_returns_int():
    assert _parse_int_header("42") == 42


def test_parse_int_header_zero_returns_zero():
    assert _parse_int_header("0") == 0


def test_parse_int_header_not_a_number_returns_none():
    assert _parse_int_header("not_a_number") is None


def test_parse_int_header_empty_string_returns_none():
    assert _parse_int_header("") is None


def test_parse_int_header_float_string_returns_none():
    assert _parse_int_header("3.14") is None


def test_parse_int_header_large_number():
    assert _parse_int_header("9999999999") == 9999999999


# ── send_reply with no user_access_token ──────────────────────────────────────

@pytest.fixture
def settings_no_token() -> AppSettings:
    """AppSettings without user_access_token."""
    return AppSettings(
        consumer_key="test_key",
        consumer_secret="test_secret",
        transport_mode="stream",
        crypto_mode="stub",
        # user_access_token intentionally omitted
    )


async def test_send_reply_returns_failure_when_no_user_access_token(
    settings_no_token: AppSettings,
):
    adapter = XApiReplyAdapter(settings_no_token)
    result = await adapter.send_reply(
        conversation_id="conv_001",
        text="Hello!",
    )
    assert result.success is False
    assert result.error is not None
    assert "user_access_token" in result.error.lower() or "No user_access_token" in result.error


async def test_send_reply_no_token_error_message_mentions_login(
    settings_no_token: AppSettings,
):
    adapter = XApiReplyAdapter(settings_no_token)
    result = await adapter.send_reply(
        conversation_id="conv_001",
        text="Test message",
    )
    assert result.success is False
    # Error should guide the user to run auth login
    assert result.error is not None
    assert len(result.error) > 0


async def test_send_reply_no_token_with_mock_settings(mock_settings: AppSettings):
    """mock_settings from conftest has no user_access_token — should return failure."""
    adapter = XApiReplyAdapter(mock_settings)
    result = await adapter.send_reply(
        conversation_id="conv_test",
        text="Test",
    )
    assert result.success is False
    assert result.error is not None


@pytest.fixture
def settings_with_token() -> AppSettings:
    from pydantic import SecretStr
    s = AppSettings(
        consumer_key="k",
        consumer_secret="s",
    )
    return s.model_copy(update={"user_access_token": SecretStr("fake_oauth2_token")})


async def test_send_reply_success(settings_with_token: AppSettings) -> None:
    """Mock httpx to return a 201 success response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.is_success = True
    mock_resp.headers = {"x-rate-limit-remaining": "99", "x-rate-limit-reset": "1700000000"}
    mock_resp.json.return_value = {"data": {"dm_event_id": "event_abc123"}}

    with patch("xchat_bot.reply.x_api.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        adapter = XApiReplyAdapter(settings_with_token)
        result = await adapter.send_reply("conv_001", "Hello!")

    assert result.success is True
    assert result.event_id == "event_abc123"
    assert result.rate_limit_remaining == 99


async def test_send_reply_rate_limited(settings_with_token: AppSettings) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.is_success = False
    mock_resp.headers = {"x-rate-limit-remaining": "0", "x-rate-limit-reset": "1700000000"}
    mock_resp.text = "Rate limit exceeded"

    with patch("xchat_bot.reply.x_api.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        adapter = XApiReplyAdapter(settings_with_token)
        result = await adapter.send_reply("conv_001", "Hello!")

    assert result.success is False
    assert "429" in (result.error or "")
    assert result.rate_limit_remaining == 0


async def test_send_reply_api_error(settings_with_token: AppSettings) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.is_success = False
    mock_resp.headers = {}
    mock_resp.text = "Forbidden"

    with patch("xchat_bot.reply.x_api.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        adapter = XApiReplyAdapter(settings_with_token)
        result = await adapter.send_reply("conv_001", "Hello!")

    assert result.success is False
    assert "403" in (result.error or "")
