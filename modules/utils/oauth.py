"""OAuth utilities supporting Jira's 3-legged OAuth flow."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from urllib.parse import parse_qs, urlparse

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - fallback when zoneinfo unavailable
    ZoneInfo = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from requests_oauthlib import OAuth2Session
else:
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


import requests

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
            LOGGER.info(
                "Authorization code captured from callback",
                extra={
                    "event": "oauth_authorize_callback_success",
                    "slice_id": "07",
                },
            )
            response = "Authorization successful. You may close this window."
        else:
            OAuthCallbackHandler.error = params.get("error", ["unknown_error"])[0]
            LOGGER.error(
                "Authorization callback returned error",
                extra={
                    "event": "oauth_authorize_callback_error",
                    "error": OAuthCallbackHandler.error,
                    "slice_id": "07",
                },
            )
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


def _should_open_browser() -> bool:
    """Determine whether to launch the user's browser automatically."""

    toggle = os.environ.get("OAUTH_BROWSER_OPEN")
    if toggle is None:
        return True

    return toggle.strip().lower() not in {"0", "false", "no"}


def authorize_jira() -> dict:
    """Perform the initial Jira OAuth authorization flow and return the token."""
    config = load_config()
    auth_url = config["jira"].get("auth_url")
    audience = (
        os.environ.get("JIRA_AUDIENCE")
        or config["jira"].get("audience")
        or "api.atlassian.com"
    )

    session = _build_oauth_session(config)
    redirect_uri = config["jira"].get("redirect_uri")
    LOGGER.info(
        "Preparing Jira authorization request",
        extra={
            "event": "oauth_authorize_parameters",
            "audience": audience,
            "redirect_uri": redirect_uri,
            "slice_id": "07",
        },
    )

    authorization_url, _ = session.authorization_url(
        auth_url,
        audience=audience,
        prompt="consent",
    )

    LOGGER.info("Starting local HTTP server to capture Jira OAuth callback")
    parsed = urlparse(redirect_uri)
    server_address = (parsed.hostname or "localhost", int(parsed.port or 8080))
    httpd = HTTPServer(server_address, OAuthCallbackHandler)

    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    LOGGER.info(
        "Generated Jira authorization URL: %s",
        authorization_url,
        extra={
            "event": "oauth_authorize_url",
            "url": authorization_url,
            "slice_id": "07",
        },
    )

    print("\n1️⃣ Copy this authorization URL if needed:\n")
    print(authorization_url)

    if _should_open_browser():
        try:
            webbrowser.open(authorization_url)
            print("\n🔗 Opening browser for Jira login...")
        except Exception:
            print(
                "\n⚠️ Unable to open browser automatically. Please open this URL manually:\n"
            )
            print(authorization_url)
    else:
        print(
            "\n🌐 Automatic browser launch disabled by OAUTH_BROWSER_OPEN. Open the URL manually."
        )

    print(
        "\nIf you encounter an Atlassian 'trouble logging in' message or are redirected to "
        "home.atlassian.com, copy the URL you land on. If it contains '?code=XYZ', copy that "
        "code and run:\n\npython -m modules.utils.oauth complete <auth_code>\n"
    )

    try:
        while (
            OAuthCallbackHandler.auth_code is None
            and OAuthCallbackHandler.error is None
        ):
            time.sleep(0.2)
    except KeyboardInterrupt:  # pragma: no cover - interactive flow
        print(
            "\nAuthorization flow interrupted. If you obtained an authorization code, run:\n"
            "python -m modules.utils.oauth complete <auth_code>"
        )
        raise
    finally:
        httpd.shutdown()

    if OAuthCallbackHandler.error:
        LOGGER.error(
            "Authorization failed during callback",
            extra={
                "event": "oauth_authorize_callback_error",
                "error": OAuthCallbackHandler.error,
                "slice_id": "07",
            },
        )
        raise RuntimeError(f"Authorization failed: {OAuthCallbackHandler.error}")

    LOGGER.info("Authorization code received; exchanging for access token")
    verify_target = ssl_verify_path()
    token_url = config["jira"].get("token_url")
    client_id = os.environ.get("JIRA_CLIENT_ID")
    client_secret = os.environ.get("JIRA_SECRET")
    if not client_id:
        raise RuntimeError("Environment variable JIRA_CLIENT_ID is required")

    client_id_prefix = client_id[:4] if len(client_id) >= 4 else client_id[0]
    LOGGER.info("Exchanging authorization code for token at %s", token_url)
    LOGGER.debug("Using Basic Auth with client_id=%s***", client_id_prefix)

    attempts = 0
    max_attempts = 3
    authorization_code = OAuthCallbackHandler.auth_code or ""
    while True:
        attempts += 1
        try:
            if hasattr(session, "_client") and getattr(
                session._client, "redirect_uri", None
            ):
                LOGGER.debug(
                    "Redirect URI already set on session; omitting duplicate argument.",
                )
            diagnostic_payload = {
                "action": "token_exchange_request",
                "token_url": token_url,
                "client_id_prefix": f"{client_id_prefix}***",
                "audience": "api.atlassian.com",
                "redirect_uri_in_session": getattr(session, "redirect_uri", None),
                "redirect_uri_in_config": config["jira"].get("redirect_uri"),
                "authorization_code_prefix": (
                    f"{authorization_code[:6]}***" if authorization_code else None
                ),
                "attempt": attempts,
            }
            LOGGER.debug(diagnostic_payload)
            _write_oauth_debug_snapshot(diagnostic_payload)
            try:
                token = session.fetch_token(
                    token_url=token_url,
                    code=authorization_code,
                    auth=(client_id, client_secret),
                    include_client_id=False,
                    verify=str(verify_target) if verify_target else True,
                )
            except Exception as error:  # noqa: BLE001 - propagate rich context
                response = getattr(error, "response", None)
                if response is not None:
                    headers = dict(getattr(response, "headers", {}))
                    if "Authorization" in headers:
                        headers["Authorization"] = "***"
                    if "authorization" in headers:
                        headers["authorization"] = "***"
                    error_payload = {
                        "event": "oauth_token_exchange_http_error",
                        "status_code": getattr(response, "status_code", None),
                        "response_text": getattr(response, "text", ""),
                        "headers": headers,
                        "attempt": attempts,
                    }
                    LOGGER.error(error_payload)
                    _write_oauth_debug_snapshot({**diagnostic_payload, **error_payload})
                else:
                    error_payload = {
                        "event": "oauth_token_exchange_exception",
                        "error": str(error),
                        "attempt": attempts,
                    }
                    LOGGER.error(error_payload)
                    _write_oauth_debug_snapshot({**diagnostic_payload, **error_payload})
                raise
            success_payload = {
                "event": "oauth_token_exchange_success",
                "attempt": attempts,
            }
            LOGGER.debug(success_payload)
            _write_oauth_debug_snapshot({**diagnostic_payload, **success_payload})
            if attempts > 1:
                LOGGER.info(
                    "Token exchange succeeded after %s attempts",
                    attempts,
                    extra={
                        "event": "oauth_token_exchange_retry_success",
                        "attempts": attempts,
                        "slice_id": "07",
                    },
                )
            break
        except (
            Exception
        ) as error:  # noqa: BLE001 - propagate context for troubleshooting
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            should_retry = (
                response is not None
                and isinstance(status_code, int)
                and 500 <= status_code < 600
                and attempts < max_attempts
            )
            if should_retry:
                LOGGER.warning(
                    "Transient OAuth token exchange failure (status=%s); retrying %s/%s",
                    status_code,
                    attempts + 1,
                    max_attempts,
                    extra={
                        "event": "oauth_token_exchange_retry",
                        "status_code": status_code,
                        "attempt": attempts,
                        "slice_id": "07",
                    },
                )
                time.sleep(min(2 ** (attempts - 1), 4))
                continue

            if response is not None:
                body = None
                try:
                    body = response.text
                except Exception:  # noqa: BLE001 - best-effort logging
                    body = "<unable to read body>"
                LOGGER.error(
                    "OAuth token exchange failed",
                    extra={
                        "event": "oauth_token_exchange_failure",
                        "status_code": response.status_code,
                        "response_body": body,
                        "slice_id": "07",
                    },
                )
            else:
                LOGGER.error(
                    "OAuth token exchange raised unexpected error",
                    extra={
                        "event": "oauth_token_exchange_error",
                        "error": type(error).__name__,
                        "slice_id": "07",
                    },
                )
            raise

    save_token(token, config)
    return token


def _write_oauth_debug_snapshot(payload: dict) -> None:
    """Persist diagnostic payloads for OAuth troubleshooting."""

    try:
        tz = ZoneInfo("America/Phoenix") if ZoneInfo else timezone.utc
    except Exception:  # pragma: no cover - fallback if timezone unavailable
        tz = timezone.utc

    timestamp = datetime.now(tz).strftime("%Y%m%dT%H%M%S%f%z")
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = logs_dir / f"oauth_debug_{timestamp}.json"

    try:
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:  # noqa: BLE001 - diagnostics should not raise
        LOGGER.debug("Failed to write OAuth debug snapshot", exc_info=True)


def complete_authorization(auth_code: str) -> dict:
    """Exchange a manually retrieved authorization code for tokens."""

    config = load_config()
    client_id = os.environ.get("JIRA_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Environment variable JIRA_CLIENT_ID is required")

    client_secret = os.environ.get("JIRA_SECRET", "")
    token_url = config["jira"].get("token_url")
    redirect_uri = config["jira"].get("redirect_uri")
    audience = (
        os.environ.get("JIRA_AUDIENCE")
        or config["jira"].get("audience")
        or "api.atlassian.com"
    )

    verify_target = ssl_verify_path()
    verify = str(verify_target) if verify_target else True

    response = requests.post(
        token_url,
        json={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "audience": audience,
        },
        auth=(client_id, client_secret),
        verify=verify,
        timeout=30,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        body = None
        try:
            body = response.text
        except Exception:  # noqa: BLE001 - best-effort logging
            body = "<unable to read body>"
        LOGGER.error(
            "Manual token exchange failed",
            extra={
                "event": "oauth_manual_exchange_failure",
                "status_code": response.status_code,
                "response_body": body,
                "slice_id": "07",
            },
        )
        raise error
    tokens = response.json()

    token_path = save_token(tokens, config)
    print(f"✅ Authorization successful. Tokens saved to {token_path}")
    return tokens


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
    parser = argparse.ArgumentParser(description="Jira OAuth utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    authorize_parser = subparsers.add_parser(
        "authorize", help="Run the OAuth authorization flow"
    )
    authorize_parser.set_defaults(func=lambda _: authorize_jira())

    complete_parser = subparsers.add_parser(
        "complete", help="Exchange an authorization code for tokens"
    )
    complete_parser.add_argument("auth_code", help="Authorization code from Jira")
    complete_parser.set_defaults(
        func=lambda args: complete_authorization(args.auth_code)
    )

    cli_args = parser.parse_args()
    cli_args.func(cli_args)
