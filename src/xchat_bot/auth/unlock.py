"""
Key unlock flow — retrieves E2EE private keys from X API.

EXPERIMENTAL STATUS
-------------------
The unlock API endpoint and payload format are observed from xchat-bot-python
but are NOT yet fully documented in official X developer docs.
chat-xdk has not been officially released as a stable library.

Current behavior:
  - Creates a minimal state.json placeholder (private_keys will be empty).
  - Does NOT make a real API call — the endpoint is not yet confirmed.
  - For a real state.json: run xchat-bot-python's unlock flow and copy the
    resulting state.json into your project directory.

When the official unlock API is documented:
  1. Replace the placeholder body with the real API call.
  2. Parse the response to extract private_keys.
  3. Remove the EXPERIMENTAL warning from this docstring.

Run with: xchat unlock
"""

from __future__ import annotations

from pathlib import Path

import structlog

from xchat_bot.state.manager import StateManager

logger = structlog.get_logger(__name__)

# EXPERIMENTAL: Endpoint observed from xchat-bot-python. Not yet officially documented.
_UNLOCK_ENDPOINT = "https://api.x.com/2/dm_conversations/with/:participant_id/dm_events"


async def run_unlock_flow(
    user_access_token: str,
    state_file: Path = Path("state.json"),
    *,
    force: bool = False,
) -> StateManager:
    """Write a placeholder state.json for E2EE key material.

    EXPERIMENTAL: Real key retrieval is a placeholder pending official
    documentation of the unlock API and stable release of chat-xdk.

    Args:
        user_access_token: OAuth 2.0 user access token (from `xchat auth login`).
                           Reserved for the real implementation — not used yet.
        state_file: Where to write state.json.
        force: If True, overwrite existing state.json.

    Returns:
        StateManager pointing to the written file.

    Raises:
        FileExistsError: If state_file exists and force=False.
    """
    log = logger.bind(state_file=str(state_file))

    if state_file.exists() and not force:
        raise FileExistsError(
            f"state.json already exists at {state_file}. "
            "Use --force to overwrite, or delete it manually."
        )

    log.info("unlock_starting")
    log.warning(
        "unlock_experimental",
        message=(
            "EXPERIMENTAL: The unlock API is not yet officially documented and "
            "chat-xdk has not been officially released. "
            "This creates an empty state.json placeholder. "
            "For real E2EE keys: run xchat-bot-python's unlock flow and copy "
            "the resulting state.json here."
        ),
    )

    # Placeholder: create minimal state.json
    # Real implementation will call _UNLOCK_ENDPOINT with user_access_token
    # and parse the response to populate private_keys.
    manager = StateManager(state_file)
    manager.save()

    log.info("unlock_complete", state_file=str(state_file))
    return manager
