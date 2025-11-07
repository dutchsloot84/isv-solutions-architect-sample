from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import requests

from modules.utils import oauth as oauth_utils


class DummyOAuthSession:
    """Capture parameters passed to the OAuth session during testing."""

    def __init__(self, failures: Optional[List[int]] = None) -> None:
        self.fetch_kwargs: Dict[str, Any] | None = None
        self.fetch_attempts = 0
        self.failures = failures or []

    def authorization_url(self, url: str, **kwargs: Any) -> tuple[str, str]:
        return url, "state-token"

    def fetch_token(self, *_, **kwargs: Any) -> Dict[str, Any]:
        self.fetch_attempts += 1
        self.fetch_kwargs = dict(kwargs)
        if self.failures:
            status = self.failures.pop(0)
            response = requests.Response()
            response.status_code = status
            response._content = b"server error"  # type: ignore[attr-defined]
            error = requests.HTTPError("server error")
            error.response = response  # type: ignore[assignment]
            raise error

        return {
            "access_token": "abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expires_at": time.time() + 3600,
        }


class DummyHTTPServer:
    def __init__(self, *_: Any) -> None:
        self.shutdown_called = False

    def serve_forever(self) -> None:  # pragma: no cover - thread target
        return

    def shutdown(self) -> None:
        self.shutdown_called = True


def test_token_exchange_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dummy_session = DummyOAuthSession(failures=[500])
    saved_token: Dict[str, Any] = {}

    monkeypatch.setenv("JIRA_CLIENT_ID", "abcd1234client")
    monkeypatch.setenv("JIRA_SECRET", "supersecret")
    monkeypatch.setenv("OAUTH_BROWSER_OPEN", "0")

    info_messages: list[str] = []
    original_info = oauth_utils.LOGGER.info

    def info_spy(msg: str, *args: Any, **kwargs: Any) -> Any:
        info_messages.append(str(msg))
        return original_info(msg, *args, **kwargs)

    monkeypatch.setattr(oauth_utils.LOGGER, "info", info_spy)

    monkeypatch.setattr(
        oauth_utils, "_build_oauth_session", lambda config: dummy_session
    )
    monkeypatch.setattr(oauth_utils, "ssl_verify_path", lambda: None)
    monkeypatch.setattr(oauth_utils, "HTTPServer", DummyHTTPServer)
    monkeypatch.setattr(oauth_utils.webbrowser, "open", lambda *_: True)

    def fake_save(token: Dict[str, Any], config: Dict[str, Any] | None = None) -> Path:
        saved_token.update(token)
        return tmp_path / "token.json"

    monkeypatch.setattr(oauth_utils, "save_token", fake_save)
    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "auth_url": "https://example.com/authorize",
                "token_url": "https://example.com/token",
                "redirect_uri": "http://localhost:8000/callback",
                "token_path": str(tmp_path / "token.json"),
                "api_scope": "read:me",
            }
        },
    )

    oauth_utils.OAuthCallbackHandler.auth_code = "auth-code-123"
    oauth_utils.OAuthCallbackHandler.error = None

    token = oauth_utils.authorize_jira()

    assert token["access_token"] == "abc"
    assert saved_token["access_token"] == "abc"
    assert dummy_session.fetch_kwargs is not None
    assert dummy_session.fetch_kwargs["auth"] == ("abcd1234client", "supersecret")
    assert dummy_session.fetch_kwargs["include_client_id"] is False
    assert "redirect_uri" not in dummy_session.fetch_kwargs
    assert dummy_session.fetch_kwargs["verify"] is True
    assert dummy_session.fetch_attempts == 2

    assert oauth_utils.OAuthCallbackHandler.auth_code is None
    assert oauth_utils.OAuthCallbackHandler.error is None

    basic_auth = requests.auth.HTTPBasicAuth(*dummy_session.fetch_kwargs["auth"])
    request = requests.Request("POST", "https://example.com")
    prepared = request.prepare()
    basic_auth(prepared)
    assert prepared.headers["Authorization"].startswith("Basic ")


def test_complete_authorization_uses_basic_auth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: Dict[str, Any] = {}

    monkeypatch.setenv("JIRA_CLIENT_ID", "abcd1234client")
    monkeypatch.setenv("JIRA_SECRET", "supersecret")

    monkeypatch.setattr(oauth_utils, "ssl_verify_path", lambda: None)
    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "token_url": "https://example.com/token",
                "redirect_uri": "http://localhost:8000/callback",
                "token_path": str(tmp_path / "token.json"),
                "audience": "api.atlassian.com",
            }
        },
    )

    def fake_post(url: str, json: Dict[str, Any], **kwargs: Any) -> requests.Response:
        captured["url"] = url
        captured["json"] = json
        captured.update(kwargs)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"access_token": "abc", "refresh_token": "refresh-456", "expires_in": 3600}'  # type: ignore[attr-defined]

        def _json() -> Dict[str, Any]:
            return {
                "access_token": "abc",
                "refresh_token": "refresh-456",
                "expires_in": 3600,
            }

        response.json = _json  # type: ignore[assignment]
        return response

    saved: Dict[str, Any] = {}

    def fake_save(token: Dict[str, Any], _: Dict[str, Any] | None = None) -> Path:
        saved.update(token)
        return tmp_path / "token.json"

    monkeypatch.setattr(oauth_utils.requests, "post", fake_post)
    monkeypatch.setattr(oauth_utils, "save_token", fake_save)

    tokens = oauth_utils.complete_authorization("auth-code-xyz")

    assert tokens["access_token"] == "abc"
    assert captured["auth"] == ("abcd1234client", "supersecret")
    assert captured["json"]["audience"] == "api.atlassian.com"
    basic_auth = requests.auth.HTTPBasicAuth(*captured["auth"])
    request = requests.Request("POST", captured["url"])
    prepared = request.prepare()
    basic_auth(prepared)
    assert prepared.headers["Authorization"].startswith("Basic ")


def test_authorize_jira_persists_token_and_logs_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dummy_session = DummyOAuthSession()
    token_path = tmp_path / ".secrets" / "jira_token.json"

    monkeypatch.setenv("JIRA_CLIENT_ID", "abcd1234client")
    monkeypatch.setenv("JIRA_SECRET", "supersecret")
    monkeypatch.setenv("OAUTH_BROWSER_OPEN", "0")

    info_messages: list[str] = []
    original_info = oauth_utils.LOGGER.info

    def info_spy(msg: str, *args: Any, **kwargs: Any) -> Any:
        info_messages.append(str(msg))
        return original_info(msg, *args, **kwargs)

    monkeypatch.setattr(oauth_utils.LOGGER, "info", info_spy)

    monkeypatch.setattr(
        oauth_utils, "_build_oauth_session", lambda config: dummy_session
    )
    monkeypatch.setattr(oauth_utils, "ssl_verify_path", lambda: None)
    monkeypatch.setattr(oauth_utils, "HTTPServer", DummyHTTPServer)
    monkeypatch.setattr(oauth_utils.webbrowser, "open", lambda *_: True)
    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "auth_url": "https://example.com/authorize",
                "token_url": "https://example.com/token",
                "redirect_uri": "http://localhost:8000/callback",
                "token_path": str(token_path),
                "api_scope": "read:me",
            }
        },
    )

    oauth_utils.OAuthCallbackHandler.auth_code = "auth-code-123"
    oauth_utils.OAuthCallbackHandler.error = None

    oauth_utils.authorize_jira()

    assert token_path.exists()
    data = json.loads(token_path.read_text(encoding="utf-8"))
    assert data["access_token"] == "abc"
    assert any(
        "✅ Access token successfully retrieved" in message for message in info_messages
    )


def test_authorize_jira_warns_when_refresh_token_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoRefreshSession(DummyOAuthSession):
        def fetch_token(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:  # type: ignore[override]
            super().fetch_token(*args, **kwargs)
            return {
                "access_token": "abc",
                "expires_in": 3600,
                "expires_at": time.time() + 3600,
            }

    dummy_session = NoRefreshSession()
    token_path = tmp_path / ".secrets" / "jira_token.json"

    monkeypatch.setenv("JIRA_CLIENT_ID", "abcd1234client")
    monkeypatch.setenv("JIRA_SECRET", "supersecret")
    monkeypatch.setenv("OAUTH_BROWSER_OPEN", "0")

    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "auth_url": "https://example.com/authorize",
                "token_url": "https://example.com/token",
                "redirect_uri": "http://localhost:8000/callback",
                "token_path": str(token_path),
                "api_scope": "read:me",
            }
        },
    )
    monkeypatch.setattr(
        oauth_utils, "_build_oauth_session", lambda config: dummy_session
    )
    monkeypatch.setattr(oauth_utils, "ssl_verify_path", lambda: None)
    monkeypatch.setattr(oauth_utils, "HTTPServer", DummyHTTPServer)
    monkeypatch.setattr(oauth_utils.webbrowser, "open", lambda *_: True)

    warnings: list[str] = []
    original_warning = oauth_utils.LOGGER.warning

    def warning_spy(msg: str, *args: Any, **kwargs: Any) -> Any:
        warnings.append(str(msg))
        return original_warning(msg, *args, **kwargs)

    monkeypatch.setattr(oauth_utils.LOGGER, "warning", warning_spy)

    oauth_utils.OAuthCallbackHandler.auth_code = "auth-code-123"
    oauth_utils.OAuthCallbackHandler.error = None

    oauth_utils.authorize_jira()

    assert any("No refresh_token received" in message for message in warnings)


def test_authorize_jira_skips_when_token_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token_path = tmp_path / ".secrets" / "jira_token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_payload = {
        "access_token": "existing",
        "refresh_token": "refresh",
        "expires_at": time.time() + 3600,
    }
    token_path.write_text(json.dumps(token_payload), encoding="utf-8")

    monkeypatch.setenv("OAUTH_BROWSER_OPEN", "0")

    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "auth_url": "https://example.com/authorize",
                "token_url": "https://example.com/token",
                "redirect_uri": "http://localhost:8000/callback",
                "token_path": str(token_path),
                "api_scope": "read:me",
            }
        },
    )

    def fail_build(_: dict) -> None:
        raise AssertionError("Should not build OAuth session when token valid")

    monkeypatch.setattr(oauth_utils, "_build_oauth_session", fail_build)

    oauth_utils.OAuthCallbackHandler.auth_code = None
    oauth_utils.OAuthCallbackHandler.error = None

    result = oauth_utils.authorize_jira()

    assert result == token_payload
