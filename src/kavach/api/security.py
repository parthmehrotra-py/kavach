"""Security middleware and validation."""

import ipaddress
from typing import Any

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from kavach.config import settings


def validate_loopback_host(host: str) -> str:
    """Reject server bind hosts that could expose Kavach beyond this device."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Kavach must bind to a loopback IP address") from exc

    if not address.is_loopback:
        raise ValueError("Kavach must bind to a loopback IP address")

    return host


class LoopbackMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce loopback-only access."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        client_host = request.client.host if request.client else None
        try:
            is_loopback = client_host is not None and ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            is_loopback = False

        if not is_loopback:
            return Response("Only loopback requests allowed", status_code=403)

        return await call_next(request)


class RequestSizeLimitMiddleware:
    """Read and bound HTTP bodies before passing them to the application."""

    def __init__(self, app: Any, max_request_size: int) -> None:
        self.app = app
        self.max_request_size = max_request_size

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = next(
            (
                value.decode("latin-1")
                for key, value in scope["headers"]
                if key.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                await self._respond(
                    scope,
                    receive,
                    send,
                    400,
                    "invalid_request",
                    "Invalid Content-Length",
                )
                return
            if declared_size < 0:
                await self._respond(
                    scope,
                    receive,
                    send,
                    400,
                    "invalid_request",
                    "Invalid Content-Length",
                )
                return
            if declared_size > self.max_request_size:
                await self._respond(
                    scope,
                    receive,
                    send,
                    413,
                    "request_too_large",
                    "Request body is too large",
                )
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.max_request_size:
                await self._respond(
                    scope,
                    receive,
                    send,
                    413,
                    "request_too_large",
                    "Request body is too large",
                )
                return
            if not message.get("more_body", False):
                break

        sent_body = False

        async def replay_body() -> dict[str, Any]:
            nonlocal sent_body
            if sent_body:
                return {"type": "http.disconnect"}
            sent_body = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _respond(
        scope: dict[str, Any], receive: Any, send: Any, status: int, error: str, message: str
    ) -> None:
        response = JSONResponse(
            status_code=status,
            content={"error": error, "message": message},
        )
        await response(scope, receive, send)


def add_cors_middleware(app: Any) -> None:
    """Add configured CORS middleware to app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )


def add_security_middleware(app: Any) -> None:
    """Add security middleware to app."""
    app.add_middleware(RequestSizeLimitMiddleware, max_request_size=settings.max_request_size)
    app.add_middleware(LoopbackMiddleware)
