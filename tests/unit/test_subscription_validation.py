"""Unit tests for subscription create validation — chat.* filter rules."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from xchat_bot.cli.cmd_subscriptions import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _invoke(runner: CliRunner, *args: str) -> object:
    """Invoke the subscriptions CLI with env vars patched to avoid real API calls."""

    env = {
        "XCHAT_BEARER_TOKEN": "fake_bearer",
        "XCHAT_USER_ACCESS_TOKEN": "fake_user_token",
    }
    return runner.invoke(app, ["create", *args], env=env, catch_exceptions=False)


# ── chat.* requires user_id ───────────────────────────────────────────────────


def test_chat_received_requires_user_id(runner: CliRunner) -> None:
    result = _invoke(runner, "--event-type", "chat.received")
    assert result.exit_code != 0
    assert "user-id" in result.output or "user_id" in result.output


def test_chat_sent_requires_user_id(runner: CliRunner) -> None:
    result = _invoke(runner, "--event-type", "chat.sent")
    assert result.exit_code != 0
    assert "user-id" in result.output or "user_id" in result.output


def test_chat_conversation_join_requires_user_id(runner: CliRunner) -> None:
    result = _invoke(runner, "--event-type", "chat.conversation_join")
    assert result.exit_code != 0
    assert "user-id" in result.output or "user_id" in result.output


# ── chat.* rejects keyword ────────────────────────────────────────────────────


def test_chat_received_rejects_keyword(runner: CliRunner) -> None:
    result = _invoke(
        runner,
        "--event-type",
        "chat.received",
        "--user-id",
        "123",
        "--keyword",
        "hello",
    )
    assert result.exit_code != 0
    assert "keyword" in result.output.lower()
    assert "chat" in result.output.lower()


# ── chat.* rejects direction ──────────────────────────────────────────────────


def test_chat_received_rejects_direction(runner: CliRunner) -> None:
    result = _invoke(
        runner,
        "--event-type",
        "chat.received",
        "--user-id",
        "123",
        "--direction",
        "inbound",
    )
    assert result.exit_code != 0
    assert "direction" in result.output.lower()
    assert "chat" in result.output.lower()


# ── non-chat event types still support filters ────────────────────────────────


def test_non_chat_event_allows_keyword(runner: CliRunner) -> None:
    """news.new with --keyword should NOT be rejected by chat.* validation."""
    import unittest.mock as mock

    with mock.patch("xchat_bot.cli.cmd_subscriptions.httpx.post") as mock_post:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"data": {"subscription_id": "sub_1"}}
        mock_post.return_value = mock_resp

        result = _invoke(
            runner,
            "--event-type",
            "news.new",
            "--keyword",
            "AI",
            "--auth",
            "app",
        )

    assert result.exit_code == 0
    assert "Error" not in result.output or "keyword" not in result.output.lower()


def test_non_chat_event_allows_user_id_and_direction(runner: CliRunner) -> None:
    """profile.update.bio with --user-id and --direction should pass chat.* validation."""
    import unittest.mock as mock

    with mock.patch("xchat_bot.cli.cmd_subscriptions.httpx.post") as mock_post:
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"data": {"subscription_id": "sub_2"}}
        mock_post.return_value = mock_resp

        result = _invoke(
            runner,
            "--event-type",
            "profile.update.bio",
            "--user-id",
            "12345",
            "--direction",
            "inbound",
            "--auth",
            "app",
        )

    assert result.exit_code == 0
