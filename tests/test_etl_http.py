from __future__ import annotations

import httpx
import pytest

from freight_second_brain.config import Settings
from freight_second_brain.etl.http import HttpError, HttpResult, fetch


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def fake_client(settings: Settings, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(transport=transport, follow_redirects=True, timeout=timeout or 5)

    monkeypatch.setattr("freight_second_brain.etl.http._client", fake_client)
    monkeypatch.setattr("freight_second_brain.etl.http.time.sleep", lambda *_args, **_kwargs: None)


def test_http_result_hash_and_json() -> None:
    result = HttpResult(
        url="https://example.test",
        status_code=200,
        content=b'{"ok": true}',
        headers={"content-type": "application/json"},
        elapsed_s=0.1,
    )
    assert result.json() == {"ok": True}
    assert result.text == '{"ok": true}'
    assert len(result.sha256) == 64


def test_fetch_returns_body(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "1"
        return httpx.Response(200, content=b"payload", headers={"X-Test": "yes"})

    _install_transport(monkeypatch, handler)
    result = fetch("https://example.test/data", settings=settings, params={"q": "1"})
    assert result.status_code == 200
    assert result.content == b"payload"
    assert result.headers["x-test"] == "yes"


def test_fetch_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = Settings(data_root=tmp_path, http_retries=2, comtrade_delay_s=0)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, content=b"slow down")
        return httpx.Response(200, content=b"ok")

    _install_transport(monkeypatch, handler)
    result = fetch("https://example.test/retry", settings=settings)
    assert result.content == b"ok"
    assert calls["n"] == 3


def test_fetch_raises_after_client_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = Settings(data_root=tmp_path, http_retries=1, comtrade_delay_s=0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"missing")

    _install_transport(monkeypatch, handler)
    with pytest.raises(HttpError) as exc:
        fetch("https://example.test/missing", settings=settings)
    assert exc.value.status_code == 404
