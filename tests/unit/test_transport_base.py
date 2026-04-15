"""Unit tests for xchat_bot.transport.base."""

from __future__ import annotations

import pytest

from xchat_bot.events.models import NormalizedEvent
from xchat_bot.transport.base import (
    AuthError,
    EventHandler,
    StreamDisconnected,
    Transport,
    TransportError,
)

# ── Exception hierarchy ────────────────────────────────────────────────────────

def test_transport_error_is_exception():
    assert issubclass(TransportError, Exception)


def test_auth_error_is_exception():
    assert issubclass(AuthError, Exception)


def test_stream_disconnected_is_exception():
    assert issubclass(StreamDisconnected, Exception)


def test_auth_error_is_transport_error():
    assert issubclass(AuthError, TransportError)


def test_stream_disconnected_is_transport_error():
    assert issubclass(StreamDisconnected, TransportError)


def test_transport_error_can_be_raised():
    with pytest.raises(TransportError):
        raise TransportError("test error")


def test_auth_error_can_be_raised():
    with pytest.raises(AuthError):
        raise AuthError("bad credentials")


def test_stream_disconnected_can_be_raised():
    with pytest.raises(StreamDisconnected):
        raise StreamDisconnected("lost connection")


# ── Transport ABC cannot be instantiated directly ──────────────────────────────

def test_transport_abc_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Transport()  # type: ignore[abstract]


# ── Concrete subclass ──────────────────────────────────────────────────────────

class ConcreteTransport(Transport):
    """Minimal concrete implementation of Transport for testing."""

    async def run(self, handler: EventHandler) -> None:
        pass

    async def stop(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "test_transport"


def test_concrete_transport_can_be_instantiated():
    t = ConcreteTransport()
    assert t is not None


def test_concrete_transport_name():
    t = ConcreteTransport()
    assert t.name == "test_transport"


async def test_concrete_transport_stop_does_not_raise():
    t = ConcreteTransport()
    await t.stop()


async def test_concrete_transport_run_does_not_raise():
    async def dummy_handler(event: NormalizedEvent) -> None:  # noqa: ARG001
        pass

    t = ConcreteTransport()
    await t.run(dummy_handler)


# ── Subclass missing abstract method cannot be instantiated ───────────────────

def test_incomplete_subclass_cannot_be_instantiated():
    class IncompleteTransport(Transport):
        async def run(self, handler: EventHandler) -> None:
            pass

        # Missing stop() and name

    with pytest.raises(TypeError):
        IncompleteTransport()  # type: ignore[abstract]
