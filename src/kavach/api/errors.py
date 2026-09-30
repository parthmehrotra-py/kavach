"""Safe error handling for API responses."""

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str


def safe_http_exception(status_code: int, message: str) -> HTTPException:
    """Create HTTP exception with safe user-readable message."""
    return HTTPException(
        status_code=status_code,
        detail={"error": "request_error", "message": message}
    )
