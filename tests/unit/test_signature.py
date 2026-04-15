"""Unit tests for webhook signature verification."""

from __future__ import annotations

import base64
import hashlib
import hmac

from xchat_bot.webhook.signature import (
    SIGNATURE_HEADER,
    explain_signature,
    generate_signature,
    verify_signature,
)


def test_generate_signature_format() -> None:
    sig = generate_signature(b"payload", "secret")
    assert sig.startswith("sha256=")


def test_generate_signature_correctness() -> None:
    payload = b'{"event_type": "chat.received"}'
    secret = "my_consumer_secret"

    sig = generate_signature(payload, secret)

    expected_digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    expected = "sha256=" + base64.b64encode(expected_digest).decode("utf-8")

    assert sig == expected


def test_verify_signature_valid() -> None:
    payload = b'{"data": {"event_type": "chat.received"}}'
    secret = "test_secret"
    sig = generate_signature(payload, secret)
    assert verify_signature(payload, sig, secret) is True


def test_verify_signature_invalid() -> None:
    payload = b'{"data": {"event_type": "chat.received"}}'
    secret = "test_secret"
    assert verify_signature(payload, "sha256=wrong", secret) is False


def test_verify_signature_tampered_payload() -> None:
    secret = "test_secret"
    original_payload = b'{"event_type": "chat.received"}'
    tampered_payload = b'{"event_type": "chat.sent"}'

    sig = generate_signature(original_payload, secret)
    assert verify_signature(tampered_payload, sig, secret) is False


def test_verify_signature_wrong_secret() -> None:
    payload = b"test payload"
    sig = generate_signature(payload, "correct_secret")
    assert verify_signature(payload, sig, "wrong_secret") is False


def test_explain_signature_structure() -> None:
    payload = b"test"
    secret = "mysecret"
    info = explain_signature(payload, secret)

    assert "algorithm" in info
    assert info["algorithm"] == "HMAC-SHA256"
    assert "expected_header_name" in info
    assert info["expected_header_name"] == SIGNATURE_HEADER
    assert "expected_header_value" in info
    assert str(info["expected_header_value"]).startswith("sha256=")
    assert "payload_length" in info
    assert info["payload_length"] == len(payload)


def test_explain_signature_key_preview_hides_secret() -> None:
    info = explain_signature(b"payload", "mysupersecretkey")
    # Key preview should not expose full secret
    assert "mysupersecretkey" not in str(info.get("key_preview", ""))
