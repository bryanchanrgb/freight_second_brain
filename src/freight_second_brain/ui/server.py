"""HTTP research desk: streaming chat API plus static frontend."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from freight_second_brain.agent.preload import apply_preload, candidate_paths, load_preload
from freight_second_brain.agent.research import startup_check
from freight_second_brain.agent.session import get_desk
from freight_second_brain.config import repo_root
from freight_second_brain.ui.auth import (
    auth_required,
    auth_status,
    clear_access_cookie,
    configured_token,
    is_authorized,
    is_public_path,
    set_access_cookie,
    tokens_match,
    unauthorized_response,
)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)


class LoginRequest(BaseModel):
    token: str = Field(min_length=1)


def ui_host(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    return os.environ.get("HOST") or "127.0.0.1"


def ui_port(explicit: int | None = None) -> int:
    if explicit is not None:
        return explicit
    return int(os.environ.get("PORT") or "8787")


def web_dist() -> Path:
    return repo_root() / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Freight Second Brain", version="0.1.0")

    @app.middleware("http")
    async def desk_gate(request: Request, call_next):
        if is_public_path(request.url.path) or is_authorized(request):
            return await call_next(request)
        return unauthorized_response()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    def health() -> dict:
        report = startup_check()
        return {
            "ok": report["ok"],
            "model": report["model"],
            "exa_backend": report["exa_backend"],
            "auth_required": auth_required(),
        }

    @app.get("/api/auth")
    def read_auth(request: Request) -> dict:
        return auth_status(request)

    @app.post("/api/login")
    def login(body: LoginRequest, request: Request) -> JSONResponse:
        expected = configured_token()
        if not expected or not tokens_match(body.token.strip(), expected):
            return unauthorized_response()
        response = JSONResponse({"ok": True, "auth_required": True, "authenticated": True})
        set_access_cookie(response, body.token.strip(), request)
        return response

    @app.post("/api/logout")
    def logout() -> JSONResponse:
        response = JSONResponse({"ok": True, "authenticated": False, "auth_required": auth_required()})
        clear_access_cookie(response)
        return response

    @app.post("/api/sessions")
    def create_session(preload: bool = False) -> dict:
        desk = get_desk()
        if preload:
            payload = load_preload()
            if payload:
                session = apply_preload(desk, payload)
                return {
                    "session_id": session.session_id,
                    "title": session.title,
                    "preloaded": True,
                    "messages": payload.get("messages") or [],
                    "artifacts": list(session.artifacts.values()),
                    "display": payload.get("display")
                    or {
                        "showReport": session.show_report,
                        "turn": session.turn,
                        "activeReportId": session.active_report_id,
                    },
                }
        session = desk.create_session()
        return {
            "session_id": session.session_id,
            "title": session.title,
            "preloaded": False,
            "messages": [],
            "artifacts": [],
            "display": {"showReport": False, "turn": 0, "activeReportId": None},
        }

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict:
        try:
            session = get_desk().get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown session") from exc
        return session.snapshot()

    @app.post("/api/sessions/{session_id}/stop")
    def stop_session(session_id: str) -> dict:
        desk = get_desk()
        try:
            return desk.stop_turn(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown session") from exc

    @app.post("/api/sessions/{session_id}/messages")
    async def post_message(session_id: str, body: ChatRequest, request: Request) -> StreamingResponse:
        desk = get_desk()
        try:
            desk.get(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="unknown session") from exc

        async def events():
            async for event in desk.stream_turn(session_id, body.content):
                if await request.is_disconnected():
                    desk.stop_turn(session_id)
                    break
                yield f"data: {json.dumps(event, default=str)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/preload.json")
    def preload_asset():
        for path in candidate_paths():
            if path.is_file():
                return FileResponse(path, media_type="application/json")
        raise HTTPException(status_code=404, detail="no preload asset")

    dist = web_dist()
    if dist.is_dir():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            candidate = dist / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(
                dist / "index.html",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
    else:

        @app.get("/")
        def missing_ui():
            return HTMLResponse(
                "<html><body style='background:#07080c;color:#e6edf7;font-family:sans-serif;padding:40px'>"
                "<p>Research desk frontend is not built.</p>"
                "<p><code>cd web && npm install && npm run build</code> then restart "
                "<code>uv run freight-sb ui</code>.</p></body></html>"
            )

    return app


def run_ui(*, host: str | None = None, port: int | None = None, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "freight_second_brain.ui.server:create_app",
        factory=True,
        host=ui_host(host),
        port=ui_port(port),
        reload=reload,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
