from __future__ import annotations

import pytest
from requests import Response
from requests.exceptions import ConnectionError, SSLError

from modules.utils import http_retry


def _response(status_code: int) -> Response:
    resp = Response()
    resp.status_code = status_code
    resp._content = b"{}"  # noqa: SLF001 - setting private for test convenience
    return resp


def test_request_with_retry_recovers_from_ssl_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []

    class DummySession:
        def request(self, method: str, url: str, **kwargs):  # noqa: D401 - test stub
            attempts.append(1)
            if len(attempts) == 1:
                raise SSLError("handshake failed")
            return _response(200)

    monkeypatch.setattr(http_retry, "_sleep", lambda _: None)

    response = http_retry.request_with_retry(
        DummySession(), "GET", "https://example.com", verify=True
    )

    assert response.status_code == 200
    assert len(attempts) == 2


def test_request_with_retry_retries_on_status_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []

    class DummySession:
        def request(self, method: str, url: str, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                return _response(503)
            return _response(200)

    monkeypatch.setattr(http_retry, "_sleep", lambda _: None)

    response = http_retry.request_with_retry(
        DummySession(), "GET", "https://example.com", verify=True
    )

    assert response.status_code == 200
    assert len(attempts) == 2


def test_request_with_retry_raises_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummySession:
        def request(self, method: str, url: str, **kwargs):
            raise ConnectionError("network down")

    monkeypatch.setattr(http_retry, "_sleep", lambda _: None)

    with pytest.raises(ConnectionError):
        http_retry.request_with_retry(
            DummySession(),
            "GET",
            "https://example.com",
            verify=True,
            retry_config=http_retry.RetryConfig(retries=1, backoff_factor=0),
        )
