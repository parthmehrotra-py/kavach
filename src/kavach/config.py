"""Configuration and settings for Kavach."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server configuration
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # API versioning
    api_prefix: str = "/api/v1"

    # Security
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    allowed_origins: list[str] = ["http://127.0.0.1:8000"]

    # Ingestion limits
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    max_pdf_pages: int = 20  # Maximum pages in PDF
    max_image_width: int = 4096  # Maximum image width
    max_image_height: int = 4096  # Maximum image height
    max_image_pixels: int = 16 * 1024 * 1024  # 16MP maximum

    # In-memory session limits
    max_sessions: int = 16
    max_session_bytes: int = 1_000_000
    session_ttl_seconds: int = 30 * 60
    max_text_length: int = 1_000_000

    class Config:
        env_prefix = "KAVACH_"


settings = Settings()
