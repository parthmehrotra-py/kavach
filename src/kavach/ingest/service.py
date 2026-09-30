"""File validation and ingestion routing."""

import mimetypes
from io import BytesIO

from PIL import Image, ImageOps

from kavach.config import settings


class IngestError(Exception):
    """Ingestion error."""


def validate_file_upload(file_content: bytes, filename: str) -> tuple[str, str]:
    """Validate uploaded file and return MIME type and content type.

    Returns:
        Tuple of (mime_type, content_type) where content_type is 'image' or 'pdf'
    """
    if len(file_content) > settings.max_upload_size:
        raise IngestError(f"File too large: {len(file_content)} bytes")

    if len(file_content) == 0:
        raise IngestError("Empty file")

    # Detect MIME type
    mime_type, _ = mimetypes.guess_type(filename)

    # Validate by file signature
    if file_content.startswith(b'\x89PNG'):
        mime_type = 'image/png'
    elif file_content.startswith(b'\xff\xd8\xff'):
        mime_type = 'image/jpeg'
    elif file_content.startswith(b'%PDF'):
        mime_type = 'application/pdf'
    elif file_content.startswith(b'GIF8'):
        mime_type = 'image/gif'
    elif file_content.startswith(b'RIFF') and b'WEBP' in file_content[:12]:
        mime_type = 'image/webp'

    if mime_type in ['image/png', 'image/jpeg', 'image/gif', 'image/webp']:
        return mime_type, 'image'
    elif mime_type == 'application/pdf':
        return mime_type, 'pdf'
    else:
        raise IngestError(f"Unsupported file type: {mime_type}")


def validate_image_constraints(image_data: bytes) -> Image.Image:
    """Validate image constraints and return PIL Image."""
    try:
        image = Image.open(BytesIO(image_data))
    except Exception as e:
        raise IngestError(f"Invalid image file: {e}") from e

    # Check dimensions
    if image.width > settings.max_image_width or image.height > settings.max_image_height:
        raise IngestError(
            f"Image too large: {image.width}x{image.height}. "
            f"Max: {settings.max_image_width}x{settings.max_image_height}"
        )

    # Check total pixels
    total_pixels = image.width * image.height
    if total_pixels > settings.max_image_pixels:
        raise IngestError(f"Too many pixels: {total_pixels}. Max: {settings.max_image_pixels}")

    return image


def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess image for OCR (orientation, format normalization)."""
    image = ImageOps.exif_transpose(image)

    # Convert to RGB if needed
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')

    return image
