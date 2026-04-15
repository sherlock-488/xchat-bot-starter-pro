"""xchat auth — OAuth 2.0 authentication commands."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="OAuth 2.0 authentication commands")
console = Console()


@app.command("login")
def login(
    scopes: str = typer.Option(
        "dm.read dm.write tweet.read users.read offline.access",
        "--scopes",
        help="Space-separated OAuth 2.0 scopes",
    ),
    data_dir: Path = typer.Option(
        Path("~/.config/xchat-bot"), "--data-dir", help="Directory to store tokens.json"
    ),
    update_env: bool = typer.Option(
        True,
        "--update-env/--no-update-env",
        help="Write XCHAT_USER_ACCESS_TOKEN and XCHAT_USER_REFRESH_TOKEN into .env",
    ),
) -> None:
    """Authenticate with X via OAuth 2.0 Authorization Code + PKCE.

    Opens your browser for authorization and saves the user access token
    to tokens.json. Optionally writes the token into your .env file so
    `xchat run` can pick it up immediately.

    Prerequisites:
      - XCHAT_OAUTH_CLIENT_ID set (OAuth 2.0 Client ID from X Developer Portal →
        your app → Keys and tokens → OAuth 2.0 — different from the API Key)
      - http://127.0.0.1:7171/callback registered in X Developer Portal
        under your app's "Callback URLs"

    The user access token produced here is used by `xchat run` to send
    DM replies via XApiReplyAdapter (XCHAT_USER_ACCESS_TOKEN).
    It is separate from the app Bearer Token used for the Activity Stream.
    """
    from xchat_bot.auth.oauth import run_oauth_flow
    from xchat_bot.auth.token_store import TokenStore
    from xchat_bot.config.settings import AppSettings

    _load_dotenv()

    try:
        settings = AppSettings()  # type: ignore[call-arg]
    except Exception as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        console.print("Run [cyan]xchat doctor[/cyan] to diagnose issues.")
        raise typer.Exit(code=1) from exc

    # XCHAT_OAUTH_CLIENT_ID is required — it is NOT the same as the API Key (consumer_key).
    # In X Developer Portal: App Settings → Keys and tokens → OAuth 2.0 Client ID
    if not settings.oauth_client_id:
        console.print(
            "[red]Error:[/red] XCHAT_OAUTH_CLIENT_ID is not set.\n"
            "\n"
            "  The OAuth 2.0 Client ID is different from the API Key (XCHAT_CONSUMER_KEY).\n"
            "  Find it in X Developer Portal → App Settings → Keys and tokens → OAuth 2.0.\n"
            "\n"
            "  Add to your .env:\n"
            "    [cyan]XCHAT_OAUTH_CLIENT_ID=<your OAuth 2.0 Client ID>[/cyan]\n"
            "    [cyan]XCHAT_OAUTH_CLIENT_SECRET=<your OAuth 2.0 Client Secret>[/cyan]"
            "  [dim]# confidential clients only[/dim]"
        )
        raise typer.Exit(code=1)

    client_id: str = settings.oauth_client_id
    client_secret: str | None = (
        settings.oauth_client_secret.get_secret_value() if settings.oauth_client_secret else None
    )

    console.print("\n[bold]xchat auth login[/bold] (OAuth 2.0 PKCE)\n")
    console.print(f"  Client ID  : [cyan]{client_id}[/cyan]")
    confidential = "yes" if client_secret else "no (public client)"
    console.print(f"  Confidential: [cyan]{confidential}[/cyan]")
    console.print(f"  Redirect   : [cyan]{settings.oauth_redirect_uri}[/cyan]")
    console.print(f"  Scopes     : [cyan]{scopes}[/cyan]")
    console.print()

    async def _run() -> None:
        token_resp = await run_oauth_flow(
            client_id=client_id,
            redirect_uri=settings.oauth_redirect_uri,
            scopes=scopes,
            client_secret=client_secret,
        )

        access_token: str = token_resp.get("access_token", "")
        refresh_token: str | None = token_resp.get("refresh_token")
        granted_scope: str | None = token_resp.get("scope")

        # Fetch user identity so `xchat auth status` can show account name
        user_id: str | None = None
        screen_name: str | None = None
        try:
            import httpx as _httpx

            me_resp = await _httpx.AsyncClient().get(
                "https://api.x.com/2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if me_resp.is_success:
                me_data = me_resp.json().get("data", {})
                user_id = me_data.get("id")
                screen_name = me_data.get("username")
        except Exception:  # noqa: BLE001, S110
            pass  # non-fatal — identity lookup is best-effort

        store = TokenStore(data_dir.expanduser())
        store.save(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=user_id,
            screen_name=screen_name,
            scope=granted_scope,
        )

        console.print("[green]✓[/green] Authorization complete.")
        console.print(f"[green]✓[/green] Tokens saved to {store.tokens_file}")
        console.print()

        if update_env:
            env_file = Path(".env")
            _write_token_to_env(env_file, access_token, refresh_token)
            console.print(f"[green]✓[/green] XCHAT_USER_ACCESS_TOKEN written to {env_file}")
        else:
            console.print("Add to your .env:")
            console.print(f"  [cyan]XCHAT_USER_ACCESS_TOKEN={access_token}[/cyan]")
            if refresh_token:
                console.print(f"  [cyan]XCHAT_USER_REFRESH_TOKEN={refresh_token}[/cyan]")

        console.print()
        console.print(
            "You can now run [cyan]xchat run[/cyan] — "
            "the bot will use this token to send DM replies."
        )

    try:
        asyncio.run(_run())
    except TimeoutError as exc:
        console.print(f"[red]Timeout:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        console.print(f"[red]Auth error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Auth failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command("status")
def status(
    data_dir: Path = typer.Option(
        Path("~/.config/xchat-bot"), "--data-dir", help="Directory containing tokens.json"
    ),
) -> None:
    """Show current authentication status."""
    from xchat_bot.auth.token_store import TokenStore

    store = TokenStore(data_dir.expanduser())
    tokens = store.load()

    console.print("\n[bold]Auth status[/bold]\n")

    if tokens:
        screen_name = tokens.get("screen_name") or "unknown"
        has_token = bool(tokens.get("access_token"))
        has_refresh = bool(tokens.get("refresh_token"))
        scope = tokens.get("scope") or "unknown"
        token_status = "[green]present[/green]" if has_token else "[red]missing[/red]"
        refresh_status = "[green]present[/green]" if has_refresh else "[dim]not stored[/dim]"
        console.print(f"  Authenticated as : [cyan]@{screen_name}[/cyan]")
        console.print(f"  Access token     : {token_status}")
        console.print(f"  Refresh token    : {refresh_status}")
        console.print(f"  Scopes           : [dim]{scope}[/dim]")
        console.print(f"  Tokens file      : {store.tokens_file}")
    else:
        console.print("  [yellow]Not authenticated[/yellow]")
        console.print("  Run [cyan]xchat auth login[/cyan] to authenticate.")


def _write_token_to_env(env_file: Path, access_token: str, refresh_token: str | None) -> None:
    """Write or update XCHAT_USER_ACCESS_TOKEN in .env.

    If the key already exists, replaces its value in-place.
    If it doesn't exist, appends it.
    """
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()

    def _set_key(key: str, value: str) -> None:
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$")
        replaced = False
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                replaced = True
                break
        if not replaced:
            # Add a blank line before appending if file doesn't end with one
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"{key}={value}")

    _set_key("XCHAT_USER_ACCESS_TOKEN", access_token)
    if refresh_token:
        _set_key("XCHAT_USER_REFRESH_TOKEN", refresh_token)

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass
