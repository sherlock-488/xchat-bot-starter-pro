"""xchat unlock — retrieve E2EE private keys and write to state.json."""

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
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing state.json"
    ),
) -> None:
    """Retrieve E2EE private keys and write to state.json.

    EXPERIMENTAL: The unlock API is observed from xchat-bot-python.
    Run `xchat-bot-python unlock` to generate a real state.json,
    then use it with this starter kit.
    """
    from xchat_bot.auth.unlock import run_unlock_flow
    from xchat_bot.config.settings import AppSettings

    _load_dotenv()

    try:
        settings = AppSettings()  # type: ignore[call-arg]
    except Exception as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not settings.access_token:
        console.print("[red]Not authenticated.[/red] Run [cyan]xchat auth login[/cyan] first.")
        raise typer.Exit(code=1)

    console.print(f"\n[bold]xchat unlock[/bold] — writing to {state_file}\n")
    console.print("[yellow]EXPERIMENTAL:[/yellow] Unlock API follows xchat-bot-python pattern.")

    async def _run() -> None:
        await run_unlock_flow(
            access_token=settings.access_token or "",
            consumer_key=settings.consumer_key,
            consumer_secret=settings.consumer_secret.get_secret_value(),
            access_token_secret=(settings.access_token_secret.get_secret_value()
                                  if settings.access_token_secret else ""),
            state_file=state_file,
            force=force,
        )
        console.print(f"[green]✓[/green] state.json written to {state_file}")
        console.print("[dim]Note: state.json contains private keys — never commit to git.[/dim]")

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
