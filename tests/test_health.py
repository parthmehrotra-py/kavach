"""Test health endpoint."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from kavach.api.routes import router
from kavach.api.security import LoopbackMiddleware
from kavach.config import settings
from kavach.main import create_app


@pytest.fixture
def client():
    """Test health routes separately from the client-IP middleware."""
    app = FastAPI()
    app.include_router(router, prefix=settings.api_prefix)
    return TestClient(app)


def test_health_endpoint(client):
    """Test health endpoint returns expected structure."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "version" in data
    assert data["ocr_provider"] == "none"
    assert data["contextual_model_available"] is False


def test_health_endpoint_no_stack_trace_on_error(client):
    """Test invalid routes return safe errors."""
    response = client.get("/api/v1/nonexistent")

    assert response.status_code == 404
    # Should contain safe error message, not stack trace
    assert "detail" in response.json()
    error_text = str(response.json()).lower()
    assert "traceback" not in error_text
    assert "exception" not in error_text


def test_non_loopback_bind_host_is_rejected(monkeypatch):
    """The app must refuse a configuration that exposes its server externally."""
    monkeypatch.setattr(settings, "host", "0.0.0.0")  # noqa: S104

    with pytest.raises(ValueError, match="loopback IP"):
        create_app()


def test_spoofed_test_user_agent_does_not_bypass_loopback_check():
    """A remote caller cannot bypass the request check with a test-looking header."""
    middleware = LoopbackMiddleware(FastAPI())
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"user-agent", b"testclient")],
        "client": ("192.0.2.10", 50000),
        "server": ("127.0.0.1", 8000),
    }

    async def call_next(_request):
        return Response("ok")

    response = asyncio.run(middleware.dispatch(Request(scope), call_next))

    assert response.status_code == 403
