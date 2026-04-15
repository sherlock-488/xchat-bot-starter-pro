"""xchat subscriptions — manage X Activity API subscriptions.

Activity subscriptions define *what* events your app receives. They are
separate from webhook registration (which defines *where* events are sent).

A subscription specifies:
  - event_type: e.g. "chat.received", "chat.sent"
  - Optional: filter, tag, webhook_id

Typical flow:
  1. xchat webhook register --url https://bot.example.com/webhook
  2. xchat subscriptions create --event-type chat.received
  3. xchat run --transport webhook

For Activity Stream mode (no webhook), subscriptions are still needed
to tell X which events to include in your stream.

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


def _bearer_headers() -> dict[str, str]:
    bearer_token = os.environ.get("XCHAT_BEARER_TOKEN", "")
    if not bearer_token:
        console.print(
            "[red]Error:[/red] XCHAT_BEARER_TOKEN is not set. "
            "The subscriptions API requires the app Bearer Token. "
            "Set it in .env or as an environment variable."
        )
        raise typer.Exit(code=1)
    return {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }


@app.command("create")
def create(
    event_type: str = typer.Option(
        "chat.received",
        "--event-type",
        help="Event type to subscribe to (e.g. chat.received, chat.sent)",
    ),
    user_id: str = typer.Option(
        ...,
        "--user-id",
        help=(
            "Your bot's X user ID (numeric). Required by the filter field. "
            "Find it at: https://developer.x.com/en/docs/twitter-api/users/lookup/api-reference"
        ),
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
) -> None:
    """Create an Activity API subscription (POST /2/activity/subscriptions).

    This tells X which event types to deliver to your bot. The filter.user_id
    field is required by the API to scope events to your bot account.

    Common event types:
      chat.received          — incoming DM (the main one for bots)
      chat.sent              — outgoing DM confirmation
      chat.conversation_join — joined a conversation

    Prerequisites:
      - XCHAT_BEARER_TOKEN set (app Bearer Token)
      - For webhook mode: register a webhook first with:
          xchat webhook register --url https://...

    Example:
      xchat subscriptions create --user-id 123456789 --event-type chat.received
    """
    _load_dotenv()
    headers = _bearer_headers()

    body: dict[str, object] = {
        "event_type": event_type,
        "filter": {"user_id": user_id},
    }
    if tag:
        body["tag"] = tag
    if webhook_id:
        body["webhook_id"] = webhook_id

    console.print("\n[bold]xchat subscriptions create[/bold]")
    console.print(f"  Event type : [cyan]{event_type}[/cyan]")
    console.print(f"  User ID    : [cyan]{user_id}[/cyan]")
    if tag:
        console.print(f"  Tag        : [cyan]{tag}[/cyan]")
    if webhook_id:
        console.print(f"  Webhook ID : [cyan]{webhook_id}[/cyan]")
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
        # Official response uses subscription_id, fall back to id for compatibility
        sub_id = (
            data.get("data", {}).get("subscription_id")
            or data.get("data", {}).get("id")
            or data.get("subscription_id")
            or data.get("id", "")
        )
        console.print("[green]✓[/green] Subscription created.")
        if sub_id:
            console.print(f"  Subscription ID: [cyan]{sub_id}[/cyan]")
    elif resp.status_code == 401:
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
    headers = _bearer_headers()

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
    headers = _bearer_headers()

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
