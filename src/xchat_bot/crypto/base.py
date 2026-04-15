"""
CryptoAdapter protocol — the interface all crypto implementations must satisfy.

Two implementations are provided:
  - StubCrypto: for development and testing, no real keys needed
  - RealCrypto: for production, uses state.json + XChaCha20-Poly1305 (EXPERIMENTAL)

To use a custom implementation, implement this protocol.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xchat_bot.events.models import DecryptResult


@runtime_checkable
class CryptoAdapter(Protocol):
    """Protocol for message encryption/decryption adapters.

    Implementations must be safe to call from async context (no blocking I/O).
    """

    def decrypt(
        self,
        encoded_event: str,
        encrypted_conversation_key: str | None = None,
    ) -> DecryptResult:
        """Decrypt an encoded event payload.

        Args:
            encoded_event: The encoded_event field from the official XAA payload,
                           or encrypted_content from the demo schema.
            encrypted_conversation_key: The encrypted_conversation_key from the
                                        official XAA payload, if available.

        Returns:
            DecryptResult with plaintext (or None on failure) and diagnostic notes.
            Never raises — use notes field for error context.
        """
        ...

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string (used for testing/fixture generation).

        Args:
            plaintext: The message to encrypt.

        Returns:
            Encrypted payload string suitable for use in test fixtures.
        """
        ...
