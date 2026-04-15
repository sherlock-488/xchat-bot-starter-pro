"""
FastAPI application for the webhook transport.

Endpoints:
  GET  /webhook?crc_token=xxx  — CRC challenge response
  POST /webhook                — Receive and process events
  GET  /health                 — Health check (verbose)
  GET  /healthz                — Liveness probe (minimal)
  GET  /readyz                 — Readiness probe

The webhook endpoint accepts events, verifies the signature, normalizes the payload,
and dispatches to the registered EventHandler asynchronously (non-blocking).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from xchat_bot.events.models import NormalizedEvent
from xchat_bot.events.normalizer import EventNormalizer
from xchat_bot.webhook.crc import compute_crc_response
from xchat_bot.webhook.signature import verify_signature

logger = structlog.get_logger(__name__)

EventHandler = Callable[[NormalizedEvent], Coroutine[Any, Any, None]]


def create_app(
    consumer_secret: str,
    handler: EventHandler | None = None,
    *,
    normalizer: EventNormalizer | None = None,
    title: str = "xchat-bot-starter-pro",
    version: str = "0.1.0",
) -> FastAPI:
    """Create the FastAPI webhook application.

    Args:
        consumer_secret: X app consumer secret for signature verification.
        handler: Async callable that receives NormalizedEvent objects.
                 If None, events are logged but not dispatched.
        normalizer: EventNormalizer instance. Uses default if not provided.
        title: App title for OpenAPI docs.
        version: App version for OpenAPI docs.

    Returns:
        Configured FastAPI application.

    Usage::

        app = create_app(
            consumer_secret=settings.consumer_secret.get_secret_value(),
            handler=my_bot.handle,
        )
        uvicorn.run(app, host="0.0.0.0", port=8080)
    """
    _normalizer = normalizer or EventNormalizer()
    _ready = {"value": handler is not None}

    app = FastAPI(title=title, version=version, docs_url="/docs")

    @app.get("/webhook")
    async def crc_challenge(
        crc_token: str = Query(..., description="CRC token from X"),
    ) -> JSONResponse:
        """Respond to X's CRC challenge to verify webhook ownership."""
        log = logger.bind(crc_token=crc_token[:8] + "...")
        response = compute_crc_response(crc_token, consumer_secret)
        log.info("crc_challenge_responded")
        return JSONResponse(content=response)

    @app.post("/webhook", status_code=200)
    async def receive_event(
        request: Request,
        x_twitter_webhooks_signature: str | None = Header(None),
        x_signature_256: str | None = Header(None),
    ) -> dict[str, str]:
        """Receive a webhook event from X.

        Verifies signature, normalizes payload, and dispatches to handler.
        Returns 200 per X webhook documentation — event is queued for processing.
        """
        body = await request.body()
        request_id = request.headers.get("x-request-id", "")
        log = logger.bind(request_id=request_id, content_length=len(body))

        # Determine which signature header was provided
        sig_header = x_twitter_webhooks_signature or x_signature_256

        # Verify signature if consumer_secret is set
        if consumer_secret:
            if not sig_header:
                log.warning("webhook_missing_signature")
                raise HTTPException(status_code=400, detail="Missing signature header")

            if not verify_signature(body, sig_header, consumer_secret):
                log.warning("webhook_invalid_signature", sig_preview=sig_header[:20])
                raise HTTPException(status_code=403, detail="Invalid signature")

            log.debug("webhook_signature_ok")

        # Parse and normalize
        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            log.warning("webhook_invalid_json", error=str(exc))
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        event = _normalizer.normalize(raw)
        log.info(
            "webhook_event_received",
            event_type=event.event_type,
            event_id=event.event_id,
            schema_source=event.schema_source,
        )

        # Dispatch to handler asynchronously (non-blocking)
        if handler is not None:
            asyncio.create_task(_dispatch(handler, event, log))

        return {"status": "ok", "event_id": event.event_id}

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Verbose health check."""
        return {
            "status": "ok",
            "ready": _ready["value"],
            "timestamp": datetime.now(UTC).isoformat(),
            "version": version,
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Minimal liveness probe — just returns 200."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        """Readiness probe — returns 200 when handler is registered."""
        if _ready["value"]:
            return JSONResponse({"status": "ready"}, status_code=200)
        return JSONResponse(
            {"status": "not_ready", "reason": "no handler registered"}, status_code=503
        )

    return app


async def _dispatch(
    handler: EventHandler,
    event: NormalizedEvent,
    log: structlog.BoundLogger,
) -> None:
    """Dispatch event to handler, catching and logging any exceptions."""
    try:
        await handler(event)
    except Exception as exc:
        log.error(
            "handler_error",
            event_type=event.event_type,
            event_id=event.event_id,
            error=str(exc),
            exc_info=True,
        )
