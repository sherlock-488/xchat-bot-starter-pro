"""xchat unlock — retrieve E2EE private keys and write to state.json.

EXPERIMENTAL: The unlock API is not yet officially documented.
This command creates a placeholder state.json.
For real E2EE keys, run xchat-bot-python's unlock flow and copy state.json here.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def unlock(
    state_file: Path = typer.Option(
        Path("state.json"), "--state-file", help="Path to write state.json"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing state.json"),
) -> None:
    """Write a placeholder state.json for E2EE key material.

    EXPERIMENTAL: The real unlock API is not yet officially documented and
    chat-xdk has not been officially released. This command creates a minimal
    state.json so the rest of the bot can start in crypto=real mode.

    For real E2EE keys:
      1. Run xchat-bot-python's unlock flow (see https://github.com/xdevplatform/xchat-bot-python)
      2. Copy the resulting state.json into your project directory.

    Requires:
      - XCHAT_USER_ACCESS_TOKEN set (run `xchat auth login` first)
    """
    from xchat_bot.auth.unlock import run_unlock_flow
    from xchat_bot.config.settings import AppSettings

    _load_dotenv()

    try:
        settings = AppSettings()  # type: ignore[call-arg]
    except Exception as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not settings.user_access_token:
        console.print(
            "[red]Not authenticated.[/red] Run [cyan]xchat auth login[/cyan] first to obtain "
            "an OAuth 2.0 user access token."
        )
        raise typer.Exit(code=1)

    console.print(f"\n[bold]xchat unlock[/bold] — writing to {state_file}")
    console.print(
        "[yellow]EXPERIMENTAL:[/yellow] This creates a placeholder state.json. "
        "Full private-key recovery and decrypt require chat-xdk and remain experimental "
        "until stable public tooling is available."
    )
    console.print()

    async def _run() -> None:
        await run_unlock_flow(
            user_access_token=settings.user_access_token.get_secret_value(),  # type: ignore[union-attr]
            state_file=state_file,
            force=force,
        )
        console.print(f"[green]✓[/green] state.json written to {state_file}")
        console.print("[dim]Note: state.json contains private keys — never commit to git.[/dim]")
        console.print()
        console.print(
            "For real E2EE keys, see: [cyan]https://github.com/xdevplatform/xchat-bot-python[/cyan]"
        )

    try:
        asyncio.run(_run())
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Unlock failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass
