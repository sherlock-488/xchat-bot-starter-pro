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

## Reply API Endpoint (EXPERIMENTAL)

**Field:** `XApiReplyAdapter._REPLY_ENDPOINT_TEMPLATE`

**Observation:** The DM reply endpoint pattern follows xchat-bot-python observations.
The exact path, required headers, and request body format are not yet fully documented.

**Risk:** This endpoint may change when officially documented.

**Mitigation:** All X API calls are wrapped in `XApiReplyAdapter`. If the endpoint changes,
update only `x_api.py` — bot logic is unaffected.

---

## conversation_token Field (EXPERIMENTAL)

**Field:** `NormalizedEvent.conversation_token`

**Observation:** Observed in xchat-bot-python as `data.payload.conversation_token`.
Appears to be required for sending replies in some contexts.

**Risk:** Field may be renamed, removed, or have different semantics when officially documented.

**Mitigation:** Field is labeled `description="EXPERIMENTAL"` in the Pydantic model.
Reply adapter accepts it as an optional parameter.

---

## Activity Stream Endpoint (EXPERIMENTAL)

**Field:** `ActivityStreamTransport._STREAM_ENDPOINT`

**Observation:** Stream endpoint URL follows xchat-bot-python pattern.
The exact URL and required parameters are not yet fully documented.

**Risk:** URL may change.

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
- **OAuth 1.0a flow** — documented
- **127.0.0.1 vs localhost distinction** — documented behavior
- **`STUB_ENC_` crypto format** — internal convention, not X API
