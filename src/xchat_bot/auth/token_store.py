"""
TokenStore — persists OAuth tokens to disk with restricted permissions.

Tokens are stored in data_dir/tokens.json (mode 600).
This file must never be committed to git.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class TokenStore:
    """Manages OAuth token persistence.

    Args:
        data_dir: Directory where tokens.json is stored.
                  Defaults to ~/.config/xchat-bot.

    Usage::

        store = TokenStore()
        store.save(access_token="...", access_token_secret="...")
        tokens = store.load()
    """

    def __init__(self, data_dir: Path = Path("~/.config/xchat-bot")) -> None:
        self._data_dir = data_dir.expanduser()
        self._tokens_file = self._data_dir / "tokens.json"

    def _ensure_dir(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        # Restrict directory to owner only
        os.chmod(self._data_dir, 0o700)

    def save(
        self,
        access_token: str,
        access_token_secret: str,
        user_id: str | None = None,
        screen_name: str | None = None,
    ) -> None:
        """Save tokens to disk.

        Args:
            access_token: OAuth 1.0a access token.
            access_token_secret: OAuth 1.0a access token secret.
            user_id: X user ID (optional, for reference).
            screen_name: X screen name (optional, for reference).
        """
        self._ensure_dir()
        data: dict[str, str | None] = {
            "access_token": access_token,
            "access_token_secret": access_token_secret,
            "user_id": user_id,
            "screen_name": screen_name,
        }
        self._tokens_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.chmod(self._tokens_file, 0o600)

    def load(self) -> dict[str, str | None] | None:
        """Load tokens from disk.

        Returns:
            Dict with access_token, access_token_secret, user_id, screen_name.
            Returns None if tokens file does not exist.
        """
        if not self._tokens_file.exists():
            return None
        try:
            return json.loads(self._tokens_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def clear(self) -> None:
        """Delete tokens file."""
        if self._tokens_file.exists():
            self._tokens_file.unlink()

    def exists(self) -> bool:
        """Return True if tokens file exists."""
        return self._tokens_file.exists()

    @property
    def tokens_file(self) -> Path:
        """Path to the tokens file."""
        return self._tokens_file
