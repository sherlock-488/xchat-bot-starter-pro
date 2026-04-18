"""
Normalized event model — the internal representation of all XChat events.

Both transport modes (stream and webhook) produce NormalizedEvent objects.
Bot logic only ever sees NormalizedEvent; it never touches raw payloads.

Schema sources:
  - "observed-xchat": XAA envelope observed from xchat-bot-python (chat.* events)
  - "docs-xaa": XAA envelope from official docs.x.com examples (profile.update.bio etc.)
      {"data": {"event_type": "...", "payload": {...}}}
  - "demo": Flat demo format used in xchat-playground fixtures
      {"event_type": "...", "direct_message_events": [...]}
  - "unknown": Unrecognized format (preserved in raw, not dropped)

TAL fields are labeled in their docstrings. These fields come from
observed behavior in official examples or the playground, but are not yet
fully documented in official X developer docs. Treat them as unstable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EncryptedPayload(BaseModel):
    """Encrypted message material — populated before decryption.

    Fields from the observed XAA envelope (data.payload.*) are the primary
    source (inferred from xchat-bot-python; not yet fully in docs.x.com).
    Fields from the demo schema are labeled EXPERIMENTAL.
    """

    # Observed XAA envelope fields (inferred from xchat-bot-python)
    encoded_event: str | None = Field(
        None,
        description=(
            "Base64-encoded encrypted message blob. "
            "From data.payload.encoded_event in the observed XAA envelope (xchat-bot-python). "
            "Decrypted with XChaCha20-Poly1305 using the conversation key."
        ),
    )
    encrypted_conversation_key: str | None = Field(
        None,
        description=(
            "Encrypted symmetric conversation key, one per recipient. "
            "From data.payload.encrypted_conversation_key."
        ),
    )
    conversation_key_version: str | None = Field(
        None,
        description="Key version string used to select the correct private key from state.json.",
    )

    # Demo schema fields — EXPERIMENTAL
    encrypted_content: str | None = Field(
        None,
        description=(
            "EXPERIMENTAL: encrypted_content from demo schema "
            "(direct_message_events[].message.encrypted_content). "
            "Not confirmed in official docs — field shape may change."
        ),
    )
    encryption_type: str | None = Field(
        None,
        description=(
            "EXPERIMENTAL: encryption algorithm label from demo schema. "
            "Observed value: 'XChaCha20Poly1305'. Not confirmed in official docs."
        ),
    )
    key_version: str | None = Field(
        None,
        description=(
            "EXPERIMENTAL: key version from demo schema message.key_version. "
            "May differ from conversation_key_version."
        ),
    )
    recipient_keys: dict[str, str] | None = Field(
        None,
        description=(
            "EXPERIMENTAL: per-recipient encrypted key blobs from demo schema. "
            "Keyed by user_id. Not confirmed in official docs."
        ),
    )

    @property
    def has_real_payload(self) -> bool:
        """True if this looks like a real (non-stub) encrypted payload."""
        if self.encoded_event:
            return not self.encoded_event.startswith("STUB_")
        if self.encrypted_content:
            return not self.encrypted_content.startswith("STUB_")
        return False


class DecryptResult(BaseModel):
    """Result from a CryptoAdapter.decrypt() call."""

    plaintext: str | None = Field(None, description="Decrypted message text, or None on failure")
    mode: Literal["stub", "real", "real-fallback-stub"] = Field(
        description="Which crypto path was used"
    )
    key_id: str | None = Field(None, description="Key version used for decryption")
    notes: str | None = Field(
        None, description="Human-readable notes about what happened (useful for debugging)"
    )


class NormalizedEvent(BaseModel):
    """Canonical internal representation of a single XChat event.

    Produced by EventNormalizer from raw webhook/stream payloads.
    Both transport modes produce this same model — bot logic never
    needs to know which transport delivered the event.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    event_id: str = Field(
        description=(
            "Stable, deterministic event identifier used for deduplication. "
            "Derived from payload fields — same event always produces the same ID."
        )
    )
    event_type: str = Field(
        description="Event type string, e.g. 'chat.received', 'chat.sent', 'chat.conversation_join'"
    )
    schema_source: Literal["docs-xaa", "observed-xchat", "demo", "unknown"] = Field(
        description="Which schema format was detected in the raw payload"
    )

    # ── Timing ────────────────────────────────────────────────────────────
    received_at: datetime = Field(description="When our server/stream received this event (UTC)")
    created_at: datetime | None = Field(
        None, description="Event creation time from payload, if present (UTC)"
    )

    # ── Participants ──────────────────────────────────────────────────────
    conversation_id: str | None = Field(None, description="Conversation/DM conversation identifier")
    sender_id: str | None = Field(None, description="X user ID of the message sender")
    for_user_id: str | None = Field(
        None,
        description=(
            "X user ID this event is addressed to (typically the bot's user ID). "
            "From for_user_id in demo schema."
        ),
    )
    participant_ids: list[str] = Field(
        default_factory=list,
        description="All participant user IDs in this conversation",
    )

    # ── Content ───────────────────────────────────────────────────────────
    plaintext: str | None = Field(
        None,
        description=(
            "Decrypted message text. Populated by CryptoAdapter after normalization. "
            "None if decryption failed or was not attempted."
        ),
    )
    encrypted: EncryptedPayload | None = Field(
        None, description="Raw encrypted payload fields, before decryption"
    )

    # ── Reply metadata ────────────────────────────────────────────────────
    conversation_token: str | None = Field(
        None,
        description=(
            "EXPERIMENTAL: Opaque token required by the reply API. "
            "Observed in xchat-bot-python as data.payload.conversation_token. "
            "Required for sending replies — may change when official docs publish."
        ),
    )

    # ── XAA envelope metadata (preserved for debugging) ──────────────────
    filter: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "XAA envelope filter dict (e.g. {'user_id': '...'} for profile events). "
            "Preserved from the data.filter field in the XAA envelope."
        ),
    )
    tag: str | None = Field(
        None,
        description="Subscription tag from data.tag in the XAA envelope, if present.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Generic inner payload dict. For chat.* events this is the encrypted payload. "
            "For profile.update.bio this contains before/after. Always set for XAA events."
        ),
    )

    # ── Processing metadata ───────────────────────────────────────────────
    is_stub: bool = Field(
        False,
        description="True if this event used stub crypto (STUB_ENC_ prefix payload)",
    )
    decrypt_notes: str | None = Field(
        None, description="Notes from CryptoAdapter (useful for debugging)"
    )

    # ── Raw preservation ──────────────────────────────────────────────────
    raw: dict[str, Any] = Field(
        default_factory=dict,
        exclude=True,
        description="Original raw payload — not serialized, available for debugging",
    )

    @property
    def is_incoming(self) -> bool:
        """True if this is an incoming message (chat.received)."""
        return self.event_type == "chat.received"

    @property
    def is_outgoing(self) -> bool:
        """True if this is an outgoing message (chat.sent)."""
        return self.event_type == "chat.sent"

    @property
    def is_join(self) -> bool:
        """True if this is a conversation join event."""
        return self.event_type == "chat.conversation_join"

    @property
    def is_chat(self) -> bool:
        """True if this is any chat.* event."""
        return self.event_type.startswith("chat.")

    @property
    def is_profile_update(self) -> bool:
        """True if this is a profile.update.* event."""
        return self.event_type.startswith("profile.update.")

    @property
    def filter_user_id(self) -> str | None:
        """Convenience accessor for filter.user_id (common in XAA subscriptions)."""
        value = self.filter.get("user_id")
        return str(value) if value is not None else None

    def now_utc() -> datetime:  # type: ignore[misc]
        return datetime.now(UTC)
