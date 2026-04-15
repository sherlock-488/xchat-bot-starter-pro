"""
Application settings — loaded from environment variables and .env file.

All settings use the XCHAT_ prefix.
Run `xchat doctor` to validate your configuration.

Authentication model
--------------------
X Activity API uses two separate credentials:

1. App Bearer Token (``XCHAT_BEARER_TOKEN``)
   - Used by the Activity Stream transport to connect and receive events.
   - App-only credential; does not act on behalf of a user.
   - Generate in X Developer Portal → Keys and tokens → Bearer Token.

2. OAuth 2.0 User Access Token (``XCHAT_USER_ACCESS_TOKEN``)
   - Used by the Reply adapter to send DMs on behalf of the bot account.
   - Obtained via ``xchat auth login`` (OAuth 2.0 PKCE flow).
   - Stored in tokens.json after login.

Legacy OAuth 1.0a fields (``access_token`` / ``access_token_secret``) are
kept for backward compatibility with older X API endpoints but are NOT used
for the Activity Stream or reply flows.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="XCHAT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App credentials (required) ────────────────────────────────────────
    consumer_key: str = Field(..., description="X app consumer key (API key)")
    consumer_secret: SecretStr = Field(..., description="X app consumer secret")

    # ── App Bearer Token — used by Activity Stream transport ──────────────
    bearer_token: SecretStr | None = Field(
        None,
        description=(
            "X app Bearer Token. Used by the Activity Stream transport to connect "
            "and receive events. Generate in X Developer Portal → Keys and tokens."
        ),
    )

    # ── OAuth 2.0 User Access Token — used by Reply adapter ──────────────
    user_access_token: SecretStr | None = Field(
        None,
        description=(
            "OAuth 2.0 user access token for the bot account. Used to send DM replies. "
            "Obtained via `xchat auth login` and stored in tokens.json."
        ),
    )
    user_refresh_token: SecretStr | None = Field(
        None,
        description="OAuth 2.0 refresh token for renewing user_access_token.",
    )

    # ── Legacy OAuth 1.0a tokens (kept for compatibility) ─────────────────
    # These are NOT used for Activity Stream or DM replies in the XAA flow.
    # Kept for any OAuth 1.0a-only endpoints you may need.
    access_token: str | None = Field(
        None,
        description=(
            "Legacy OAuth 1.0a access token. "
            "NOT used for Activity Stream or DM replies — use user_access_token instead."
        ),
    )
    access_token_secret: SecretStr | None = Field(
        None,
        description="Legacy OAuth 1.0a access token secret. See access_token note.",
    )

    # ── Transport ─────────────────────────────────────────────────────────
    transport_mode: Literal["stream", "webhook"] = Field(
        "stream",
        description=(
            "Transport mode: 'stream' opens a persistent HTTP connection to X "
            "(simpler, no public URL needed), 'webhook' lets X POST events to your server "
            "(requires public HTTPS URL)."
        ),
    )

    # ── Webhook-specific ──────────────────────────────────────────────────
    webhook_host: str = Field("0.0.0.0", description="Bind host for webhook server")
    webhook_port: int = Field(8080, ge=1, le=65535, description="Bind port for webhook server")
    webhook_path: str = Field("/webhook", description="Path for webhook endpoint")
    webhook_public_url: str | None = Field(
        None,
        description="Your public HTTPS URL for webhook CRC registration (e.g. https://bot.example.com)",
    )

    # ── OAuth redirect ────────────────────────────────────────────────────
    oauth_redirect_uri: str = Field(
        "http://127.0.0.1:7171/callback",
        description=(
            "OAuth callback URL. MUST use 127.0.0.1, not 'localhost'. "
            "X treats them as different origins. "
            "Must match your X Developer Portal setting exactly."
        ),
    )
    oauth_scopes: list[str] = Field(
        default_factory=list,
        description="OAuth 2.0 scopes to request. Consult X developer docs for valid values.",
    )

    # ── State / secrets files ─────────────────────────────────────────────
    state_file: Path = Field(
        Path("state.json"),
        description="Path to state.json (contains E2EE private keys — never commit to git)",
    )
    data_dir: Path = Field(
        Path("~/.config/xchat-bot"),
        description="Directory for tokens.json and other auth artifacts",
    )

    # ── Crypto ────────────────────────────────────────────────────────────
    crypto_mode: Literal["stub", "real"] = Field(
        "stub",
        description=(
            "'stub' uses STUB_ENC_ prefix payloads for dev/test without real keys. "
            "'real' loads state.json and attempts XChaCha20-Poly1305 decryption. "
            "NOTE: 'real' is EXPERIMENTAL — chat-xdk is not yet officially released."
        ),
    )

    # ── HTTP / retry ──────────────────────────────────────────────────────
    http_timeout: float = Field(30.0, ge=1.0, description="HTTP request timeout (seconds)")
    stream_connect_timeout: float = Field(
        60.0, ge=1.0, description="Stream connection timeout (seconds)"
    )
    max_retries: int = Field(5, ge=0, le=20, description="Max retry attempts for transient errors")
    retry_backoff_base: float = Field(1.0, ge=0.1, description="Base backoff multiplier (seconds)")
    retry_backoff_max: float = Field(
        60.0, ge=1.0, description="Maximum backoff cap (seconds)"
    )

    # ── Event dedup ───────────────────────────────────────────────────────
    dedup_max_size: int = Field(
        10_000, ge=100, description="Max event IDs to track for deduplication"
    )

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = Field("INFO", description="Log level: DEBUG, INFO, WARNING, ERROR")
    log_format: Literal["json", "console"] = Field(
        "console", description="'console' for human-readable, 'json' for structured production logs"
    )

    # ── Bot user identity ─────────────────────────────────────────────────
    bot_user_id: str | None = Field(
        None,
        description="Bot's X user ID. Auto-read from state.json if not set.",
    )

    # ── Validators ────────────────────────────────────────────────────────

    @field_validator("oauth_redirect_uri")
    @classmethod
    def no_localhost_in_redirect(cls, v: str) -> str:
        if "localhost" in v.lower():
            raise ValueError(
                "OAuth redirect URI must use '127.0.0.1', not 'localhost'. "
                "X Developer Portal treats them as different origins and will reject "
                "the callback if they don't match exactly. "
                "Change XCHAT_OAUTH_REDIRECT_URI to use 127.0.0.1."
            )
        return v

    @field_validator("log_level")
    @classmethod
    def valid_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}, got {v!r}")
        return v.upper()

    @model_validator(mode="after")
    def expand_data_dir(self) -> AppSettings:
        self.data_dir = self.data_dir.expanduser()
        return self


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return validated settings singleton.

    Raises pydantic.ValidationError if required settings are missing or invalid.
    Call this once at startup; the result is cached.
    """
    return AppSettings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear the settings cache (useful in tests)."""
    get_settings.cache_clear()
