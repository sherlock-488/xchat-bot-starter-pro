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
    return {"label": label, "ok": ok, "fix": fix}


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

    # 4. XCHAT_CONSUMER_KEY set
    consumer_key = os.getenv("XCHAT_CONSUMER_KEY", "")
    results.append(
        _check(
            "XCHAT_CONSUMER_KEY is set",
            bool(consumer_key),
            "Set XCHAT_CONSUMER_KEY in .env — get it from developer.x.com",
        )
    )

    # 5. XCHAT_CONSUMER_SECRET set
    consumer_secret = os.getenv("XCHAT_CONSUMER_SECRET", "")
    results.append(
        _check(
            "XCHAT_CONSUMER_SECRET is set",
            bool(consumer_secret),
            "Set XCHAT_CONSUMER_SECRET in .env — get it from developer.x.com",
        )
    )

    # 5b. XCHAT_BEARER_TOKEN set (required for Activity Stream)
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

    # 5c. XCHAT_USER_ACCESS_TOKEN set (required for sending replies)
    user_access_token = os.getenv("XCHAT_USER_ACCESS_TOKEN", "")
    results.append(
        _check(
            "XCHAT_USER_ACCESS_TOKEN is set (required for sending DM replies)",
            bool(user_access_token),
            "Run: xchat auth login  to obtain an OAuth 2.0 user access token. "
            "Without this, the bot can receive messages but cannot reply.",
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
) -> None:
    """Validate your environment and configuration.

    Checks Python version, uv, credentials, OAuth redirect URI,
    secret file protection, and more.
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

    results = _run_checks(check_connectivity=check_connectivity)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check", style="dim", min_width=40)
    table.add_column("Status", min_width=8)
    table.add_column("Fix", style="dim")

    failures = 0
    for r in results:
        ok = r["ok"]
        if ok:
            status = "[green]✓ PASS[/green]"
        else:
            status = "[red]✗ FAIL[/red]"
            failures += 1

        table.add_row(
            str(r["label"]),
            status,
            str(r["fix"]) if not ok else "",
        )

    console.print(table)

    if failures == 0:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print(f"\n[bold red]{failures} check(s) failed.[/bold red]")
        console.print("Run [cyan]xchat init[/cyan] to fix .gitignore issues automatically.\n")
        raise typer.Exit(code=1)
