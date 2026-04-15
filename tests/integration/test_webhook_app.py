"""Integration tests for the webhook FastAPI app."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from xchat_bot.events.models import NormalizedEvent
from xchat_bot.webhook.app import create_app
from xchat_bot.webhook.signature import generate_signature


CONSUMER_SECRET = "test_consumer_secret"


@pytest.fixture
def mock_handler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def app(mock_handler: AsyncMock) -> TestClient:
    fastapi_app = create_app(
        consumer_secret=CONSUMER_SECRET,
        handler=mock_handler,
    )
    return TestClient(fastapi_app, raise_server_exceptions=True)


# ── CRC challenge ─────────────────────────────────────────────────────────────

def test_crc_challenge(app: TestClient) -> None:
    resp = app.get("/webhook?crc_token=test_token_123")
    assert resp.status_code == 200
    data = resp.json()
    assert "response_token" in data
    assert data["response_token"].startswith("sha256=")


def test_crc_challenge_missing_token(app: TestClient) -> None:
    resp = app.get("/webhook")
    assert resp.status_code == 422  # FastAPI validation error


# ── Webhook POST ──────────────────────────────────────────────────────────────

def _make_signed_request(app: TestClient, payload: dict) -> tuple:
    body = json.dumps(payload).encode()
    sig = generate_signature(body, CONSUMER_SECRET)
    resp = app.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-twitter-webhooks-signature": sig,
        },
    )
    return resp, body


def test_webhook_official_schema(app: TestClient, mock_handler: AsyncMock) -> None:
    payload = {
        "data": {
            "event_type": "chat.received",
            "payload": {
                "conversation_id": "CONV_001",
                "encoded_event": "STUB_ENC_SGVsbG8h",
            },
        }
    }
    resp, _ = _make_signed_request(app, payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert "event_id" in data


def test_webhook_demo_schema(app: TestClient, mock_handler: AsyncMock) -> None:
    payload = {
        "event_type": "chat.received",
        "direct_message_events": [
            {"id": "msg001", "event_type": "MessageCreate", "dm_conversation_id": "DM_001"}
        ],
    }
    resp, _ = _make_signed_request(app, payload)
    assert resp.status_code == 202


def test_webhook_missing_signature_rejected(app: TestClient) -> None:
    payload = {"event_type": "chat.received"}
    resp = app.post(
        "/webhook",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_webhook_invalid_signature_rejected(app: TestClient) -> None:
    payload = {"event_type": "chat.received"}
    resp = app.post(
        "/webhook",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "x-twitter-webhooks-signature": "sha256=invalid_sig",
        },
    )
    assert resp.status_code == 403


def test_webhook_invalid_json_rejected(app: TestClient) -> None:
    body = b"not valid json"
    sig = generate_signature(body, CONSUMER_SECRET)
    resp = app.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "x-twitter-webhooks-signature": sig,
        },
    )
    assert resp.status_code == 400


# ── Health endpoints ──────────────────────────────────────────────────────────

def test_health_endpoint(app: TestClient) -> None:
    resp = app.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_healthz_endpoint(app: TestClient) -> None:
    resp = app.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_endpoint_with_handler(app: TestClient) -> None:
    resp = app.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_readyz_endpoint_without_handler() -> None:
    app_no_handler = create_app(consumer_secret=CONSUMER_SECRET, handler=None)
    client = TestClient(app_no_handler)
    resp = client.get("/readyz")
    assert resp.status_code == 503


# ── No consumer_secret mode (open webhook) ───────────────────────────────────

def test_webhook_no_secret_accepts_unsigned() -> None:
    app_open = create_app(consumer_secret="", handler=None)
    client = TestClient(app_open)
    resp = client.post(
        "/webhook",
        json={"event_type": "chat.received"},
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 202
