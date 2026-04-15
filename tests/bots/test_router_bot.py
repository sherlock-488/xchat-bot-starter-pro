"""Tests for RouterBot."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from bots.router_bot import RouterBot

from tests.conftest import make_event


@pytest.fixture
def router_bot(mock_settings, mock_reply):
    return RouterBot(settings=mock_settings, reply=mock_reply)


async def test_ping_command(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="/ping")
    await router_bot.handle(event)
    mock_reply.send_reply.assert_called_once()
    call_args = mock_reply.send_reply.call_args
    text = call_args.kwargs.get("text") or call_args.args[1]
    assert "pong" in text.lower()


async def test_help_command(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="/help")
    await router_bot.handle(event)
    mock_reply.send_reply.assert_called_once()
    call_args = mock_reply.send_reply.call_args
    text = call_args.kwargs.get("text") or call_args.args[1]
    assert "/ping" in text


async def test_unknown_command(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="/unknown_cmd")
    await router_bot.handle(event)
    mock_reply.send_reply.assert_called_once()
    call_args = mock_reply.send_reply.call_args
    text = call_args.kwargs.get("text") or call_args.args[1]
    assert "unknown" in text.lower() or "Unknown" in text


async def test_custom_route(router_bot, mock_reply) -> None:
    custom_handler = AsyncMock()
    router_bot.register("/custom", custom_handler)

    event = make_event(event_type="chat.received", plaintext="/custom some args")
    await router_bot.handle(event)

    custom_handler.assert_called_once_with(event)
    mock_reply.send_reply.assert_not_called()


async def test_ignores_outgoing(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.sent", plaintext="/ping")
    await router_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_ignores_no_plaintext(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext=None)
    await router_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_command_case_insensitive(router_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="/PING")
    await router_bot.handle(event)
    mock_reply.send_reply.assert_called_once()
    call_args = mock_reply.send_reply.call_args
    text = call_args.kwargs.get("text") or call_args.args[1]
    assert "pong" in text.lower()
