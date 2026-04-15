"""
Key unlock flow — retrieves E2EE private keys from X API.

EXPERIMENTAL: The exact unlock API endpoint and payload format are observed
from xchat-bot-python but not yet fully documented in official X developer docs.
This implementation follows the xchat-bot-python pattern.

The unlock flow:
  1. Call X API to get the bot's current E2EE key material
  2. Write private keys to state.json (never commit to git)

Run with: xchat unlock
"""

from __future__ import annotations

from pathlib import Path

import structlog

from xchat_bot.state.manager import StateManager

logger = structlog.get_logger(__name__)

# OBSERVED: Endpoint from xchat-bot-python. May change when officially documented.
# Marked as EXPERIMENTAL.
_UNLOCK_ENDPOINT = "https://api.x.com/2/dm_conversations/with/:participant_id/dm_events"


async def run_unlock_flow(
    access_token: str,
    consumer_key: str,
    consumer_secret: str,
    access_token_secret: str,
    state_file: Path = Path("state.json"),
    *,
    force: bool = False,
) -> StateManager:
    """Retrieve E2EE private keys and write to state.json.

    EXPERIMENTAL: The exact API call is observed from xchat-bot-python.
    This will be updated when the official unlock API is documented.

    Args:
        access_token: OAuth 1.0a access token.
        consumer_key: X app consumer key.
        consumer_secret: X app consumer secret.
        access_token_secret: OAuth 1.0a access token secret.
        state_file: Where to write state.json.
        force: If True, overwrite existing state.json.

    Returns:
        Loaded StateManager with the new keys.

    Raises:
        FileExistsError: If state_file exists and force=False.
        RuntimeError: If the unlock API call fails.
    """
    log = logger.bind(state_file=str(state_file))

    if state_file.exists() and not force:
        raise FileExistsError(
            f"state.json already exists at {state_file}. "
            "Use --force to overwrite, or delete it manually."
        )

    log.info("unlock_starting")

    # PLACEHOLDER: Real unlock API call
    # The actual implementation depends on the officially documented unlock endpoint.
    # This follows the pattern observed in xchat-bot-python.
    log.warning(
        "unlock_experimental",
        message=(
            "EXPERIMENTAL: The unlock API endpoint is not yet fully documented. "
            "This is a placeholder implementation. "
            "Run xchat-bot-python's unlock flow to generate state.json, "
            "then use it with this starter kit."
        ),
    )

    # For now, create a minimal state.json structure
    # In production, this would be populated by the real unlock API response
    manager = StateManager(state_file)
    manager.save()

    log.info("unlock_complete", state_file=str(state_file))
    return manager
