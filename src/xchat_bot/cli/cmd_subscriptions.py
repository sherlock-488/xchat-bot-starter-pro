"""xchat subscriptions — manage X Activity API subscriptions.

Activity subscriptions define *what* events your app receives. They are
separate from webhook registration (which defines *where* events are sent).

A subscription specifies:
  - event_type: e.g. "chat.received", "profile.update.bio"
  - filter: user_id, keyword, direction, etc.
  - Optional: tag, webhook_id

Auth model:
  - Public events (profile.update.*, follow.*, spaces.*): use app Bearer Token (--auth app)
  - Private events (chat.*, dm.*): require OAuth 2.0 user access token (--auth user)
  - --auth auto (default): picks the right token automatically based on event_type

Typical flow:
  # Public smoke test (no OAuth needed)
  xchat subscriptions create --event-type profile.update.bio --user-id <id> --tag "smoke"

  # Private XChat events (requires xchat auth login first)
  xchat subscriptions create --event-type chat.received --user-id <bot_user_id>

Reference: https://docs.x.com/x-api/direct-messages/activity-stream
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
from rich.console import Console

app = typer.Typer(help="Manage X Activity API subscriptions (POST /2/activity/subscriptions)")
console = Console()

# X Activity Subscriptions API v2
_SUBSCRIPTIONS_URL = "https://api.x.com/2/activity/subscriptions"

# Known XAA event types (from official docs.x.com)
_KNOWN_EVENT_TYPES: set[str] = {
    "profile.update.bio",
    "profile.update.profile_picture",
    "profile.update.banner_picture",
    "profile.update.screenname",
    "profile.update.geo",
    "profile.update.url",
    "profile.update.verified_badge",
    "profile.update.affiliate_badge",
    "profile.update.handle",
    "follow.follow",
    "follow.unfollow",
    "spaces.start",
    "spaces.end",
    "chat.received",
    "chat.sent",
    "chat.conversation_join",
    "dm.sent",
    "dm.received",
    "dm.indicate_typing",
    "dm.read",
    "news.new",
}

# Private event prefixes — require OAuth 2.0 user token
_PRIVATE_EVENT_PREFIXES = ("chat.", "dm.")


def _is_private_event(event_type: str) -> bool:
    return event_type.startswith(_PRIVATE_EVENT_PREFIXES)


def _auth_headers(auth_mode: str, event_type: str) -> dict[str, str]:
    """Return auth headers for the given mode and event type.

    auth_mode:
      "auto"  — use user token for private events, bearer token for public
      "user"  — always use XCHAT_USER_ACCESS_TOKEN
      "app"   — always use XCHAT_BEARER_TOKEN
    """
    if auth_mode == "auto":
        auth_mode = "user" if _is_private_event(event_type) else "app"

    if auth_mode == "user":
        token = os.environ.get("XCHAT_USER_ACCESS_TOKEN", "")
        if not token:
            console.print(
                "[red]Error:[/red] XCHAT_USER_ACCESS_TOKEN is not set. "
                f"'{event_type}' is a private event and requires an OAuth 2.0 user token. "
                "Run: [cyan]xchat auth login[/cyan]"
            )
            raise typer.Exit(code=1)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    else:  # app
        token = os.environ.get("XCHAT_BEARER_TOKEN", "")
        if not token:
            console.print(
                "[red]Error:[/red] XCHAT_BEARER_TOKEN is not set. "
                "Set it in .env or as an environment variable."
            )
            raise typer.Exit(code=1)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@app.command("create")
def create(
    event_type: str = typer.Option(
        "chat.received",
        "--event-type",
        help=(
            "Event type to subscribe to. "
            "Public: profile.update.bio, follow.follow, spaces.start, news.new, ... "
            "Private (requires --auth user): chat.received, chat.sent, dm.received, ..."
        ),
    ),
    user_id: str | None = typer.Option(
        None,
        "--user-id",
        help=(
            "X user ID for filter.user_id. Required for most event types. "
            "Find it at: https://developer.x.com/en/docs/twitter-api/users/lookup/api-reference"
        ),
    ),
    keyword: str | None = typer.Option(
        None,
        "--keyword",
        help="Keyword filter (e.g. for news.new events)",
    ),
    direction: str | None = typer.Option(
        None,
        "--direction",
        help="Direction filter (e.g. 'incoming' or 'outgoing')",
    ),
    tag: str | None = typer.Option(
        None,
        "--tag",
        help="Optional label to identify this subscription",
    ),
    webhook_id: str | None = typer.Option(
        None,
        "--webhook-id",
        help="Webhook ID to associate this subscription with (webhook mode only)",
    ),
    auth: str = typer.Option(
        "auto",
        "--auth",
        help=(
            "Auth mode: 'auto' (default) uses OAuth user token for chat/dm private events "
            "and app Bearer Token for public events. "
            "'user' forces user token. 'app' forces Bearer Token."
        ),
    ),
) -> None:
    """Create an Activity API subscription (POST /2/activity/subscriptions).

    This tells X which event types to deliver to your bot.

    Auth is selected automatically:
      - Public events (profile.update.*, follow.*, spaces.*): app Bearer Token
      - Private events (chat.*, dm.*): OAuth 2.0 user token (xchat auth login)

    Examples:
      # Public smoke test — no OAuth needed
      xchat subscriptions create --event-type profile.update.bio --user-id 2244994945 --tag "smoke"

      # Private XChat events — requires xchat auth login first
      xchat subscriptions create --event-type chat.received --user-id <bot_user_id>

      # Keyword subscription
      xchat subscriptions create --event-type news.new --keyword "AI" --tag "AI news"
    """
    _load_dotenv()

    # Warn on unknown event types (not a hard error — API may accept new types)
    if event_type not in _KNOWN_EVENT_TYPES:
        console.print(
            f"[yellow]Warning:[/yellow] '{event_type}' is not in the known event type list. "
            "Proceeding anyway — the API may accept it."
        )

    headers = _auth_headers(auth, event_type)

    # Build filter
    filter_: dict[str, str] = {}
    if user_id:
        filter_["user_id"] = user_id
    if keyword:
        filter_["keyword"] = keyword
    if direction:
        filter_["direction"] = direction

    if not filter_:
        console.print(
            "[red]Error:[/red] At least one filter field is required "
            "(--user-id, --keyword, or --direction)."
        )
        raise typer.Exit(code=1)

    body: dict[str, object] = {
        "event_type": event_type,
        "filter": filter_,
    }
    if tag:
        body["tag"] = tag
    if webhook_id:
        body["webhook_id"] = webhook_id

    # Determine which auth was actually used
    effective_auth = "user" if _is_private_event(event_type) and auth == "auto" else auth
    if auth == "auto":
        effective_auth = "user" if _is_private_event(event_type) else "app"

    console.print("\n[bold]xchat subscriptions create[/bold]")
    console.print(f"  Event type : [cyan]{event_type}[/cyan]")
    if user_id:
        console.print(f"  User ID    : [cyan]{user_id}[/cyan]")
    if keyword:
        console.print(f"  Keyword    : [cyan]{keyword}[/cyan]")
    if direction:
        console.print(f"  Direction  : [cyan]{direction}[/cyan]")
    if tag:
        console.print(f"  Tag        : [cyan]{tag}[/cyan]")
    if webhook_id:
        console.print(f"  Webhook ID : [cyan]{webhook_id}[/cyan]")
    console.print(f"  Auth       : [dim]{effective_auth}[/dim]")
    console.print()

    try:
        resp = httpx.post(
            _SUBSCRIPTIONS_URL,
            headers=headers,
            json=body,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 201):
        data = resp.json()
        sub_id = (
            data.get("data", {}).get("subscription", {}).get("subscription_id")
            or data.get("data", {}).get("subscription_id")
            or data.get("data", {}).get("id", "")
        )
        console.print("[green]✓[/green] Subscription created.")
        if sub_id:
            console.print(f"  Subscription ID: [cyan]{sub_id}[/cyan]")
    elif resp.status_code == 401:
        if _is_private_event(event_type):
            console.print(
                "[red]Error 401:[/red] OAuth user token rejected. "
                "Run [cyan]xchat auth login[/cyan] to re-authenticate."
            )
        else:
            console.print("[red]Error 401:[/red] Check that XCHAT_BEARER_TOKEN is correct.")
        raise typer.Exit(code=1)
    elif resp.status_code == 403:
        console.print(
            "[red]Error 403:[/red] Your app may not have Activity API access. "
            "Check permissions at developer.x.com."
        )
        raise typer.Exit(code=1)
    else:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)


@app.command("list")
def list_subscriptions() -> None:
    """List current Activity API subscriptions (GET /2/activity/subscriptions)."""
    _load_dotenv()
    headers = _auth_headers("app", "")

    console.print("\n[bold]Current subscriptions[/bold]")
    try:
        resp = httpx.get(_SUBSCRIPTIONS_URL, headers=headers, timeout=30.0)
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not resp.is_success:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)

    data = resp.json()
    subs = data.get("data", [])
    if not subs:
        console.print("  No subscriptions found.")
        return

    for sub in subs:
        sub_id = sub.get("subscription_id") or sub.get("id", "?")
        event_type = sub.get("event_type", "?")
        tag = sub.get("tag", "")
        tag_str = f"  [dim]({tag})[/dim]" if tag else ""
        console.print(f"  [cyan]{sub_id}[/cyan]  {event_type}{tag_str}")


@app.command("delete")
def delete(
    subscription_id: str = typer.Argument(..., help="Subscription ID to delete"),
) -> None:
    """Delete an Activity API subscription (DELETE /2/activity/subscriptions/{id})."""
    _load_dotenv()
    headers = _auth_headers("app", "")

    console.print(f"\nDeleting subscription [cyan]{subscription_id}[/cyan]...")
    try:
        resp = httpx.delete(
            f"{_SUBSCRIPTIONS_URL}/{subscription_id}",
            headers=headers,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 204):
        console.print(f"[green]✓[/green] Subscription {subscription_id} deleted.")
    elif resp.status_code == 404:
        console.print(f"[yellow]Not found:[/yellow] Subscription {subscription_id} does not exist.")
        raise typer.Exit(code=1)
    else:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)


def _load_dotenv() -> None:
    env_file = Path(".env")
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass
