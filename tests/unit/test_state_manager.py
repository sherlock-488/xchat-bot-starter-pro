"""Unit tests for StateManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xchat_bot.state.manager import StateManager


def test_load_valid_state(state_stub_path: Path) -> None:
    manager = StateManager(state_stub_path)
    manager.load()

    assert manager.user_id == "444555666"
    assert manager.signing_key_version == "2"
    assert len(manager.private_keys) == 2


def test_load_missing_file_raises(tmp_path: Path) -> None:
    manager = StateManager(tmp_path / "nonexistent.json")
    with pytest.raises(FileNotFoundError):
        manager.load()


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "state.json"
    bad.write_text("not json")
    manager = StateManager(bad)
    with pytest.raises(ValueError):
        manager.load()


def test_get_latest_key(state_stub_path: Path) -> None:
    manager = StateManager(state_stub_path)
    manager.load()

    result = manager.get_latest_key()
    assert result is not None
    version, key = result
    assert version == "2"
    assert "v2" in key


def test_get_private_key_by_version(state_stub_path: Path) -> None:
    manager = StateManager(state_stub_path)
    manager.load()

    key = manager.get_private_key("1")
    assert key is not None
    assert "v1" in key


def test_get_nonexistent_key_version(state_stub_path: Path) -> None:
    manager = StateManager(state_stub_path)
    manager.load()
    assert manager.get_private_key("999") is None


def test_save_creates_file(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    manager = StateManager(state_file)
    manager.user_id = "user123"
    manager.signing_key_version = "1"
    manager.set_private_key("1", "base64key==")
    manager.save()

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["user_id"] == "user123"
    assert data["private_keys"]["1"] == "base64key=="


def test_save_sets_permissions(tmp_path: Path) -> None:
    import stat
    state_file = tmp_path / "state.json"
    manager = StateManager(state_file)
    manager.save()

    mode = oct(stat.S_IMODE(state_file.stat().st_mode))
    assert mode == "0o600"


def test_validate_empty_state() -> None:
    manager = StateManager(Path("nonexistent.json"))
    errors = manager.validate()
    assert any("private_keys" in e for e in errors)
    assert any("user_id" in e for e in errors)


def test_validate_loaded_state(state_stub_path: Path) -> None:
    manager = StateManager(state_stub_path)
    manager.load()
    errors = manager.validate()
    assert errors == []
