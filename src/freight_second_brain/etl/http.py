from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from freight_second_brain.config import USER_AGENT, Settings, get_settings


class HttpError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class HttpResult:
    url: str
    status_code: int
    content: bytes
    headers: dict[str, str]
    elapsed_s: float

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    def json(self) -> Any:
        return json.loads(self.content)


def _client(settings: Settings, timeout: float | None = None) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"},
        follow_redirects=True,
        http2=False,
        timeout=timeout or settings.http_timeout_s,
    )


def fetch(
    url: str,
    *,
    settings: Settings | None = None,
    timeout: float | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResult:
    settings = settings or get_settings()
    retries = settings.http_retries
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            with _client(settings, timeout=timeout) as client:
                response = client.get(url, params=params, headers=headers)
            elapsed = time.monotonic() - started
            if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(min(2**attempt, 8) + 0.2)
                continue
            if response.status_code >= 400:
                raise HttpError(
                    f"GET {url} failed with {response.status_code}",
                    status_code=response.status_code,
                )
            return HttpResult(
                url=str(response.url),
                status_code=response.status_code,
                content=response.content,
                headers={k.lower(): v for k, v in response.headers.items()},
                elapsed_s=elapsed,
            )
        except (httpx.HTTPError, HttpError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8) + 0.2)
                continue
            raise
    raise HttpError(f"GET {url} failed after retries: {last_error}")
