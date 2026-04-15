"""
OAuth 1.0a login flow for X Activity API.

Starts a local HTTP server to capture the OAuth callback, opens the browser
for user authorization, and exchanges the verifier for access tokens.

IMPORTANT: The redirect URI must use 127.0.0.1, not localhost.
X Developer Portal treats them as different origins.

Usage::

    from xchat_bot.auth.oauth import run_oauth_flow

    tokens = await run_oauth_flow(
        consumer_key="...",
        consumer_secret="...",
        redirect_uri="http://127.0.0.1:7171/callback",
    )
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import time
import urllib.parse
import webbrowser

import httpx

REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
AUTHORIZE_URL = "https://api.twitter.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"


def _oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    oauth_token: str = "",
    oauth_token_secret: str = "",
    extra_params: dict[str, str] | None = None,
) -> str:
    """Build OAuth 1.0a Authorization header."""
    nonce = secrets.token_hex(16)
    timestamp = str(int(time.time()))

    oauth_params: dict[str, str] = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_version": "1.0",
    }
    if oauth_token:
        oauth_params["oauth_token"] = oauth_token

    all_params = {**oauth_params, **(extra_params or {})}
    sorted_params = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        method.upper(),
        urllib.parse.quote(url, safe=""),
        urllib.parse.quote(sorted_params, safe=""),
    ])
    signing_key = (
        urllib.parse.quote(consumer_secret, safe="")
        + "&"
        + urllib.parse.quote(oauth_token_secret, safe="")
    )
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    oauth_params["oauth_signature"] = signature
    header_value = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return header_value


async def _get_request_token(
    consumer_key: str,
    consumer_secret: str,
    redirect_uri: str,
) -> tuple[str, str]:
    """Get OAuth request token from X."""
    auth_header = _oauth1_header(
        "POST",
        REQUEST_TOKEN_URL,
        consumer_key,
        consumer_secret,
        extra_params={"oauth_callback": redirect_uri},
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            REQUEST_TOKEN_URL,
            headers={"Authorization": auth_header},
            data={"oauth_callback": redirect_uri},
        )
        resp.raise_for_status()

    params = dict(urllib.parse.parse_qsl(resp.text))
    return params["oauth_token"], params["oauth_token_secret"]


async def _exchange_for_access_token(
    consumer_key: str,
    consumer_secret: str,
    oauth_token: str,
    oauth_token_secret: str,
    oauth_verifier: str,
) -> dict[str, str]:
    """Exchange verifier for access tokens."""
    auth_header = _oauth1_header(
        "POST",
        ACCESS_TOKEN_URL,
        consumer_key,
        consumer_secret,
        oauth_token=oauth_token,
        oauth_token_secret=oauth_token_secret,
        extra_params={"oauth_verifier": oauth_verifier},
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ACCESS_TOKEN_URL,
            headers={"Authorization": auth_header},
            data={"oauth_verifier": oauth_verifier},
        )
        resp.raise_for_status()

    return dict(urllib.parse.parse_qsl(resp.text))


async def run_oauth_flow(
    consumer_key: str,
    consumer_secret: str,
    redirect_uri: str = "http://127.0.0.1:7171/callback",
    *,
    open_browser: bool = True,
    timeout: float = 120.0,
) -> dict[str, str]:
    """Run the full OAuth 1.0a authorization flow.

    Starts a local server to capture the callback, opens the browser,
    and returns access tokens.

    Args:
        consumer_key: X app consumer key.
        consumer_secret: X app consumer secret.
        redirect_uri: Must use 127.0.0.1, not localhost.
        open_browser: If True, open browser automatically.
        timeout: Seconds to wait for user authorization.

    Returns:
        Dict with access_token, access_token_secret, user_id, screen_name.

    Raises:
        TimeoutError: If user doesn't authorize within timeout.
        httpx.HTTPStatusError: If X API returns an error.
    """
    # Parse port from redirect_uri
    parsed = urllib.parse.urlparse(redirect_uri)
    port = parsed.port or 7171
    callback_path = parsed.path or "/callback"

    # Step 1: Get request token
    oauth_token, oauth_token_secret = await _get_request_token(
        consumer_key, consumer_secret, redirect_uri
    )

    # Step 2: Build authorize URL
    authorize_url = f"{AUTHORIZE_URL}?oauth_token={oauth_token}"

    # Step 3: Start local callback server
    verifier_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    callback_app = FastAPI()

    @callback_app.get(callback_path)
    async def callback(oauth_verifier: str = "", oauth_token: str = "") -> HTMLResponse:  # type: ignore[misc]
        if not verifier_future.done():
            verifier_future.set_result(oauth_verifier)
        return HTMLResponse(
            "<html><body><h2>Authorization complete!</h2>"
            "<p>You can close this window and return to the terminal.</p></body></html>"
        )

    config = uvicorn.Config(callback_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Step 4: Open browser
    print("\nOpening browser for X authorization...")
    print(f"If the browser doesn't open, visit:\n  {authorize_url}\n")
    if open_browser:
        webbrowser.open(authorize_url)

    # Step 5: Wait for callback
    try:
        oauth_verifier = await asyncio.wait_for(verifier_future, timeout=timeout)
    except TimeoutError as exc:
        server.should_exit = True
        raise TimeoutError(
            f"OAuth authorization timed out after {timeout}s. "
            "The user did not complete authorization."
        ) from exc
    finally:
        server.should_exit = True
        await asyncio.sleep(0.1)
        server_task.cancel()

    # Step 6: Exchange for access tokens
    tokens = await _exchange_for_access_token(
        consumer_key,
        consumer_secret,
        oauth_token,
        oauth_token_secret,
        oauth_verifier,
    )
    return tokens
