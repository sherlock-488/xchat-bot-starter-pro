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

## conversation_token Field

**Field:** `NormalizedEvent.conversation_token`

`conversation_token` has different documentation status depending on context:

- **Chat conversation REST responses** (`GET /2/chat/conversations/{id}`): the field
  is documented in the official Chat API response schema.
- **XAA `chat.received` delivery payloads** (`data.payload.conversation_token`):
  its appearance and usage inside the XAA envelope is observed / sample-driven
  (inferred from xchat-bot-python). Treat this as unstable until officially documented.
- **`xchat-observed` reply extras** (passing `conversation_token` in the DM v2 body):
  EXPERIMENTAL. Not in official DM Manage docs. Only used when `reply_mode="xchat-observed"`.

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

## Chat API Routes (Documented)

**Status:** Documented in the official XChat migration guide.

The following routes are now documented:

- `GET /2/users/{id}/public_keys` — retrieve public key material for a user
- `GET /2/chat/conversations` — list conversations for the authenticated user
- `GET /2/chat/conversations/{conversation_id}` — get a single conversation
- `POST /2/chat/conversations/{conversation_id}/messages` — send an encrypted message

All Chat API messages are **end-to-end encrypted**. Apps receive encrypted payloads
and must decrypt/encrypt using chat-xdk. This starter provides `ChatApiClient` as a
skeleton that calls these documented routes but does NOT perform encryption.

**`chat-api` reply mode** expects already-encrypted payload fields. Passing plaintext
to `send_reply()` in `chat-api` mode returns a clear error directing you to use
`send_encrypted_reply()` with an `EncryptedReplyPayload` instead.

---

## chat-xdk (Pending Stable Release)

**Status:** chat-xdk is pending stable public release and security review.

Real decrypt/encrypt of XChat messages requires chat-xdk. Until it is officially
released as a stable public dependency:

- `event.plaintext` will be `None` for real encrypted payloads
- `send_encrypted_reply()` accepts the already-encrypted payload shape but you
  must produce those fields with chat-xdk yourself
- `xchat unlock` creates a placeholder `state.json` only

**Where to track:** https://github.com/xdevplatform/xchat-bot-python

---

## Chat Media Upload (Coming Soon)

**Status:** Coming soon / not yet in production.

Media upload routes for XChat are not yet available. Do not attempt to send
media attachments via the Chat API until this is documented and released.

---

## DM v2 Manage vs Encrypted Chat API

DM v2 Manage endpoints (`POST /2/dm_conversations/…/messages` with `{"text": "..."}`)
are documented for plain DM sending, but they are separate from the encrypted Chat API.
DM v2 send remains the documented default (`reply_mode="dm-v2"`).

Encrypted XChat messages use a distinct endpoint:
`POST /2/chat/conversations/{conversation_id}/messages`

These are two distinct paths. Do not conflate them.

---

## What IS stable

The following are based on official X documentation or well-established patterns:

- **CRC challenge** (`GET /webhook?crc_token=xxx`) — documented
- **Webhook signature** (`x-twitter-webhooks-signature: sha256=...`) — documented
- **OAuth 2.0 PKCE flow** (`xchat auth login`) — documented
- **127.0.0.1 vs localhost distinction** — documented behavior
- **DM v2 send** (`POST /2/dm_conversations/{id}/messages`, body `{"text": "..."}`) — documented
- **Chat API routes** (GET public_keys, GET/list conversations, POST messages) — documented
- **`STUB_ENC_` crypto format** — internal convention, not X API
