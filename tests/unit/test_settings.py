"""Unit tests for AppSettings validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from xchat_bot.config.settings import AppSettings


def test_valid_settings() -> None:
    settings = AppSettings(
        consumer_key="key123",
        consumer_secret="secret123",
    )
    assert settings.consumer_key == "key123"
    assert settings.transport_mode == "stream"
    assert settings.crypto_mode == "stub"


def test_consumer_key_optional_in_stream_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """consumer_key is optional when transport_mode=stream (stream doesn't need HMAC signing)."""
    monkeypatch.delenv("XCHAT_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("XCHAT_CONSUMER_SECRET", raising=False)
    settings = AppSettings(transport_mode="stream")  # type: ignore[call-arg]
    assert settings.consumer_key is None
    assert settings.consumer_secret is None


def test_consumer_key_required_in_webhook_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """consumer_key + consumer_secret are required when transport_mode=webhook."""
    monkeypatch.delenv("XCHAT_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("XCHAT_CONSUMER_SECRET", raising=False)
    with pytest.raises(ValidationError, match="XCHAT_CONSUMER_KEY"):
        AppSettings(transport_mode="webhook")  # type: ignore[call-arg]


def test_localhost_redirect_uri_rejected() -> None:
    with pytest.raises(ValidationError, match="127.0.0.1"):
        AppSettings(
            consumer_key="key",
            consumer_secret="secret",
            oauth_redirect_uri="http://localhost:7171/callback",
        )


def test_127_redirect_uri_accepted() -> None:
    settings = AppSettings(
        consumer_key="key",
        consumer_secret="secret",
        oauth_redirect_uri="http://127.0.0.1:7171/callback",
    )
    assert "127.0.0.1" in settings.oauth_redirect_uri


def test_secret_not_in_repr() -> None:
    settings = AppSettings(consumer_key="key", consumer_secret="my_super_secret")
    repr_str = repr(settings)
    assert "my_super_secret" not in repr_str


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        AppSettings(
            consumer_key="key",
            consumer_secret="secret",
            log_level="INVALID",
        )


def test_log_level_normalized_to_uppercase() -> None:
    settings = AppSettings(
        consumer_key="key",
        consumer_secret="secret",
        log_level="debug",
    )
    assert settings.log_level == "DEBUG"


def test_data_dir_expanded() -> None:
    settings = AppSettings(consumer_key="key", consumer_secret="secret")
    assert not str(settings.data_dir).startswith("~")
