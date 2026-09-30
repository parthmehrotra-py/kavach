"""Main application entry point."""

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from uvicorn import run

from kavach import __version__
from kavach.api.routes import router
from kavach.api.security import add_cors_middleware, add_security_middleware, validate_loopback_host
from kavach.config import settings
from kavach.core.session_store import SessionStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Clear all in-memory token maps when the local server shuts down."""
    try:
        yield
    finally:
        app.state.session_store.clear()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    validate_loopback_host(settings.host)

    app = FastAPI(
        title="Kavach",
        version=__version__,
        description="Local-first PII redaction and restoration",
        lifespan=lifespan,
    )
    app.state.session_store = SessionStore(
        max_sessions=settings.max_sessions,
        max_session_bytes=settings.max_session_bytes,
        ttl_seconds=settings.session_ttl_seconds,
    )

    # Add security and CORS middleware
    add_security_middleware(app)
    add_cors_middleware(app)

    # Include API routes
    app.include_router(router, prefix=settings.api_prefix)

    # Mount static files
    web_dir = Path(__file__).parent / "web"
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")

    return app


def main() -> None:
    """Run the application."""
    if len(sys.argv) > 1 and sys.argv[1] == "--validate-loopback":
        try:
            validate_loopback_host(settings.host)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        print("Loopback validation passed")
        return

    app = create_app()

    run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
