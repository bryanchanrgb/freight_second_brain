"""HTTP research desk: streaming chat API plus static frontend."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from freight_second_brain.agent.preload import apply_preload, candidate_paths, load_preload
from freight_second_brain.agent.research import startup_check
from freight_second_brain.agent.session import get_desk
from freight_second_brain.config import repo_root


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)


def web_dist() -> Path:
    return repo_root() / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Freight Second Brain", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        report = startup_check()
        return {"ok": report["ok"], "model": report["model"], "exa_backend": report["exa_backend"]}

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


def run_ui(*, host: str = "127.0.0.1", port: int = 8787, reload: bool = False) -> None:
    import uvicorn

    uvicorn.run(
        "freight_second_brain.ui.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
