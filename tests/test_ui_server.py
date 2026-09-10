from __future__ import annotations

from freight_second_brain.config import get_settings
from freight_second_brain.ui.auth import COOKIE_NAME
from freight_second_brain.ui.server import create_app, ui_host, ui_port


def _stub_desk(monkeypatch) -> None:
    from freight_second_brain.agent.session import ResearchSession

    class Stub:
        def __init__(self) -> None:
            self.sessions: dict[str, ResearchSession] = {}

        def create_session(self) -> ResearchSession:
            session = ResearchSession(session_id="stub-session")
            self.sessions[session.session_id] = session
            return session

        def get(self, session_id: str) -> ResearchSession:
            return self.sessions[session_id]

    stub = Stub()
    monkeypatch.setattr("freight_second_brain.ui.server.get_desk", lambda: stub)


def test_ui_host_defaults_to_localhost(monkeypatch) -> None:
    monkeypatch.delenv("HOST", raising=False)
    assert ui_host() == "127.0.0.1"
    assert ui_host("0.0.0.0") == "0.0.0.0"
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert ui_host() == "0.0.0.0"


def test_ui_port_reads_platform_env(monkeypatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    assert ui_port() == 8787
    assert ui_port(9000) == 9000
    monkeypatch.setenv("PORT", "10000")
    assert ui_port() == 10000


def test_health_is_public(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DESK_ACCESS_TOKEN", "desk-secret")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["auth_required"] is True
        assert "model" in body
        assert "openrouter_key" in body
    finally:
        get_settings.cache_clear()


def test_sessions_require_token_when_configured(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    _stub_desk(monkeypatch)
    monkeypatch.setenv("DESK_ACCESS_TOKEN", "desk-secret")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.post("/api/sessions").status_code == 401
        assert client.get("/preload.json").status_code == 401
        bearer = client.post("/api/sessions", headers={"Authorization": "Bearer desk-secret"})
        assert bearer.status_code == 200
        assert bearer.json()["preloaded"] is False
        wrong = client.post("/api/login", json={"token": "nope"})
        assert wrong.status_code == 401
        login = client.post("/api/login", json={"token": "desk-secret"})
        assert login.status_code == 200
        assert COOKIE_NAME in login.cookies
        authed = client.post("/api/sessions")
        assert authed.status_code == 200
        me = client.get("/api/auth")
        assert me.json()["authenticated"] is True
        logout = client.post("/api/logout")
        assert logout.status_code == 200
        assert client.post("/api/sessions").status_code == 401
    finally:
        get_settings.cache_clear()


def test_open_desk_when_token_unset(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    _stub_desk(monkeypatch)
    monkeypatch.setenv("DESK_ACCESS_TOKEN", "")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        health = client.get("/api/health")
        assert health.json()["auth_required"] is False
        created = client.post("/api/sessions")
        assert created.status_code == 200
    finally:
        get_settings.cache_clear()


def test_missing_openrouter_key_is_503(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from freight_second_brain.agent.session import reset_desk

    reset_desk()
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("DESK_ACCESS_TOKEN", "")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/api/health").json()["openrouter_key"] is False
        res = client.post("/api/sessions")
        assert res.status_code == 503
        assert "OPENROUTER_API_KEY" in res.json()["detail"]
    finally:
        reset_desk()
        get_settings.cache_clear()
