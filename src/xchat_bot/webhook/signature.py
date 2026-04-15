"""
Webhook signature verification for X Activity API.

X signs each webhook POST with HMAC-SHA256 using your consumer secret.
The signature is in the x-twitter-webhooks-signature header as "sha256=<base64>".

Always use verify_signature() — it uses hmac.compare_digest() for timing-safe comparison.
Never compare signature strings with == (vulnerable to timing attacks).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

SIGNATURE_HEADER = "x-twitter-webhooks-signature"
LEGACY_SIGNATURE_HEADER = "x-signature-256"  # observed in some environments


def generate_signature(payload: bytes, consumer_secret: str) -> str:
    """Generate the x-twitter-webhooks-signature header value.

    Args:
        payload: Raw request body bytes.
        consumer_secret: Your X app consumer secret.

    Returns:
        Header value string: "sha256=<base64_encoded_digest>"
    """
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return "sha256=" + base64.b64encode(digest).decode("utf-8")


def verify_signature(payload: bytes, signature_header: str, consumer_secret: str) -> bool:
    """Verify the webhook signature using timing-safe comparison.

    Args:
        payload: Raw request body bytes (before any parsing).
        signature_header: Value of x-twitter-webhooks-signature header.
        consumer_secret: Your X app consumer secret.

    Returns:
        True if the signature is valid.

    Note:
        Always verify the signature before processing any webhook payload.
        Reject requests with invalid signatures with HTTP 403.
    """
    expected = generate_signature(payload, consumer_secret)
    return hmac.compare_digest(expected, signature_header)


def explain_signature(payload: bytes, consumer_secret: str) -> dict[str, str | int]:
    """Return step-by-step signature computation details for debugging.

    Useful when troubleshooting signature mismatches.

    Returns:
        Dict with algorithm, key preview, payload length, raw digest, base64 digest,
        and the full header value you should expect.
    """
    raw_digest = hmac.new(
        consumer_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    b64 = base64.b64encode(raw_digest).decode("utf-8")
    key_preview = (
        f"{consumer_secret[:4]}...{consumer_secret[-4:]}"
        if len(consumer_secret) > 8
        else "****"
    )
    return {
        "algorithm": "HMAC-SHA256",
        "key_preview": key_preview,
        "payload_length": len(payload),
        "raw_digest_hex": raw_digest.hex(),
        "base64_digest": b64,
        "expected_header_name": SIGNATURE_HEADER,
        "expected_header_value": f"sha256={b64}",
    }
