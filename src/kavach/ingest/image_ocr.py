"""RapidOCR wrapper for image text extraction."""

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


class OCRError(Exception):
    """OCR processing error."""


class ImageOCR:
    """Image OCR using RapidOCR with CPU provider."""

    def __init__(self):
        """Initialize RapidOCR with CPU provider."""
        try:
            # Initialize RapidOCR with CPU provider (default)
            self._ocr = RapidOCR()
            self._provider = "rapidocr-cpu"
        except Exception as e:
            raise OCRError(f"Failed to initialize OCR: {e}") from e

    @property
    def provider(self) -> str:
        """Return OCR provider name."""
        return self._provider

    def extract_text(self, image: Image.Image) -> tuple[str, dict]:
        """Extract text from image using OCR.

        Returns:
            Tuple of (extracted_text, metadata)
        """
        try:
            # Convert PIL Image to numpy array
            image_array = np.array(image)

            # Run OCR
            result = self._ocr(image_array)

            if result is None or not result:
                return "", {"boxes": 0, "confidence": 0.0}

            # Extract text and metadata
            # RapidOCR returns list of [box_coordinates, text, confidence]
            texts = []
            confidences = []

            for box_result in result:
                if box_result is None:
                    continue

                # box_result is tuple/list: [coordinates, text, confidence]
                if len(box_result) >= 2:
                    text = str(box_result[1]) if box_result[1] is not None else ""
                    confidence = (
                        float(box_result[2])
                        if len(box_result) > 2 and box_result[2] is not None
                        else 0.0
                    )

                    if text and text.strip():
                        texts.append(text.strip())
                        confidences.append(confidence)

            extracted_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            metadata = {
                "boxes": len(texts),
                "confidence": avg_confidence,
                "provider": self._provider,
                "image_size": f"{image.width}x{image.height}"
            }

            return extracted_text, metadata

        except Exception as e:
            raise OCRError(f"OCR failed: {e}") from e


# Global OCR instance
_ocr_instance = None


def get_ocr_instance() -> ImageOCR:
    """Get singleton OCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = ImageOCR()
    return _ocr_instance
