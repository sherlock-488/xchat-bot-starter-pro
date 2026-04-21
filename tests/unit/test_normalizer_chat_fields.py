"""Unit tests for normalizer preservation of chat.* payload fields."""

from __future__ import annotations

import pytest

from xchat_bot.events.normalizer import EventNormalizer


@pytest.fixture
def norm() -> EventNormalizer:
    return EventNormalizer()


def test_observed_xchat_preserves_conversation_key_version(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_abc",
                "conversation_key_version": "v2",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.schema_source == "observed-xchat"
    assert event.encrypted is not None
    assert event.encrypted.conversation_key_version == "v2"


def test_observed_xchat_preserves_conversation_key_change_event(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_abc",
                "conversation_key_change_event": "KEY_CHANGE_BLOB_base64",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.encrypted is not None
    assert event.encrypted.conversation_key_change_event == "KEY_CHANGE_BLOB_base64"


def test_observed_xchat_preserves_conversation_token(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_abc",
                "conversation_token": "TOKEN_xyz",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.conversation_token == "TOKEN_xyz"


def test_observed_xchat_preserves_conversation_id(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_999",
                "encoded_event": "STUB_ENC_abc",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.conversation_id == "CONV_999"


def test_observed_xchat_preserves_sender_id(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_abc",
                "sender_id": "user_777",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.sender_id == "user_777"


def test_observed_xchat_preserves_encoded_event(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "REAL_ENC_BLOB_abc123",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.encrypted is not None
    assert event.encrypted.encoded_event == "REAL_ENC_BLOB_abc123"


def test_observed_xchat_preserves_encrypted_conversation_key(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_abc",
                "encrypted_conversation_key": "ENC_KEY_blob==",
            },
        }
    }
    event = norm.normalize(raw)
    assert event.encrypted is not None
    assert event.encrypted.encrypted_conversation_key == "ENC_KEY_blob=="


def test_observed_xchat_schema_source_is_observed_xchat(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {"conversation_id": "CONV_001", "encoded_event": "STUB_ENC_abc"},
        }
    }
    event = norm.normalize(raw)
    assert event.schema_source == "observed-xchat"


def test_observed_xchat_all_fields_none_when_absent(norm: EventNormalizer) -> None:
    raw = {
        "data": {
            "event_type": "chat.received",
            "payload": {},
        }
    }
    event = norm.normalize(raw)
    assert event.conversation_id is None
    assert event.sender_id is None
    assert event.conversation_token is None
    assert event.encrypted is not None
    assert event.encrypted.encoded_event is None
    assert event.encrypted.encrypted_conversation_key is None
    assert event.encrypted.conversation_key_version is None
    assert event.encrypted.conversation_key_change_event is None
