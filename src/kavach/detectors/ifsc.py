"""IFSC code detection."""

import re

from kavach.detectors.base import DetectionSpan


class IFSCDetector:
    """IFSC code detector (format validation only)."""

    @property
    def name(self) -> str:
        return "ifsc"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect IFSC codes in text."""
        spans = []

        # IFSC format: AAAA0999999 (4 letters, 1 zero, 6 alphanumeric)
        pattern = r'\b[A-Z]{4}0[A-Z0-9]{6}\b'

        for match in re.finditer(pattern, text):
            spans.append(DetectionSpan(
                start=match.start(),
                end=match.end(),
                value=match.group(),
                category="ifsc",
                confidence=0.85,  # Format-only validation
                source=self.name,
                validator_status="format_valid"
            ))

        return spans
