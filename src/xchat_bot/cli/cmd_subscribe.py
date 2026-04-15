"""xchat subscribe — manage X Activity API subscriptions."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
from rich.console import Console

console = Console()

# X Activity API v2 subscription endpoints.
# Reference: https://docs.x.com/x-api/direct-messages/activity-stream
_SUBSCRIPTIONS_URL = "https://api.x.com/2/activity/subscriptions"


def subscribe(
    url: str = typer.Option(..., "--url", help="Your public HTTPS webhook URL"),
    list_subs: bool = typer.Option(
        False, "--list", help="List current subscriptions instead of creating one"
    ),
    delete_id: str | None = typer.Option(
        None, "--delete", metavar="SUBSCRIPTION_ID", help="Delete a subscription by ID"
    ),
) -> None:
    """Manage X Activity API subscriptions.

    Uses the app Bearer Token (XCHAT_BEARER_TOKEN) to call
    POST /2/activity/subscriptions.

    Prerequisites:
      - XCHAT_BEARER_TOKEN set (app Bearer Token from X Developer Portal)
      - URL must be publicly accessible HTTPS (not localhost)
      - Your webhook server must be running (X will send a CRC challenge)

    Examples::

        # Register a webhook URL
        xchat subscribe --url https://bot.example.com/webhook

        # List current subscriptions
        xchat subscribe --url "" --list

        # Delete a subscription
        xchat subscribe --url "" --delete sub_123abc
    """
    _load_dotenv()

    bearer_token = os.environ.get("XCHAT_BEARER_TOKEN", "")
    if not bearer_token:
        console.print(
            "[red]Error:[/red] XCHAT_BEARER_TOKEN is not set. "
            "The subscription API requires the app Bearer Token. "
            "Set it in .env or as an environment variable."
        )
        raise typer.Exit(code=1)

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    if list_subs:
        _list_subscriptions(headers)
        return

    if delete_id:
        _delete_subscription(delete_id, headers)
        return

    # Create subscription
    if "localhost" in url or "127.0.0.1" in url:
        console.print(
            "[yellow]Warning:[/yellow] Webhook URL contains localhost/127.0.0.1. "
            "X cannot reach local addresses. Use ngrok or Cloudflare Tunnel for testing."
        )

    if not url.startswith("https://"):
        console.print(
            "[yellow]Warning:[/yellow] Webhook URL should be HTTPS. "
            "X will reject HTTP URLs."
        )
        raise typer.Exit(code=1)

    console.print("\n[bold]xchat subscribe[/bold]")
    console.print(f"  Registering: [cyan]{url}[/cyan]")
    console.print()

    try:
        resp = httpx.post(
            _SUBSCRIPTIONS_URL,
            headers=headers,
            json={"url": url},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 201):
        data = resp.json()
        sub_id = data.get("data", {}).get("id") or data.get("id", "")
        console.print("[green]✓[/green] Subscription created.")
        if sub_id:
            console.print(f"  Subscription ID: [cyan]{sub_id}[/cyan]")
        console.print()
        console.print(
            "X will now send a CRC challenge to your webhook URL. "
            "Make sure your server is running and responding correctly."
        )
    elif resp.status_code == 401:
        console.print(
            "[red]Error 401:[/red] Authentication failed. "
            "Check that XCHAT_BEARER_TOKEN is correct."
        )
        raise typer.Exit(code=1)
    elif resp.status_code == 403:
        console.print(
            "[red]Error 403:[/red] Forbidden. "
            "Your app may not have Activity API access. "
            "Check your app permissions in X Developer Portal."
        )
        raise typer.Exit(code=1)
    else:
        console.print(
            f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}"
        )
        raise typer.Exit(code=1)


def _list_subscriptions(headers: dict[str, str]) -> None:
    """List current Activity API subscriptions."""
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
        sub_id = sub.get("id", "?")
        sub_url = sub.get("url", "?")
        console.print(f"  [cyan]{sub_id}[/cyan]  {sub_url}")


def _delete_subscription(sub_id: str, headers: dict[str, str]) -> None:
    """Delete a subscription by ID."""
    console.print(f"\nDeleting subscription [cyan]{sub_id}[/cyan]...")
    try:
        resp = httpx.delete(
            f"{_SUBSCRIPTIONS_URL}/{sub_id}",
            headers=headers,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 204):
        console.print(f"[green]✓[/green] Subscription {sub_id} deleted.")
    elif resp.status_code == 404:
        console.print(f"[yellow]Not found:[/yellow] Subscription {sub_id} does not exist.")
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
