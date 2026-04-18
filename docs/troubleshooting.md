# Troubleshooting Guide

## localhost vs 127.0.0.1 callback mismatch

**Symptom:** OAuth callback fails with "callback URL mismatch" or "invalid_request".

**Cause:** X Developer Portal treats `http://localhost:7171/callback` and `http://127.0.0.1:7171/callback` as **different URLs**, even though they resolve to the same address.

**Fix:**
1. In your `.env`, set: `XCHAT_OAUTH_REDIRECT_URI=http://127.0.0.1:7171/callback`
2. In X Developer Portal → App Settings → User authentication settings, set the callback URL to exactly: `http://127.0.0.1:7171/callback`
3. They must match character-for-character.

`xchat doctor` will catch this automatically.

---

## Missing or stale state.json

**Symptom:** `xchat run --crypto real` fails with "state.json not found" or decryption returns no plaintext.

**Cause:** `state.json` hasn't been generated, or was generated with an old key version.

**Fix:**
```bash
xchat unlock               # generates state.json
xchat run --crypto real    # now works
```

If state.json exists but is stale:
```bash
xchat unlock --force       # overwrites with fresh keys
```

**Note:** state.json contains private keys. Never commit it to git. `xchat doctor` checks this.

---

## Webhook vs stream confusion

**When to use stream:**
- Simpler setup — no public URL needed
- Good for development and single-instance bots
- X pushes events over a persistent HTTP connection you open

**When to use webhook:**
- Multiple replicas (load-balanced)
- You want X to retry failed deliveries
- Requires a public HTTPS URL (not localhost)
- Requires CRC challenge setup

**Common mistake:** Setting `XCHAT_TRANSPORT_MODE=webhook` but running locally without a public URL.

**Fix:** Use `ngrok` or Cloudflare Tunnel for local webhook testing:
```bash
ngrok http 8080
# Copy the https:// URL → set as XCHAT_WEBHOOK_PUBLIC_URL
xchat webhook register --url https://your-ngrok-url.ngrok.io
xchat subscriptions create --user-id <your_bot_user_id> --event-type chat.received
```

---

## Secret and token setup mistakes

**Symptom:** `xchat doctor` fails on credential checks, or API calls return 401.

**Checklist:**
- [ ] `XCHAT_CONSUMER_KEY` set (from X Developer Portal → Keys and tokens → API Key)
- [ ] `XCHAT_CONSUMER_SECRET` set
- [ ] `XCHAT_OAUTH_CLIENT_ID` set (from X Developer Portal → Keys and tokens → OAuth 2.0 Client ID — **different from API Key**)
- [ ] `XCHAT_BEARER_TOKEN` set (for stream mode — from X Developer Portal → Keys and tokens → Bearer Token)
- [ ] `xchat auth login` completed (produces `XCHAT_USER_ACCESS_TOKEN`)
- [ ] `.env` file exists (not just `.env.example`)

**Never commit:**
- `.env`
- `state.json`
- `tokens.json`

Run `xchat init` to ensure `.gitignore` has all required entries.

---

## Duplicate events

**Symptom:** Your bot processes the same message twice, or replies multiple times.

**Cause:** X may deliver the same event multiple times (especially for webhook retries). The `EventDeduplicator` handles this, but only within a single process.

**Fix:**
- Default dedup is in-memory LRU (10,000 events). This is sufficient for most single-instance bots.
- For multi-replica deployments, implement a Redis-backed deduplicator that shares state across instances.
- Check `dedup_max_size` setting if you're processing very high volumes.

---

## Replay and debug workflow

**Capture events from a running bot:**
```bash
xchat replay export --server http://localhost:8080 --output recordings/session.jsonl
```

**Replay captured events:**
```bash
xchat replay run recordings/session.jsonl --target http://localhost:8080/webhook --sign
```

**Inspect a fixture file:**
```bash
xchat inspect tests/fixtures/chat_received_observed_xchat.json --decrypt
```

**Compare two bot versions:**
```bash
# Run old version on port 8080, new version on 8081
xchat replay diff tests/fixtures/batch_events.jsonl \
    --baseline http://localhost:8080/webhook \
    --candidate http://localhost:8081/webhook
```

---

## E2EE decryption not working

**Symptom:** `event.plaintext` is None even with `--crypto real`.

**Cause:** `chat-xdk` is not yet officially released as a stable library. The real decryption is a placeholder.

**Current status:**
- `--crypto stub` works for all `STUB_ENC_` payloads (test fixtures)
- `--crypto real` loads your private keys from `state.json` but cannot yet perform the actual XChaCha20-Poly1305 decryption
- `event.decrypt_notes` will explain the current status

**Workaround:** Use `xchat-bot-python` directly for real decryption while waiting for `chat-xdk` to stabilize.

---

## CRC challenge failing

**Symptom:** X can't verify your webhook URL (CRC challenge fails).

**Checklist:**
1. Your webhook server is publicly accessible (not localhost)
2. `XCHAT_CONSUMER_SECRET` matches what's in X Developer Portal
3. Your server responds to `GET /webhook?crc_token=xxx` with `{"response_token": "sha256=..."}`
4. Response is returned within 3 seconds

**Test your CRC locally:**
```bash
xchat inspect tests/fixtures/chat_received_observed_xchat.json
# The inspect command shows what CRC would produce
```

**Debug a specific CRC token:**
```python
from xchat_bot.webhook.crc import compute_crc_response
print(compute_crc_response("your_crc_token", "your_consumer_secret"))
```
