"""Unit tests for RealCrypto."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xchat_bot.crypto.real import RealCrypto
from xchat_bot.crypto.stub import STUB_PREFIX


def test_load_valid_state_file(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    assert crypto.user_id == "444555666"
    assert crypto.signing_key_version == "2"


def test_missing_state_file_raises() -> None:
    with pytest.raises(FileNotFoundError, match="state.json"):
        RealCrypto(Path("/nonexistent/state.json"))


def test_malformed_state_file_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "state.json"
    bad_file.write_text("not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        RealCrypto(bad_file)


def test_state_missing_private_keys_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "state.json"
    bad_file.write_text(json.dumps({"user_id": "123"}), encoding="utf-8")
    with pytest.raises(ValueError, match="private_keys"):
        RealCrypto(bad_file)


def test_decrypt_stub_payload_falls_back(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    result = crypto.decrypt(f"{STUB_PREFIX}SGVsbG8h")

    assert result.plaintext == "Hello!"
    assert result.mode == "real-fallback-stub"


def test_decrypt_real_payload_returns_placeholder(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    result = crypto.decrypt("REAL_ENCRYPTED_PAYLOAD_BASE64==")

    assert result.plaintext is None
    assert result.mode == "real"
    assert "EXPERIMENTAL" in (result.notes or "")
    assert result.key_id == "2"  # latest key version from state_stub.json


def test_get_latest_key_version(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    version, key = crypto.get_latest_key()  # type: ignore[misc]
    assert version == "2"
    assert "STUB_PRIVATE_KEY_v2" in key


def test_get_private_key_by_version(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    key_v1 = crypto.get_private_key("1")
    assert key_v1 is not None
    assert "v1" in key_v1

    key_v2 = crypto.get_private_key("2")
    assert key_v2 is not None
    assert "v2" in key_v2


def test_get_nonexistent_key_returns_none(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    assert crypto.get_private_key("999") is None


def test_encrypt_not_implemented(state_stub_path: Path) -> None:
    crypto = RealCrypto(state_stub_path)
    with pytest.raises(NotImplementedError):
        crypto.encrypt("hello")
