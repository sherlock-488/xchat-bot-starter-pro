"""Unit tests for xchat_bot.logging.setup."""

from __future__ import annotations

from xchat_bot.logging.setup import bind_request_id, configure_logging

# ── configure_logging ──────────────────────────────────────────────────────────

def test_configure_logging_info_console_does_not_raise():
    configure_logging("INFO", "console")


def test_configure_logging_debug_json_does_not_raise():
    configure_logging("DEBUG", "json")


def test_configure_logging_warning_console_does_not_raise():
    configure_logging("WARNING", "console")


def test_configure_logging_error_json_does_not_raise():
    configure_logging("ERROR", "json")


def test_configure_logging_critical_console_does_not_raise():
    configure_logging("CRITICAL", "console")


# ── bind_request_id ────────────────────────────────────────────────────────────

def test_bind_request_id_does_not_raise():
    with bind_request_id():
        pass


def test_bind_request_id_yields_string():
    with bind_request_id() as rid:
        assert isinstance(rid, str)
        assert len(rid) > 0


def test_bind_request_id_with_explicit_id():
    with bind_request_id("my-request-id") as rid:
        assert rid == "my-request-id"


def test_bind_request_id_without_arg_generates_id():
    with bind_request_id() as rid:
        assert rid is not None
        assert isinstance(rid, str)


def test_bind_request_id_context_manager_cleans_up():
    # Should not raise even after exiting the context
    with bind_request_id("cleanup-test"):
        pass
    # A second context should work fine after cleanup
    with bind_request_id("second-call"):
        pass
