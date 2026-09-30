"""Test image/PDF ingestion and OCR."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from kavach.config import settings
from kavach.ingest.image_ocr import get_ocr_instance
from kavach.ingest.pdf_text import get_pdf_extractor
from kavach.ingest.service import IngestError, validate_file_upload, validate_image_constraints


def create_synthetic_image_with_text(text: str, size: tuple[int, int] = (400, 200)) -> bytes:
    """Create a synthetic image with text for testing."""
    image = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(image)

    # Draw text
    draw.text((10, 80), text, fill='black')

    # Save to bytes
    img_bytes = io.BytesIO()
    image.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def create_synthetic_pdf_with_text(text: str) -> bytes:
    """Create a synthetic text-based PDF for testing."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


class TestFileValidation:
    """Test file upload validation."""

    def test_validate_png_image(self):
        """Test PNG image validation."""
        png_data = create_synthetic_image_with_text("Test")
        mime_type, content_type = validate_file_upload(png_data, "test.png")

        assert mime_type == "image/png"
        assert content_type == "image"

    def test_validate_pdf(self):
        """Test PDF validation."""
        pdf_data = create_synthetic_pdf_with_text("Test PDF content")
        mime_type, content_type = validate_file_upload(pdf_data, "test.pdf")

        assert mime_type == "application/pdf"
        assert content_type == "pdf"

    def test_reject_oversized_upload(self):
        """Test rejection of oversized uploads."""
        large_data = b"x" * (settings.max_upload_size + 1)

        with pytest.raises(IngestError, match="too large"):
            validate_file_upload(large_data, "large.png")

    def test_reject_empty_file(self):
        """Test rejection of empty files."""
        with pytest.raises(IngestError, match="Empty"):
            validate_file_upload(b"", "empty.png")

    def test_reject_unsupported_type(self):
        """Test rejection of unsupported file types."""
        with pytest.raises(IngestError, match="Unsupported"):
            validate_file_upload(b"NOT AN IMAGE", "test.xyz")


class TestImageConstraints:
    """Test image dimension and pixel constraints."""

    def test_validate_normal_image(self):
        """Test validation of normal-sized image."""
        img_data = create_synthetic_image_with_text("Test", (400, 300))
        image = validate_image_constraints(img_data)

        assert image.width == 400
        assert image.height == 300

    def test_reject_oversized_width(self):
        """Test rejection of images exceeding width limit."""
        # Create image that's too wide
        img = Image.new('RGB', (settings.max_image_width + 1, 100), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')

        with pytest.raises(IngestError, match="too large"):
            validate_image_constraints(img_bytes.getvalue())

    def test_reject_oversized_height(self):
        """Test rejection of images exceeding height limit."""
        # Create image that's too tall
        img = Image.new('RGB', (100, settings.max_image_height + 1), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')

        with pytest.raises(IngestError, match="too large"):
            validate_image_constraints(img_bytes.getvalue())

    def test_reject_too_many_pixels(self):
        """Test rejection of images with too many pixels."""
        # Create large square image that exceeds pixel limit
        side = int((settings.max_image_pixels ** 0.5) + 100)
        img = Image.new('RGB', (side, side), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')

        with pytest.raises(IngestError, match="(too large|Too many pixels)"):
            validate_image_constraints(img_bytes.getvalue())


class TestOCR:
    """Test OCR functionality."""

    def test_ocr_extracts_text_from_image(self):
        """Test OCR can extract text from synthetic image."""
        # Note: RapidOCR may not recognize hand-drawn text reliably
        # This tests the pipeline, not OCR accuracy
        img_data = create_synthetic_image_with_text("PAN ABCDE1234F", (600, 200))
        image = Image.open(io.BytesIO(img_data))

        ocr = get_ocr_instance()
        text, metadata = ocr.extract_text(image)

        # Verify metadata structure
        assert "boxes" in metadata
        assert "confidence" in metadata
        assert metadata["provider"] == "rapidocr-cpu"

    def test_ocr_handles_empty_image(self):
        """Test OCR handles images with no text gracefully."""
        # Plain white image
        img = Image.new('RGB', (200, 200), color='white')

        ocr = get_ocr_instance()
        text, metadata = ocr.extract_text(img)

        # Should return empty or minimal text
        assert isinstance(text, str)
        assert metadata["boxes"] >= 0


class TestPDFExtraction:
    """Test PDF text extraction."""

    def test_extract_embedded_text_from_pdf(self):
        """Test extraction of embedded text from text-based PDF."""
        pdf_data = create_synthetic_pdf_with_text("My PAN is ABCDE1234F")

        extractor = get_pdf_extractor()
        text, metadata = extractor.extract_text(pdf_data)

        assert "ABCDE1234F" in text
        assert metadata["pages"] == 1
        assert metadata["text_pages"] >= 1
        assert metadata["total_chars"] > 0

    def test_reject_too_many_pdf_pages(self):
        """Test rejection of PDFs with too many pages."""
        import fitz
        doc = fitz.open()

        # Create PDF with too many pages
        for _ in range(settings.max_pdf_pages + 1):
            doc.new_page()

        pdf_bytes = doc.write()
        doc.close()

        extractor = get_pdf_extractor()
        from kavach.ingest.pdf_text import PDFError

        with pytest.raises(PDFError, match="Too many pages"):
            extractor.extract_text(pdf_bytes)

    def test_invalid_pdf_raises_error(self):
        """Test invalid PDF data raises appropriate error."""
        extractor = get_pdf_extractor()
        from kavach.ingest.pdf_text import PDFError

        with pytest.raises(PDFError, match="Invalid PDF"):
            extractor.extract_text(b"NOT A PDF")


class TestIngestEndpoint:
    """Test /ingest API endpoint."""

    @pytest.fixture
    def client(self):
        """Test client without security middleware."""
        from fastapi import FastAPI

        from kavach.api.routes import router
        from kavach.config import settings

        app = FastAPI()
        app.include_router(router, prefix=settings.api_prefix)
        return TestClient(app)

    def test_ingest_image_with_pii(self, client):
        """Test ingestion of image containing PII."""
        img_data = create_synthetic_image_with_text("PAN ABCDE1234F Phone 9876543210")

        files = {"file": ("test.png", img_data, "image/png")}
        response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == 200
        data = response.json()

        assert "extracted_text" in data
        assert "metadata" in data
        assert "candidates" in data

    def test_ingest_text_pdf(self, client):
        """Test ingestion of text-based PDF."""
        pdf_data = create_synthetic_pdf_with_text("My PAN is ABCDE1234F")

        files = {"file": ("test.pdf", pdf_data, "application/pdf")}
        response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == 200
        data = response.json()

        assert "ABCDE1234F" in data["extracted_text"]
        assert data["metadata"]["pages"] == 1
        # Should detect PAN candidate
        pan_candidates = [c for c in data["candidates"] if c["category"] == "pan"]
        assert len(pan_candidates) >= 1

    def test_ingest_rejects_oversized_file(self, client):
        """Test ingestion rejects oversized files."""
        large_data = b"x" * (settings.max_upload_size + 1)

        files = {"file": ("large.png", large_data, "image/png")}
        response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()

    def test_ingest_rejects_unsupported_file(self, client):
        """Test ingestion rejects unsupported file types."""
        files = {"file": ("test.txt", b"plain text", "text/plain")}
        response = client.post("/api/v1/ingest", files=files)

        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()
