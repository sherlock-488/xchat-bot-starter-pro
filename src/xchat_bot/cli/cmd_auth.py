"""xchat auth — OAuth authentication commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="OAuth authentication commands")
console = Console()


@app.command("login")
def login(
    scopes: str = typer.Option(
        "", "--scopes", help="Comma-separated OAuth scopes (consult X developer docs)"
    ),
    data_dir: Path = typer.Option(
        Path("~/.config/xchat-bot"), "--data-dir", help="Directory to store tokens.json"
    ),
) -> None:
    """Authenticate with X via OAuth 1.0a.

    Opens your browser for authorization and saves tokens to tokens.json.

    IMPORTANT: The redirect URI must use 127.0.0.1, not localhost.
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

    console.print("\n[bold]xchat auth login[/bold]\n")
    console.print(f"Redirect URI: [cyan]{settings.oauth_redirect_uri}[/cyan]")
    if scopes:
        console.print(f"Scopes: [cyan]{scopes}[/cyan]")
    console.print()

    async def _run() -> None:
        tokens = await run_oauth_flow(
            consumer_key=settings.consumer_key,
            consumer_secret=settings.consumer_secret.get_secret_value(),
            redirect_uri=settings.oauth_redirect_uri,
        )

        store = TokenStore(data_dir.expanduser())
        store.save(
            access_token=tokens.get("oauth_token", ""),
            access_token_secret=tokens.get("oauth_token_secret", ""),
            user_id=tokens.get("user_id"),
            screen_name=tokens.get("screen_name"),
        )

        console.print(f"[green]✓[/green] Authenticated as @{tokens.get('screen_name', 'unknown')}")
        console.print(f"[green]✓[/green] Tokens saved to {store.tokens_file}")
        console.print("\nAdd to your .env:")
        console.print(f"  [cyan]XCHAT_ACCESS_TOKEN={tokens.get('oauth_token', '')}[/cyan]")
        secret_val = tokens.get('oauth_token_secret', '')
        console.print(f"  [cyan]XCHAT_ACCESS_TOKEN_SECRET={secret_val}[/cyan]")

    try:
        asyncio.run(_run())
    except TimeoutError as exc:
        console.print(f"[red]Timeout:[/red] {exc}")
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
        user_id = tokens.get("user_id") or "unknown"
        has_token = bool(tokens.get("access_token"))
        console.print(f"  Authenticated as: [cyan]@{screen_name}[/cyan] (user_id: {user_id})")
        token_status = "[green]present[/green]" if has_token else "[red]missing[/red]"
        console.print(f"  Access token: {token_status}")
        console.print(f"  Tokens file: {store.tokens_file}")
    else:
        console.print("  [yellow]Not authenticated[/yellow]")
        console.print("  Run [cyan]xchat auth login[/cyan] to authenticate.")


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        except ImportError:
            pass
