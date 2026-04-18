"""xchat webhook — manage X webhook registrations.

Webhooks are the delivery mechanism: X sends POST requests to your URL
when events occur. This is separate from Activity subscriptions, which
define *what* events you want to receive.

Typical flow:
  1. xchat webhook register --url https://bot.example.com/webhook
  2. xchat subscriptions create --user-id <bot_user_id> --event-type chat.received
  3. xchat run --transport webhook

Reference: https://docs.x.com/x-api/direct-messages/activity-stream
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import typer
from rich.console import Console

app = typer.Typer(help="Manage X webhook registrations (POST /2/webhooks)")
console = Console()

# X Webhooks API v2
_WEBHOOKS_URL = "https://api.x.com/2/webhooks"


def _bearer_headers() -> dict[str, str]:
    bearer_token = os.environ.get("XCHAT_BEARER_TOKEN", "")
    if not bearer_token:
        console.print(
            "[red]Error:[/red] XCHAT_BEARER_TOKEN is not set. "
            "The webhook API requires the app Bearer Token. "
            "Set it in .env or as an environment variable."
        )
        raise typer.Exit(code=1)
    return {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }


@app.command("register")
def register(
    url: str = typer.Option(..., "--url", help="Your public HTTPS webhook URL"),
) -> None:
    """Register a webhook URL with X (POST /2/webhooks).

    X will immediately send a CRC challenge GET request to this URL to
    verify ownership. Your server must be running and respond correctly.

    Prerequisites:
      - XCHAT_BEARER_TOKEN set (app Bearer Token)
      - URL must be publicly accessible HTTPS (not localhost)
      - Your webhook server must be running: xchat run --transport webhook

    After registering the webhook, create subscriptions to define what
    events you want to receive:
      xchat subscriptions create --user-id <bot_user_id> --event-type chat.received
    """
    _load_dotenv()
    headers = _bearer_headers()

    if "localhost" in url or "127.0.0.1" in url:
        console.print(
            "[yellow]Warning:[/yellow] Webhook URL contains localhost/127.0.0.1. "
            "X cannot reach local addresses. Use ngrok or Cloudflare Tunnel for local testing."
        )

    if not url.startswith("https://"):
        console.print("[red]Error:[/red] Webhook URL must be HTTPS. X rejects HTTP URLs.")
        raise typer.Exit(code=1)

    from urllib.parse import urlparse

    if urlparse(url).port is not None:
        console.print(
            "[red]Error:[/red] Webhook URL cannot include a port number. "
            "X requires a standard HTTPS URL without a port."
        )
        raise typer.Exit(code=1)

    console.print("\n[bold]xchat webhook register[/bold]")
    console.print(f"  URL: [cyan]{url}[/cyan]\n")

    try:
        resp = httpx.post(
            _WEBHOOKS_URL,
            headers=headers,
            json={"url": url},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 201):
        data = resp.json()
        webhook_id = data.get("data", {}).get("id") or data.get("id", "")
        console.print("[green]✓[/green] Webhook registered.")
        if webhook_id:
            console.print(f"  Webhook ID: [cyan]{webhook_id}[/cyan]")
        console.print()
        console.print(
            "X sent a CRC challenge to your URL — if your server responded correctly,\n"
            "the webhook is now active. Next step:\n"
            "  [cyan]xchat subscriptions create"
            " --user-id <bot_user_id> --event-type chat.received[/cyan]"
        )
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
def list_webhooks() -> None:
    """List registered webhooks (GET /2/webhooks)."""
    _load_dotenv()
    headers = _bearer_headers()

    console.print("\n[bold]Registered webhooks[/bold]")
    try:
        resp = httpx.get(_WEBHOOKS_URL, headers=headers, timeout=30.0)
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not resp.is_success:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)

    data = resp.json()
    webhooks = data.get("data", [])
    if not webhooks:
        console.print("  No webhooks registered.")
        return

    for wh in webhooks:
        wh_id = wh.get("id", "?")
        wh_url = wh.get("url", "?")
        wh_valid = wh.get("valid", "?")
        console.print(f"  [cyan]{wh_id}[/cyan]  {wh_url}  (valid: {wh_valid})")


@app.command("delete")
def delete(
    webhook_id: str = typer.Argument(..., help="Webhook ID to delete"),
) -> None:
    """Delete a registered webhook (DELETE /2/webhooks/{id})."""
    _load_dotenv()
    headers = _bearer_headers()

    console.print(f"\nDeleting webhook [cyan]{webhook_id}[/cyan]...")
    try:
        resp = httpx.delete(
            f"{_WEBHOOKS_URL}/{webhook_id}",
            headers=headers,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 204):
        console.print(f"[green]✓[/green] Webhook {webhook_id} deleted.")
    elif resp.status_code == 404:
        console.print(f"[yellow]Not found:[/yellow] Webhook {webhook_id} does not exist.")
        raise typer.Exit(code=1)
    else:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)


@app.command("validate")
def validate(
    webhook_id: str = typer.Argument(..., help="Webhook ID to validate (trigger CRC re-check)"),
) -> None:
    """Trigger a CRC re-validation for a registered webhook (PUT /2/webhooks/{id}).

    X will send a new CRC challenge to your webhook URL. Useful for:
      - Confirming your webhook is still reachable after a deployment
      - Re-validating after changing your consumer secret
      - Debugging CRC failures
    """
    _load_dotenv()
    headers = _bearer_headers()

    console.print(f"\nValidating webhook [cyan]{webhook_id}[/cyan] (triggering CRC challenge)...")
    try:
        resp = httpx.put(
            f"{_WEBHOOKS_URL}/{webhook_id}",
            headers=headers,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 204):
        console.print(f"[green]✓[/green] CRC challenge sent to webhook {webhook_id}.")
        console.print("  If your server responded correctly, the webhook is now validated.")
    elif resp.status_code == 404:
        console.print(f"[yellow]Not found:[/yellow] Webhook {webhook_id} does not exist.")
        raise typer.Exit(code=1)
    else:
        console.print(f"[red]Error {resp.status_code}:[/red] {resp.text[:300]}")
        raise typer.Exit(code=1)


@app.command("replay")
def replay(
    webhook_id: str = typer.Argument(..., help="Webhook ID to replay events for"),
    from_date: str = typer.Option(
        ...,
        "--from",
        help="Start of replay window, 12-digit UTC: yyyymmddhhmm (e.g. 202604170000)",
    ),
    to_date: str = typer.Option(
        ...,
        "--to",
        help="End of replay window, 12-digit UTC: yyyymmddhhmm (e.g. 202604172359)",
    ),
) -> None:
    """Replay webhook events from the last 24 hours (POST /2/webhooks/replay).

    X re-delivers events that were delivered or attempted in the given time window.
    Useful for recovering events missed during downtime.

    Time format: 12-digit UTC yyyymmddhhmm (NOT ISO 8601).
    Max window: 24 hours. Rate limit: 100 requests per 15 minutes.

    Example:
      xchat webhook replay 1234567890 --from 202604170000 --to 202604172359
    """
    _load_dotenv()
    headers = _bearer_headers()

    # Validate format (basic check)
    for label, value in (("--from", from_date), ("--to", to_date)):
        if not value.isdigit() or len(value) != 12:
            console.print(
                f"[red]Error:[/red] {label} must be 12 digits in yyyymmddhhmm format "
                f"(e.g. 202604170000), got: {value!r}"
            )
            raise typer.Exit(code=1)

    body = {
        "webhook_id": webhook_id,
        "from_date": from_date,
        "to_date": to_date,
    }

    console.print("\n[bold]xchat webhook replay[/bold]")
    console.print(f"  Webhook ID : [cyan]{webhook_id}[/cyan]")
    console.print(f"  From       : [cyan]{from_date}[/cyan]")
    console.print(f"  To         : [cyan]{to_date}[/cyan]\n")

    try:
        resp = httpx.post(
            f"{_WEBHOOKS_URL}/replay",
            headers=headers,
            json=body,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 201, 202):
        console.print("[green]✓[/green] Replay requested.")
        console.print(
            "  X will re-deliver matching events to your webhook. "
            "Check your event log for incoming events."
        )
    elif resp.status_code == 404:
        console.print(f"[yellow]Not found:[/yellow] Webhook {webhook_id} does not exist.")
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
