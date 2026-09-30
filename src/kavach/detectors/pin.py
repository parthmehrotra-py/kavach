"""Indian PIN code detection."""

import re

from kavach.detectors.base import DetectionSpan


class PINDetector:
    """Indian PIN code detector."""

    @property
    def name(self) -> str:
        return "pin"

    def detect(self, text: str) -> list[DetectionSpan]:
        """Detect Indian PIN codes in text."""
        spans = []

        # PIN code: 6 digits, first digit 1-8 (regional codes)
        pattern = r'\b[1-8]\d{5}\b'

        # Context words that suggest this is a PIN code
        pin_context = ['pin', 'pincode', 'postal', 'zip', 'area', 'code']

        for match in re.finditer(pattern, text):
            start, end = match.span()
            candidate = match.group()

            # Look for context within 20 characters before/after
            context_start = max(0, start - 20)
            context_end = min(len(text), end + 20)
            context = text[context_start:context_end].lower()

            # Higher confidence if PIN-related context found
            has_context = any(word in context for word in pin_context)
            confidence = 0.8 if has_context else 0.6

            spans.append(DetectionSpan(
                start=start,
                end=end,
                value=candidate,
                category="pin",
                confidence=confidence,
                source=self.name,
                validator_status="format_valid"
            ))

        return spans
