"""Optional shared-secret gate for a public research-desk URL."""

from __future__ import annotations

import hmac
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from freight_second_brain.config import Settings, get_settings

COOKIE_NAME = "freight_sb_desk"
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/auth", "/api/login", "/api/logout"})


def configured_token(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return (settings.desk_access_token or "").strip()


def auth_required(settings: Settings | None = None) -> bool:
    return bool(configured_token(settings))


def tokens_match(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    try:
        return hmac.compare_digest(provided, expected)
    except (TypeError, ValueError):
        return False


def provided_token(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    extra = request.headers.get("x-desk-token")
    if extra:
        return extra.strip()
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        return cookie.strip()
    return ""


def is_authorized(request: Request, settings: Settings | None = None) -> bool:
    expected = configured_token(settings)
    if not expected:
        return True
    return tokens_match(provided_token(request), expected)


def is_public_path(path: str) -> bool:
    if path in PUBLIC_API_PATHS:
        return True
    if path.startswith("/api/") or path == "/preload.json":
        return False
    return True


def unauthorized_response() -> JSONResponse:
    return JSONResponse({"detail": "unauthorized", "auth": "required"}, status_code=401)


def cookie_secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return proto.split(",")[0].strip().lower() == "https"


def set_access_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request),
        path="/",
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def auth_status(request: Request, settings: Settings | None = None) -> dict[str, Any]:
    required = auth_required(settings)
    return {
        "ok": True,
        "auth_required": required,
        "authenticated": (not required) or is_authorized(request, settings),
    }
