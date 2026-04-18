"""xchat inspect — parse and display fixture files."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def inspect(
    fixture: Path = typer.Argument(..., help="Path to .json or .jsonl fixture file"),
    decrypt: bool = typer.Option(False, "--decrypt", help="Attempt to decrypt encrypted payloads"),
    state_file: Path = typer.Option(
        Path("state.json"), "--state-file", help="Path to state.json for real decryption"
    ),
    crypto_mode: str = typer.Option("stub", "--crypto", help="Crypto mode: stub or real"),
) -> None:
    """Parse and display a fixture file.

    Shows the normalized event structure for each event in the file.
    Useful for understanding payload shapes and testing your normalizer.

    Examples:
        xchat inspect tests/fixtures/chat_received_observed_xchat.json
        xchat inspect tests/fixtures/batch.jsonl --decrypt
    """
    from xchat_bot.crypto.real import RealCrypto
    from xchat_bot.crypto.stub import StubCrypto
    from xchat_bot.events.normalizer import EventNormalizer

    if not fixture.exists():
        console.print(f"[red]File not found:[/red] {fixture}")
        raise typer.Exit(code=1)

    normalizer = EventNormalizer()

    if decrypt:
        if crypto_mode == "real":
            try:
                crypto = RealCrypto(state_file)
            except FileNotFoundError as exc:
                console.print(f"[red]Crypto error:[/red] {exc}")
                raise typer.Exit(code=1) from exc
        else:
            crypto = StubCrypto()
    else:
        crypto = None

    # Load events
    events_raw: list[dict[str, object]] = []
    content = fixture.read_text(encoding="utf-8")

    if fixture.suffix == ".jsonl":
        for line in content.splitlines():
            line = line.strip()
            if line:
                events_raw.append(json.loads(line))
    else:
        data = json.loads(content)
        if isinstance(data, list):
            events_raw = data
        else:
            events_raw = [data]

    console.print(f"\n[bold]xchat inspect[/bold] — {fixture} ({len(events_raw)} event(s))\n")

    for i, raw in enumerate(events_raw):
        event = normalizer.normalize(raw)

        if decrypt and crypto:
            enc = event.encrypted
            if enc:
                payload = enc.encoded_event or enc.encrypted_content or ""
                if payload:
                    result = crypto.decrypt(
                        encoded_event=payload,
                        encrypted_conversation_key=enc.encrypted_conversation_key,
                    )
                    event = event.model_copy(
                        update={
                            "plaintext": result.plaintext,
                            "is_stub": result.mode == "stub",
                            "decrypt_notes": result.notes,
                        }
                    )

        info_lines = [
            f"[bold]event_id:[/bold]       {event.event_id}",
            f"[bold]event_type:[/bold]     {event.event_type}",
            f"[bold]schema_source:[/bold]  {event.schema_source}",
            f"[bold]conversation_id:[/bold] {event.conversation_id or '—'}",
            f"[bold]sender_id:[/bold]      {event.sender_id or '—'}",
            f"[bold]for_user_id:[/bold]    {event.for_user_id or '—'}",
            f"[bold]is_stub:[/bold]        {event.is_stub}",
        ]
        if event.plaintext:
            info_lines.append(f"[bold]plaintext:[/bold]      [green]{event.plaintext!r}[/green]")
        if event.decrypt_notes:
            info_lines.append(f"[bold]decrypt_notes:[/bold]  [dim]{event.decrypt_notes}[/dim]")

        console.print(
            Panel(
                "\n".join(info_lines),
                title=f"Event {i + 1}",
                border_style="blue",
            )
        )

    console.print()
