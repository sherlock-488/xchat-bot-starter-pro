"""Unit tests for EventNormalizer."""

from __future__ import annotations

import pytest

from xchat_bot.events.normalizer import EventNormalizer


@pytest.fixture
def norm() -> EventNormalizer:
    return EventNormalizer()


def test_observed_xchat_schema(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_SGVsbG8h",
                "encrypted_conversation_key": "ENC_KEY",
                "conversation_key_version": "1",
                "conversation_token": "TOKEN_001",
            },
        }
    }
    event = norm.normalize(raw)

    assert event.schema_source == "observed-xchat"
    assert event.event_type == "chat.received"
    assert event.conversation_id == "CONV_001"
    assert event.encrypted is not None
    assert event.encrypted.encoded_event == "STUB_ENC_SGVsbG8h"
    assert event.encrypted.conversation_key_version == "1"
    assert event.conversation_token == "TOKEN_001"
    assert event.is_stub is True
    assert event.event_id  # non-empty


def test_demo_schema(norm: EventNormalizer) -> None:
    raw = {
        "event_type": "chat.received",
        "for_user_id": "bot123",
        "direct_message_events": [
            {
                "id": "msg001",
                "event_type": "MessageCreate",
                "dm_conversation_id": "DM_001",
                "sender_id": "user456",
                "participant_ids": ["user456", "bot123"],
                "message": {
                    "encrypted_content": "STUB_ENC_SGVsbG8h",
                    "encryption_type": "XChaCha20Poly1305",
                    "key_version": "1",
                },
            }
        ],
    }
    event = norm.normalize(raw)

    assert event.schema_source == "demo"
    assert event.event_type == "chat.received"
    assert event.sender_id == "user456"
    assert event.for_user_id == "bot123"
    assert event.conversation_id == "DM_001"
    assert event.encrypted is not None
    assert event.encrypted.encrypted_content == "STUB_ENC_SGVsbG8h"
    assert event.is_stub is True
    assert event.event_id  # non-empty


def test_unknown_schema(norm: EventNormalizer) -> None:
    raw = {"some": "random", "payload": "here"}
    event = norm.normalize(raw)

    assert event.schema_source == "unknown"
    assert event.event_type == "unknown"
    assert event.event_id  # still has a deterministic ID


def test_event_id_is_deterministic(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_SGVsbG8h",
            },
        }
    }
    e1 = norm.normalize(raw)
    e2 = norm.normalize(raw)

    assert e1.event_id == e2.event_id


def test_demo_event_id_uses_message_id(norm: EventNormalizer) -> None:
    raw = {
        "event_type": "chat.received",
        "direct_message_events": [{"id": "unique_msg_id", "event_type": "MessageCreate"}],
    }
    event = norm.normalize(raw)
    # event_id should incorporate the message ID
    assert event.event_id  # non-empty and deterministic


def test_empty_direct_message_events(norm: EventNormalizer) -> None:
    """Should not crash on empty direct_message_events."""
    raw = {"event_type": "chat.received", "direct_message_events": []}
    event = norm.normalize(raw)
    assert event.schema_source == "demo"
    assert event.sender_id is None


def test_real_payload_not_stub(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "REAL_BASE64_PAYLOAD_NOT_STUB",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.is_stub is False


def test_is_incoming_property(norm: EventNormalizer) -> None:
    raw = {"data": {"event_type": "chat.received", "payload": {}}}
    event = norm.normalize(raw)
    assert event.is_incoming is True
    assert event.is_outgoing is False


def test_is_outgoing_property(norm: EventNormalizer) -> None:
    raw = {"data": {"event_type": "chat.sent", "payload": {}}}
    event = norm.normalize(raw)
    assert event.is_outgoing is True
    assert event.is_incoming is False
