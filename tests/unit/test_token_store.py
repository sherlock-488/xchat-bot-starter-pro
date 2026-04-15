"""Unit tests for xchat_bot.auth.token_store.TokenStore."""

from __future__ import annotations

import json
from pathlib import Path

from xchat_bot.auth.token_store import TokenStore

# ── tokens_file property ───────────────────────────────────────────────────────


def test_tokens_file_property_returns_correct_path(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    assert store.tokens_file == tmp_path / "tokens.json"


# ── save() ─────────────────────────────────────────────────────────────────────


def test_save_creates_file(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok")
    assert store.tokens_file.exists()


def test_save_writes_correct_content(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(
        access_token="my_token",
        refresh_token="my_refresh",
        user_id="12345",
        screen_name="testuser",
        scope="dm.read dm.write",
    )
    data = json.loads(store.tokens_file.read_text(encoding="utf-8"))
    assert data["access_token"] == "my_token"
    assert data["refresh_token"] == "my_refresh"
    assert data["user_id"] == "12345"
    assert data["screen_name"] == "testuser"
    assert data["scope"] == "dm.read dm.write"


def test_save_without_optional_fields(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok")
    data = json.loads(store.tokens_file.read_text(encoding="utf-8"))
    assert data["access_token"] == "tok"
    assert data["refresh_token"] is None
    assert data["user_id"] is None
    assert data["screen_name"] is None
    assert data["scope"] is None


# ── load() ─────────────────────────────────────────────────────────────────────


def test_load_returns_saved_tokens(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(
        access_token="tok",
        refresh_token="ref",
        user_id="999",
        screen_name="bot",
    )
    result = store.load()
    assert result is not None
    assert result["access_token"] == "tok"
    assert result["refresh_token"] == "ref"
    assert result["user_id"] == "999"
    assert result["screen_name"] == "bot"


def test_load_returns_none_if_file_does_not_exist(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path / "nonexistent_subdir")
    result = store.load()
    assert result is None


def test_load_after_save_round_trip(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="a", refresh_token="b")
    loaded = store.load()
    assert loaded is not None
    assert loaded["access_token"] == "a"
    assert loaded["refresh_token"] == "b"


# ── exists() / clear() ─────────────────────────────────────────────────────────


def test_exists_returns_false_before_save(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    assert store.exists() is False


def test_exists_returns_true_after_save(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok")
    assert store.exists() is True


def test_clear_removes_tokens_file(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok")
    store.clear()
    assert not store.tokens_file.exists()
