"""Unit tests for xchat_bot.auth.token_store.TokenStore."""

from __future__ import annotations

from pathlib import Path

from xchat_bot.auth.token_store import TokenStore

# ── tokens_file property ───────────────────────────────────────────────────────

def test_tokens_file_property_returns_correct_path(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    assert store.tokens_file == tmp_path / "tokens.json"


# ── save() ─────────────────────────────────────────────────────────────────────

def test_save_creates_file(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok", access_token_secret="sec")
    assert store.tokens_file.exists()


def test_save_writes_correct_content(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(
        access_token="my_token",
        access_token_secret="my_secret",
        user_id="12345",
        screen_name="testuser",
    )
    import json
    data = json.loads(store.tokens_file.read_text(encoding="utf-8"))
    assert data["access_token"] == "my_token"
    assert data["access_token_secret"] == "my_secret"
    assert data["user_id"] == "12345"
    assert data["screen_name"] == "testuser"


def test_save_without_optional_fields(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok", access_token_secret="sec")
    import json
    data = json.loads(store.tokens_file.read_text(encoding="utf-8"))
    assert data["access_token"] == "tok"
    assert data["access_token_secret"] == "sec"
    assert data["user_id"] is None
    assert data["screen_name"] is None


# ── load() ─────────────────────────────────────────────────────────────────────

def test_load_returns_saved_tokens(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(
        access_token="tok",
        access_token_secret="sec",
        user_id="999",
        screen_name="bot",
    )
    result = store.load()
    assert result is not None
    assert result["access_token"] == "tok"
    assert result["access_token_secret"] == "sec"
    assert result["user_id"] == "999"
    assert result["screen_name"] == "bot"


def test_load_returns_none_if_file_does_not_exist(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path / "nonexistent_subdir")
    result = store.load()
    assert result is None


def test_load_after_save_round_trip(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="a", access_token_secret="b")
    loaded = store.load()
    assert loaded is not None
    assert loaded["access_token"] == "a"
    assert loaded["access_token_secret"] == "b"


# ── exists() / clear() ─────────────────────────────────────────────────────────

def test_exists_returns_false_before_save(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    assert store.exists() is False


def test_exists_returns_true_after_save(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok", access_token_secret="sec")
    assert store.exists() is True


def test_clear_removes_tokens_file(tmp_path: Path):
    store = TokenStore(data_dir=tmp_path)
    store.save(access_token="tok", access_token_secret="sec")
    store.clear()
    assert not store.tokens_file.exists()
