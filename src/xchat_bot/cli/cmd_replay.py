"""xchat replay — replay fixture files against webhook endpoints."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Replay fixture files against webhook endpoints")
console = Console()


@app.command("run")
def replay_run(
    fixture: Path = typer.Argument(..., help="Path to .json or .jsonl fixture file"),
    target: str = typer.Option(
        "http://127.0.0.1:8080/webhook", "--target", help="Target webhook URL"
    ),
    delay: float = typer.Option(0.1, "--delay", help="Delay between events (seconds)"),
    sign: bool = typer.Option(False, "--sign", help="Sign requests with consumer_secret"),
) -> None:
    """Replay events from a fixture file to a webhook endpoint.

    Useful for testing your bot against known event shapes.

    Examples:
        xchat replay run tests/fixtures/chat_received_official.json
        xchat replay run tests/fixtures/batch.jsonl --sign --target http://localhost:8080/webhook
    """
    from xchat_bot.webhook.signature import generate_signature

    events = _load_fixture(fixture)
    console.print(f"\n[bold]xchat replay run[/bold] — {len(events)} event(s) → {target}\n")

    consumer_secret = ""
    if sign:
        import os
        consumer_secret = os.getenv("XCHAT_CONSUMER_SECRET", "")
        if not consumer_secret:
            console.print("[red]--sign requires XCHAT_CONSUMER_SECRET to be set[/red]")
            raise typer.Exit(code=1)

    async def _run() -> None:
        import httpx
        results = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for event in events:
                payload = json.dumps(event).encode()
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if sign and consumer_secret:
                    headers["x-twitter-webhooks-signature"] = generate_signature(payload, consumer_secret)

                event_type = (
                    event.get("data", {}).get("event_type")
                    or event.get("event_type", "unknown")
                )
                try:
                    resp = await client.post(target, content=payload, headers=headers)
                    results.append({
                        "event_type": event_type,
                        "status": resp.status_code,
                        "ok": resp.is_success,
                        "error": None,
                    })
                except httpx.ConnectError as exc:
                    results.append({
                        "event_type": event_type,
                        "status": None,
                        "ok": False,
                        "error": f"Connection refused: {exc}",
                    })

                if delay > 0:
                    await asyncio.sleep(delay)

        return results

    results = asyncio.run(_run())

    table = Table(show_header=True)
    table.add_column("Event Type")
    table.add_column("Status")
    table.add_column("Result")

    ok_count = 0
    for r in results:
        ok = r["ok"]
        if ok:
            ok_count += 1
        table.add_row(
            str(r["event_type"]),
            str(r["status"] or "—"),
            "[green]OK[/green]" if ok else f"[red]FAIL: {r['error'] or r['status']}[/red]",
        )

    console.print(table)
    console.print(f"\n{ok_count}/{len(results)} events delivered successfully.")


@app.command("diff")
def replay_diff(
    fixture: Path = typer.Argument(..., help="Path to .json or .jsonl fixture file"),
    baseline: str = typer.Option(
        "http://127.0.0.1:8080/webhook", "--baseline", help="Baseline webhook URL"
    ),
    candidate: str = typer.Option(
        "http://127.0.0.1:8081/webhook", "--candidate", help="Candidate webhook URL"
    ),
) -> None:
    """Compare responses from two webhook handlers.

    Sends the same events to both handlers and shows differences.
    Useful for regression testing when refactoring bot logic.
    """
    events = _load_fixture(fixture)
    console.print(f"\n[bold]xchat replay diff[/bold] — {len(events)} event(s)\n")
    console.print(f"  Baseline:  {baseline}")
    console.print(f"  Candidate: {candidate}\n")

    async def _run() -> list[dict[str, object]]:
        import httpx
        results = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for event in events:
                payload = json.dumps(event).encode()
                headers = {"Content-Type": "application/json"}

                async def _post(url: str) -> tuple[int | None, str]:
                    try:
                        r = await client.post(url, content=payload, headers=headers)
                        return r.status_code, r.text[:200]
                    except Exception as exc:
                        return None, str(exc)

                b_status, b_body = await _post(baseline)
                c_status, c_body = await _post(candidate)
                identical = (b_status, b_body) == (c_status, c_body)

                results.append({
                    "event_type": event.get("data", {}).get("event_type") or event.get("event_type", "?"),
                    "baseline": f"{b_status} {b_body[:50]}",
                    "candidate": f"{c_status} {c_body[:50]}",
                    "identical": identical,
                })
        return results

    results = asyncio.run(_run())

    table = Table(show_header=True)
    table.add_column("Event Type")
    table.add_column("Baseline")
    table.add_column("Candidate")
    table.add_column("Match")

    for r in results:
        table.add_row(
            str(r["event_type"]),
            str(r["baseline"]),
            str(r["candidate"]),
            "[green]✓[/green]" if r["identical"] else "[red]✗ DIFF[/red]",
        )

    console.print(table)
    diffs = sum(1 for r in results if not r["identical"])
    if diffs:
        console.print(f"\n[red]{diffs} difference(s) found.[/red]")
    else:
        console.print("\n[green]All responses identical.[/green]")


@app.command("export")
def replay_export(
    server: str = typer.Option(
        "http://127.0.0.1:8080", "--server", help="Bot server base URL"
    ),
    output: Path = typer.Option(
        Path("recordings/export.jsonl"), "--output", help="Output JSONL file"
    ),
    no_scrub: bool = typer.Option(False, "--no-scrub", help="Skip PII scrubbing"),
) -> None:
    """Export events from a running bot server to a JSONL file.

    Requires the bot server to have an /api/events endpoint.
    """
    console.print(f"\n[bold]xchat replay export[/bold] — from {server}\n")
    console.print("[yellow]Note:[/yellow] Export endpoint requires xchat-playground server.")
    console.print("Use [cyan]xchat inspect[/cyan] for local fixture inspection.")


def _load_fixture(fixture: Path) -> list[dict[str, object]]:
    if not fixture.exists():
        console.print(f"[red]File not found:[/red] {fixture}")
        raise typer.Exit(code=1)

    content = fixture.read_text(encoding="utf-8")
    events: list[dict[str, object]] = []

    if fixture.suffix == ".jsonl":
        for line in content.splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
    else:
        data = json.loads(content)
        if isinstance(data, list):
            events = data
        else:
            events = [data]

    return events
