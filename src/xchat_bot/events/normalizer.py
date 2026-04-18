"""
EventNormalizer — converts raw XChat payloads to NormalizedEvent.

Handles two observed schema formats:
  1. XAA envelope: {"data": {"event_type": "...", "payload": {...}}}
  2. Demo/flat schema:      {"event_type": "...", "direct_message_events": [...]}

The normalizer never raises on unexpected shapes — it returns a NormalizedEvent
with schema_source="unknown" so bot logic can handle or log it gracefully.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from xchat_bot.events.models import EncryptedPayload, NormalizedEvent


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _stable_event_id(parts: list[str]) -> str:
    """Produce a 32-char deterministic event ID from a list of string parts."""
    combined = ":".join(p for p in parts if p)
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class EventNormalizer:
    """Converts raw dict payloads to NormalizedEvent objects.

    Usage::

        normalizer = EventNormalizer()
        event = normalizer.normalize(raw_dict)
    """

    def normalize(self, raw: dict[str, Any]) -> NormalizedEvent:
        """Normalize a raw payload dict into a NormalizedEvent.

        Never raises — returns schema_source="unknown" on unexpected input.
        """
        if "data" in raw and isinstance(raw.get("data"), dict):
            return self._normalize_xaa(raw)
        elif "event_type" in raw:
            return self._normalize_demo(raw)
        else:
            return self._normalize_unknown(raw)

    # ── XAA envelope (docs-xaa for profile.*, observed-xchat for chat.*) ────

    def _normalize_xaa(self, raw: dict[str, Any]) -> NormalizedEvent:
        """Handle XAA envelope: {"data": {"event_type": "...", "payload": {...}}}

        schema_source:
          - "docs-xaa" for profile.update.* and other events with docs.x.com examples
          - "observed-xchat" for chat.* events (inferred from xchat-bot-python)
        """
        data = raw["data"]
        event_type = str(data.get("event_type") or "unknown")
        payload = data.get("payload") or {}
        filter_ = data.get("filter") or {}
        tag = data.get("tag")
        schema_source = "observed-xchat" if event_type.startswith("chat.") else "docs-xaa"

        # chat.* events: extract encrypted XChat fields
        if event_type.startswith("chat."):
            conv_id = payload.get("conversation_id")
            encoded = payload.get("encoded_event")
            enc_key = payload.get("encrypted_conversation_key")
            key_ver = payload.get("conversation_key_version")
            conv_token = payload.get("conversation_token")  # EXPERIMENTAL
            encrypted = EncryptedPayload(
                encoded_event=encoded,
                encrypted_conversation_key=enc_key,
                conversation_key_version=key_ver,
            )
            event_id = _stable_event_id([conv_id or "", (encoded or "")[:32], event_type])
            is_stub = bool(encoded and encoded.startswith("STUB_"))
            return NormalizedEvent(
                event_id=event_id,
                event_type=event_type,
                schema_source=schema_source,
                received_at=_now_utc(),
                filter=filter_,
                tag=tag,
                payload=payload,
                conversation_id=conv_id,
                encrypted=encrypted,
                conversation_token=conv_token,
                is_stub=is_stub,
                raw=raw,
            )

        # Non-chat XAA events (profile.update.bio, follow.*, spaces.*, etc.)
        event_id = _stable_event_id([
            event_type,
            json.dumps(filter_, sort_keys=True, ensure_ascii=False),
            json.dumps(payload, sort_keys=True, ensure_ascii=False),
            str(tag or ""),
        ])
        return NormalizedEvent(
            event_id=event_id,
            event_type=event_type,
            schema_source=schema_source,
            received_at=_now_utc(),
            filter=filter_,
            tag=tag,
            payload=payload,
            raw=raw,
        )

    # ── Demo / flat schema ────────────────────────────────────────────────

    def _normalize_demo(self, raw: dict[str, Any]) -> NormalizedEvent:
        """Handle: {"event_type": "...", "direct_message_events": [...]}"""
        event_type = raw.get("event_type", "unknown")
        for_user_id = raw.get("for_user_id")
        created_at = _parse_datetime(raw.get("created_at"))

        dm_events: list[dict[str, Any]] = raw.get("direct_message_events", [])
        first = dm_events[0] if dm_events else {}

        msg_id = first.get("id")
        sender_id = first.get("sender_id")
        conv_id = first.get("dm_conversation_id")
        participant_ids: list[str] = first.get("participant_ids", [])
        msg_created = _parse_datetime(first.get("created_at"))

        message: dict[str, Any] = first.get("message", {})
        enc_content = message.get("encrypted_content")
        enc_type = message.get("encryption_type")
        key_ver = message.get("key_version")
        recipient_keys = message.get("recipient_keys")

        encrypted: EncryptedPayload | None = None
        if enc_content or enc_type or recipient_keys:
            encrypted = EncryptedPayload(
                encrypted_content=enc_content,
                encryption_type=enc_type,
                key_version=key_ver,
                recipient_keys=recipient_keys,
            )

        # Stable event ID: prefer message ID, fall back to hash
        if msg_id:
            event_id = _stable_event_id([msg_id, event_type])
        else:
            event_id = _stable_event_id([json.dumps(raw, sort_keys=True, ensure_ascii=False)])

        is_stub = bool(enc_content and enc_content.startswith("STUB_"))

        return NormalizedEvent(
            event_id=event_id,
            event_type=event_type,
            schema_source="demo",
            received_at=_now_utc(),
            created_at=msg_created or created_at,
            conversation_id=conv_id,
            sender_id=sender_id,
            for_user_id=for_user_id,
            participant_ids=participant_ids,
            encrypted=encrypted,
            is_stub=is_stub,
            raw=raw,
        )

    # ── Unknown / fallback ────────────────────────────────────────────────

    def _normalize_unknown(self, raw: dict[str, Any]) -> NormalizedEvent:
        """Handle unrecognized formats gracefully."""
        event_id = _stable_event_id([json.dumps(raw, sort_keys=True, ensure_ascii=False)])
        return NormalizedEvent(
            event_id=event_id,
            event_type="unknown",
            schema_source="unknown",
            received_at=_now_utc(),
            raw=raw,
        )
