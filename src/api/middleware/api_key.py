"""API key authentication for production deployments."""
from __future__ import annotations

import os
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def is_api_key_required() -> bool:
    return os.getenv("REQUIRE_API_KEY", "0").lower() in ("1", "true", "yes")


def load_api_keys() -> frozenset[str]:
    raw = os.getenv("API_KEYS", "")
    return frozenset(k.strip() for k in raw.split(",") if k.strip())


def is_exempt_path(path: str) -> bool:
    if path == "/health" or path.startswith("/health/"):
        return True
    return path in ("/docs", "/openapi.json", "/redoc") or path.startswith("/docs/")


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key on /v1/* when REQUIRE_API_KEY=1."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not is_api_key_required():
            return await call_next(request)

        path = request.url.path
        if is_exempt_path(path) or not path.startswith("/v1/"):
            return await call_next(request)

        keys = load_api_keys()
        if not keys:
            return JSONResponse(
                status_code=503,
                content={"detail": "API key auth enabled but API_KEYS is empty"},
            )

        provided = request.headers.get("X-API-Key", "").strip()
        if not provided or provided not in keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
