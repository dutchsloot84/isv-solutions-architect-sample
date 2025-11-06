"""HTTP retry helpers with SSL-aware exponential backoff."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from requests import Response, Session
from requests.exceptions import ConnectionError, SSLError, Timeout

from .logger import get_logger


LOGGER = get_logger(__name__)


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry behaviour."""

    retries: int = 3
    backoff_factor: float = 0.5
    status_forcelist: Iterable[int] = (500, 502, 503, 504)


def _should_retry_response(status_code: int, status_forcelist: Iterable[int]) -> bool:
    return status_code in set(status_forcelist)


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _backoff_delay(backoff_factor: float, attempt: int) -> float:
    return backoff_factor * (2**attempt)


def request_with_retry(
    session: Session,
    method: str,
    url: str,
    *,
    retry_config: Optional[RetryConfig] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs,
) -> Response:
    """Execute an HTTP request with retry/backoff for SSL and transient failures."""

    cfg = retry_config or RetryConfig()
    log = logger or LOGGER
    attempts = 0
    last_exception: Optional[Exception] = None

    while attempts <= cfg.retries:
        try:
            response = session.request(method, url, **kwargs)
        except (SSLError, ConnectionError, Timeout) as error:
            last_exception = error
            if attempts == cfg.retries:
                log.error(
                    "HTTP request failed after retries",
                    extra={
                        "event": "http_retry_failure",
                        "method": method,
                        "attempts": attempts + 1,
                        "reason": type(error).__name__,
                    },
                )
                raise
            delay = _backoff_delay(cfg.backoff_factor, attempts)
            log.warning(
                "Retrying HTTP request after transient error",
                extra={
                    "event": "http_retry",
                    "method": method,
                    "attempt": attempts + 1,
                    "delay_seconds": round(delay, 3),
                    "reason": type(error).__name__,
                },
            )
            _sleep(delay)
            attempts += 1
            continue

        if _should_retry_response(response.status_code, cfg.status_forcelist):
            if attempts == cfg.retries:
                log.error(
                    "HTTP request failed with status",
                    extra={
                        "event": "http_status_failure",
                        "method": method,
                        "status_code": response.status_code,
                    },
                )
                response.raise_for_status()
            delay = _backoff_delay(cfg.backoff_factor, attempts)
            log.warning(
                "Retrying HTTP request due to status code",
                extra={
                    "event": "http_retry",
                    "method": method,
                    "attempt": attempts + 1,
                    "delay_seconds": round(delay, 3),
                    "status_code": response.status_code,
                },
            )
            _sleep(delay)
            attempts += 1
            continue

        return response

    assert last_exception is not None  # pragma: no cover - defensive
    raise last_exception


__all__ = ["RetryConfig", "request_with_retry"]
