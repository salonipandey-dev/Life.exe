"""Pure-ASGI middleware: request IDs, structured access logs, security headers."""

from __future__ import annotations

import secrets
import time
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lifeexe.core.logging import get_logger

log = get_logger("http")

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "frame-ancestors 'none'; form-action 'self'"
)


class SecurityAndLoggingMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = secrets.token_hex(8)
        started = time.perf_counter()
        status: dict[str, Any] = {"code": 500}
        path: str = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Content-Security-Policy"] = CSP
                if self.hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                if path.startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Only method, path, status and timing are logged — never bodies,
            # cookies or query strings (which could carry personal data).
            log.info(
                "request",
                extra={"fields": {
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": path,
                    "status": status["code"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }},
            )
