"""xchat doctor — validate your environment and configuration."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def _check(label: str, ok: bool, fix: str = "") -> dict[str, object]:
    return {"label": label, "ok": ok, "warn": False, "fix": fix}


def _check_warn(label: str, ok: bool, fix: str = "") -> dict[str, object]:
    """Like _check but failure is a warning (yellow), not an error (red)."""
    return {"label": label, "ok": ok, "warn": True, "fix": fix}


def _run_checks(check_connectivity: bool = False) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []

    # 1. Python version
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 11)
    results.append(
        _check(
            f"Python >= 3.11 (found {major}.{minor})",
            ok,
            "Install Python 3.11+ from https://python.org",
        )
    )

    # 2. uv installed
    uv_path = shutil.which("uv")
    results.append(
        _check(
            f"uv installed ({uv_path or 'not found'})",
            uv_path is not None,
            "Install uv: pip install uv  or  curl -LsSf https://astral.sh/uv/install.sh | sh",
        )
    )

    # 3. .env file exists
    env_file = Path(".env")
    results.append(
        _check(
            ".env file exists",
            env_file.exists(),
            "Run: cp .env.example .env  then fill in your credentials",
        )
    )

    # 4. XCHAT_CONSUMER_KEY set (required for webhook mode; optional for stream)
    consumer_key = os.getenv("XCHAT_CONSUMER_KEY", "")
    _transport_for_check = os.getenv("XCHAT_TRANSPORT_MODE", "stream")
    if _transport_for_check == "webhook":
        results.append(
            _check(
                "XCHAT_CONSUMER_KEY is set (required for webhook HMAC signing)",
                bool(consumer_key),
                "Set XCHAT_CONSUMER_KEY in .env — get it from developer.x.com",
            )
        )
    else:
        results.append(
            _check_warn(
                "XCHAT_CONSUMER_KEY is set (required for webhook mode only)",
                bool(consumer_key),
                "Set XCHAT_CONSUMER_KEY if you plan to use webhook transport. "
                "Not required for stream mode.",
            )
        )

    # 5. XCHAT_CONSUMER_SECRET set (required for webhook mode; optional for stream)
    consumer_secret = os.getenv("XCHAT_CONSUMER_SECRET", "")
    if _transport_for_check == "webhook":
        results.append(
            _check(
                "XCHAT_CONSUMER_SECRET is set (required for webhook HMAC signing)",
                bool(consumer_secret),
                "Set XCHAT_CONSUMER_SECRET in .env — get it from developer.x.com",
            )
        )
    else:
        results.append(
            _check_warn(
                "XCHAT_CONSUMER_SECRET is set (required for webhook mode only)",
                bool(consumer_secret),
                "Set XCHAT_CONSUMER_SECRET if you plan to use webhook transport. "
                "Not required for stream mode.",
            )
        )

    # 5b. XCHAT_OAUTH_CLIENT_ID set (required for xchat auth login)
    oauth_client_id = os.getenv("XCHAT_OAUTH_CLIENT_ID", "")
    results.append(
        _check(
            "XCHAT_OAUTH_CLIENT_ID is set (required for xchat auth login)",
            bool(oauth_client_id),
            "Set XCHAT_OAUTH_CLIENT_ID in .env — find it in X Developer Portal → "
            "your app → Keys and tokens → OAuth 2.0 Client ID. "
            "This is DIFFERENT from the API Key (XCHAT_CONSUMER_KEY).",
        )
    )

    # 5c. XCHAT_BEARER_TOKEN set (required for Activity Stream)
    bearer_token = os.getenv("XCHAT_BEARER_TOKEN", "")
    transport_mode_check = os.getenv("XCHAT_TRANSPORT_MODE", "stream")
    if transport_mode_check == "stream":
        results.append(
            _check(
                "XCHAT_BEARER_TOKEN is set (required for stream mode)",
                bool(bearer_token),
                "Set XCHAT_BEARER_TOKEN in .env — App Bearer Token from developer.x.com. "
                "Separate from XCHAT_CONSUMER_KEY; needed to connect to Activity Stream.",
            )
        )

    # 5d. XCHAT_USER_ACCESS_TOKEN set (needed for DM replies, optional for receive-only)
    # This is a WARNING, not a hard failure — the bot can still receive events without it,
    # using LoggingReplyAdapter. Only xchat auth login is needed to enable actual replies.
    user_access_token = os.getenv("XCHAT_USER_ACCESS_TOKEN", "")
    results.append(
        _check_warn(
            "XCHAT_USER_ACCESS_TOKEN is set (needed for sending DM replies)",
            bool(user_access_token),
            "Run: xchat auth login  to obtain an OAuth 2.0 user access token. "
            "Without this, the bot will receive events but replies will only be logged.",
        )
    )

    # 6. redirect URI uses 127.0.0.1, not localhost
    redirect_uri = os.getenv("XCHAT_OAUTH_REDIRECT_URI", "http://127.0.0.1:7171/callback")
    uses_localhost = "localhost" in redirect_uri.lower()
    results.append(
        _check(
            f"OAuth redirect URI uses 127.0.0.1 (not localhost) — {redirect_uri}",
            not uses_localhost,
            "Change XCHAT_OAUTH_REDIRECT_URI to use 127.0.0.1 instead of localhost. "
            "X Developer Portal treats them as different origins.",
        )
    )

    # 7. state.json exists (if crypto=real)
    crypto_mode = os.getenv("XCHAT_CRYPTO_MODE", "stub")
    state_file_path = os.getenv("XCHAT_STATE_FILE", "state.json")
    state_file = Path(state_file_path)
    if crypto_mode == "real":
        results.append(
            _check(
                f"state.json exists at {state_file} (required for crypto_mode=real)",
                state_file.exists(),
                "Run: xchat unlock  to generate state.json",
            )
        )

    # 8. state.json in .gitignore
    results.append(
        _check(
            "state.json is in .gitignore",
            _is_in_gitignore("state.json"),
            "Add 'state.json' to .gitignore — it contains private keys",
        )
    )

    # 9. tokens.json in .gitignore
    results.append(
        _check(
            "tokens.json is in .gitignore",
            _is_in_gitignore("tokens.json"),
            "Add 'tokens.json' to .gitignore — it contains OAuth tokens",
        )
    )

    # 10. .env in .gitignore
    results.append(
        _check(
            ".env is in .gitignore",
            _is_in_gitignore(".env"),
            "Add '.env' to .gitignore — it contains secrets",
        )
    )

    # 11. webhook_public_url is HTTPS (if webhook mode)
    transport_mode = os.getenv("XCHAT_TRANSPORT_MODE", "stream")
    webhook_url = os.getenv("XCHAT_WEBHOOK_PUBLIC_URL", "")
    if transport_mode == "webhook":
        if webhook_url:
            is_https = webhook_url.startswith("https://")
            is_local = "127.0.0.1" in webhook_url or "localhost" in webhook_url
            ok = is_https or is_local  # allow local for dev
            results.append(
                _check(
                    f"Webhook public URL is HTTPS — {webhook_url}",
                    ok,
                    "X requires HTTPS for webhook URLs in production. "
                    "Use ngrok, Cloudflare Tunnel, or a real domain for testing.",
                )
            )
        else:
            results.append(
                _check(
                    "XCHAT_WEBHOOK_PUBLIC_URL is set (required for webhook mode)",
                    False,
                    "Set XCHAT_WEBHOOK_PUBLIC_URL to your public HTTPS webhook URL",
                )
            )

    # 12. Connectivity check (optional)
    if check_connectivity:
        try:
            import httpx

            resp = httpx.get("https://api.x.com/2/openapi.json", timeout=5.0)
            ok = resp.status_code < 500
        except Exception:
            ok = False
        results.append(
            _check(
                "X API connectivity (api.x.com)",
                ok,
                "Check your internet connection and firewall settings",
            )
        )

    return results


def _print_scenario(scenario: str) -> None:
    """Print a targeted readiness checklist for a specific use case."""
    from rich.panel import Panel

    _SCENARIOS: dict[str, dict[str, object]] = {
        "public-smoke": {
            "title": "Public smoke test (profile.update.bio)",
            "description": (
                "Verify you can subscribe to profile.update.bio — a public event "
                "that requires no OAuth consent from the monitored user. "
                "Requires approved app + App Bearer Token."
            ),
            "checklist": [
                ("XCHAT_BEARER_TOKEN set", bool(os.getenv("XCHAT_BEARER_TOKEN"))),
                (".env file exists", Path(".env").exists()),
            ],
            "next_steps": (
                "xchat subscriptions create "
                "--event-type profile.update.bio "
                "--user-id <test_user_id> "
                "--tag 'smoke test' "
                "--auth app\n"
                "xchat run --transport stream --crypto stub"
            ),
        },
        "chat-bot": {
            "title": "XChat private event bot (chat.received)",
            "description": (
                "Verify you have OAuth user token + dm.read/dm.write scopes "
                "for receiving and replying to XChat messages."
            ),
            "checklist": [
                ("XCHAT_BEARER_TOKEN set", bool(os.getenv("XCHAT_BEARER_TOKEN"))),
                ("XCHAT_OAUTH_CLIENT_ID set", bool(os.getenv("XCHAT_OAUTH_CLIENT_ID"))),
                ("XCHAT_USER_ACCESS_TOKEN set", bool(os.getenv("XCHAT_USER_ACCESS_TOKEN"))),
                (".env file exists", Path(".env").exists()),
            ],
            "next_steps": (
                "xchat auth login\n"
                "xchat subscriptions create "
                "--event-type chat.received "
                "--user-id <bot_user_id> "
                "--auth user\n"
                "xchat run --transport stream --crypto stub"
            ),
        },
        "webhook-prod": {
            "title": "Production webhook deployment",
            "description": (
                "Verify your webhook URL is public HTTPS, no port, not localhost, "
                "and your consumer secret is configured."
            ),
            "checklist": [
                ("XCHAT_CONSUMER_KEY set", bool(os.getenv("XCHAT_CONSUMER_KEY"))),
                ("XCHAT_CONSUMER_SECRET set", bool(os.getenv("XCHAT_CONSUMER_SECRET"))),
                ("XCHAT_WEBHOOK_PUBLIC_URL set", bool(os.getenv("XCHAT_WEBHOOK_PUBLIC_URL"))),
                (
                    "Webhook URL is HTTPS",
                    (os.getenv("XCHAT_WEBHOOK_PUBLIC_URL") or "").startswith("https://"),
                ),
                (
                    "Webhook URL has no port",
                    ":"
                    not in (os.getenv("XCHAT_WEBHOOK_PUBLIC_URL") or "")
                    .replace("https://", "")
                    .replace("http://", ""),
                ),
                (
                    "Webhook URL is not localhost",
                    "localhost" not in (os.getenv("XCHAT_WEBHOOK_PUBLIC_URL") or "")
                    and "127.0.0.1" not in (os.getenv("XCHAT_WEBHOOK_PUBLIC_URL") or ""),
                ),
            ],
            "next_steps": (
                "xchat webhook register --url <your_https_url>\n"
                "xchat webhook validate <webhook_id>\n"
                "xchat subscriptions create --event-type chat.received --user-id <bot_user_id>"
            ),
        },
    }

    info = _SCENARIOS.get(scenario)
    if not info:
        console.print(
            f"[yellow]Unknown scenario:[/yellow] {scenario!r}. "
            "Available: public-smoke, chat-bot, webhook-prod"
        )
        return

    console.print(
        Panel(
            f"[bold]{info['title']}[/bold]\n\n{info['description']}\n",
            title=f"Scenario: {scenario}",
            border_style="cyan",
        )
    )

    checklist: list[tuple[str, bool]] = info["checklist"]  # type: ignore[assignment]
    all_ok = True
    for label, ok in checklist:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {status}  {label}")
        if not ok:
            all_ok = False

    console.print()
    if all_ok:
        console.print("[green]All scenario prerequisites met.[/green]")
    else:
        console.print("[yellow]Some prerequisites missing — fix before proceeding.[/yellow]")

    console.print(
        Panel(
            str(info["next_steps"]),
            title="Next steps",
            border_style="dim",
        )
    )
    console.print()


def _is_in_gitignore(pattern: str) -> bool:
    """Check if a pattern appears in .gitignore."""
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        return False
    content = gitignore.read_text(encoding="utf-8")
    return any(line.strip() == pattern for line in content.splitlines())


def doctor(
    check_connectivity: bool = typer.Option(
        False, "--check-connectivity", help="Also test network connectivity to X API"
    ),
    fix: bool = typer.Option(
        False, "--fix", help="Attempt to auto-fix simple issues (add to .gitignore)"
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help=(
            "Check readiness for a specific use case. "
            "Options: public-smoke, chat-bot, webhook-prod. "
            "Prints a targeted checklist for that scenario."
        ),
    ),
) -> None:
    """Validate your environment and configuration.

    Checks Python version, uv, credentials, OAuth redirect URI,
    secret file protection, and more.

    Use --scenario for targeted readiness checks:

      xchat doctor --scenario public-smoke
          Verify you can subscribe to profile.update.bio
          (no monitored-user OAuth consent; app Bearer Token required).

      xchat doctor --scenario chat-bot
          Verify you have OAuth user token + dm.read/dm.write scopes for XChat.

      xchat doctor --scenario webhook-prod
          Verify your webhook URL is public HTTPS, no port, not localhost.
    """
    # Load .env if present
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass

    console.print("\n[bold]xchat doctor[/bold] — environment validation\n")

    if scenario:
        _print_scenario(scenario)

    results = _run_checks(check_connectivity=check_connectivity)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check", style="dim", min_width=40)
    table.add_column("Status", min_width=8)
    table.add_column("Fix", style="dim")

    failures = 0
    warnings = 0
    for r in results:
        ok = r["ok"]
        is_warn = r.get("warn", False)
        if ok:
            status = "[green]✓ PASS[/green]"
        elif is_warn:
            status = "[yellow]⚠ WARN[/yellow]"
            warnings += 1
        else:
            status = "[red]✗ FAIL[/red]"
            failures += 1

        table.add_row(
            str(r["label"]),
            status,
            str(r["fix"]) if not ok else "",
        )

    console.print(table)

    if failures == 0 and warnings == 0:
        console.print("\n[bold green]All checks passed![/bold green]")
    elif failures == 0:
        console.print(f"\n[bold yellow]{warnings} warning(s).[/bold yellow]")
        console.print(
            "Warnings are non-blocking — the bot can start, but some features may be unavailable."
        )
    else:
        console.print(f"\n[bold red]{failures} check(s) failed.[/bold red]")
        if warnings:
            console.print(f"[yellow]{warnings} warning(s).[/yellow]")

        # Collect labels of failed checks to give targeted advice
        failed_labels = [str(r["label"]) for r in results if not r["ok"] and not r.get("warn")]
        has_env = any(".env" in lbl for lbl in failed_labels)
        has_gitignore = any("gitignore" in lbl.lower() for lbl in failed_labels)
        _cred_keys = ("CONSUMER_KEY", "CONSUMER_SECRET", "BEARER_TOKEN", "OAUTH_CLIENT_ID")
        has_credentials = any(any(k in lbl for k in _cred_keys) for lbl in failed_labels)
        has_token = any("USER_ACCESS_TOKEN" in lbl for lbl in failed_labels)
        has_redirect = any("redirect" in lbl.lower() or "127.0.0.1" in lbl for lbl in failed_labels)
        has_webhook_url = any("WEBHOOK_PUBLIC_URL" in lbl for lbl in failed_labels)

        if has_env:
            console.print("  → [cyan]cp .env.example .env[/cyan] then fill in your credentials")
        if has_credentials:
            console.print(
                "  → Get credentials from [cyan]developer.x.com[/cyan] → your app → Keys and tokens"
            )
        if has_token:
            console.print("  → Run [cyan]xchat auth login[/cyan] to obtain an OAuth 2.0 user token")
        if has_redirect:
            console.print(
                "  → Set [cyan]XCHAT_OAUTH_REDIRECT_URI=http://127.0.0.1:7171/callback[/cyan]"
                " (not localhost)"
            )
        if has_webhook_url:
            console.print(
                "  → Set [cyan]XCHAT_WEBHOOK_PUBLIC_URL[/cyan] to your public HTTPS URL"
                " (e.g. https://bot.example.com)"
            )
        if has_gitignore:
            console.print("  → Run [cyan]xchat init[/cyan] to update .gitignore automatically")
        console.print()
        raise typer.Exit(code=1)
