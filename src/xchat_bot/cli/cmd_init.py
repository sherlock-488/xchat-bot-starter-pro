"""xchat init — initialize a new bot project directory."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


GITIGNORE_ENTRIES = [
    ".env",
    "state.json",
    "tokens.json",
    "*.key",
    "*.pem",
    "__pycache__/",
    ".venv/",
    "*.pyc",
    ".coverage",
    "htmlcov/",
    "recordings/",
]


def _load_env_example() -> str:
    """Load .env.example from package data (single source of truth)."""
    pkg = importlib.resources.files("xchat_bot")
    return (pkg / "env.example").read_text(encoding="utf-8")


def init(
    directory: Path = typer.Argument(Path("."), help="Directory to initialize"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
) -> None:
    """Initialize a new xchat bot project.

    Creates .env.example and updates .gitignore with required secret exclusions.
    """
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Initializing xchat bot project in[/bold] {directory}\n")

    # Create .env.example
    env_example = directory / ".env.example"
    if not env_example.exists() or force:
        env_example.write_text(_load_env_example(), encoding="utf-8")
        console.print(f"  [green]✓[/green] Created {env_example.name}")
    else:
        console.print(f"  [dim]· Skipped {env_example.name} (already exists)[/dim]")

    # Update .gitignore
    gitignore = directory / ".gitignore"
    existing_entries: set[str] = set()
    if gitignore.exists():
        existing_entries = set(gitignore.read_text(encoding="utf-8").splitlines())

    new_entries = [e for e in GITIGNORE_ENTRIES if e not in existing_entries]
    if new_entries:
        with gitignore.open("a", encoding="utf-8") as f:
            if gitignore.exists() and gitignore.stat().st_size > 0:
                f.write("\n# xchat-bot-starter-pro secrets\n")
            for entry in new_entries:
                f.write(f"{entry}\n")
        console.print(f"  [green]✓[/green] Updated .gitignore ({len(new_entries)} entries added)")
    else:
        console.print("  [dim]· .gitignore already has all required entries[/dim]")

    console.print(
        Panel(
            "[bold]Next steps:[/bold]\n\n"
            "1. [cyan]cp .env.example .env[/cyan] — fill in credentials\n"
            "2. [cyan]xchat doctor[/cyan] — validate your setup\n"
            "3. [cyan]xchat auth login[/cyan] — authenticate (opens browser)\n"
            "4. [cyan]xchat subscriptions create --user-id <bot_user_id>[/cyan]\n"
            "   [dim]Tell X which events to deliver to your bot[/dim]\n"
            "   [dim](webhook mode: run `xchat webhook register --url ...` first)[/dim]\n"
            "5. [cyan]xchat run[/cyan] — start the bot\n"
            "   [dim](default: xchat_bot.examples.echo_bot:EchoBot)[/dim]",
            title="xchat init complete",
            border_style="green",
        )
    )
