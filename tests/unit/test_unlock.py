"""Unit tests for xchat_bot.auth.unlock."""

from __future__ import annotations

from pathlib import Path

import pytest

from xchat_bot.auth.unlock import run_unlock_flow

# ── run_unlock_flow creates a valid state file ─────────────────────────────────


async def test_run_unlock_flow_creates_state_file(tmp_path: Path):
    state_file = tmp_path / "state.json"
    await run_unlock_flow(
        user_access_token="fake_oauth2_token",
        state_file=state_file,
    )
    assert state_file.exists()


async def test_run_unlock_flow_creates_valid_json(tmp_path: Path):
    import json

    state_file = tmp_path / "state.json"
    await run_unlock_flow(
        user_access_token="fake_oauth2_token",
        state_file=state_file,
    )
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


async def test_run_unlock_flow_raises_if_file_exists(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        await run_unlock_flow(
            user_access_token="fake_oauth2_token",
            state_file=state_file,
        )


async def test_run_unlock_flow_force_overwrites_existing(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")

    # Should not raise with force=True
    await run_unlock_flow(
        user_access_token="fake_oauth2_token",
        state_file=state_file,
        force=True,
    )
    assert state_file.exists()


async def test_run_unlock_flow_returns_state_manager(tmp_path: Path):
    from xchat_bot.state.manager import StateManager

    state_file = tmp_path / "state.json"
    result = await run_unlock_flow(
        user_access_token="fake_oauth2_token",
        state_file=state_file,
    )
    assert isinstance(result, StateManager)
