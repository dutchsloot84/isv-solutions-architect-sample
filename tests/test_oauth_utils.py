from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from modules.utils import oauth as oauth_utils


def test_token_expired_handles_variations() -> None:
    assert oauth_utils._token_expired(None)
    assert oauth_utils._token_expired({"expires_at": time.time() - 10})
    assert oauth_utils._token_expired({"expires_in": 0})
    assert not oauth_utils._token_expired({"expires_at": time.time() + 3600})


def test_get_jira_session_refreshes_expired_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    saved_tokens: list[Dict[str, Any]] = []

    def fake_save(token: Dict[str, Any], config: Optional[dict] = None) -> Path:
        saved_tokens.append(token)
        return tmp_path / "token.json"

    class DummySession:
        def __init__(self, token: Optional[dict] = None, **_: Any):
            self.token = token or {}
            self.token_updater = None
            self.verify: Any = True
            self.refresh_kwargs: Dict[str, Any] | None = None

        def refresh_token(self, url: str, **kwargs: Any) -> Dict[str, Any]:
            self.refresh_kwargs = {"url": url, **kwargs}
            new_token = {"access_token": "new", "expires_at": time.time() + 3600}
            if self.token_updater:
                self.token_updater(new_token)
            self.token = new_token
            return new_token

    monkeypatch.setattr(oauth_utils, "save_token", fake_save)
    monkeypatch.setattr(oauth_utils, "_load_token", lambda config: {"access_token": "old", "expires_at": time.time() - 5})
    monkeypatch.setattr(oauth_utils, "_build_oauth_session", lambda config, token=None: DummySession(token))
    monkeypatch.setattr(oauth_utils, "ssl_verify_path", lambda: tmp_path / "corp.pem")
    monkeypatch.setattr(
        oauth_utils,
        "load_config",
        lambda: {
            "jira": {
                "token_url": "https://example.com/token",
                "token_path": str(tmp_path / "token.json"),
            }
        },
    )

    monkeypatch.setenv("JIRA_CLIENT_ID", "client")
    monkeypatch.setenv("JIRA_SECRET", "secret")

    session = oauth_utils.get_jira_session()

    assert session.refresh_kwargs is not None
    assert session.refresh_kwargs["url"] == "https://example.com/token"
    assert session.verify == str(tmp_path / "corp.pem")
    assert saved_tokens, "token should be persisted after refresh"
    assert session.token.get("access_token") == "new"
