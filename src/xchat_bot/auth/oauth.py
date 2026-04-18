"""
OAuth 2.0 Authorization Code with PKCE flow for X Activity API.

This is the recommended authentication path for DM bots that need to send
replies on behalf of a user account.

Two separate credentials are used:
  1. App Bearer Token (XCHAT_BEARER_TOKEN)  — for reading the Activity Stream
  2. OAuth 2.0 user access token            — for sending DM replies

This module handles #2: the interactive browser-based OAuth 2.0 PKCE flow
that produces the user access token.

PKCE (Proof Key for Code Exchange) is required by X for public clients.
It prevents authorization code interception attacks without requiring a
client secret in the token exchange.

Reference: https://docs.x.com/resources/fundamentals/authentication/oauth-2-0/authorization-code

IMPORTANT: The redirect URI must use 127.0.0.1, not localhost.
X Developer Portal treats them as different origins.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import urllib.parse
import webbrowser

import httpx

# OAuth 2.0 endpoints (api.x.com)
AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"

# Default scopes for a DM bot.
# dm.write requires dm.read + tweet.read + users.read per official DM integration guide.
# offline.access is required to receive a refresh_token.
DEFAULT_SCOPES = "dm.read dm.write tweet.read users.read offline.access"


def _pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256 method).

    Returns:
        (code_verifier, code_challenge) — both URL-safe strings.
    """
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


async def _exchange_code(
    code: str,
    code_verifier: str,
    client_id: str,
    redirect_uri: str,
    client_secret: str | None = None,
) -> dict[str, str]:
    """Exchange an authorization code for access + refresh tokens.

    Args:
        code: The authorization code from the callback.
        code_verifier: The PKCE verifier generated before the auth request.
        client_id: OAuth 2.0 Client ID from X Developer Portal.
        redirect_uri: Must match the URI used in the authorization request.
        client_secret: OAuth 2.0 Client Secret (required for confidential clients).
                       Public clients (PKCE-only) may omit this.

    Returns:
        Token response dict containing access_token, refresh_token, scope, etc.

    Raises:
        httpx.HTTPStatusError: If the token exchange fails.
    """
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    # Confidential clients send client_secret in the request body.
    # Public clients (PKCE-only) omit it — the code_verifier is sufficient.
    if client_secret:
        payload["client_secret"] = client_secret

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


async def run_oauth_flow(
    client_id: str,
    redirect_uri: str = "http://127.0.0.1:7171/callback",
    scopes: str = DEFAULT_SCOPES,
    *,
    client_secret: str | None = None,
    open_browser: bool = True,
    timeout: float = 120.0,
) -> dict[str, str]:
    """Run the full OAuth 2.0 PKCE authorization flow.

    Starts a local callback server on 127.0.0.1, opens the browser for
    user authorization, captures the callback code, and exchanges it for
    access + refresh tokens.

    Args:
        client_id: OAuth 2.0 Client ID from X Developer Portal → your app →
                   Keys and tokens → OAuth 2.0 Client ID. This is DIFFERENT
                   from the API Key (consumer_key / XCHAT_CONSUMER_KEY).
        redirect_uri: Must use 127.0.0.1, not localhost. Must be registered
                      in X Developer Portal under your app's callback URLs.
        scopes: Space-separated OAuth 2.0 scopes.
                Default: "dm.read dm.write tweet.read users.read offline.access"
        open_browser: If True, open the browser automatically.
        timeout: Seconds to wait for user to complete authorization.

    Returns:
        Dict with at least: access_token, token_type, scope.
        Also contains refresh_token if offline.access scope was requested.

    Raises:
        TimeoutError: If the user doesn't authorize within timeout seconds.
        httpx.HTTPStatusError: If the token exchange request fails.
        ValueError: If the callback contains an error parameter.
    """
    parsed = urllib.parse.urlparse(redirect_uri)
    port = parsed.port or 7171
    callback_path = parsed.path or "/callback"

    # Generate PKCE pair and state nonce (CSRF protection)
    code_verifier, code_challenge = _pkce_pair()
    expected_state = secrets.token_urlsafe(16)

    # Build authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": expected_state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(auth_params)

    # Start local callback server to capture the authorization code
    code_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

    import uvicorn
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse

    callback_app = FastAPI()

    @callback_app.get(callback_path)
    async def callback(  # type: ignore[misc]
        code: str = Query(default=""),
        state: str = Query(default=""),
        error: str = Query(default=""),
    ) -> HTMLResponse:

        if not code_future.done():
            if error:
                code_future.set_exception(ValueError(f"Authorization denied: {error}"))
            elif state != expected_state:
                code_future.set_exception(ValueError("State mismatch — possible CSRF attack"))
            elif code:
                code_future.set_result(code)

        if error:
            body = f"<h2>Authorization failed</h2><p>{error}</p>"
        else:
            body = (
                "<h2>Authorization complete!</h2>"
                "<p>You can close this window and return to the terminal.</p>"
            )
        return HTMLResponse(f"<html><body>{body}</body></html>")

    config = uvicorn.Config(callback_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    print("\nOpening browser for X authorization...")
    print(f"If the browser doesn't open, visit:\n  {authorize_url}\n")
    if open_browser:
        webbrowser.open(authorize_url)

    try:
        code = await asyncio.wait_for(code_future, timeout=timeout)
    except TimeoutError as exc:
        server.should_exit = True
        raise TimeoutError(
            f"OAuth 2.0 authorization timed out after {timeout}s. "
            "The user did not complete authorization."
        ) from exc
    finally:
        server.should_exit = True
        await asyncio.sleep(0.1)
        server_task.cancel()

    return await _exchange_code(code, code_verifier, client_id, redirect_uri, client_secret)
