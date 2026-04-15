"""xchat run — start your bot."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

console = Console()


def run(
    bot: str = typer.Option(
        "bots.echo_bot:EchoBot",
        "--bot",
        help="Bot module path, e.g. bots.echo_bot:EchoBot",
    ),
    transport: str = typer.Option(
        "", "--transport", help="Override transport mode: stream or webhook"
    ),
    crypto: str = typer.Option(
        "", "--crypto", help="Override crypto mode: stub or real"
    ),
    host: str = typer.Option("", "--host", help="Webhook host (webhook mode only)"),
    port: int = typer.Option(0, "--port", help="Webhook port (webhook mode only)"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload (dev only)"),
) -> None:
    """Start your XChat bot.

    Loads the bot class from the specified module, initializes the transport,
    and starts processing events.

    Examples:
        xchat run --bot bots.echo_bot:EchoBot
        xchat run --transport webhook --bot bots.router_bot:RouterBot
        xchat run --crypto real --bot bots.echo_bot:EchoBot
    """
    _load_dotenv()

    from xchat_bot.config.settings import AppSettings

    try:
        settings = AppSettings()  # type: ignore[call-arg]
    except Exception as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        console.print("Run [cyan]xchat doctor[/cyan] to diagnose issues.")
        raise typer.Exit(code=1)

    # Apply CLI overrides
    if transport:
        if transport not in ("stream", "webhook"):
            console.print(f"[red]Invalid transport:[/red] {transport!r}. Use 'stream' or 'webhook'.")
            raise typer.Exit(code=1)
        settings = settings.model_copy(update={"transport_mode": transport})
    if crypto:
        if crypto not in ("stub", "real"):
            console.print(f"[red]Invalid crypto:[/red] {crypto!r}. Use 'stub' or 'real'.")
            raise typer.Exit(code=1)
        settings = settings.model_copy(update={"crypto_mode": crypto})
    if host:
        settings = settings.model_copy(update={"webhook_host": host})
    if port:
        settings = settings.model_copy(update={"webhook_port": port})

    # Load bot class
    bot_instance = _load_bot(bot, settings)

    console.print(f"\n[bold]xchat run[/bold]")
    console.print(f"  Bot: [cyan]{bot}[/cyan]")
    console.print(f"  Transport: [cyan]{settings.transport_mode}[/cyan]")
    console.print(f"  Crypto: [cyan]{settings.crypto_mode}[/cyan]")
    if settings.transport_mode == "webhook":
        console.print(f"  Webhook: [cyan]http://{settings.webhook_host}:{settings.webhook_port}{settings.webhook_path}[/cyan]")
    console.print()

    asyncio.run(_run_bot(bot_instance, settings))


def _load_bot(bot_path: str, settings: object) -> object:
    """Load bot class from module:ClassName path."""
    from xchat_bot.config.settings import AppSettings
    from xchat_bot.reply.adapter import LoggingReplyAdapter
    from xchat_bot.reply.x_api import XApiReplyAdapter

    try:
        module_path, class_name = bot_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        bot_class = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as exc:
        console.print(f"[red]Failed to load bot {bot_path!r}:[/red] {exc}")
        raise typer.Exit(code=1)

    assert isinstance(settings, AppSettings)
    reply = XApiReplyAdapter(settings) if settings.access_token else LoggingReplyAdapter()
    if not settings.access_token:
        console.print("[yellow]No access_token — using LoggingReplyAdapter (replies will be logged, not sent)[/yellow]")

    return bot_class(settings=settings, reply=reply)


async def _run_bot(bot: object, settings: object) -> None:
    """Initialize transport and run bot."""
    from xchat_bot.config.settings import AppSettings
    from xchat_bot.crypto.real import RealCrypto
    from xchat_bot.crypto.stub import StubCrypto
    from xchat_bot.events.dedup import EventDeduplicator
    from xchat_bot.events.normalizer import EventNormalizer
    from xchat_bot.logging.setup import configure_logging
    from xchat_bot.transport.stream import ActivityStreamTransport
    from xchat_bot.transport.webhook import WebhookTransport

    assert isinstance(settings, AppSettings)
    configure_logging(settings.log_level, settings.log_format)

    normalizer = EventNormalizer()
    deduplicator = EventDeduplicator(settings.dedup_max_size)

    if settings.crypto_mode == "real":
        try:
            crypto = RealCrypto(settings.state_file)
        except FileNotFoundError as exc:
            console.print(f"[red]Crypto error:[/red] {exc}")
            raise typer.Exit(code=1)
    else:
        crypto = StubCrypto()

    if settings.transport_mode == "webhook":
        transport = WebhookTransport(settings, normalizer, deduplicator, crypto)
    else:
        transport = ActivityStreamTransport(settings, normalizer, deduplicator, crypto)

    from xchat_bot.bot.base import BotBase
    assert isinstance(bot, BotBase)

    await bot.on_start()
    try:
        await transport.run(handler=bot.handle)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
    finally:
        await bot.on_stop()
        await transport.stop()


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        except ImportError:
            pass
