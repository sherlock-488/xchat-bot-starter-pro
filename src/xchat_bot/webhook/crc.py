"""
CRC challenge handler for X webhook verification.

X sends a GET request with a crc_token query parameter to verify your webhook URL.
You must respond with an HMAC-SHA256 signature of the token using your consumer secret.

Reference: https://docs.x.com/resources/fundamentals/authentication/guides/securing-webhooks
"""

from __future__ import annotations

import base64
import hashlib
import hmac


def compute_crc_response(crc_token: str, consumer_secret: str) -> dict[str, str]:
    """Compute the CRC challenge response dict.

    Args:
        crc_token: The crc_token value from the GET request query string.
        consumer_secret: Your X app consumer secret.

    Returns:
        Dict with "response_token" key, value is "sha256=<base64_digest>".
        Return this as JSON in your GET /webhook handler.

    Example::

        response = compute_crc_response(crc_token, settings.consumer_secret.get_secret_value())
        return JSONResponse(response)
    """
    digest = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    response_token = "sha256=" + base64.b64encode(digest).decode("utf-8")
    return {"response_token": response_token}


def verify_crc_response(crc_token: str, consumer_secret: str, expected: str) -> bool:
    """Verify a CRC response token (useful for testing your own implementation).

    Args:
        crc_token: The original crc_token.
        consumer_secret: Your consumer secret.
        expected: The response_token value to verify against.

    Returns:
        True if the expected value matches the computed response.
    """
    computed = compute_crc_response(crc_token, consumer_secret)["response_token"]
    return hmac.compare_digest(computed, expected)
