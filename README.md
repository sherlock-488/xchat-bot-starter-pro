# xchat-bot-starter-pro

A production-grade starter kit for building XChat bots on the X Activity API.

[![CI](https://github.com/sherlock-488/xchat-bot-starter-pro/actions/workflows/ci.yml/badge.svg)](https://github.com/sherlock-488/xchat-bot-starter-pro/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Status and Caveats

**This is not an official X / Twitter SDK.**

This starter kit follows current official examples and documentation. Some XChat details are still observed rather than fully documented:

| Feature | Status |
|---------|--------|
| CRC challenge + webhook signature | ✅ Documented, stable |
| OAuth 2.0 user token (reply) | ✅ Documented, stable |
| App Bearer Token (stream) | ✅ Documented, stable |
| Activity Stream transport | ✅ GET /2/activity/stream (official docs) |
| Reply API | ⚠️ Endpoint/format observed, not yet fully documented |
| E2EE decryption | ⚠️ EXPERIMENTAL — chat-xdk not yet officially released |
| `conversation_token` field | ⚠️ EXPERIMENTAL — observed, not yet documented |

Fields and behaviors marked **EXPERIMENTAL** may change when official documentation is published. See [docs/known-caveats.md](docs/known-caveats.md) for the full list.

---

## What This Is

A starting point for teams building serious XChat bots. It gives you:

- **Clean architecture**: config → auth → transport → events → crypto → bot → reply
- **Dual transport**: Activity Stream (persistent connection) and Webhook (X POSTs to you), both feeding the same bot logic
- **Strong CLI**: `xchat doctor`, `xchat auth login`, `xchat run`, `xchat inspect`, `xchat replay`
- **Production hygiene**: structured logging, retry/backoff, deduplication, health endpoints, Docker, CI
- **5 example bots**: echo, router, draft-reply, moderation, handoff

## What This Is Not

- Not an official X SDK
- Not a complete E2EE implementation (chat-xdk placeholder)
- Not a guarantee of API stability for EXPERIMENTAL fields
- Not a replacement for reading the [X developer docs](https://docs.x.com)

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/sherlock-488/xchat-bot-starter-pro
cd xchat-bot-starter-pro
pip install uv
uv sync

# 2. Configure
cp .env.example .env
# Edit .env: set XCHAT_CONSUMER_KEY and XCHAT_CONSUMER_SECRET

# 3. Validate setup
xchat doctor

# 4. Authenticate
xchat auth login

# 5. Run your first bot
xchat run
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      xchat run                               │
│                         │                                    │
│          ┌──────────────┴──────────────┐                    │
│          │                             │                     │
│  ActivityStreamTransport    WebhookTransport                 │
│  (persistent HTTP GET)      (FastAPI POST)                   │
│          │                             │                     │
│          └──────────────┬──────────────┘                    │
│                         │                                    │
│              EventNormalizer.normalize()                     │
│              (official-xaa or demo schema)                   │
│                         │                                    │
│              EventDeduplicator.check_and_mark()              │
│                         │                                    │
│              CryptoAdapter.decrypt()                         │
│              (stub or real — EXPERIMENTAL)                   │
│                         │                                    │
│              BotBase.handle(NormalizedEvent)                 │
│                         │                                    │
│              ReplyAdapter.send_reply()                       │
│              (XApiReplyAdapter — EXPERIMENTAL)               │
└─────────────────────────────────────────────────────────────┘
```

Both transports produce the same `NormalizedEvent`. Your bot never knows which transport delivered the event.

---

## Transport Guide

| | Activity Stream | Webhook |
|---|---|---|
| **How it works** | You connect to X; X pushes events | X POSTs events to your server |
| **Public URL needed** | No | Yes (HTTPS) |
| **Setup complexity** | Low | Medium (CRC, subscription) |
| **Multi-replica** | Harder (each replica gets all events) | Easy (load balance naturally) |
| **X retry on failure** | No | Yes |
| **Best for** | Development, single-instance bots | Production, multi-replica |

Switch with: `XCHAT_TRANSPORT_MODE=stream` or `XCHAT_TRANSPORT_MODE=webhook`

---

## Writing Your First Bot

```python
# bots/my_bot.py
from xchat_bot.bot.base import BotBase
from xchat_bot.events.models import NormalizedEvent

class MyBot(BotBase):
    async def handle(self, event: NormalizedEvent) -> None:
        if not event.is_incoming or not event.plaintext:
            return
        await self.reply_to(event, f"You said: {event.plaintext}")
```

```bash
xchat run --bot bots.my_bot:MyBot
```

That's it. `BotBase` provides `reply_to()`, `on_start()`, `on_stop()`, and `on_error()`.

---

## CLI Reference

```
xchat init                          Initialize project directory
xchat doctor [--check-connectivity] Validate environment (12+ checks)
xchat auth login [--scopes TEXT]    OAuth 2.0 login (obtains user access token)
xchat auth status                   Show auth status
xchat unlock [--state-file PATH]    Get E2EE keys → state.json
xchat subscribe --url URL           Register webhook with X
xchat run [OPTIONS]                 Start bot
  --bot MODULE:CLASS                Bot to run (default: xchat_bot.examples.echo_bot:EchoBot)
  --transport stream|webhook        Override transport mode
  --crypto stub|real                Override crypto mode
xchat inspect FIXTURE [--decrypt]   Parse and display fixture file
xchat replay run FIXTURE            Replay events to webhook URL
xchat replay diff FIXTURE           Compare two webhook handlers
xchat replay export                 Export events from running server
xchat version                       Print version
```

---

## Configuration Reference

All settings use the `XCHAT_` prefix. Set in `.env` or environment.

| Variable | Default | Description |
|----------|---------|-------------|
| `XCHAT_CONSUMER_KEY` | required | X app consumer key (API key) |
| `XCHAT_CONSUMER_SECRET` | required | X app consumer secret |
| `XCHAT_BEARER_TOKEN` | — | App Bearer Token — used by Activity Stream |
| `XCHAT_USER_ACCESS_TOKEN` | — | OAuth 2.0 user token — used for DM replies (set after `xchat auth login`) |
| `XCHAT_USER_REFRESH_TOKEN` | — | OAuth 2.0 refresh token |
| `XCHAT_TRANSPORT_MODE` | `stream` | `stream` or `webhook` |
| `XCHAT_WEBHOOK_PORT` | `8080` | Webhook server port |
| `XCHAT_WEBHOOK_PUBLIC_URL` | — | Public HTTPS URL (webhook mode) |
| `XCHAT_OAUTH_REDIRECT_URI` | `http://127.0.0.1:7171/callback` | Must use 127.0.0.1, not localhost |
| `XCHAT_CRYPTO_MODE` | `stub` | `stub` (dev) or `real` (EXPERIMENTAL) |
| `XCHAT_STATE_FILE` | `state.json` | Path to E2EE key state file |
| `XCHAT_LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `XCHAT_LOG_FORMAT` | `console` | `console` or `json` |
| `XCHAT_MAX_RETRIES` | `5` | Max retry attempts |
| `XCHAT_HTTP_TIMEOUT` | `30.0` | HTTP timeout (seconds) |

---

## Security

**Files that must never be committed to git:**
- `.env` — contains API credentials
- `state.json` — contains E2EE private keys
- `tokens.json` — contains OAuth tokens

`xchat init` adds all of these to `.gitignore` automatically.
`xchat doctor` verifies they're excluded.

**Token storage:** `tokens.json` is written with `chmod 600` (owner read/write only).

**Webhook verification:** All webhook POST requests are verified with HMAC-SHA256 before processing.

**Docker:** The provided `Dockerfile` runs as a non-root user.

---

## Sample Bots

| Bot | Description |
|-----|-------------|
| `echo_bot.py` | Reflects every incoming message back. Good smoke test. |
| `router_bot.py` | Routes `/commands` to handlers. Foundation for command-driven bots. |
| `draft_reply_bot.py` | Queues messages for human review before replying. |
| `moderation_bot.py` | Filters messages against a blocklist. |
| `handoff_bot.py` | Escalates to human agents on trigger words. |

Each bot file explains what it does, when to use it, what credentials it needs, and what is EXPERIMENTAL.

---

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for:
- localhost vs 127.0.0.1 callback mismatch
- Missing or stale state.json
- Webhook vs stream confusion
- Secret and token setup mistakes
- Duplicate events
- Replay and debug workflow
- E2EE decryption not working
- CRC challenge failing

---

## Known Caveats

See [docs/known-caveats.md](docs/known-caveats.md) for the full list of EXPERIMENTAL features.

Short version:
- E2EE decryption is a placeholder (chat-xdk not yet stable)
- Reply API endpoint is observed, not yet fully documented
- `conversation_token` field is EXPERIMENTAL
- Activity Stream endpoint: GET /2/activity/stream (official docs)

---

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
pytest tests/ -x

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
pyright src/
```

---

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Run `pytest` and `ruff check`
5. Open a PR with the provided template

---

## License

MIT — see [LICENSE](LICENSE).

---

*Not affiliated with X Corp. / Twitter. This is a community starter kit following official examples and documentation.*
