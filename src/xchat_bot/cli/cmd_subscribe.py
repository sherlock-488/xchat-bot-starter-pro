"""xchat subscribe — register your webhook URL with X."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()


def subscribe(
    url: str = typer.Option(..., "--url", help="Your public HTTPS webhook URL"),
    env_name: str = typer.Option(
        "prod", "--env-name", help="X developer environment name"
    ),
) -> None:
    """Register your webhook URL with X Activity API.

    EXPERIMENTAL: The subscription API endpoint is observed from xchat-bot-python.

    Prerequisites:
      - xchat auth login completed
      - URL must be publicly accessible HTTPS (not localhost)
      - URL must be registered in X Developer Portal

    After subscribing, X will send a CRC challenge to verify your endpoint.
    Make sure your webhook server is running before subscribing.
    """
    _load_dotenv()

    if "localhost" in url or "127.0.0.1" in url:
        console.print(
            "[yellow]Warning:[/yellow] Webhook URL contains localhost/127.0.0.1. "
            "X cannot reach local addresses. Use ngrok or a public URL for testing."
        )

    if not url.startswith("https://"):
        console.print(
            "[yellow]Warning:[/yellow] Webhook URL should be HTTPS. "
            "X may reject HTTP URLs in production."
        )

    console.print(f"\n[bold]xchat subscribe[/bold]\n")
    console.print(f"  URL: [cyan]{url}[/cyan]")
    console.print(f"  Environment: [cyan]{env_name}[/cyan]")
    console.print()
    console.print(
        "[yellow]EXPERIMENTAL:[/yellow] Subscription API follows xchat-bot-python pattern. "
        "Consult official X docs for the current subscription endpoint."
    )
    console.print()
    console.print("Manual subscription via X Developer Portal:")
    console.print("  1. Go to https://developer.twitter.com/en/portal")
    console.print("  2. Select your app → Webhooks")
    console.print(f"  3. Add webhook URL: {url}")
    console.print("  4. X will send a CRC challenge — your server must respond correctly")


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        except ImportError:
            pass
