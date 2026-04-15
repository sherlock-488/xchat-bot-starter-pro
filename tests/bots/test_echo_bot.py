"""Tests for EchoBot."""

from __future__ import annotations

import pytest

from bots.echo_bot import EchoBot
from tests.conftest import make_event


@pytest.fixture
def echo_bot(mock_settings, mock_reply):
    return EchoBot(settings=mock_settings, reply=mock_reply)


async def test_echo_replies_with_plaintext(echo_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="Hello!")
    await echo_bot.handle(event)

    mock_reply.send_reply.assert_called_once()
    call_kwargs = mock_reply.send_reply.call_args
    assert call_kwargs.kwargs.get("text") == "Hello!" or call_kwargs.args[1] == "Hello!"


async def test_echo_ignores_outgoing(echo_bot, mock_reply) -> None:
    event = make_event(event_type="chat.sent", plaintext="My outgoing message")
    await echo_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_echo_ignores_no_plaintext(echo_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext=None)
    await echo_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_echo_handles_reply_failure(echo_bot, mock_reply) -> None:
    from xchat_bot.reply.adapter import ReplyResult
    mock_reply.send_reply.return_value = ReplyResult(success=False, error="API error")

    event = make_event(event_type="chat.received", plaintext="Hello!")
    # Should not raise even if reply fails
    await echo_bot.handle(event)
    mock_reply.send_reply.assert_called_once()


async def test_echo_ignores_join_events(echo_bot, mock_reply) -> None:
    event = make_event(event_type="chat.conversation_join", plaintext=None)
    await echo_bot.handle(event)
    mock_reply.send_reply.assert_not_called()
