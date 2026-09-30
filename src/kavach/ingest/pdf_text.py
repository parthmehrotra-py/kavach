"""PDF text extraction with OCR fallback."""

from io import BytesIO
from math import ceil

import fitz  # PyMuPDF
from PIL import Image

from kavach.config import settings
from kavach.ingest.image_ocr import OCRError, get_ocr_instance


class PDFError(Exception):
    """PDF processing error."""


class PDFTextExtractor:
    """PDF text extraction with OCR fallback."""

    def __init__(self):
        self._ocr = None

    def extract_text(self, pdf_data: bytes) -> tuple[str, dict]:
        """Extract text from PDF with OCR fallback for images.

        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
        except Exception as e:
            raise PDFError(f"Invalid PDF file: {e}") from e

        # Check page limit before processing
        page_count = doc.page_count
        if page_count > settings.max_pdf_pages:
            doc.close()
            raise PDFError(f"Too many pages: {page_count}. Max: {settings.max_pdf_pages}")

        extracted_texts = []
        metadata = {
            "pages": page_count,
            "text_pages": 0,
            "ocr_pages": 0,
            "provider": "pymupdf+rapidocr-cpu",
            "total_chars": 0
        }

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                # First try to extract embedded text
                text = page.get_text().strip()

                if text:
                    extracted_texts.append(text)
                    metadata["text_pages"] += 1
                else:
                    # No meaningful text, try OCR on page image
                    ocr_text = self._ocr_page(page, page_num)
                    if ocr_text:
                        extracted_texts.append(ocr_text)
                        metadata["ocr_pages"] += 1

            final_text = '\n\n'.join(extracted_texts)
            metadata["total_chars"] = len(final_text)

            return final_text, metadata

        finally:
            doc.close()

    def _ocr_page(self, page: fitz.Page, page_num: int) -> str:
        """OCR a single PDF page."""
        try:
            # Check the scaled page bounds before rasterizing it.
            scale = 2.0
            width = ceil(page.rect.width * scale)
            height = ceil(page.rect.height * scale)
            if (
                width > settings.max_image_width
                or height > settings.max_image_height
                or width * height > settings.max_image_pixels
            ):
                return ""

            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            if (
                pix.width > settings.max_image_width
                or pix.height > settings.max_image_height
                or pix.width * pix.height > settings.max_image_pixels
            ):
                return ""

            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(BytesIO(img_data))

            # Run OCR
            if self._ocr is None:
                self._ocr = get_ocr_instance()
            text, _ = self._ocr.extract_text(image)
            return text

        except (OCRError, Exception):
            return ""  # Silent failure for individual pages


# Global PDF extractor instance
_pdf_extractor = None


def get_pdf_extractor() -> PDFTextExtractor:
    """Get singleton PDF extractor instance."""
    global _pdf_extractor
    if _pdf_extractor is None:
        _pdf_extractor = PDFTextExtractor()
    return _pdf_extractor
