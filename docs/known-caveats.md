# Known Caveats and Experimental Features

This document lists all features and fields in xchat-bot-starter-pro that are
based on observed behavior rather than fully documented official APIs.

## E2EE Decryption (EXPERIMENTAL)

**Status:** Placeholder — will be implemented when chat-xdk is officially released.

**What works:**
- Loading `state.json` and validating private key structure
- Decrypting `STUB_ENC_` payloads (for testing)
- Returning clear error context when real decryption is not yet possible

**What doesn't work yet:**
- Actual XChaCha20-Poly1305 decryption of real production messages
- `event.plaintext` will be `None` for real encrypted payloads

**Where to track:** https://github.com/xdevplatform/xchat-bot-python

---

## DM Reply — Documented vs Experimental

**Status:** Split into two modes as of 2026-04-18.

### Documented: DM Manage v2 (default)

`XApiReplyAdapter` defaults to `reply_mode="dm-v2"`:
- Endpoint: `POST /2/dm_conversations/{conversation_id}/messages`
- Body: `{"text": "..."}` — documented in X DM Manage API
- This path is **stable and documented**.

### Experimental: XChat reply extras (`reply_mode="xchat-observed"`)

When `reply_mode="xchat-observed"`, the adapter also sends:
- `reply_to_dm_event_id` — observed from xchat-bot-python
- `conversation_token` — observed from xchat-bot-python

**Risk:** These fields are not yet in official DM Manage docs and may change.

**Mitigation:** Default mode is `dm-v2`. Switch to `xchat-observed` only when
you have confirmed the XChat reply path is available and you have a valid
`conversation_token` from the event payload.

---

## conversation_token Field (EXPERIMENTAL)

**Field:** `NormalizedEvent.conversation_token`

**Observation:** Observed in xchat-bot-python as `data.payload.conversation_token`.
May be required for XChat encrypted reply path.

**Risk:** Field may be renamed, removed, or have different semantics when officially documented.

**Mitigation:** Field is preserved in `NormalizedEvent` but only forwarded to the
reply API when `reply_mode="xchat-observed"` is explicitly set.

---

## Activity Stream Endpoint (partially observed)

**Field:** `ActivityStreamTransport._STREAM_ENDPOINT`

**Status:** The endpoint URL (`GET /2/activity/stream`) is documented. Reconnection
behavior, heartbeat handling, and some query parameters follow xchat-bot-python
observations and may not be fully specified in official docs.

**Risk:** Reconnect parameters or heartbeat format may change.

**Mitigation:** Configurable via constructor parameter `stream_url=` for easy override.

---

## Unlock API (EXPERIMENTAL)

**Command:** `xchat unlock`

**Observation:** The unlock flow is observed from xchat-bot-python.
The API endpoint for retrieving E2EE private keys is not yet officially documented.

**Current behavior:** `xchat unlock` is a placeholder that creates an empty `state.json`.
For real keys, use `xchat-bot-python`'s unlock flow and copy the resulting `state.json`.

---

## demo Schema Fields (EXPERIMENTAL)

The following `EncryptedPayload` fields come from the "demo" schema (flat format)
used in xchat-playground fixtures. They are not confirmed in official X developer docs:

- `encrypted_content` — alternative to `encoded_event`
- `encryption_type` — observed value: `"XChaCha20Poly1305"`
- `key_version` — per-message key version
- `recipient_keys` — per-recipient encrypted key blobs

These fields are labeled `description="EXPERIMENTAL"` in the Pydantic model.

---

## What IS stable

The following are based on official X documentation or well-established patterns:

- **CRC challenge** (`GET /webhook?crc_token=xxx`) — documented
- **Webhook signature** (`x-twitter-webhooks-signature: sha256=...`) — documented
- **OAuth 2.0 PKCE flow** (`xchat auth login`) — documented
- **127.0.0.1 vs localhost distinction** — documented behavior
- **`STUB_ENC_` crypto format** — internal convention, not X API
