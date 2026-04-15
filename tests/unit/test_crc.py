"""Unit tests for CRC challenge computation."""

from __future__ import annotations

import base64
import hashlib
import hmac

from xchat_bot.webhook.crc import compute_crc_response, verify_crc_response


def test_compute_crc_response_format() -> None:
    result = compute_crc_response("test_token", "my_secret")
    assert "response_token" in result
    assert result["response_token"].startswith("sha256=")


def test_compute_crc_response_correctness() -> None:
    crc_token = "challenge_token_123"
    consumer_secret = "my_consumer_secret"

    result = compute_crc_response(crc_token, consumer_secret)

    # Manually compute expected value
    expected_digest = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected = "sha256=" + base64.b64encode(expected_digest).decode("utf-8")

    assert result["response_token"] == expected


def test_verify_crc_response_valid() -> None:
    token = "test_crc_token"
    secret = "test_secret"
    response = compute_crc_response(token, secret)["response_token"]
    assert verify_crc_response(token, secret, response) is True


def test_verify_crc_response_invalid() -> None:
    token = "test_crc_token"
    secret = "test_secret"
    assert verify_crc_response(token, secret, "sha256=wrong_value") is False


def test_different_secrets_produce_different_responses() -> None:
    token = "same_token"
    r1 = compute_crc_response(token, "secret_a")
    r2 = compute_crc_response(token, "secret_b")
    assert r1["response_token"] != r2["response_token"]


def test_different_tokens_produce_different_responses() -> None:
    secret = "same_secret"
    r1 = compute_crc_response("token_a", secret)
    r2 = compute_crc_response("token_b", secret)
    assert r1["response_token"] != r2["response_token"]
