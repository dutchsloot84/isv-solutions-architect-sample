"""OAuth utilities supporting Jira's 3-legged OAuth flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import webbrowser
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
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

from .helpers import (
    ensure_directory,
    load_config,
    project_root,
    resolve_path,
    ssl_verify_path,
)
from .logger import get_logger

LOGGER = get_logger(__name__)


def _phoenix_now() -> datetime:
    try:
        tz = ZoneInfo("America/Phoenix") if ZoneInfo else timezone.utc
    except Exception:  # pragma: no cover - fallback when timezone unavailable
        tz = timezone.utc
    return datetime.now(tz)


def _phoenix_timestamp() -> str:
    return _phoenix_now().strftime("%Y%m%dT%H%M%S%f%z")


def _resolve_requested_scopes(config: dict) -> list[str]:
    raw_scope = (
        os.environ.get("JIRA_SCOPES")
        or os.environ.get("JIRA_API_SCOPE")
        or config.get("jira", {}).get("api_scope")
        or ""
    )
    if isinstance(raw_scope, str):
        scopes = [part for part in re.split(r"[\s,]+", raw_scope) if part]
    elif isinstance(raw_scope, Iterable):
        scopes = [str(part).strip() for part in raw_scope if str(part).strip()]
    else:
        scopes = []
    return scopes


def _scopes_to_oauthlib(scopes: Sequence[str]) -> list[str] | None:
    return list(scopes) if scopes else None


def _scopes_to_string(scopes: Sequence[str]) -> str:
    return " ".join(scopes)


_SENSITIVE_PATTERN = re.compile(
    r"(\"(?:client_secret|refresh_token)\"\s*:\s*\")([^\"\\\n]+)"
)


def _mask_sensitive(value: str | None) -> str | None:
    if not value:
        return value

    def _replacer(match: re.Match[str]) -> str:
        prefix = match.group(1)
        return f"{prefix}***"

    masked = _SENSITIVE_PATTERN.sub(_replacer, value)
    return masked


class OAuthDiagnosticRecorder:
    """Persist structured OAuth diagnostics for the current authorization run."""

    def __init__(
        self, scopes: Sequence[str], logs_dir: Path | str | None = None
    ) -> None:
        self._entries: list[dict[str, object]] = []
        base_dir = ensure_directory(logs_dir or Path("logs"))
        self._scopes = list(scopes)
        timestamp = _phoenix_timestamp()
        self.path = Path(base_dir) / f"oauth_diagnostics_{timestamp}.json"

    def log_attempt(
        self,
        *,
        scopes: Sequence[str] | None = None,
        status_code: int | None,
        error: str | None,
        response: str | None,
        retry_fallback: bool,
    ) -> None:
        entry = {
            "timestamp": _phoenix_now().isoformat(),
            "scopes": _scopes_to_string(
                list(scopes) if scopes is not None else self._scopes
            ),
            "status_code": status_code,
            "error": _mask_sensitive(error),
            "response": _mask_sensitive(response),
            "retry_fallback": retry_fallback,
        }
        self._entries.append(entry)
        try:
            self.path.write_text(
                json.dumps(self._entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001 - diagnostics should not raise
            LOGGER.debug("Failed to write OAuth diagnostic log", exc_info=True)


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


def _build_oauth_session(
    config: dict, token: Optional[dict] = None, scopes: Optional[Sequence[str]] = None
) -> OAuth2Session:
    """Create an OAuth2Session configured for Jira."""
    client_id = os.environ.get("JIRA_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Environment variable JIRA_CLIENT_ID is required")

    redirect_uri = config["jira"].get("redirect_uri")
    resolved_scopes = _scopes_to_oauthlib(
        scopes if scopes is not None else _resolve_requested_scopes(config)
    )
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
        scope=resolved_scopes,
        auto_refresh_url=token_url,
        auto_refresh_kwargs=extra,
        token_updater=lambda t: save_token(t, config),
    )


def _default_token_path() -> Path:
    """Return the default filesystem location for Jira OAuth tokens."""

    return project_root() / ".secrets" / "jira_token.json"


def _resolve_token_path(config: Optional[dict]) -> Path:
    cfg = config or load_config()
    configured_path = cfg.get("jira", {}).get("token_path")
    if configured_path:
        return resolve_path(configured_path)
    return _default_token_path()


def save_token(token: dict, config: Optional[dict] = None) -> Path:
    """Persist the OAuth token to disk."""
    token_path = _resolve_token_path(config)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(token)
    metadata: dict[str, str] = dict(payload.get("_metadata", {}))
    metadata["saved_at"] = _phoenix_now().isoformat()
    scope_value = token.get("scope")
    scopes: list[str] = []
    if isinstance(scope_value, str):
        scopes = [part for part in scope_value.split() if part]
    elif isinstance(scope_value, Iterable):
        scopes = [str(part).strip() for part in scope_value if str(part).strip()]
    if not scopes and config is not None:
        scopes = _resolve_requested_scopes(config)
    if scopes:
        metadata["scopes"] = _scopes_to_string(scopes)
    payload["_metadata"] = metadata
    with token_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    LOGGER.info("OAuth token saved to %s", token_path)
    return token_path


def _load_token(config: dict) -> Optional[dict]:
    configured_path = config.get("jira", {}).get("token_path")
    token_path = (
        resolve_path(configured_path) if configured_path else _default_token_path()
    )
    if not token_path.exists():
        return None
    with token_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def token_is_valid(token: dict) -> bool:
    """Return True when the token is present and not close to expiry."""

    expires_at = token.get("expires_at")
    if not expires_at:
        return False

    try:
        expiry = datetime.fromtimestamp(float(expires_at), tz=timezone.utc)
    except (TypeError, ValueError):
        return False

    buffer = timedelta(minutes=5)
    return datetime.now(timezone.utc) < (expiry - buffer)


def _should_open_browser() -> bool:
    """Determine whether to launch the user's browser automatically."""

    toggle = os.environ.get("OAUTH_BROWSER_OPEN")
    if toggle is None:
        return True

    return toggle.strip().lower() not in {"0", "false", "no"}


def authorize_jira() -> dict:
    """Perform the initial Jira OAuth authorization flow and return the token."""
    config = load_config()
    existing_token = _load_token(config)
    if existing_token and token_is_valid(existing_token):
        print("✅ Existing Jira access token is still valid.")
        LOGGER.info(
            "Existing Jira access token is valid; skipping authorization",
            extra={"event": "oauth_authorize_skip", "slice_id": "07"},
        )
        return existing_token

    auth_url = config["jira"].get("auth_url")
    audience = (
        os.environ.get("JIRA_AUDIENCE")
        or config["jira"].get("audience")
        or "api.atlassian.com"
    )

    requested_scopes = _resolve_requested_scopes(config)
    normalized_scopes = _scopes_to_oauthlib(requested_scopes) or []
    session = _build_oauth_session(config, scopes=requested_scopes)
    current_scopes = list(requested_scopes)
    offline_scope = "offline_access"
    using_fallback_scopes = False
    offline_requested = any(scope.lower() == offline_scope for scope in current_scopes)

    logs_dir_setting = config.get("paths", {}).get("logs_dir")
    logs_dir_path = (
        resolve_path(logs_dir_setting) if logs_dir_setting else project_root() / "logs"
    )

    scope_diagnostics = {
        "event": "oauth_scope_normalization",
        "requested_scopes": requested_scopes,
        "normalized_scopes": normalized_scopes,
        "session_scope": getattr(session, "scope", None),
    }
    LOGGER.debug(scope_diagnostics)
    _write_scope_normalization_log(logs_dir_path, scope_diagnostics)

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

    diagnostic_recorder = OAuthDiagnosticRecorder(current_scopes, logs_dir_path)

    start_time = time.monotonic()
    fallback_notified = False

    try:
        while (
            OAuthCallbackHandler.auth_code is None
            and OAuthCallbackHandler.error is None
        ):
            time.sleep(0.2)
            if not fallback_notified and time.monotonic() - start_time > 30:
                fallback_notified = True
                LOGGER.warning(
                    "⚠️ Did not receive an authorization callback automatically.",
                    extra={
                        "event": "oauth_authorize_callback_timeout",
                        "slice_id": "07",
                    },
                )
                print("\n⚠️ Did not receive an authorization callback automatically.")
                print(
                    "If your browser did not redirect, copy the code from the URL and run:"
                )
                print("python -m modules.utils.oauth complete <auth_code>")
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
                "scopes": _scopes_to_string(current_scopes),
                "using_fallback_scopes": using_fallback_scopes,
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
                    scope=_scopes_to_oauthlib(current_scopes),
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
            diagnostic_recorder.log_attempt(
                scopes=current_scopes,
                status_code=200,
                error=None,
                response="success",
                retry_fallback=using_fallback_scopes,
            )
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
            status_code_value = status_code if isinstance(status_code, int) else None
            response_body = None
            if response is not None:
                try:
                    response_body = response.text
                except Exception:  # noqa: BLE001 - best-effort logging
                    response_body = "<unable to read body>"
            error_text = str(error)

            fallback_candidate = (
                offline_requested
                and not using_fallback_scopes
                and (
                    (status_code_value in {401, 403})
                    or (
                        isinstance(response_body, str)
                        and "access_denied" in response_body.lower()
                    )
                    or ("access_denied" in error_text.lower())
                )
            )

            diagnostic_recorder.log_attempt(
                scopes=current_scopes,
                status_code=status_code_value,
                error=error_text,
                response=response_body,
                retry_fallback=fallback_candidate,
            )

            if fallback_candidate:
                fallback_scopes = [
                    scope for scope in current_scopes if scope.lower() != offline_scope
                ]
                if not fallback_scopes:
                    fallback_scopes = [
                        scope
                        for scope in requested_scopes
                        if scope.lower() != offline_scope
                    ]
                current_scopes = fallback_scopes
                using_fallback_scopes = True
                LOGGER.warning(
                    "⚠️ Atlassian rejected 'offline_access' scope — falling back to short-lived tokens.",
                    extra={
                        "event": "oauth_offline_scope_fallback",
                        "slice_id": "07",
                    },
                )
                print(
                    "\n⚠️ Atlassian rejected 'offline_access' scope — falling back to short-lived tokens.\n"
                )
                session = _build_oauth_session(config, scopes=current_scopes)
                continue

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
                LOGGER.error(
                    "OAuth token exchange failed",
                    extra={
                        "event": "oauth_token_exchange_failure",
                        "status_code": response.status_code,
                        "response_body": response_body,
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

    if "expires_at" not in token and "expires_in" in token:
        try:
            token["expires_at"] = time.time() + float(token["expires_in"])
        except (TypeError, ValueError):
            LOGGER.debug("Unable to derive expires_at from expires_in", exc_info=True)

    token_path = save_token(token, config)
    OAuthCallbackHandler.auth_code = None
    OAuthCallbackHandler.error = None
    LOGGER.info(
        "✅ Access token successfully retrieved and saved to %s",
        token_path,
        extra={"event": "oauth_token_exchange_complete", "slice_id": "07"},
    )
    print("\n🎉 Jira authorization complete! Token saved securely for future use.")
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


def _write_scope_normalization_log(base_dir: Path, payload: dict) -> None:
    """Persist structured diagnostics for scope normalization."""

    try:
        directory = ensure_directory(base_dir)
        path = directory / f"oauth_scope_normalization_{_phoenix_timestamp()}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 - diagnostics should not raise
        LOGGER.debug("Failed to write OAuth scope normalization log", exc_info=True)


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

    if "expires_at" not in tokens and "expires_in" in tokens:
        try:
            tokens["expires_at"] = time.time() + float(tokens["expires_in"])
        except (TypeError, ValueError):
            LOGGER.debug("Unable to derive expires_at from expires_in", exc_info=True)

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
