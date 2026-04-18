# Real XAA Fixtures

Captured from live X Activity API on 2026-04-19.

## profile_update_bio_20260419.json
- event_type: profile.update.bio
- schema_source: docs-xaa
- sig_valid: true
- Captured via webhook replay after bio change on x.com

## chat_received_20260419_meta.json
- event_type: chat.received
- schema_source: observed-xchat
- event_id: 7620444452576785342
- Payload is real encrypted content (not included — contains private data)
- Bot correctly identified as real encrypted payload requiring crypto_mode=real
