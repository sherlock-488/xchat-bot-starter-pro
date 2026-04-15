"""xchat run — start your bot."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import typer
from rich.console import Console

from xchat_bot.config.settings import AppSettings

console = Console()


def run(
    bot: str = typer.Option(
        "xchat_bot.examples.echo_bot:EchoBot",
        "--bot",
        help=(
            "Bot module path, e.g. xchat_bot.examples.echo_bot:EchoBot. "
            "For a custom bot in the current directory: bots.my_bot:MyBot"
        ),
    ),
    transport: str = typer.Option(
        "", "--transport", help="Override transport mode: stream or webhook"
    ),
    crypto: str = typer.Option("", "--crypto", help="Override crypto mode: stub or real"),
    host: str = typer.Option("", "--host", help="Webhook host (webhook mode only)"),
    port: int = typer.Option(0, "--port", help="Webhook port (webhook mode only)"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn reload (dev only)"),
) -> None:
    """Start your XChat bot.

    Loads the bot class from the specified module, initializes the transport,
    and starts processing events.

    Examples:
        xchat run
        xchat run --bot xchat_bot.examples.echo_bot:EchoBot
        xchat run --transport webhook --bot xchat_bot.examples.router_bot:RouterBot
        xchat run --bot bots.my_bot:MyBot   # custom bot in current directory
    """
    _load_dotenv()

    try:
        settings = AppSettings()  # type: ignore[call-arg]
    except Exception as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        console.print("Run [cyan]xchat doctor[/cyan] to diagnose issues.")
        raise typer.Exit(code=1) from exc

    # If user_access_token is not in env/.env, try tokens.json as fallback.
    # This ensures `xchat run` works even when --no-update-env was used during login.
    if not settings.user_access_token:
        settings = _inject_token_from_store(settings)

    # Apply CLI overrides
    if transport:
        if transport not in ("stream", "webhook"):
            console.print(
                f"[red]Invalid transport:[/red] {transport!r}. Use 'stream' or 'webhook'."
            )
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

    console.print("\n[bold]xchat run[/bold]")
    console.print(f"  Bot: [cyan]{bot}[/cyan]")
    console.print(f"  Transport: [cyan]{settings.transport_mode}[/cyan]")
    console.print(f"  Crypto: [cyan]{settings.crypto_mode}[/cyan]")
    if settings.transport_mode == "webhook":
        console.print(
            f"  Webhook: [cyan]http://{settings.webhook_host}:{settings.webhook_port}{settings.webhook_path}[/cyan]"
        )
    console.print()

    asyncio.run(_run_bot(bot_instance, settings))


def _load_bot(bot_path: str, settings: AppSettings) -> object:
    """Load bot class from module:ClassName path."""
    from xchat_bot.reply.adapter import LoggingReplyAdapter
    from xchat_bot.reply.x_api import XApiReplyAdapter

    try:
        module_path, class_name = bot_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        bot_class = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as exc:
        console.print(f"[red]Failed to load bot {bot_path!r}:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    reply = XApiReplyAdapter(settings) if settings.user_access_token else LoggingReplyAdapter()
    if not settings.user_access_token:
        console.print(
            "[yellow]No user_access_token — using LoggingReplyAdapter "
            "(replies will be logged, not sent). Run `xchat auth login` to enable replies.[/yellow]"
        )

    return bot_class(settings=settings, reply=reply)


async def _run_bot(bot: object, settings: AppSettings) -> None:
    """Initialize transport and run bot."""
    from xchat_bot.crypto.real import RealCrypto
    from xchat_bot.crypto.stub import StubCrypto
    from xchat_bot.events.dedup import EventDeduplicator
    from xchat_bot.events.normalizer import EventNormalizer
    from xchat_bot.logging.setup import configure_logging
    from xchat_bot.transport.stream import ActivityStreamTransport
    from xchat_bot.transport.webhook import WebhookTransport

    configure_logging(settings.log_level, settings.log_format)

    normalizer = EventNormalizer()
    deduplicator = EventDeduplicator(settings.dedup_max_size)

    if settings.crypto_mode == "real":
        try:
            crypto = RealCrypto(settings.state_file)
        except FileNotFoundError as exc:
            console.print(f"[red]Crypto error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
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


def _inject_token_from_store(settings: AppSettings) -> AppSettings:
    """If user_access_token is absent from env, load it from tokens.json.

    This ensures xchat run works even when --no-update-env was used during
    `xchat auth login`.
    """
    from pydantic import SecretStr

    from xchat_bot.auth.token_store import TokenStore

    store = TokenStore(settings.data_dir)
    tokens = store.load()
    if not tokens:
        return settings

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token:
        return settings

    console.print(
        "[dim]user_access_token loaded from tokens.json "
        "(set XCHAT_USER_ACCESS_TOKEN in .env to avoid this)[/dim]"
    )
    updates: dict[str, object] = {"user_access_token": SecretStr(access_token)}
    if refresh_token and not settings.user_refresh_token:
        updates["user_refresh_token"] = SecretStr(refresh_token)
    return settings.model_copy(update=updates)


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass
