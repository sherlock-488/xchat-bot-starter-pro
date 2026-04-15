"""
StubCrypto — development/test crypto adapter.

Uses a simple STUB_ENC_<base64> encoding instead of real encryption.
No keys required. Safe to use in CI and local development.

Payload format: "STUB_ENC_" + base64(plaintext)

This is intentionally transparent — the goal is to let you develop and test
bot logic without needing real X credentials or E2EE keys.
"""

from __future__ import annotations

import base64

from xchat_bot.events.models import DecryptResult

STUB_PREFIX = "STUB_ENC_"


class StubCrypto:
    """Stub crypto adapter for development and testing.

    Decodes STUB_ENC_<base64> payloads without any real keys.
    Real encrypted payloads (from production) return a placeholder message.

    Usage::

        crypto = StubCrypto()
        result = crypto.decrypt("STUB_ENC_SGVsbG8h")
        assert result.plaintext == "Hello!"
        assert result.mode == "stub"
    """

    def decrypt(
        self,
        encoded_event: str,
        encrypted_conversation_key: str | None = None,
    ) -> DecryptResult:
        """Decode a STUB_ENC_ payload.

        Args:
            encoded_event: Stub-encoded payload string.
            encrypted_conversation_key: Ignored in stub mode.

        Returns:
            DecryptResult with decoded plaintext, or a placeholder for real payloads.
        """
        if encoded_event.startswith(STUB_PREFIX):
            b64_part = encoded_event[len(STUB_PREFIX):]
            try:
                plaintext = base64.b64decode(b64_part).decode("utf-8")
                return DecryptResult(
                    plaintext=plaintext,
                    mode="stub",
                    key_id=None,
                    notes="Decoded from STUB_ENC_ prefix (stub mode)",
                )
            except Exception as exc:
                return DecryptResult(
                    plaintext=None,
                    mode="stub",
                    key_id=None,
                    notes=f"STUB_ENC_ decode failed: {exc}",
                )
        else:
            # Real encrypted payload — can't decode without real keys
            preview = encoded_event[:40] + ("..." if len(encoded_event) > 40 else "")
            return DecryptResult(
                plaintext=None,
                mode="stub",
                key_id=None,
                notes=(
                    f"Real encrypted payload detected (preview: {preview!r}). "
                    "Use crypto_mode='real' with a valid state.json to decrypt. "
                    "Note: real decryption is EXPERIMENTAL (chat-xdk not yet stable)."
                ),
            )

    def encrypt(self, plaintext: str) -> str:
        """Encode plaintext as a STUB_ENC_ payload.

        Args:
            plaintext: Message text to encode.

        Returns:
            "STUB_ENC_<base64>" string suitable for test fixtures.
        """
        b64 = base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")
        return f"{STUB_PREFIX}{b64}"
