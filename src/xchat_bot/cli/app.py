"""
xchat CLI — root application and command registration.

Usage:
    xchat --help
    xchat init
    xchat doctor
    xchat auth login
    xchat webhook register --url https://...
    xchat subscriptions create --user-id <bot_user_id> --event-type chat.received
    xchat dm send "hello" --participant-id 9876543210
    xchat run
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="xchat",
    help="xchat-bot-starter-pro — XChat bot starter kit",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Import and register sub-commands
from xchat_bot.cli import (  # noqa: E402
    cmd_auth,
    cmd_dm,
    cmd_doctor,
    cmd_init,
    cmd_inspect,
    cmd_replay,
    cmd_run,
    cmd_subscriptions,
    cmd_unlock,
    cmd_webhook,
)

app.add_typer(cmd_auth.app, name="auth")
app.add_typer(cmd_dm.app, name="dm")
app.add_typer(cmd_replay.app, name="replay")
app.add_typer(cmd_webhook.app, name="webhook")
app.add_typer(cmd_subscriptions.app, name="subscriptions")
app.command("init")(cmd_init.init)
app.command("doctor")(cmd_doctor.doctor)
app.command("unlock")(cmd_unlock.unlock)
app.command("run")(cmd_run.run)
app.command("inspect")(cmd_inspect.inspect)


@app.command("version")
def version() -> None:
    """Print version information."""
    from xchat_bot import __version__

    typer.echo(f"xchat-bot-starter-pro {__version__}")
