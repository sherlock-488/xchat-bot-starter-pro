"""
Application settings — loaded from environment variables and .env file.

All settings use the XCHAT_ prefix.
Run `xchat doctor` to validate your configuration.

Authentication model
--------------------
X Activity API uses three separate credential sets:

1. App credentials (``XCHAT_CONSUMER_KEY`` / ``XCHAT_CONSUMER_SECRET``)
   - Used for webhook HMAC-SHA256 signature verification only.

2. App Bearer Token (``XCHAT_BEARER_TOKEN``)
   - Used by the Activity Stream transport to connect and receive events.
   - App-only credential; does not act on behalf of a user.
   - Generate in X Developer Portal → Keys and tokens → Bearer Token.

3. OAuth 2.0 Client credentials (``XCHAT_OAUTH_CLIENT_ID`` / ``XCHAT_OAUTH_CLIENT_SECRET``)
   - Used by ``xchat auth login`` (PKCE flow) to obtain a user access token.
   - In X Developer Portal, these appear as "OAuth 2.0 Client ID and Secret"
     under your app's "Keys and tokens" tab — they are DIFFERENT from the
     API Key & Secret (consumer key/secret).
   - ``XCHAT_OAUTH_CLIENT_ID`` is REQUIRED for ``xchat auth login``.

4. OAuth 2.0 User Access Token (``XCHAT_USER_ACCESS_TOKEN``)
   - Used by the Reply adapter to send DMs on behalf of the bot account.
   - Obtained via ``xchat auth login`` and stored in tokens.json.
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

    # ── App credentials (required for webhook mode; optional for stream-only) ──
    # Used for webhook HMAC-SHA256 signature verification.
    # Not needed if you only use stream transport (XCHAT_TRANSPORT_MODE=stream).
    consumer_key: str | None = Field(
        None, description="X app consumer key (API key). Required for webhook mode HMAC signing."
    )
    consumer_secret: SecretStr | None = Field(
        None, description="X app consumer secret. Required for webhook mode HMAC signing."
    )

    # ── OAuth 2.0 Client credentials — used by auth login (PKCE flow) ──────
    # These appear as "OAuth 2.0 Client ID and Secret" in X Developer Portal.
    # They are DIFFERENT from the API Key & Secret (consumer_key/consumer_secret).
    # XCHAT_OAUTH_CLIENT_ID is REQUIRED for `xchat auth login`.
    oauth_client_id: str | None = Field(
        None,
        description=(
            "OAuth 2.0 Client ID from X Developer Portal → your app → Keys and tokens. "
            "DIFFERENT from the API Key (consumer_key). "
            "Required for `xchat auth login` PKCE flow."
        ),
    )
    oauth_client_secret: SecretStr | None = Field(
        None,
        description=(
            "OAuth 2.0 Client Secret from X Developer Portal. "
            "DIFFERENT from the API Secret (consumer_secret). "
            "Optional for public clients using PKCE."
        ),
    )

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

    # ── NOT part of the main flow — ignore unless you need OAuth 1.0a endpoints ──
    # The XAA / Activity API flow uses Bearer Token + OAuth 2.0 user token only.
    # These legacy fields are kept so existing .env files with OAuth 1.0a tokens
    # don't cause validation errors, but xchat itself does not read them.
    access_token: str | None = Field(None, exclude=True)
    access_token_secret: SecretStr | None = Field(None, exclude=True)

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
    retry_backoff_max: float = Field(60.0, ge=1.0, description="Maximum backoff cap (seconds)")

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

    @model_validator(mode="after")
    def webhook_requires_consumer_credentials(self) -> AppSettings:
        """consumer_key + consumer_secret are required in webhook mode for HMAC signing."""
        if self.transport_mode == "webhook":
            missing: list[str] = []
            if not self.consumer_key:
                missing.append("XCHAT_CONSUMER_KEY")
            if not self.consumer_secret:
                missing.append("XCHAT_CONSUMER_SECRET")
            if missing:
                raise ValueError(
                    f"{', '.join(missing)} must be set when XCHAT_TRANSPORT_MODE=webhook. "
                    "These are used for webhook HMAC-SHA256 signature verification. "
                    "For stream mode, they are not required."
                )
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
