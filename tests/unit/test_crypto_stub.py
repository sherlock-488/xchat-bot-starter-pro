"""Unit tests for StubCrypto."""

from __future__ import annotations

import base64

from xchat_bot.crypto.stub import STUB_PREFIX, StubCrypto


def test_encrypt_produces_stub_prefix() -> None:
    crypto = StubCrypto()
    result = crypto.encrypt("Hello!")
    assert result.startswith(STUB_PREFIX)


def test_decrypt_stub_payload() -> None:
    crypto = StubCrypto()
    encoded = crypto.encrypt("Hello, world!")
    result = crypto.decrypt(encoded)

    assert result.plaintext == "Hello, world!"
    assert result.mode == "stub"


def test_round_trip() -> None:
    crypto = StubCrypto()
    original = "Test message 🎉"
    encrypted = crypto.encrypt(original)
    result = crypto.decrypt(encrypted)
    assert result.plaintext == original


def test_decrypt_real_payload_returns_placeholder() -> None:
    crypto = StubCrypto()
    result = crypto.decrypt("REAL_BASE64_PAYLOAD_NOT_STUB")

    assert result.plaintext is None
    assert result.mode == "stub"
    assert result.notes is not None
    assert "real" in result.notes.lower() or "stub" in result.notes.lower()


def test_decrypt_malformed_stub_payload() -> None:
    crypto = StubCrypto()
    # Valid prefix but invalid base64
    result = crypto.decrypt(f"{STUB_PREFIX}!!!not_valid_base64!!!")

    assert result.plaintext is None
    assert result.mode == "stub"
    assert result.notes is not None


def test_decrypt_empty_stub_payload() -> None:
    crypto = StubCrypto()
    # STUB_ENC_ with empty base64 (empty string encodes to "")
    result = crypto.decrypt(f"{STUB_PREFIX}{base64.b64encode(b'').decode()}")
    assert result.plaintext == ""
    assert result.mode == "stub"


def test_decrypt_unicode_message() -> None:
    crypto = StubCrypto()
    msg = "你好世界 🌍"
    encrypted = crypto.encrypt(msg)
    result = crypto.decrypt(encrypted)
    assert result.plaintext == msg
