"""Tests for ModerationBot."""

from __future__ import annotations

import pytest
from bots.moderation_bot import ModerationBot

from tests.conftest import make_event


@pytest.fixture
def mod_bot(mock_settings, mock_reply):
    return ModerationBot(
        settings=mock_settings,
        reply=mock_reply,
        blocklist={"badword", "spam"},
    )


async def test_clean_message_passes(mod_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="Hello, how are you?")
    await mod_bot.handle(event)
    mock_reply.send_reply.assert_called_once()


async def test_blocked_message_dropped(mod_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="This is spam content")
    await mod_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_blocked_word_case_insensitive(mod_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext="This is SPAM")
    await mod_bot.handle(event)
    mock_reply.send_reply.assert_not_called()


async def test_flagged_count_increments(mod_bot, mock_reply) -> None:
    assert mod_bot.flagged_count == 0

    event1 = make_event(event_type="chat.received", plaintext="spam here", event_id="e1")
    event2 = make_event(event_type="chat.received", plaintext="more spam", event_id="e2")
    await mod_bot.handle(event1)
    await mod_bot.handle(event2)

    assert mod_bot.flagged_count == 2


async def test_ignores_outgoing(mod_bot, mock_reply) -> None:
    event = make_event(event_type="chat.sent", plaintext="spam")
    await mod_bot.handle(event)
    mock_reply.send_reply.assert_not_called()
    assert mod_bot.flagged_count == 0  # outgoing events don't count


async def test_ignores_no_plaintext(mod_bot, mock_reply) -> None:
    event = make_event(event_type="chat.received", plaintext=None)
    await mod_bot.handle(event)
    mock_reply.send_reply.assert_not_called()
