"""PAN card number detection."""

import re

from kavach.detectors.base import DetectionSpan


class PANDetector:
    """PAN card number detector (format validation only)."""

    @property
    def name(self) -> str:
        return "pan"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect PAN numbers in text."""
        spans = []

        # PAN format: AAAAA9999A (5 letters, 4 digits, 1 letter)
        pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'

        for match in re.finditer(pattern, text):
            spans.append(DetectionSpan(
                start=match.start(),
                end=match.end(),
                value=match.group(),
                category="pan",
                confidence=0.8,  # Format-only validation
                source=self.name,
                validator_status="format_valid"
            ))

        return spans
