"""xchat dm — send DMs via documented X DM Manage API.

Useful for:
  - Verifying your OAuth token and DM permissions before running a bot
  - Sending a test message to confirm the reply pipeline works
  - Debugging "why isn't my bot replying?" by isolating the auth layer

Endpoints used (documented in X DM Manage API):
  POST /2/dm_conversations/{conversation_id}/messages
  POST /2/dm_conversations/with/{participant_id}/messages

Both require OAuth 2.0 user access token (XCHAT_USER_ACCESS_TOKEN).
App-only Bearer Token is not supported for DM sends.

Common failure reasons (from X DM integration guide):
  - Target user has DMs restricted to people they follow
  - Target user has blocked the bot account
  - Missing dm.write scope in OAuth token
  - App not approved for DM access
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import typer
from rich.console import Console

app = typer.Typer(help="Send DMs via documented X DM Manage API")
console = Console()

_DM_BY_CONVERSATION = "https://api.x.com/2/dm_conversations/{conversation_id}/messages"
_DM_BY_PARTICIPANT = "https://api.x.com/2/dm_conversations/with/{participant_id}/messages"


def _user_auth_headers() -> dict[str, str]:
    token = os.environ.get("XCHAT_USER_ACCESS_TOKEN", "")
    if not token:
        console.print(
            "[red]Error:[/red] XCHAT_USER_ACCESS_TOKEN is not set. "
            "Run [cyan]xchat auth login[/cyan] to obtain an OAuth 2.0 user token."
        )
        raise typer.Exit(code=1)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@app.command("send")
def send(
    text: str = typer.Argument(..., help="Message text to send"),
    conversation_id: str | None = typer.Option(
        None,
        "--conversation-id",
        "-c",
        help="DM conversation ID (use this or --participant-id)",
    ),
    participant_id: str | None = typer.Option(
        None,
        "--participant-id",
        "-p",
        help="Recipient X user ID — opens or reuses a 1:1 DM conversation",
    ),
) -> None:
    """Send a DM via the documented X DM Manage API.

    Requires XCHAT_USER_ACCESS_TOKEN (run xchat auth login first).

    Examples:
      # By conversation ID
      xchat dm send "hello" --conversation-id 1582103724607971328

      # By participant (opens or reuses a 1:1 DM)
      xchat dm send "hello" --participant-id 9876543210

    Common failures:
      401 — token expired or missing dm.write scope (re-run xchat auth login)
      403 — target user has DMs restricted or has blocked the bot
      404 — conversation not found
    """
    _load_dotenv()

    if not conversation_id and not participant_id:
        console.print(
            "[red]Error:[/red] Provide either --conversation-id or --participant-id."
        )
        raise typer.Exit(code=1)
    if conversation_id and participant_id:
        console.print(
            "[red]Error:[/red] Provide either --conversation-id or --participant-id, not both."
        )
        raise typer.Exit(code=1)

    headers = _user_auth_headers()

    if conversation_id:
        url = _DM_BY_CONVERSATION.format(conversation_id=conversation_id)
        target_label = f"conversation {conversation_id}"
    else:
        url = _DM_BY_PARTICIPANT.format(participant_id=participant_id)
        target_label = f"participant {participant_id}"

    console.print(f"\nSending DM to [cyan]{target_label}[/cyan]...")

    asyncio.run(_send(url, headers, text))


async def _send(url: str, headers: dict[str, str], text: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(url, headers=headers, json={"text": text})
        except httpx.HTTPError as exc:
            console.print(f"[red]Request failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

    if resp.status_code in (200, 201):
        data = resp.json()
        dm_id = data.get("data", {}).get("dm_conversation_id") or data.get("data", {}).get("id", "")
        console.print("[green]✓[/green] Message sent.")
        if dm_id:
            console.print(f"  Conversation ID: [cyan]{dm_id}[/cyan]")
    elif resp.status_code == 401:
        console.print(
            "[red]Error 401:[/red] Token rejected. "
            "Run [cyan]xchat auth login[/cyan] to re-authenticate. "
            "Ensure dm.write scope is included."
        )
        raise typer.Exit(code=1)
    elif resp.status_code == 403:
        console.print(
            "[red]Error 403:[/red] DM not allowed. "
            "Target user may have DMs restricted, or may have blocked this account."
        )
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
