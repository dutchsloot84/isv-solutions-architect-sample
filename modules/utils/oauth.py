"""OAuth utilities supporting Jira's 3-legged OAuth flow."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

try:
    from requests_oauthlib import OAuth2Session
except ImportError:
    import requests

    class OAuth2Session:  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            self.token = kwargs.get("token")
            self.verify = kwargs.get("verify")
            self._session = requests.Session()
            self.token_updater = kwargs.get("token_updater")

        def authorization_url(self, *args, **kwargs):
            raise RuntimeError(
                "requests_oauthlib is required for the authorization flow. Install the dependency to continue."
            )

        def fetch_token(self, *args, **kwargs):
            raise RuntimeError(
                "requests_oauthlib is required for the authorization flow. Install the dependency to continue."
            )

        def refresh_token(self, *args, **kwargs):
            raise RuntimeError(
                "Token refresh requires requests_oauthlib. Install the dependency to continue."
            )

        def get(self, url, **kwargs):
            return self._session.get(url, **kwargs)


from .helpers import load_config, resolve_path, ssl_verify_path
from .logger import get_logger

LOGGER = get_logger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the authorization code from the callback."""

    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(
        self,
    ) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        """Handle GET request and extract authorization code."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            response = "Authorization successful. You may close this window."
        else:
            OAuthCallbackHandler.error = params.get("error", ["unknown_error"])[0]
            response = "Authorization failed. Check the terminal for details."

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))

    def log_message(
        self, format: str, *args
    ) -> None:  # noqa: A003 - method signature required
        """Silence default HTTP server logging."""
        return


def _build_oauth_session(config: dict, token: Optional[dict] = None) -> OAuth2Session:
    """Create an OAuth2Session configured for Jira."""
    client_id = os.environ.get("JIRA_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Environment variable JIRA_CLIENT_ID is required")

    redirect_uri = config["jira"].get("redirect_uri")
    scope = config["jira"].get("api_scope")
    token_url = config["jira"].get("token_url")

    secret = os.environ.get("JIRA_SECRET", "")
    extra = {
        "client_id": client_id,
        "client_secret": secret,
    }

    return OAuth2Session(
        client_id=client_id,
        token=token,
        redirect_uri=redirect_uri,
        scope=scope,
        auto_refresh_url=token_url,
        auto_refresh_kwargs=extra,
        token_updater=lambda t: save_token(t, config),
    )


def save_token(token: dict, config: Optional[dict] = None) -> Path:
    """Persist the OAuth token to disk."""
    cfg = config or load_config()
    token_path = resolve_path(cfg["jira"].get("token_path", "~/.jira_token.json"))
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with token_path.open("w", encoding="utf-8") as handle:
        json.dump(token, handle)
    LOGGER.info("OAuth token saved to disk")
    return token_path


def _load_token(config: dict) -> Optional[dict]:
    token_path = resolve_path(config["jira"].get("token_path", "~/.jira_token.json"))
    if not token_path.exists():
        return None
    with token_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def authorize_jira() -> dict:
    """Perform the initial Jira OAuth authorization flow and return the token."""
    config = load_config()
    base_url = config["jira"].get("base_url")
    auth_url = config["jira"].get("auth_url")

    session = _build_oauth_session(config)
    authorization_url, _ = session.authorization_url(
        auth_url,
        audience=f"{base_url}/",
        prompt="consent",
    )

    LOGGER.info("Starting local HTTP server to capture Jira OAuth callback")
    redirect_uri = config["jira"].get("redirect_uri")
    parsed = urlparse(redirect_uri)
    server_address = (parsed.hostname or "localhost", int(parsed.port or 8080))
    httpd = HTTPServer(server_address, OAuthCallbackHandler)

    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    LOGGER.info(
        "Open the following URL in a browser to authorize access: %s",
        authorization_url,
    )

    while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.error is None:
        pass  # Busy-wait; kept simple for CLI scenario

    httpd.shutdown()

    if OAuthCallbackHandler.error:
        raise RuntimeError(f"Authorization failed: {OAuthCallbackHandler.error}")

    LOGGER.info("Authorization code received; exchanging for access token")
    verify_target = ssl_verify_path()
    token = session.fetch_token(
        token_url=config["jira"].get("token_url"),
        code=OAuthCallbackHandler.auth_code,
        client_secret=os.environ.get("JIRA_SECRET"),
        include_client_id=True,
        verify=str(verify_target) if verify_target else True,
    )

    save_token(token, config)
    return token


def get_jira_session() -> OAuth2Session:
    """Return an authenticated OAuth2 session for Jira."""
    config = load_config()
    token = _load_token(config)

    if not token:
        raise RuntimeError("No OAuth token found. Run the authorize_jira flow first.")

    session = _build_oauth_session(config, token=token)

    # Ensure token refresh using corporate certificate
    verify_path = ssl_verify_path()
    if not verify_path:
        LOGGER.warning(
            "SSL_CERT_PATH is not set; HTTPS requests may fail certificate validation."
        )

    def _token_updater(new_token: dict) -> None:
        LOGGER.info(
            "OAuth token updated",
            extra={"event": "token_refresh_write", "slice_id": "07"},
        )
        save_token(new_token, config)

    session.token_updater = _token_updater
    session.verify = str(verify_path) if verify_path else True

    # Attempt to refresh token if required
    if _token_expired(session.token):
        _refresh_token(
            session,
            config,
            verify=str(verify_path) if verify_path else True,
        )

    return session


def _token_expired(token: Optional[dict], *, leeway: int = 60) -> bool:
    """Determine whether the token is expired or close to expiring."""

    if not token:
        return True

    expires_at = token.get("expires_at")
    if expires_at is not None:
        try:
            return float(expires_at) <= time.time() + leeway
        except (TypeError, ValueError):
            return True

    expires_in = token.get("expires_in")
    if expires_in is not None:
        try:
            return float(expires_in) <= leeway
        except (TypeError, ValueError):
            return True

    return False


def _refresh_token(
    session: OAuth2Session,
    config: dict,
    *,
    verify: bool | str,
) -> None:
    """Refresh the OAuth token and persist the new credentials."""

    LOGGER.info(
        "Refreshing OAuth token due to expiry",
        extra={"event": "token_refresh", "slice_id": "07"},
    )
    try:
        refreshed = session.refresh_token(
            config["jira"].get("token_url"),
            client_id=os.environ.get("JIRA_CLIENT_ID"),
            client_secret=os.environ.get("JIRA_SECRET"),
            verify=verify,
        )
    except Exception as error:  # noqa: BLE001 - propagate friendly context
        LOGGER.error(
            "OAuth token refresh failed",
            extra={
                "event": "token_refresh_failure",
                "error": type(error).__name__,
                "slice_id": "07",
            },
        )
        raise

    if isinstance(refreshed, dict):
        save_token(refreshed, config)
        session.token = refreshed

    LOGGER.info(
        "OAuth token refresh completed",
        extra={"event": "token_refresh_success", "slice_id": "07"},
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Jira OAuth utilities")
    parser.add_argument(
        "command",
        choices=["authorize"],
        help="Run the OAuth authorization flow",
    )

    args = parser.parse_args()
    if args.command == "authorize":
        authorize_jira()
