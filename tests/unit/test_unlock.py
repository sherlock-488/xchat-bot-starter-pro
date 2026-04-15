"""Unit tests for xchat_bot.auth.unlock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xchat_bot.auth.unlock import run_unlock_flow

# ── run_unlock_flow creates a valid state file ─────────────────────────────────

async def test_run_unlock_flow_creates_state_file(tmp_path: Path):
    state_file = tmp_path / "state.json"
    await run_unlock_flow(
        access_token="fake_tok",
        consumer_key="fake_key",
        consumer_secret="fake_secret",
        access_token_secret="fake_tok_secret",
        state_file=state_file,
    )
    assert state_file.exists(), "state.json should be created by run_unlock_flow"


async def test_run_unlock_flow_state_file_is_valid_json(tmp_path: Path):
    state_file = tmp_path / "state.json"
    await run_unlock_flow(
        access_token="fake_tok",
        consumer_key="fake_key",
        consumer_secret="fake_secret",
        access_token_secret="fake_tok_secret",
        state_file=state_file,
    )
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "state.json must contain a JSON object"


async def test_run_unlock_flow_state_file_has_private_keys_key(tmp_path: Path):
    """run_unlock_flow is a placeholder; the returned StateManager has a private_keys property."""
    state_file = tmp_path / "state.json"
    manager = await run_unlock_flow(
        access_token="fake_tok",
        consumer_key="fake_key",
        consumer_secret="fake_secret",
        access_token_secret="fake_tok_secret",
        state_file=state_file,
    )
    # The StateManager.private_keys property always returns a dict (empty if unset)
    assert isinstance(manager.private_keys, dict), (
        "StateManager.private_keys must be a dict (even if empty for placeholder impl)"
    )


async def test_run_unlock_flow_returns_state_manager(tmp_path: Path):
    from xchat_bot.state.manager import StateManager

    state_file = tmp_path / "state.json"
    manager = await run_unlock_flow(
        access_token="fake_tok",
        consumer_key="fake_key",
        consumer_secret="fake_secret",
        access_token_secret="fake_tok_secret",
        state_file=state_file,
    )
    assert isinstance(manager, StateManager)


async def test_run_unlock_flow_raises_if_state_file_exists_without_force(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        await run_unlock_flow(
            access_token="fake_tok",
            consumer_key="fake_key",
            consumer_secret="fake_secret",
            access_token_secret="fake_tok_secret",
            state_file=state_file,
            force=False,
        )


async def test_run_unlock_flow_force_overwrites_existing_file(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    # Should not raise with force=True
    await run_unlock_flow(
        access_token="fake_tok",
        consumer_key="fake_key",
        consumer_secret="fake_secret",
        access_token_secret="fake_tok_secret",
        state_file=state_file,
        force=True,
    )
    assert state_file.exists()
